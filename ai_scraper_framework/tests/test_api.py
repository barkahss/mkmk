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
        # This branch executes if Playwright browsers are installed and working
        print("Test (example.com): Received 200 OK (implies browsers are installed)")
        data = response.json()
        assert data["message"] == "Scraping successful."
        assert "output_path" in data
        assert data["url_processed"] == test_url
        assert os.path.exists(data["output_path"]) # Check if file was actually created
    elif response.status_code == 503:
        # This branch executes if Playwright browsers are NOT installed
        print("Test (example.com): Received 503 Service Unavailable (implies browsers are not installed or rendering component failed)")
        data = response.json()
        assert "Scraping service unavailable: Rendering component not ready" in data["detail"]
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
        print("Test (httpbin.org/html): Received 200 OK (implies browsers are installed)")
        data = response.json()
        assert data["message"] == "Scraping successful."
        assert "output_path" in data
        assert data["url_processed"] == test_url
        assert os.path.exists(data["output_path"])
    elif response.status_code == 503:
        print("Test (httpbin.org/html): Received 503 Service Unavailable (implies browsers are not installed or rendering component failed)")
        data = response.json()
        assert "Scraping service unavailable: Rendering component not ready" in data["detail"]
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

    # If Playwright browsers are not installed, this will be a 503 due to renderer init failure.
    # If Playwright browsers are installed, Playwright itself will fail to navigate,
    # which should be caught by ScrapingManager and result in a TaskManagementError,
    # then translated to a 500 or 503 by the API.
    assert response.status_code == 503 or response.status_code == 500
    data = response.json()
    assert "detail" in data
    if response.status_code == 503:
         assert "Scraping service unavailable" in data["detail"] or "rendering component failed" in data["detail"]
    else: # 500
        assert "Scraping failed" in data["detail"] or "An unexpected error occurred" in data["detail"]


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
