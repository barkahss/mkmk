import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy_utils.types.uuid import UUIDType # Requires sqlalchemy-utils

# Define the base for declarative models
Base = declarative_base()

class ScrapingTask(Base):
    """
    SQLAlchemy model for a scraping task.
    Represents a request to scrape a specific URL.
    """
    __tablename__ = "scraping_tasks"

    id = Column(UUIDType(binary=False), primary_key=True, default=uuid.uuid4)
    url = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True) # e.g., pending, running, completed, failed
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to ScrapingResult (one task can have multiple result entries)
    # `lazy="selectin"` is often a good default for async to avoid N+1 issues if results are accessed.
    results = relationship("ScrapingResult", back_populates="task", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<ScrapingTask(id={self.id}, url='{self.url}', status='{self.status}')>"

class ScrapingResult(Base):
    """
    SQLAlchemy model for the result of a scraping task.
    Stores the data extracted or error information from a scraping attempt.
    """
    __tablename__ = "scraping_results"

    id = Column(UUIDType(binary=False), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUIDType(binary=False), ForeignKey("scraping_tasks.id"), nullable=False, index=True)
    
    # Stores the successfully scraped data as a JSON object.
    # JSONB is a PostgreSQL-specific type offering better performance for JSON operations.
    data = Column(JSONB, nullable=True) 
    
    error_info = Column(Text, nullable=True) # Using Text for potentially longer error messages
    screenshot_file_path = Column(String, nullable=True) # Path to the screenshot, if taken
    ocr_extracted_text = Column(Text, nullable=True) # Full text extracted via OCR
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to ScrapingTask
    task = relationship("ScrapingTask", back_populates="results", lazy="joined") # `lazy="joined"` can be useful here

    def __repr__(self):
        return f"<ScrapingResult(id={self.id}, task_id={self.task_id}, has_data={self.data is not None}, has_error={self.error_info is not None})>"

# Example of how to ensure __init__.py in components/storage includes these for easier access
# (This would be done in a later step if updating __init__.py files)
# from .database_models import Base, ScrapingTask, ScrapingResult
# __all__ = ["Base", "ScrapingTask", "ScrapingResult", ...]
