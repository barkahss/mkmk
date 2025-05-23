import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any # Any for JSONB data
from pydantic import BaseModel, HttpUrl

# --- Request Models ---

class BulkScrapeRequest(BaseModel):
    """
    Request model for initiating scraping tasks for multiple URLs.
    """
    urls: List[HttpUrl]


# --- Response Models (Schemas for SQLAlchemy ORM objects) ---
# These models will be used to serialize SQLAlchemy objects to JSON.
# `orm_mode = True` (or `from_attributes = True` in Pydantic V2) allows Pydantic
# to read data from ORM model attributes.

class ScrapingTaskSchema(BaseModel):
    """
    Pydantic schema for representing a ScrapingTask.
    """
    id: uuid.UUID
    url: HttpUrl # Using HttpUrl for consistency, though DB stores String
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic V2 (orm_mode in V1)

class ScrapingResultSchema(BaseModel):
    """
    Pydantic schema for representing a ScrapingResult.
    """
    id: uuid.UUID
    task_id: uuid.UUID
    data: Optional[Dict[str, Any]] = None # Represents JSONB, can be any valid JSON structure
    error_info: Optional[str] = None
    created_at: datetime
    screenshot_file_path: Optional[str] = None
    ocr_extracted_text: Optional[str] = None

    class Config:
        from_attributes = True

# --- API Endpoint Specific Response Models ---

class TaskResponse(BaseModel):
    """
    Response model for operations returning a single task.
    """
    task: ScrapingTaskSchema

class TasksListResponse(BaseModel):
    """
    Response model for listing multiple tasks with pagination details.
    """
    tasks: List[ScrapingTaskSchema]
    total: int
    page: int
    size: int

class ResultsListResponse(BaseModel): # Changed from ResultResponse to reflect list
    """
    Response model for operations returning multiple results for a task.
    """
    results: List[ScrapingResultSchema]
    total: int # Total results for the task

class BulkScrapeResponse(BaseModel):
    """
    Response model for a bulk scraping request.
    """
    message: str
    task_ids: List[uuid.UUID]

class SingleScrapeTaskInitiatedResponse(BaseModel): # New for single scrape consistency
    """
    Response model when a single URL scrape task is initiated.
    """
    message: str
    task: ScrapingTaskSchema

class SingleScrapeResultResponse(BaseModel): # New for single scrape result
    """
    Response model for returning the direct result of a single scrape operation,
    including the task info and the specific result.
    """
    message: str
    task: ScrapingTaskSchema
    result: ScrapingResultSchema
    
# Example usage note:
# When returning SQLAlchemy objects from an endpoint, ensure they are
# passed to these Pydantic models for proper serialization, e.g.:
# db_task = await db_manager.get_task(...)
# return TaskResponse(task=ScrapingTaskSchema.from_orm(db_task))
# or directly if the endpoint response_model is set, FastAPI handles it.
