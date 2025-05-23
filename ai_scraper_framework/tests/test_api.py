import pytest
import shutil
import os
from fastapi.testclient import TestClient

# Import the FastAPI app instance from your application
from ai_scraper_framework.api.main import app
# Import the base path for file storage to help with cleanup
from ai_scraper_framework.components.storage.file_storage import FileStorage

# TestClient setup
# The client will be used by test functions to make requests to the application.
client = TestClient(app)

# Determine the base path for test outputs to help with cleanup
# This should match how ScrapingManager determines its storage path,
# assuming ScrapingManager uses FileStorage's default or a predictable path.
# For manager.py, the default storage path is 'scraped_data' if not overridden.
# The test in manager.py uses 'manager_test_output'.
# The API endpoint itself generates a dynamic filename but uses the default FileStorage path.
# So, the default FileStorage.DEFAULT_BASE_PATH is the one to clean.

# Correct determination of project root for default storage path
# tests/test_api.py -> tests -> ai_scraper_framework
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# This path should match what FileStorage uses when configured by ConfigurationManager
# in a development environment (which is the default for config_manager if APP_ENV is not set).
# From development.yaml: components.file_storage.base_path is "scraped_data_refined_dev"
CONFIGURED_DEV_STORAGE_PATH = os.path.join(project_root, "scraped_data_refined_dev")


@pytest.fixture(scope="module", autouse=True)
def manage_test_output_directory():
    """
    Fixture to manage the test output directory.
    It runs once per module: creates the directory before tests and cleans it up after.
    """
    # Before tests: Ensure the directory exists (it will be created by FileStorage if not)
    # No explicit creation needed here as FileStorage handles it.
    
    yield # This is where the tests run

    # After tests: Clean up the storage directory that the API under test would use.
    # This is crucial if tests generate files.
    if os.path.exists(CONFIGURED_DEV_STORAGE_PATH):
        print(f"\nCleaning up test output directory: {CONFIGURED_DEV_STORAGE_PATH}")
        shutil.rmtree(CONFIGURED_DEV_STORAGE_PATH)
    else:
        print(f"\nTest output directory not found, no cleanup needed: {CONFIGURED_DEV_STORAGE_PATH}")


def test_scrape_single_url_success_example_com():
    """
    Tests the /scrape-single-url endpoint with http://example.com.
    This test expects Playwright to fail if browser binaries are not installed,
    leading to a 503 error as handled by the API.
    If browsers ARE installed, it would expect a 200.
    """
    test_url = "http://example.com"
    response = client.post("/api/v1/scraping/scrape-single-url", json={"url": test_url})

    # Print response for debugging, especially in CI environments
    print(f"Response for {test_url}: {response.status_code}, {response.text}")

    if response.status_code == 200:
        print("Test (example.com): Received 200 OK (implies browsers are installed and scrape succeeded)")
        data = response.json()
        assert "Scraping task completed" in data["message"] # Or "Scraping task completed with errors"
        
        assert "task" in data
        assert "result" in data
        
        task_data = data["task"]
        result_data = data["result"]
        
        assert uuid.UUID(task_data["id"]) # Valid UUID
        assert task_data["url"] == test_url
        assert task_data["status"] == "completed" # Assuming full success
        
        assert result_data["task_id"] == task_data["id"]
        assert result_data["data"] is not None
        assert "raw_title" in result_data["data"]
        # screenshot_file_path might be a temp path that's cleaned up, so just check presence
        assert "screenshot_file_path" in result_data 
        # os.path.exists might fail if path is temp and cleaned.
        # if result_data["screenshot_file_path"]:
        #     assert os.path.exists(result_data["screenshot_file_path"])
            
    elif response.status_code == 500 or response.status_code == 503:
        # This branch executes if Playwright browsers are NOT installed OR other TaskManagementError
        print(f"Test (example.com): Received {response.status_code} (implies critical failure like no browsers or page load error)")
        data = response.json()
        # The API now returns SingleScrapeResultResponse even for TaskManagementError
        if "task" in data and "result" in data:
            assert "failed" in data["task"]["status"].lower() # Task status should be 'failed'
            assert data["result"]["error_info"] is not None
            if response.status_code == 503: # Specific check for renderer issue
                 assert "RendererError" in data["result"]["error_info"] or \
                        "Scraping service unavailable" in data["message"] # Old detail might be in message
        else: # Fallback if it's a direct HTTPException before result creation
            assert "detail" in data
            assert "Scraping service unavailable" in data["detail"] or "Scraping failed" in data["detail"]
    else:
        pytest.fail(f"Unexpected status code {response.status_code} for {test_url}. Response: {response.text}")


def test_scrape_single_url_success_httpbin():
    """
    Tests the /scrape-single-url endpoint with http://httpbin.org/html.
    Similar to example.com, expects 200 if browsers are present, 503 otherwise.
    """
    test_url = "http://httpbin.org/html" # A simple HTML page
    response = client.post("/api/v1/scraping/scrape-single-url", json={"url": test_url})

    print(f"Response for {test_url}: {response.status_code}, {response.text}")

    if response.status_code == 200:
        print("Test (httpbin.org/html): Received 200 OK (implies browsers are installed and scrape succeeded)")
        data = response.json()
        assert "Scraping task completed" in data["message"]
        
        task_data = data["task"]
        result_data = data["result"]
        
        assert uuid.UUID(task_data["id"])
        assert task_data["url"] == test_url
        assert task_data["status"] == "completed"
        
        assert result_data["task_id"] == task_data["id"]
        assert result_data["data"] is not None
        assert "raw_title" in result_data["data"]
        assert "Herman Melville - Moby-Dick" in result_data["data"]["raw_title"] # Specific check for httpbin
            
    elif response.status_code == 500 or response.status_code == 503:
        print(f"Test (httpbin.org/html): Received {response.status_code} (implies critical failure)")
        data = response.json()
        if "task" in data and "result" in data:
            assert "failed" in data["task"]["status"].lower()
            assert data["result"]["error_info"] is not None
            if response.status_code == 503:
                 assert "RendererError" in data["result"]["error_info"] or \
                        "Scraping service unavailable" in data["message"]
        else:
            assert "detail" in data
            assert "Scraping service unavailable" in data["detail"] or "Scraping failed" in data["detail"]
    else:
        pytest.fail(f"Unexpected status code {response.status_code} for {test_url}. Response: {response.text}")


def test_scrape_single_url_invalid_url_format():
    """
    Tests the /scrape-single-url endpoint with a malformed URL.
    Expects a 422 Unprocessable Entity due to Pydantic validation.
    """
    response = client.post("/api/v1/scraping/scrape-single-url", json={"url": "not_a_valid_url"})
    print(f"Response for invalid URL format: {response.status_code}, {response.text}")
    assert response.status_code == 422 # Pydantic validation error
    data = response.json()
    assert "detail" in data
    assert "Request validation failed" in data["detail"] # From our custom handler
    assert any("url_type" in error["type"] for error in data["errors"]) # Check for URL validation error type


def test_scrape_single_url_non_existent_domain():
    """
    Tests the /scrape-single-url endpoint with a syntactically valid but non-existent domain.
    This should be caught by PlaywrightManager (if browsers are installed) or bubble up.
    The API should return a 503 or 500.
    """
    test_url = "http://domainthatclearlyshouldnotexist12345.com"
    response = client.post("/api/v1/scraping/scrape-single-url", json={"url": test_url})
    print(f"Response for non-existent domain: {response.status_code}, {response.text}")

    # This should result in a TaskManagementError from ScrapingManager if page rendering fails.
    # The API should then return a SingleScrapeResultResponse with task status "failed".
    assert response.status_code == 500 or response.status_code == 503 # API maps TaskManagementError to 500 or 503
    
    data = response.json()
    # Check for the new structured error response
    if "task" in data and "result" in data:
        assert data["task"]["url"] == test_url
        assert data["task"]["status"] == "failed"
        assert data["result"]["error_info"] is not None
        assert "Failed to render page snapshot" in data["result"]["error_info"] or \
               "RendererError" in data["result"]["error_info"] # Check for part of the error message
    else: # Fallback for older direct HTTPException style, though API should prevent this.
        assert "detail" in data
        assert "Scraping failed" in data["detail"] or "Scraping service unavailable" in data["detail"]

# --- Tests for Task Management Endpoints (/api/v1/tasks) ---

def test_bulk_scrape_success():
    """Test successful submission of multiple URLs for bulk scraping."""
    urls_to_scrape = ["http://example.com/bulk1", "http://example.com/bulk2"]
    response = client.post("/api/v1/tasks/bulk", json={"urls": urls_to_scrape})
    
    print(f"Response for POST /api/v1/tasks/bulk: {response.status_code}, {response.text}")
    assert response.status_code == 202 # Accepted
    
    data = response.json()
    assert "Successfully created" in data["message"]
    assert len(data["task_ids"]) == len(urls_to_scrape)
    for task_id_str in data["task_ids"]:
        assert uuid.UUID(task_id_str) # Check if valid UUID

    # Optional: Follow-up GET to check one task
    if data["task_ids"]:
        first_task_id = data["task_ids"][0]
        task_response = client.get(f"/api/v1/tasks/{first_task_id}")
        assert task_response.status_code == 200
        task_data = task_response.json()["task"]
        assert task_data["status"] == "pending"
        assert task_data["url"] == urls_to_scrape[0]

def test_bulk_scrape_invalid_input():
    """Test bulk scraping with invalid inputs."""
    # Test with empty URL list
    response_empty = client.post("/api/v1/tasks/bulk", json={"urls": []})
    assert response_empty.status_code == 400 # Bad Request, as per task_routes.py
    assert "No URLs provided" in response_empty.json()["detail"]

    # Test with malformed URL (Pydantic validation)
    response_malformed = client.post("/api/v1/tasks/bulk", json={"urls": ["http://valid.com", "not_a_url"]})
    assert response_malformed.status_code == 422 # Unprocessable Entity
    data_malformed = response_malformed.json()
    assert "Request validation failed" in data_malformed["detail"]
    # Example check: find the error related to the URL field
    assert any("url_type" in error["type"] for error_list in data_malformed["errors"] for error in error_list if error["loc"][1] == "url")

def test_list_tasks_empty():
    """Test listing tasks when no tasks have been created (or DB is clean)."""
    # This test is sensitive to execution order if DB is not cleaned between tests.
    # For now, assume it runs first or that seeing prior tasks is acceptable for basic check.
    # A dedicated DB cleanup fixture per test/module would make this more robust.
    response = client.get("/api/v1/tasks/")
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == [] # Expect empty list if no tasks or DB was just reset
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["size"] > 0 # Default size

def test_list_tasks_with_data_and_pagination():
    """Test listing tasks with data and checking pagination."""
    # Create some tasks first
    initial_urls = [f"http://example.com/page_task_{i}" for i in range(5)]
    client.post("/api/v1/tasks/bulk", json={"urls": initial_urls})

    # Test page 1, size 2
    response_p1 = client.get("/api/v1/tasks/?page=1&size=2")
    assert response_p1.status_code == 200
    data_p1 = response_p1.json()
    assert len(data_p1["tasks"]) <= 2 # Can be less if total is less than 2
    # Total should reflect all tasks created in this session, potentially including those from other tests if DB isn't reset.
    # This makes total assertion tricky without full DB isolation per test.
    # For now, we check that pagination parameters are reflected.
    assert data_p1["page"] == 1
    assert data_p1["size"] == 2
    
    # If there are tasks, check their structure
    if data_p1["tasks"]:
        assert "id" in data_p1["tasks"][0]
        assert "url" in data_p1["tasks"][0]
        assert "status" in data_p1["tasks"][0]

    # Test page 2, size 2 (assuming at least 3 tasks were created by this or previous tests)
    if data_p1["total"] >=3: # Only test page 2 if there's enough data
        response_p2 = client.get("/api/v1/tasks/?page=2&size=2")
        assert response_p2.status_code == 200
        data_p2 = response_p2.json()
        assert len(data_p2["tasks"]) <= 2
        assert data_p2["page"] == 2
        assert data_p2["size"] == 2
        if len(data_p1["tasks"]) == 2 and len(data_p2["tasks"]) > 0 : # Ensure different tasks if possible
             assert data_p1["tasks"][0]["id"] != data_p2["tasks"][0]["id"]

def test_get_specific_task_success():
    """Test retrieving a specific task by its ID."""
    # Create a task first
    urls = ["http://example.com/specific_task_test"]
    response_create = client.post("/api/v1/tasks/bulk", json={"urls": urls})
    assert response_create.status_code == 202
    task_id = response_create.json()["task_ids"][0]

    response_get = client.get(f"/api/v1/tasks/{task_id}")
    assert response_get.status_code == 200
    data = response_get.json()
    assert "task" in data
    assert data["task"]["id"] == task_id
    assert data["task"]["url"] == urls[0]
    assert data["task"]["status"] == "pending" # Initially pending from bulk create

def test_get_specific_task_not_found():
    """Test retrieving a non-existent task returns 404."""
    non_existent_task_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/tasks/{non_existent_task_id}")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]

def test_get_task_results_success():
    """Test retrieving results for a successfully completed task."""
    # This test relies on the single scrape endpoint to create a task AND a result.
    # It also depends on the environment having Playwright browsers installed for a 200.
    # If browsers are not installed, the scrape will result in a 'failed' task with error info.
    test_url = "http://example.com/task_with_results"
    response_scrape = client.post("/api/v1/scraping/scrape-single-url", json={"url": test_url})
    
    if response_scrape.status_code == 200:
        scrape_data = response_scrape.json()
        task_id = scrape_data["task"]["id"]

        response_results = client.get(f"/api/v1/tasks/{task_id}/results")
        assert response_results.status_code == 200
        results_data = response_results.json()
        
        assert "results" in results_data
        assert isinstance(results_data["results"], list)
        assert results_data["total"] >= 1 # Should have at least one result
        
        # Verify structure of the first result (assuming one result for this basic scrape)
        first_result = results_data["results"][0]
        assert uuid.UUID(first_result["id"])
        assert first_result["task_id"] == task_id
        assert first_result["data"] is not None # Data should exist for successful scrape
        assert "raw_title" in first_result["data"]
        assert first_result["error_info"] is None
    elif response_scrape.status_code == 500 or response_scrape.status_code == 503:
        # Case where scrape failed (e.g., no Playwright browsers)
        print(f"Skipping get_task_results_success detailed assertions as initial scrape failed with {response_scrape.status_code}")
        scrape_data = response_scrape.json()
        if "task" in scrape_data and scrape_data["task"]["id"]:
            task_id = scrape_data["task"]["id"]
            response_results = client.get(f"/api/v1/tasks/{task_id}/results")
            assert response_results.status_code == 200 # Still expect 200, but results list might show error
            results_data = response_results.json()
            assert "results" in results_data
            assert isinstance(results_data["results"], list)
            assert results_data["total"] >= 1 # A result entry with error_info should be present
            first_result = results_data["results"][0]
            assert first_result["error_info"] is not None
        else:
            print("Skipping get_task_results_success detailed assertions as initial scrape failed without task ID in response.")
    else:
        pytest.fail(f"Initial scrape for test_get_task_results_success failed unexpectedly: {response_scrape.status_code} - {response_scrape.text}")


def test_get_task_results_for_pending_task():
    """Test retrieving results for a task that is still pending (no results yet)."""
    # Create a task via bulk endpoint, which leaves it as "pending"
    urls = ["http://example.com/pending_task_for_results"]
    response_create = client.post("/api/v1/tasks/bulk", json={"urls": urls})
    assert response_create.status_code == 202
    task_id = response_create.json()["task_ids"][0]

    response_results = client.get(f"/api/v1/tasks/{task_id}/results")
    assert response_results.status_code == 200
    data = response_results.json()
    assert data["results"] == [] # Expect empty list for a pending task
    assert data["total"] == 0

def test_get_task_results_task_not_found():
    """Test retrieving results for a non-existent task returns 404."""
    non_existent_task_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/tasks/{non_existent_task_id}/results")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to the AI Scraper Framework API"
    assert data["version"] == app.version # Checks if version is correctly fetched from app


# To run these tests locally:
# 1. Ensure all dependencies from requirements.txt are installed, including pytest and httpx.
# 2. If you want to test the "success" path (200 OK), ensure Playwright browsers are installed (`playwright install`).
# 3. Navigate to the `ai_scraper_framework` directory.
# 4. Run `python -m pytest tests/test_api.py` or simply `pytest tests/test_api.py`.
#
# The tests are designed to acknowledge that browser binaries might not be present in all execution environments.
# The cleanup fixture will attempt to remove any directories created by FileStorage during tests.
