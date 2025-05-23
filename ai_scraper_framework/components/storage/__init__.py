"""
Storage component for the AI Scraper Framework.

This sub-package provides utilities for storing and retrieving scraped data,
such as saving to files or databases.
"""
from .file_storage import (
    FileStorage,
    FilePathError,
    FileExistsError,
    FileNotFound,
    SerializationError
)

__all__ = [
    "FileStorage",
    "FilePathError",
    "FileExistsError",
    "FileNotFound",
    "SerializationError",
]
