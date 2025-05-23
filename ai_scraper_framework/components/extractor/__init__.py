"""
Extractor component for the AI Scraper Framework.

This sub-package provides tools for parsing HTML content and extracting
structured data from it.
It includes parsers for HTML and NLP processors for text analysis.
"""
from .basic_parser import BasicParser
from .nlp_processor import NlpProcessor
from .extractor_manager import ExtractorManager

__all__ = [
    "BasicParser",
    "NlpProcessor",
    "ExtractorManager",
]
