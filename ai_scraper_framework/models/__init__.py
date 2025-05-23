"""
Models sub-package for the AI Scraper Framework.

This package contains modules related to AI model management,
including model registries, and will host sub-packages for specific
model types like CV (Computer Vision) and NLP (Natural Language Processing).
"""

from .model_registry import ModelRegistry

__all__ = [
    "ModelRegistry",
]
