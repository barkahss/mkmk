"""
API routes for scraping operations in the AI Scraper Framework.

This module defines FastAPI routes related to initiating and managing
web scraping tasks. It uses Pydantic models for request and response
data validation and serialization.
"""
from fastapi import APIRouter, HTTPException, status
# BaseModel, HttpUrl are no longer directly used here after model migration
from typing import Optional 
from urllib.parse import urlparse 
from datetime import datetime 

# Framework core components
from ai_scraper_framework.core.manager import ScrapingManager
from ai_scraper_framework.core.exceptions import TaskManagementError, RendererError, DatabaseError
from ai_scraper_framework.core.logger import get_logger
from ai_scraper_framework.core.config import config_manager
# Import Pydantic models from api.models
from ai_scraper_framework.api.models import (
    ScrapeURLRequest, # Now imported from api.models
    ScrapingTaskSchema,
    ScrapingResultSchema,
    SingleScrapeTaskInitiatedResponse, 
    SingleScrapeResultResponse 
)
# Import DatabaseManager
from ai_scraper_framework.components.storage.db_manager import DatabaseManager
from ai_scraper_framework.components.storage.database_models import ScrapingTask 

logger = get_logger(__name__) 

# --- API Router Definition ---
router = APIRouter()

# Note on ScrapingManager Instantiation:
# (Comments remain valid)

@router.post(
    "/scrape-single-url",
    response_model=SingleScrapeResultResponse, 
    status_code=status.HTTP_200_OK, 
    summary="Scrape a single URL and get immediate results",
    description="Accepts a URL, creates a scraping task, executes it immediately, "
                "and returns the result. Data is stored in the database."
)
async def scrape_single_url_endpoint(request: ScrapeURLRequest): # ScrapeURLRequest is now from api.models
    """
    Handles requests to scrape a single URL.

    1. Creates a 'pending' ScrapingTask in the database.
    2. Calls ScrapingManager to perform the scraping, passing the task_id.
    3. ScrapingManager updates the task status and saves results/errors to the DB.
    4. Returns the task and its primary result.
    """
    db_manager = DatabaseManager(config=config_manager)
    scraping_manager = ScrapingManager(config=config_manager)
    
    created_task_orm: Optional[ScrapingTask] = None 

    try:
        logger.info(f"Creating scraping task for URL: {request.url}")
        created_task_orm = await db_manager.add_task(url=str(request.url))
        if not created_task_orm: 
            logger.error(f"Failed to create task entry for URL {request.url} in DB, add_task returned None.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create task entry in database.")
        
        logger.info(f"Task {created_task_orm.id} created for URL {request.url}, now proceeding to scrape.")

        scraping_result_orm = await scraping_manager.scrape_single_url_basic(
            url=str(request.url),
            task_id=created_task_orm.id 
        )
        
        updated_task_orm = await db_manager.get_task(task_id=created_task_orm.id)
        if not updated_task_orm: 
            logger.error(f"Task {created_task_orm.id} not found after scraping attempt for URL {request.url}.")
            updated_task_orm = created_task_orm 

        logger.info(f"Scraping completed for URL {request.url}, Task ID: {updated_task_orm.id}, Status: {updated_task_orm.status}")
        
        return SingleScrapeResultResponse(
            message=f"Scraping task {updated_task_orm.status}.",
            task=ScrapingTaskSchema.from_orm(updated_task_orm),
            result=ScrapingResultSchema.from_orm(scraping_result_orm)
        )

    except DatabaseError as e_db:
        logger.error(f"DatabaseError during single URL scrape for {request.url}: {e_db.message}", exc_info=True)
        if created_task_orm and created_task_orm.id:
            try:
                # Error info is now part of the ScrapingResult, not the task status update.
                await db_manager.update_task_status(created_task_orm.id, "failed")
            except Exception as e_update_fail:
                logger.error(f"Failed to update task status to 'failed' for task {created_task_orm.id} after initial DB error: {e_update_fail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error during scraping: {e_db.message}")

    except TaskManagementError as e:
        logger.error(f"TaskManagementError for URL {request.url}, Task ID {created_task_orm.id if created_task_orm else 'N/A'}: {e.message}", exc_info=True)
        final_task_orm = created_task_orm 
        final_result_orm = None
        if created_task_orm and created_task_orm.id:
            # ScrapingManager is responsible for setting task to "failed" and creating result with error.
            final_task_orm = await db_manager.get_task(task_id=created_task_orm.id, load_results=True)
            if final_task_orm and final_task_orm.results:
                final_result_orm = final_task_orm.results[0] 
        
        http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_detail = f"Scraping failed for URL {request.url}. Error: {e.message}"
        
        if "RendererError" in e.message and ("Executable doesn't exist" in e.message or "playwright install" in e.message):
            http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            error_detail = f"Scraping service unavailable: Rendering component not ready. Please ensure browser binaries are installed on the server ('playwright install'). Original error: {e.message}"
        
        if final_task_orm and final_result_orm:
            return SingleScrapeResultResponse(
                message="Scraping task failed.",
                task=ScrapingTaskSchema.from_orm(final_task_orm),
                result=ScrapingResultSchema.from_orm(final_result_orm)
            )
        else: 
            raise HTTPException(status_code=http_status_code, detail=error_detail)
            
    except Exception as e: 
        logger.critical(f"Unexpected error in /scrape-single-url endpoint for URL {request.url}: {str(e)}", exc_info=True)
        if created_task_orm and created_task_orm.id:
            try:
                # Error info is part of ScrapingResult now.
                await db_manager.update_task_status(created_task_orm.id, "failed")
            except Exception as e_update_final_fail:
                 logger.error(f"Failed to update task status to 'failed' for task {created_task_orm.id} after unexpected API error: {e_update_final_fail}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected server error occurred while processing {request.url}."
        )

# Example for future expansion:
# (Comment remains valid)

# The if __name__ == "__main__": block has been removed.
# Pydantic model testing should be done in dedicated test files or via API endpoint tests.
