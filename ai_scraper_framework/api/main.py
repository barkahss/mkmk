"""
Main application file for the AI Scraper Framework API.

This file initializes the FastAPI application, sets up logging,
registers global exception handlers, and includes API routers.
It also defines a root endpoint for basic API information.
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
# pydantic.ValidationError is not explicitly handled here, as RequestValidationError covers most cases.
# from pydantic import ValidationError

# Import project-specific modules
from ai_scraper_framework.api.routes import scraper_routes
from ai_scraper_framework.core.exceptions import AIScraperFrameworkError
from ai_scraper_framework.core.logger import setup_logging, get_logger # Added get_logger for potential use
from ai_scraper_framework.core.config import config_manager

# --- Logging Setup ---
# Initialize centralized logging as early as possible when the application starts.
# ConfigurationManager (via global `config_manager`) should load the configuration
# based on APP_ENV (defaults to 'development' if not set).
try:
    setup_logging(config_manager)
    # Get a logger for this main module, though it might primarily be used in handlers.
    logger = get_logger(__name__) 
    logger.info("Logging successfully initialized for FastAPI application.")
except Exception as e:
    # Fallback to Python's basic logging if `setup_logging` fails.
    # This ensures that critical errors during logging setup are still visible.
    import logging as py_logging # Alias to avoid conflict if logger was defined above
    py_logging.basicConfig(level=py_logging.WARNING, format="%(asctime)s - %(levelname)s - CRITICAL - Failed to setup custom logging: %(message)s")
    py_logging.critical(f"Failed to initialize custom logging via ConfigurationManager: {e}", exc_info=True)
    logger = py_logging.getLogger(__name__) # Use basic logger if setup failed


# --- FastAPI Application Initialization ---
# Create the FastAPI application instance.
# Metadata like title, description, and version are used for OpenAPI documentation.
app = FastAPI(
    title="AI Scraper Framework API",
    description="API for managing and triggering web scraping tasks with AI capabilities. "
                "Provides endpoints for initiating scraping jobs and potentially retrieving results.",
    version="0.1.0" # Consider making this configurable or auto-incremented.
)

# --- Global Exception Handlers ---
# These handlers catch specified exceptions that occur anywhere in the application
# and return standardized JSON error responses.

@app.exception_handler(AIScraperFrameworkError)
async def ai_scraper_framework_exception_handler(request: Request, exc: AIScraperFrameworkError):
    """
    Handles all custom exceptions derived from `AIScraperFrameworkError`.

    This provides a consistent error response format for application-specific errors.

    Args:
        request (Request): The incoming request that caused the exception.
        exc (AIScraperFrameworkError): The instance of the caught application exception.

    Returns:
        JSONResponse: A standardized JSON error response, typically with HTTP 500.
    """
    logger.error(
        f"AIScraperFrameworkError caught: {exc.__class__.__name__} - {exc.message} "
        f"for request: {request.method} {request.url}",
        exc_info=True # Includes stack trace in logs.
    )
    # Specific subclasses of AIScraperFrameworkError could be mapped to different HTTP status codes
    # if needed, by checking `isinstance(exc, SpecificErrorType)`.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"An application error occurred: {exc.message}"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handles Pydantic's `RequestValidationError` for request body, path, or query parameters.

    FastAPI provides a default handler for this, but this custom one allows for
    specific logging or error formatting if desired. It returns an HTTP 422 response.

    Args:
        request (Request): The incoming request with validation errors.
        exc (RequestValidationError): The Pydantic validation exception instance.

    Returns:
        JSONResponse: A JSON response detailing the validation failures.
    """
    logger.warning(
        f"RequestValidationError caught for: {request.method} {request.url}. Errors: {exc.errors()}",
        exc_info=False # Stack trace is usually not needed for validation errors.
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        # The content structure matches FastAPI's default for RequestValidationError.
        content={"detail": "Request validation failed", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Handles any other unhandled Python exceptions that were not caught by more specific handlers.

    This acts as a catch-all to ensure that the API always returns a JSON response,
    even for unexpected server errors. It returns an HTTP 500 response.

    Args:
        request (Request): The incoming request that led to the unhandled exception.
        exc (Exception): The instance of the caught generic exception.

    Returns:
        JSONResponse: A generic JSON error response indicating an unexpected server error.
    """
    logger.critical(
        f"Generic unhandled exception caught: {exc.__class__.__name__} - {str(exc)} "
        f"for request: {request.method} {request.url}",
        exc_info=True # Include stack trace for unexpected errors.
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"An unexpected server error occurred. Please contact support if the issue persists."},
        # Consider not exposing raw str(exc) to client in production for security.
        # content={"detail": f"An unexpected server error occurred: {str(exc)}"},
    )


# --- API Router Inclusion ---
# Include routers from other modules. Each router can define a set of related endpoints.
# `prefix` adds a common path prefix to all routes in the included router.
# `tags` are used for grouping endpoints in the OpenAPI documentation.
app.include_router(
    scraper_routes.router,
    prefix="/api/v1/scraping", # Specific prefix for scraping-related operations.
    tags=["Scraping Operations"]
)


# --- Root Endpoint ---
@app.get("/", tags=["General"], summary="API Root Endpoint")
async def read_root():
    """
    Provides basic information about the API.

    This root endpoint can be used for health checks or to quickly get
    links to the API documentation.
    """
    return {
        "message": "Welcome to the AI Scraper Framework API",
        "version": app.version,
        "documentation_url": app.docs_url, # URL for Swagger UI
        "redoc_url": app.redoc_url         # URL for ReDoc documentation
    }

# --- Main Execution Block (for development) ---
if __name__ == "__main__":
    # This block allows running the FastAPI application directly using Uvicorn
    # for local development and testing. It's not used in production deployments
    # where a WSGI/ASGI server like Gunicorn with Uvicorn workers is preferred.
    import uvicorn
    
    # The logger instance should be available here due to the setup at the top.
    logger.info("Starting Uvicorn server directly for local development/testing (not for production)...")
    
    # Note: APP_ENV should be set in the environment for ConfigurationManager to load
    # the correct configuration (e.g., 'development' or 'production').
    # Example: `export APP_ENV=development` in shell, or via .env file if using python-dotenv.
    # import os
    # if not os.getenv("APP_ENV"):
    #     logger.info("APP_ENV not set, defaulting to 'development' for local Uvicorn run.")
    #     os.environ["APP_ENV"] = "development"
        # This ensures config_manager (and thus logging) loads dev settings if not otherwise specified.
        # Re-setup logging if APP_ENV was just set and initial setup used a different default.
        # This is a bit complex for a simple __main__; usually, env is set outside.

    # Run the Uvicorn server.
    # `host="0.0.0.0"` makes the server accessible on all network interfaces.
    # `port=8000` is a common development port.
    # `reload=True` enables auto-reloading on code changes (for development only).
    uvicorn.run(app, host="0.0.0.0", port=8000) # Note: reload=True was in original, often passed via CLI
