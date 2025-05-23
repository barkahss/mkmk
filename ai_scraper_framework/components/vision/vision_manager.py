from typing import Union, List, Dict, Optional, TYPE_CHECKING, Tuple
import numpy as np
import pytesseract
from PIL import Image
import cv2 # For image manipulation if needed, and converting BGR to RGB for Pillow

from ai_scraper_framework.components.vision.yolo_detector import YoloDetector
from ai_scraper_framework.core.exceptions import ComponentError, ModelError
from ai_scraper_framework.core.logger import get_logger

if TYPE_CHECKING: # For type hinting ConfigurationManager without causing circular imports
    from ai_scraper_framework.core.config import ConfigurationManager

logger = get_logger(__name__)

class VisionManager:
    """
    Manages computer vision tasks, primarily object detection using YOLO models.
    It acts as a higher-level interface to vision components like YoloDetector.
    """
    def __init__(self, config: 'ConfigurationManager'):
        """
        Initializes the VisionManager.

        It attempts to load a YOLO model based on the path specified in the
        configuration. If the model path is not provided or the model fails to load,
        object detection capabilities will be disabled.

        Args:
            config (ConfigurationManager): The application's configuration manager instance,
                                           used to fetch the YOLO model path.
        """
        self.config = config
        self.yolo_detector: Optional[YoloDetector] = None

        yolo_model_path: Optional[str] = self.config.get('components.vision.yolo_model_path')

        if yolo_model_path:
            logger.info(f"YOLO model path found in configuration: {yolo_model_path}")
            try:
                # Note: YoloDetector expects an absolute path or a path relative to where YOLO can find it.
                # If paths in config are relative to project root, YoloDetector needs to handle that,
                # or the path needs to be resolved here.
                # For now, assuming model_path is directly usable by YoloDetector.
                self.yolo_detector = YoloDetector(model_path=yolo_model_path)
                logger.info("YoloDetector initialized successfully in VisionManager.")
            except ModelError as e:
                logger.error(f"ModelError initializing YoloDetector in VisionManager: {e.message}. Vision tasks will be disabled.")
                self.yolo_detector = None # Ensure it's None on failure
            except Exception as e:
                logger.error(f"Unexpected error initializing YoloDetector in VisionManager: {e}. Vision tasks will be disabled.", exc_info=True)
                self.yolo_detector = None
        else:
            logger.warning("YOLO model path not found in configuration (components.vision.yolo_model_path). VisionManager will operate without detection capabilities.")
            self.yolo_detector = None

    def detect_elements_on_page(self, image_source: Union[str, np.ndarray]) -> List[Dict]:
        """
        Detects elements (objects) in a given image.

        This method uses the initialized YoloDetector to perform object detection.
        If the YoloDetector is not available (e.g., due to configuration issues or
        model loading failure), it will return an empty list.

        Args:
            image_source (Union[str, np.ndarray]): The image to process. Can be a file path (str)
                                                   or a NumPy array representing the image.

        Returns:
            List[Dict]: A list of detected objects, where each object is represented
                        as a dictionary (e.g., {'box': [x1,y1,x2,y2], 'label': name, 'confidence': conf}).
                        Returns an empty list if no detector is available or no objects are found.

        Raises:
            ComponentError: If the YoloDetector is not available and an attempt is made to detect objects,
                            indicating a configuration or setup issue. (Alternative: return empty list)
        """
        if self.yolo_detector is None:
            logger.warning("YoloDetector not available in VisionManager. Cannot detect elements. Returning empty list.")
            # Option 1: Return empty list (graceful degradation)
            return []
            # Option 2: Raise an error to indicate a problem (more strict)
            # raise ComponentError(component_name="VisionManager",
            # message="YoloDetector is not available. Check configuration and model.")

        logger.debug(f"VisionManager delegating detection to YoloDetector for image source type: {type(image_source)}")
        try:
            detected_objects = self.yolo_detector.detect_objects(image_source)
            return detected_objects
        except ModelError as e: # Catch errors from YoloDetector's predict/process phase
            logger.error(f"ModelError during element detection: {e.message}", exc_info=True)
            raise ComponentError(component_name="VisionManager", message=f"Object detection failed due to a model issue: {e.message}")
        except Exception as e: # Catch any other unexpected error
            logger.error(f"Unexpected error during element detection: {e}", exc_info=True)
            raise ComponentError(component_name="VisionManager", message=f"An unexpected error occurred during object detection: {str(e)}")

    def extract_text_from_image_region(self, image_source: Union[str, np.ndarray], bounding_box: Tuple[int, int, int, int]) -> str:
        """
        Extracts text from a specified region of an image using Tesseract OCR.

        Args:
            image_source (Union[str, np.ndarray]): Path to the image file or a NumPy array
                                                   (e.g., loaded via OpenCV in BGR format).
            bounding_box (Tuple[int, int, int, int]): A tuple (x1, y1, x2, y2)
                                                      representing the crop region.

        Returns:
            str: The extracted text, stripped of leading/trailing whitespace.
                 Returns an empty string if OCR fails or Tesseract is not found.

        Raises:
            ComponentError: If image loading or processing fails before OCR (e.g. file not found, unsupported type).
        """
        if image_source is None:
            logger.warning("extract_text_from_image_region called with None image_source.")
            return ""

        logger.debug(f"Attempting OCR for region {bounding_box} in image source type: {type(image_source)}")
        try:
            if isinstance(image_source, str):
                # Load image from path using Pillow
                img = Image.open(image_source)
            elif isinstance(image_source, np.ndarray):
                # Convert NumPy array (assumed BGR from OpenCV) to RGB Pillow Image
                img = Image.fromarray(cv2.cvtColor(image_source, cv2.COLOR_BGR2RGB))
            else:
                logger.error(f"Unsupported image_source type for OCR: {type(image_source)}. Must be str (path) or numpy.ndarray.")
                # Raising ComponentError here is more informative than returning empty string directly for bad type.
                raise ComponentError(component_name="VisionManager", message=f"Unsupported image_source type: {type(image_source)}")

            # Crop the image to the specified bounding box
            cropped_img = img.crop(bounding_box)
            logger.debug(f"Image cropped to bounding box: {bounding_box}")

            # Use pytesseract to extract text
            # Specify language if needed, e.g., lang='eng'
            extracted_text = pytesseract.image_to_string(cropped_img)
            logger.info(f"OCR extracted text (raw): '{extracted_text[:100]}...'") # Log a snippet
            return extracted_text.strip()

        except pytesseract.TesseractNotFoundError:
            logger.error(
                "Tesseract is not installed or not found in your PATH. "
                "OCR functionality will not be available. Please install Tesseract."
            )
            return "" # Return empty string as a graceful fallback
        except FileNotFoundError as e: # If image_source is a path and not found
            logger.error(f"Image file not found for OCR: {image_source}", exc_info=True)
            raise ComponentError("VisionManager", f"Image file not found: {image_source}")
        except Exception as e:
            logger.error(f"Error during OCR text extraction: {e}", exc_info=True)
            # Depending on strictness, could raise ComponentError or return ""
            # raise ComponentError("VisionManager", f"An unexpected error occurred during OCR: {str(e)}")
            return "" # Graceful fallback

# The if __name__ == '__main__': block was removed as part of test formalization.
# Formal tests for this class are in tests/components/vision/test_vision_manager.py

**Recap of `YoloDetector` (from previous turn):**
-   `__init__(self, model_path: str)`: Loads YOLO model, raises `ModelError` on failure.
-   `detect_objects(self, image_source: Union[str, np.ndarray]) -> List[Dict]`: Performs detection, processes results.
-   Includes an `if __name__ == '__main__':` block for basic testing.

**`VisionManager` Implementation (current turn):**
-   `__init__(self, config: ConfigurationManager)`:
    -   Gets `yolo_model_path` from config.
    -   Instantiates `YoloDetector` if path is found.
    -   Logs warnings/errors and sets `self.yolo_detector = None` if issues occur.
-   `detect_elements_on_page(self, image_source: Union[str, np.ndarray]) -> List[Dict]`:
    -   Uses `self.yolo_detector` if available.
    -   Returns empty list or raises `ComponentError` if detector is unavailable (currently returns empty list).
    -   Handles `ModelError` from detector and re-raises as `ComponentError`.
-   Includes an `if __name__ == '__main__':` block for basic testing, dependent on `development.yaml` and model availability.

Now, I will proceed with Step 3: Update Configuration (`config/development.yaml` and `config/production.yaml`).
I will add the `vision` section under `components`.
First, `ai_scraper_framework/config/development.yaml`.
