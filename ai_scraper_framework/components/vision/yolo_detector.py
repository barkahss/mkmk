from typing import Union, List, Dict
import numpy as np
from ultralytics import YOLO
# from PIL import Image # For loading images if needed, though YOLO can handle paths and np arrays.

from ai_scraper_framework.core.exceptions import ModelError
from ai_scraper_framework.core.logger import get_logger

logger = get_logger(__name__)

class YoloDetector:
    """
    A detector class that uses a YOLO model from the 'ultralytics' library
    to detect objects in images.
    """
    def __init__(self, model_path: str):
        """
        Initializes the YoloDetector by loading a YOLO model.

        Args:
            model_path (str): The path to the YOLO model file (e.g., 'yolov8n.pt').

        Raises:
            ModelError: If the model fails to load from the specified path.
        """
        self.model_path = model_path
        try:
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO model loaded successfully from: {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model from '{self.model_path}': {e}", exc_info=True)
            raise ModelError(model_name=self.model_path, message=f"Failed to load YOLO model: {e}")

    def detect_objects(self, image_source: Union[str, np.ndarray]) -> List[Dict]:
        """
        Detects objects in an image using the loaded YOLO model.

        The input can be a file path to an image or a NumPy array representing an image.
        OpenCV is typically used to load images into NumPy arrays (BGR format).
        The YOLO model handles various image formats and sources.

        Args:
            image_source (Union[str, np.ndarray]): Path to the image file or a NumPy array
                                                   representing the image (e.g., loaded via OpenCV).

        Returns:
            List[Dict]: A list of dictionaries, where each dictionary represents a detected object
                        and contains 'box' (list of [x1, y1, x2, y2] coordinates),
                        'label' (str, class name), and 'confidence' (float).
                        Returns an empty list if no objects are detected or if an error occurs.
        """
        if image_source is None:
            logger.warning("detect_objects called with None image_source.")
            return []
            
        logger.debug(f"Performing object detection on image source: {type(image_source)}")
        try:
            results = self.model(image_source, verbose=False) # verbose=False to reduce console spam from YOLO
        except Exception as e:
            logger.error(f"Error during YOLO model prediction: {e}", exc_info=True)
            # Depending on desired behavior, could re-raise as ModelError or return empty list.
            # For now, returning empty list to indicate no detections found due to error.
            return []

        detected_objects: List[Dict] = []

        if results and len(results) > 0:
            # Process results (assuming results[0] for single image processing)
            # The structure of 'results' can vary slightly based on ultralytics version and task type.
            # For object detection, results[0].boxes should contain detections.
            res = results[0] # Get results for the first (and likely only) image
            
            if res.boxes is not None:
                for box_data in res.boxes:
                    # Extract bounding box coordinates
                    # box_data.xyxy is a tensor, get first element for single image, then convert to list
                    try:
                        xyxy = box_data.xyxy[0].tolist() # [x1, y1, x2, y2]
                        confidence = float(box_data.conf[0])
                        class_id = int(box_data.cls[0])
                        label = res.names.get(class_id, "unknown_class")

                        detected_objects.append({
                            'box': [int(coord) for coord in xyxy], # Ensure integer coordinates
                            'label': label,
                            'confidence': confidence
                        })
                    except IndexError: # If a detection is malformed
                        logger.warning(f"Skipping malformed detection result: {box_data}", exc_info=True)
                        continue
            else:
                logger.info("No boxes attribute in results or results are empty.")
        else:
            logger.info("No objects detected or results object is empty.")
            
        logger.info(f"Detection complete. Found {len(detected_objects)} objects.")
        return detected_objects

# The if __name__ == '__main__': block has been migrated to
# tests/components/vision/test_yolo_detector.py
