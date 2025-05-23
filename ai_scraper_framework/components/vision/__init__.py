"""
Computer Vision components for the AI Scraper Framework.

This sub-package includes modules for object detection, image analysis,
and other vision-related tasks that can be applied to web scraping,
such as identifying elements in screenshots.
"""
from .yolo_detector import YoloDetector
from .vision_manager import VisionManager

__all__ = [
    "YoloDetector",
    "VisionManager",
]
