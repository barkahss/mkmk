"""
Renderer component for the AI Scraper Framework.

This sub-package is responsible for rendering web pages, typically using
headless browsers, to obtain HTML content that includes dynamically
generated elements via JavaScript.
"""
from .playwright_manager import PlaywrightManager

__all__ = [
    "PlaywrightManager",
]
