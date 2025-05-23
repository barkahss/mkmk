"""
API routes for scraping operations in the AI Scraper Framework.

This module defines FastAPI routes related to initiating and managing
web scraping tasks. It uses Pydantic models for request and response
data validation and serialization.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl # HttpUrl for built-in URL validation
from typing import Optional # TYPE_CHECKING can be used if only for hints
from urllib.parse import urlparse # For parsing URL to get domain for filename prefix
from datetime import datetime # For potential use in filename generation (though now in FileStorage)

# Framework core components
from ai_scraper_framework.core.manager import ScrapingManager
from ai_scraper_framework.core.exceptions import TaskManagementError, RendererError
from ai_scraper_framework.core.logger import get_logger
from ai_scraper_framework.core.config import config_manager # Global configuration instance

logger = get_logger(__name__) # Module-level logger

# --- Pydantic Models for Request and Response ---

class ScrapeURLRequest(BaseModel):
    """
    Request model for the `/scrape-single-url` endpoint.
    Requires a valid URL to be scraped.
    """
    url: HttpUrl  # Pydantic's HttpUrl type ensures the URL is valid.
    # output_filename: Optional[str] = None # Example: Client could suggest a filename. Currently unused.

class ScrapeResponse(BaseModel):
    """
    Response model for the `/scrape-single-url` endpoint.
    Provides feedback on the scraping operation.
    """
    message: str  # A message indicating the outcome (e.g., "Scraping successful.").
    output_path: Optional[str] = None  # Path to the saved data file, if successful.
    url_processed: Optional[HttpUrl] = None # The URL that was processed.
    error_details: Optional[str] = None # Details of the error, if any occurred. (Not extensively used currently)


# --- API Router Definition ---
# All routes defined here will be included in the main FastAPI application.
router = APIRouter()

# Note on ScrapingManager Instantiation:
# For this version, ScrapingManager is instantiated per request within the endpoint.
# This is simple and ensures thread safety / fresh state for each request.
# For applications with high throughput or where ScrapingManager initialization is costly,
# consider using FastAPI's dependency injection system (`Depends`) to manage
# the lifecycle of ScrapingManager (e.g., as a singleton or request-scoped).
# Example: `async def scrape_single_url_endpoint(request: ScrapeURLRequest, manager: ScrapingManager = Depends(get_scraping_manager))`
# where `get_scraping_manager` would be a dependency provider function.

@router.post(
    "/scrape-single-url",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK, # Default status for successful POST, can be changed to 202 Accepted if async
    summary="Scrape a single URL for basic data",
    description="Accepts a URL, performs a basic scraping workflow (fetches HTML, "
                "parses title and links), and saves the extracted data to a JSON file. "
                "The filename is generated automatically based on the domain and timestamp."
)
async def scrape_single_url_endpoint(request: ScrapeURLRequest):
    """
    Handles requests to scrape a single URL.

    It instantiates a `ScrapingManager`, generates a filename prefix based on the
    URL's domain, and then calls the manager's `scrape_single_url_basic` method.
    Error handling includes distinguishing service availability issues (like missing
    browser binaries for Playwright) from general task failures.

    Args:
        request (ScrapeURLRequest): The request payload containing the URL to scrape.

    Returns:
        ScrapeResponse: A response object indicating success or failure, including
                        the path to the saved data if successful.

    Raises:
        HTTPException:
            - 503 Service Unavailable: If critical rendering components (e.g., Playwright browsers)
                                       are not ready or fail to initialize.
            - 500 Internal Server Error: For other task-related failures or unexpected errors.
            - 422 Unprocessable Entity: If the request payload (URL) is invalid (handled by FastAPI).
    """
    try:
        # Instantiate ScrapingManager for each request, passing the global config_manager.
        # This ensures that components within ScrapingManager are configured according to
        # the current application environment (e.g., development, production).
        scraping_manager = ScrapingManager(config=config_manager)

        # Generate a filename prefix from the domain of the requested URL.
        # This helps in organizing stored data. FileStorage will add timestamp & UUID for uniqueness.
        parsed_url = urlparse(str(request.url)) # Convert Pydantic's HttpUrl to string for urlparse.
        # Sanitize domain name to be filesystem-friendly for use as a prefix.
        domain_prefix = parsed_url.netloc.replace('.', '_').replace('-', '_')
        
        # Ensure a fallback prefix if domain_prefix is empty (e.g., for unusual URLs or errors).
        output_filename_prefix = f"scrape_{domain_prefix}" if domain_prefix else "scraped_content"
        logger.info(f"Generated filename prefix for {request.url}: {output_filename_prefix}")

        # Delegate the scraping task to ScrapingManager.
        # `output_filename` is omitted (defaults to None), so FileStorage generates the full name.
        saved_path = await scraping_manager.scrape_single_url_basic(
            url=str(request.url), # Pass URL as string.
            output_filename_prefix=output_filename_prefix
        )
        
        logger.info(f"Scraping successful for URL {request.url}. Data saved to: {saved_path}")
        return ScrapeResponse(
            message="Scraping successful.",
            output_path=saved_path,
            url_processed=request.url
        )
    except TaskManagementError as e:
        # Handles errors raised by ScrapingManager during the workflow.
        logger.error(f"TaskManagementError for URL {request.url}: {e.message}", exc_info=True)
        
        # Provide a more specific error message if it's a known RendererError due to missing browsers.
        # This helps in diagnosing common setup issues in deployment.
        if "RendererError" in e.message and ("Executable doesn't exist" in e.message or "playwright install" in e.message):
             raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Scraping service unavailable: Rendering component not ready. Please ensure browser binaries are installed on the server ('playwright install'). Original error: {e.message}"
            )
        # For other TaskManagementErrors, return a generic 500.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping failed for URL {request.url}. Error: {e.message}"
        )
    except RendererError as e: # Catch RendererError if it bubbles up directly (e.g., from PlaywrightManager init).
        logger.error(f"Direct RendererError for URL {request.url}: {e.message}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scraping service rendering component failed for URL {request.url}. Error: {e.message}"
        )
    except Exception as e:
        # Catch-all for any other unexpected errors not handled above.
        logger.critical(f"Unexpected error processing request for URL {request.url}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # Avoid exposing raw error messages to the client in production for security.
            detail=f"An unexpected error occurred while processing {request.url}. Please try again later."
        )

# Example for future expansion:
# @router.get("/status", summary="Get API or Scraper Status")
# async def get_status():
#     """Provides status information about the API or background scraping tasks."""
#     return {"status": "API is running", "active_tasks": 0}


# This block is for local testing of Pydantic models or utility functions within this file.
# It's not used when the FastAPI application is run by Uvicorn.
if __name__ == "__main__":
    # This section is primarily for quick, isolated testing of Pydantic models, not for running the API.
    # To run the API server, use: `uvicorn ai_scraper_framework.api.main:app --reload`
    print("--- Testing Pydantic models defined in scraper_routes.py ---")
    try:
        # Test valid request model
        req_valid = ScrapeURLRequest(url="http://example.com")
        print(f"\nValid ScrapeURLRequest model instance:\n{req_valid.model_dump_json(indent=2)}")
        
        # Test invalid URL (Pydantic should raise validation error)
        print("\nAttempting ScrapeURLRequest with an invalid URL (expecting validation error)...")
        req_invalid_url = ScrapeURLRequest(url="this_is_not_a_valid_url") 
        # The above line should ideally be wrapped in a try-except for ValidationError
        # or use pytest.raises in a formal test. For this __main__ block, direct instantiation
        # might raise the error directly, or it might depend on how Pydantic handles it here.
        # If it doesn't raise immediately, the error would be caught by FastAPI's validation layer.
        
    except Exception as e_model_test: # Catching general Exception for Pydantic's ValidationError
        print(f"Caught expected error during model validation: {e_model_test}")

    # Test success response model
    resp_success = ScrapeResponse(
        message="Scraping successful.",
        output_path="/path/to/example_output.json",
        url_processed="http://example.com"
    )
    print(f"\nExample ScrapeResponse (success):\n{resp_success.model_dump_json(indent=2)}")

    # Test error response model
    resp_error = ScrapeResponse(
        message="Scraping failed.",
        url_processed="http://example.com/error_path",
        error_details="Detailed error message explaining what went wrong."
    )
    print(f"\nExample ScrapeResponse (error):\n{resp_error.model_dump_json(indent=2)}")

    print("\n--- Pydantic model tests completed ---")
    print("\nTo run the full API, execute: uvicorn ai_scraper_framework.api.main:app --reload --host 0.0.0.0 --port 8000")
