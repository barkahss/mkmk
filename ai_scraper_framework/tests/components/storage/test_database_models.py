import uuid
from datetime import datetime
import pytest # For potential use, though basic assertions are fine here

from ai_scraper_framework.components.storage.database_models import ScrapingTask, ScrapingResult

def test_create_scraping_task_instance():
    """
    Tests basic instantiation of the ScrapingTask model and default value setting.
    This is not an ORM interaction test.
    """
    url = "http://example.com/task_test"
    task = ScrapingTask(url=url)

    assert task.url == url
    assert isinstance(task.id, uuid.UUID) # Default is uuid.uuid4()
    assert task.status == "pending" # Default status
    assert isinstance(task.created_at, datetime)
    assert isinstance(task.updated_at, datetime)
    assert task.created_at == task.updated_at # On creation, they should be very close or equal

    # Check __repr__
    assert repr(task) == f"<ScrapingTask(id={task.id}, url='{url}', status='pending')>"

def test_create_scraping_result_instance():
    """
    Tests basic instantiation of the ScrapingResult model and default value setting.
    This is not an ORM interaction test.
    """
    task_id_mock = uuid.uuid4()
    data_payload = {"key": "value", "items": [1, 2, 3]}
    screenshot_p = "/path/to/screenshot.png"
    ocr_t = "Extracted OCR text."
    error_msg = "Something went wrong during scraping."

    # Test with all optional fields provided
    result_full = ScrapingResult(
        task_id=task_id_mock,
        data=data_payload,
        screenshot_file_path=screenshot_p,
        ocr_extracted_text=ocr_t,
        error_info=error_msg
    )

    assert result_full.task_id == task_id_mock
    assert result_full.data == data_payload
    assert result_full.screenshot_file_path == screenshot_p
    assert result_full.ocr_extracted_text == ocr_t
    assert result_full.error_info == error_msg
    assert isinstance(result_full.id, uuid.UUID)
    assert isinstance(result_full.created_at, datetime)
    
    # Check __repr__ for a full instance
    assert repr(result_full) == f"<ScrapingResult(id={result_full.id}, task_id={task_id_mock}, has_data=True, has_error=True)>"

    # Test with only required fields (task_id) and some Nones
    result_minimal = ScrapingResult(task_id=task_id_mock)
    assert result_minimal.task_id == task_id_mock
    assert result_minimal.data is None
    assert result_minimal.screenshot_file_path is None
    assert result_minimal.ocr_extracted_text is None
    assert result_minimal.error_info is None
    
    # Check __repr__ for a minimal instance
    assert repr(result_minimal) == f"<ScrapingResult(id={result_minimal.id}, task_id={task_id_mock}, has_data=False, has_error=False)>"

# These tests do not interact with the database. They only check if model instances
# can be created and if default values are set as expected by SQLAlchemy's declarative system
# (before any ORM operations or database defaults might apply).
# Full ORM interaction (saving, retrieving) will be tested with DatabaseManager.
