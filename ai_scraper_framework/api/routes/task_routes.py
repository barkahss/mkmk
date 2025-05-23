import uuid
from typing import List, Tuple # Tuple for DB manager return type

from fastapi import APIRouter, HTTPException, Query, status # Query for pagination params

# Import Pydantic models from the new api.models module
from ai_scraper_framework.api.models import (
    BulkScrapeRequest,
    BulkScrapeResponse,
    ScrapingTaskSchema,
    ScrapingResultSchema,
    TaskResponse,
    TasksListResponse,
    ResultsListResponse # Changed from ResultResponse to reflect list
)
# Import DB manager and config
from ai_scraper_framework.components.storage.db_manager import DatabaseManager
from ai_scraper_framework.core.config import config_manager # Global config instance
from ai_scraper_framework.core.logger import get_logger
from ai_scraper_framework.core.exceptions import DatabaseError

logger = get_logger(__name__)
router = APIRouter()

# --- Task Management Endpoints ---

@router.post(
    "/bulk",
    response_model=BulkScrapeResponse,
    status_code=status.HTTP_202_ACCEPTED, # 202 Accepted as tasks are created but not processed yet
    summary="Submit multiple URLs for scraping",
    description="Creates scraping tasks for a list of URLs. These tasks are added to a queue for later processing."
)
async def bulk_scrape_request(request: BulkScrapeRequest):
    """
    Accepts a list of URLs and creates 'pending' scraping tasks for each.
    Actual scraping is handled by a separate worker process (future implementation).
    """
    db_manager = DatabaseManager(config=config_manager) # Instantiate DB manager
    task_ids: List[uuid.UUID] = []
    
    if not request.urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No URLs provided for scraping.")

    logger.info(f"Received bulk scrape request for {len(request.urls)} URLs.")
    
    # This loop creates tasks sequentially. For very large lists, consider optimizing.
    for url_to_scrape in request.urls:
        try:
            # The API layer is responsible for creating the initial "pending" task.
            # The ScrapingManager (or a worker) will later pick up this task.
            task = await db_manager.add_task(url=str(url_to_scrape)) # Ensure URL is string
            task_ids.append(task.id)
            logger.debug(f"Created pending task {task.id} for URL: {url_to_scrape}")
        except DatabaseError as e:
            logger.error(f"Database error creating task for URL {url_to_scrape}: {e}", exc_info=True)
            # Decide if one failure should stop all, or collect errors.
            # For now, let it fail the whole request if any DB error occurs.
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create task for URL {url_to_scrape} due to database error: {e.message}"
            )
        except Exception as e: # Catch any other unexpected error during task creation
            logger.error(f"Unexpected error creating task for URL {url_to_scrape}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while creating task for URL {url_to_scrape}."
            )
            
    return BulkScrapeResponse(
        message=f"Successfully created {len(task_ids)} scraping tasks.",
        task_ids=task_ids
    )

@router.get(
    "/",
    response_model=TasksListResponse,
    summary="List all scraping tasks with pagination",
    description="Retrieves a paginated list of all scraping tasks."
)
async def list_tasks(
    page: int = Query(1, ge=1, description="Page number, 1-indexed"),
    size: int = Query(20, ge=1, le=100, description="Number of tasks per page (max 100)")
):
    """
    Retrieves a paginated list of scraping tasks.
    """
    db_manager = DatabaseManager(config=config_manager)
    skip = (page - 1) * size
    try:
        tasks_list, total_tasks = await db_manager.get_tasks(skip=skip, limit=size)
        return TasksListResponse(
            tasks=[ScrapingTaskSchema.from_orm(task) for task in tasks_list],
            total=total_tasks,
            page=page,
            size=size
        )
    except DatabaseError as e:
        logger.error(f"Database error listing tasks: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e.message}")


@router.get(
    "/{task_id}",
    response_model=TaskResponse, # Or directly ScrapingTaskSchema if preferred
    summary="Get details of a specific scraping task",
    description="Retrieves detailed information for a single scraping task by its ID."
)
async def get_task_details(task_id: uuid.UUID):
    """
    Retrieves details for a specific scraping task.
    """
    db_manager = DatabaseManager(config=config_manager)
    try:
        task = await db_manager.get_task(task_id=task_id, load_results=False) # Results not loaded here by default
        if not task:
            logger.warning(f"Task with ID {task_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return TaskResponse(task=ScrapingTaskSchema.from_orm(task))
    except DatabaseError as e:
        logger.error(f"Database error getting task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e.message}")


@router.get(
    "/{task_id}/results",
    response_model=ResultsListResponse, # Using the corrected ResultsListResponse
    summary="Get all results for a specific scraping task",
    description="Retrieves all scraping result entries associated with a given task ID."
)
async def get_results_for_task_endpoint(task_id: uuid.UUID):
    """
    Retrieves all scraping results associated with a specific task ID.
    """
    db_manager = DatabaseManager(config=config_manager)
    try:
        # First, check if task exists to provide a clear 404 if not
        task = await db_manager.get_task(task_id=task_id)
        if not task:
            logger.warning(f"Task with ID {task_id} not found when trying to fetch results.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found, so no results available.")

        results_list = await db_manager.get_results_for_task(task_id=task_id)
        # No need to raise 404 if results_list is empty; an empty list is a valid response.
        return ResultsListResponse(
            results=[ScrapingResultSchema.from_orm(result) for result in results_list],
            total=len(results_list) # Total results for *this specific task*
        )
    except DatabaseError as e:
        logger.error(f"Database error getting results for task {task_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e.message}")

# Note: The prompt mentioned `ResultResponse` for /{task_id}/results, but since a task can have multiple results,
# I've used `ResultsListResponse` which includes a list of `ScrapingResultSchema` and a total count.
# If only one result per task was expected, then ResultResponse with an Optional result might fit,
# but the schema design (ScrapingTask has a one-to-many with ScrapingResult) implies multiple results.
# For fetching a single specific result by its own ID, a new endpoint like /results/{result_id} would be appropriate.
# The current implementation of `db_manager.get_results_for_task` returns a list.
# The `TasksListResponse` also includes `page` and `size`, which are not relevant when fetching
# all results for a single task. So, `ResultsListResponse` is simpler.I have already completed Step 1 (defining Pydantic models in `ai_scraper_framework/api/models.py`) and Step 2 (creating `ai_scraper_framework/api/routes/task_routes.py` with the specified endpoints) in the previous turns.

**Recap of Step 1:**
-   Created `ai_scraper_framework/api/models.py`.
-   Defined request and response Pydantic models, including `BulkScrapeRequest`, `ScrapingTaskSchema`, `ScrapingResultSchema`, `TaskResponse`, `TasksListResponse`, `ResultsListResponse`, `BulkScrapeResponse`, `SingleScrapeTaskInitiatedResponse`, `SingleScrapeResultResponse`.

**Recap of Step 2:**
-   Created `ai_scraper_framework/api/routes/task_routes.py`.
-   Instantiated `APIRouter` as `router`.
-   Implemented API endpoints:
    -   `POST /bulk`: Accepts `BulkScrapeRequest`, creates pending tasks using `DatabaseManager.add_task()`, returns `BulkScrapeResponse`.
    -   `GET /`: Accepts pagination query parameters, calls `DatabaseManager.get_tasks()`, returns `TasksListResponse`.
    -   `GET /{task_id}`: Calls `DatabaseManager.get_task()`, returns `TaskResponse` or 404.
    -   `GET /{task_id}/results`: Checks if task exists, calls `DatabaseManager.get_results_for_task()`, returns `ResultsListResponse`.
-   `DatabaseManager` is instantiated directly within each route using the global `config_manager`.

Now I will proceed with Step 3: Update `DatabaseManager` (`components/storage/db_manager.py`) to add the new methods required by these API routes.
