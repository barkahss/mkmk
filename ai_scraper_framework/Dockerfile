# 1. Start from a Python base image
FROM python:3.9-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Set working directory
WORKDIR /app

# 4. Install system dependencies required by Playwright and other tools
# These are common dependencies for Playwright's --with-deps chromium
RUN apt-get update && apt-get install -y \
    build-essential \
    # For Playwright specifically (chromium dependencies)
    libnss3 \
    libnspr4 \
    libdbus-glib-1-2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    # Tesseract OCR and English language pack
    tesseract-ocr \
    tesseract-ocr-eng \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Install Playwright browser binaries (Chromium in this case)
# Using --with-deps should help ensure OS dependencies are met,
# though we've also explicitly listed many above for robustness.
RUN playwright install --with-deps chromium

# Download default spaCy model (ensure 'spacy' is in requirements.txt)
RUN python -m spacy download en_core_web_sm

# 7. Copy the rest of the application code
# This assumes Dockerfile is in the root of ai_scraper_framework directory
# and the context for the docker build is this directory.
COPY . .

# 8. Define the command to run the application
# This will be overridden by docker-compose.yml for development,
# but it's good practice for a standalone Docker image.
CMD ["uvicorn", "ai_scraper_framework.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
