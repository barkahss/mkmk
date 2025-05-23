# AI Scraper Framework

## Overview

The AI Scraper Framework is a Python-based solution designed to provide a robust and extensible platform for web scraping. It leverages modern AI techniques for advanced data extraction, including computer vision for analyzing page layouts and NLP for processing textual content. The framework aims to simplify the development of complex scraping tasks by offering a structured and component-based architecture.

Core technologies used include:
*   **Python 3.9+**
*   **FastAPI:** For creating a modern, fast web API.
*   **Playwright:** For robust browser automation and page rendering.
*   **YOLO (Ultralytics):** For object detection in images (e.g., identifying elements in screenshots).
*   **Tesseract OCR:** For extracting text from images.
*   **spaCy:** For Natural Language Processing tasks like text cleaning and named entity recognition.
*   **Docker:** For containerized development and deployment.

## Key Features

*   **Core Infrastructure:**
    *   Centralized configuration management (`development.yaml`, `production.yaml`).
    *   Configurable logging system (console and rotating file handlers).
    *   Custom exception hierarchy for clear error handling.
*   **Web Rendering & Content Fetching:**
    *   Playwright-based asynchronous page rendering (Chromium, Firefox, WebKit support).
    *   Retrieval of HTML content.
    *   Screenshot capture of web pages (full page or specific elements).
*   **Data Extraction:**
    *   Basic HTML parsing for common elements (e.g., page titles, hyperlinks) using BeautifulSoup.
    *   YOLO-based object detection capabilities (stubbed, for identifying elements in images/screenshots).
    *   Tesseract-based Optical Character Recognition (OCR) for text extraction from images or specific image regions.
    *   SpaCy-based Natural Language Processing (NLP) for:
        *   Text cleaning.
        *   Named Entity Recognition (NER).
*   **Storage:**
    *   File-based storage for scraped data, primarily in JSON format.
    *   Automatic filename generation with timestamp and UUID for uniqueness if specific names are not provided.
*   **Model Management:**
    *   Basic model registry concept for accessing paths/names of AI models.
*   **API:**
    *   REST API built with FastAPI for triggering scraping tasks.
    *   Currently supports single URL scraping via `POST /api/v1/scraping/scrape-single-url`.
*   **Development & Testing:**
    *   Dockerized development environment using Docker Compose.
    *   Unit tests for core components and API endpoints using `pytest`.

## Project Structure

The project is organized into several main directories:

*   `ai_scraper_framework/`: Root package directory.
    *   `api/`: Contains FastAPI application setup, route definitions, and Pydantic models.
    *   `components/`: Houses reusable modules for specific tasks (rendering, extraction, storage, vision).
        *   `extractor/`: Parsing HTML (BasicParser), NLP (NlpProcessor), and orchestration (ExtractorManager).
        *   `renderer/`: Browser automation (PlaywrightManager).
        *   `storage/`: Data storage (FileStorage).
        *   `vision/`: Computer vision tasks (YoloDetector, VisionManager for OCR).
    *   `core/`: Core functionalities like configuration, logging, custom exceptions, and the main `ScrapingManager`.
    *   `models/`: AI model-related modules, including model registry and placeholders for model files (`cv_models/`, `nlp_models/`).
    *   `config/`: YAML configuration files (`development.yaml`, `production.yaml`).
    *   `logs/`: Default directory for log files (created at runtime, ignored by Git).
    *   `scraped_data_refined_dev/`, `scraped_data_refined_prod/`: Example default output directories for scraped data (created at runtime, ignored by Git).
    *   `temp_playwright_screenshots/`: Default directory for temporary screenshots (created at runtime, ignored by Git).
*   `tests/`: Contains all unit and integration tests, mirroring the project structure.
*   `Dockerfile`: Defines the Docker image for the application.
*   `docker-compose.yml`: Configures services for Docker Compose (e.g., the web API).
*   `requirements.txt`: Lists Python dependencies.
*   `.dockerignore`: Specifies files to ignore when building the Docker image.
*   `.gitignore`: Specifies files to ignore for Git version control.

## Setup and Installation

### Prerequisites

*   Python 3.9 or newer.
*   Docker and Docker Compose (for the containerized setup).
*   Tesseract OCR Engine:
    *   **Debian/Ubuntu:** `sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-eng`
    *   **macOS:** `brew install tesseract tesseract-lang`
    *   **Windows:** Download from the official Tesseract at UB Mannheim page or use WSL.
    *   Ensure `tesseract` command is in your system's PATH.
*   (Optional but recommended) A Python virtual environment tool like `venv` or `conda`.

### Option 1: Dockerized Setup (Recommended)

This is the easiest way to get the framework running with all dependencies.

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>/ai_scraper_framework
    ```
2.  **Build and run the services using Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
3.  The API will be available at `http://localhost:8000`.
    *   Swagger UI documentation: `http://localhost:8000/docs`
    *   ReDoc documentation: `http://localhost:8000/redoc`

    This setup includes all Python dependencies, Playwright browser binaries (Chromium by default), the Tesseract OCR engine, and the default spaCy English model (`en_core_web_sm`) within the Docker container.

### Option 2: Manual Python Setup (for development/debugging outside Docker)

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>/ai_scraper_framework
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    # On Windows: .venv\Scripts\activate
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install Playwright browser binaries:**
    (Chromium is used by default in the current configuration)
    ```bash
    playwright install --with-deps chromium
    ```
5.  **Download spaCy language models:**
    (The default development config uses `en_core_web_sm`)
    ```bash
    python -m spacy download en_core_web_sm
    ```
6.  **Ensure Tesseract OCR is installed system-wide** (see Prerequisites section above).
7.  **Set environment variables (optional, defaults to development):**
    ```bash
    export APP_ENV=development 
    # On Windows (PowerShell): $env:APP_ENV="development"
    # On Windows (CMD): set APP_ENV=development
    ```
    This ensures the correct configuration file (e.g., `config/development.yaml`) is loaded.
8.  **Run the FastAPI application using Uvicorn:**
    ```bash
    uvicorn ai_scraper_framework.api.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The API will be available at `http://localhost:8000`.

## Running Tests

*   Ensure all development dependencies, including `pytest`, are installed (they are included in `requirements.txt`).
*   If using a manual setup, make sure your virtual environment is activated.
*   Navigate to the `ai_scraper_framework` root directory.
*   Run tests using `pytest`:
    ```bash
    pytest
    ```
*   **Note:**
    *   Most unit tests use mocking and should pass without external dependencies.
    *   Integration tests (e.g., those interacting with live Playwright browsers or specific AI models) might require browser binaries, Tesseract, and downloaded models to be fully available in the environment where tests are run. These tests are typically marked with `@pytest.mark.integration` and can be skipped if needed (e.g., `pytest -m "not integration"`).

## API Usage Example

The primary endpoint for scraping is `/api/v1/scraping/scrape-single-url`.

You can trigger a scraping task using `curl` or any API client:

```bash
curl -X POST "http://localhost:8000/api/v1/scraping/scrape-single-url" \
     -H "Content-Type: application/json" \
     -d '{"url": "http://example.com"}'
```

**Expected Successful Response (example):**

```json
{
  "message": "Scraping successful.",
  "output_path": "/app/scraped_data_refined_dev/scrape_example_com_20231027_123456_789012_abcdef.json", 
  "url_processed": "http://example.com",
  "error_details": null
}
```
The `output_path` will point to the location (within the Docker container if using Docker, or on your local filesystem if manual setup) where the scraped data (including HTML, OCR text, screenshot path, etc.) is saved as a JSON file. The filename includes a timestamp and domain for uniqueness.

## Configuration

*   Environment-specific configurations are managed via YAML files in the `config/` directory (e.g., `development.yaml`, `production.yaml`).
*   The active configuration is selected using the `APP_ENV` environment variable. If not set, it defaults to `development`.
*   Configuration settings include database connections (placeholder), model paths, logging levels, and component-specific parameters.

## Future Work / Roadmap

This framework is foundational. Planned enhancements include:

*   **Dashboard:** A web interface for managing and monitoring scraping tasks.
*   **Advanced ML Models:** Integration of more sophisticated CV and NLP models for complex data extraction.
*   **Task Scheduling & Queuing:** Robust system for scheduling recurring scrapes and managing task queues (e.g., using Celery, Redis).
*   **Database Integration:** Storing scraped data and task metadata in a structured database (e.g., PostgreSQL).
*   **Proxy Management:** Support for using proxies to avoid IP blocking.
*   **Distributed Scraping:** Capabilities to distribute scraping tasks across multiple workers.
*   **More Comprehensive Extraction Logic:** Moving beyond basic title/link extraction to more configurable and targeted data point extraction.

---

This README provides a starting point. It should be updated as the project evolves.
