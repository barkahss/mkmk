"""
Components sub-package for the AI Scraper Framework.

This package contains reusable components for various scraping tasks,
such as rendering web pages, extracting data, and storing results.

The `__all__` variable defines the public API of this sub-package,
making key components directly importable from `ai_scraper_framework.components`.
"""

# Re-export key components for easier access.
from .renderer.playwright_manager import PlaywrightManager
from .extractor.basic_parser import BasicParser
from .storage.file_storage import (
    FileStorage,
    FilePathError,
    FileExistsError,
    FileNotFound,
    SerializationError
)

__all__ = [
    "PlaywrightManager",
    "BasicParser",
    "FileStorage",
    "FilePathError",        # Exporting storage-specific exceptions
    "FileExistsError",      # as they might be useful for users of FileStorage
    "FileNotFound",
    "SerializationError",
]
