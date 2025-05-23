import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image as PillowImage # To avoid conflict with any 'Image' in VisionManager if used loosely

# Modules to be tested or mocked
from ai_scraper_framework.components.vision.vision_manager import VisionManager
from ai_scraper_framework.components.vision.yolo_detector import YoloDetector # For mocking
from ai_scraper_framework.core.exceptions import ComponentError, ModelError
# Mock ConfigurationManager for testing VisionManager's config handling
from ai_scraper_framework.core.config import ConfigurationManager # For type hint if needed in future

# Mock the logger used in VisionManager to prevent console output during tests
@pytest.fixture(autouse=True)
def mock_vision_manager_logger():
    with patch('ai_scraper_framework.components.vision.vision_manager.logger', MagicMock()) as mock_log:
        yield mock_log

class MockConfigurationManager:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else {}

    def get(self, key, default=None):
        try:
            value = self.settings
            for k_part in key.split('.'):
                value = value[k_part]
            return value
        except KeyError:
            return default
        except TypeError:
            return default

# --- Tests for VisionManager Initialization ---

@patch('ai_scraper_framework.components.vision.vision_manager.YoloDetector')
def test_vision_manager_initialization_success(mock_yolo_detector_constructor):
    """Test VisionManager initializes YoloDetector successfully when model path is provided."""
    mock_yolo_instance = MagicMock(spec=YoloDetector)
    mock_yolo_detector_constructor.return_value = mock_yolo_instance
    
    config_settings = {"components": {"vision": {"yolo_model_path": "fake/model.pt"}}}
    mock_config = MockConfigurationManager(settings=config_settings)
    
    manager = VisionManager(config=mock_config)
    
    mock_yolo_detector_constructor.assert_called_once_with(model_path="fake/model.pt")
    assert manager.yolo_detector is mock_yolo_instance

@patch('ai_scraper_framework.components.vision.vision_manager.YoloDetector')
def test_vision_manager_initialization_yolo_failure(mock_yolo_detector_constructor):
    """Test VisionManager handles YoloDetector's ModelError during initialization."""
    mock_yolo_detector_constructor.side_effect = ModelError(model_name="fake/model.pt", message="Load failed")
    
    config_settings = {"components": {"vision": {"yolo_model_path": "fake/model.pt"}}}
    mock_config = MockConfigurationManager(settings=config_settings)
    
    manager = VisionManager(config=mock_config) # Should not raise, but log error and set detector to None
    
    assert manager.yolo_detector is None
    # Check logger.error was called (via the autoused mock_vision_manager_logger)
    from ai_scraper_framework.components.vision.vision_manager import logger as vision_logger
    vision_logger.error.assert_called_once()
    assert "ModelError initializing YoloDetector" in vision_logger.error.call_args[0][0]


def test_vision_manager_initialization_no_model_path_in_config():
    """Test VisionManager initializes with no YoloDetector if model path is not in config."""
    mock_config = MockConfigurationManager(settings={"components": {"vision": {}}}) # No yolo_model_path
    manager = VisionManager(config=mock_config)
    assert manager.yolo_detector is None
    # Check logger.warning was called
    from ai_scraper_framework.components.vision.vision_manager import logger as vision_logger
    vision_logger.warning.assert_called_with(
        "YOLO model path not found in configuration (components.vision.yolo_model_path). "
        "VisionManager will operate without detection capabilities."
    )

# --- Tests for detect_elements_on_page ---

def test_detect_elements_on_page_with_detector(monkeypatch):
    """Test detect_elements_on_page delegates to YoloDetector and returns its results."""
    mock_config = MockConfigurationManager(settings={"components": {"vision": {"yolo_model_path": "dummy.pt"}}})
    
    # Mock YoloDetector instance and its detect_objects method
    mock_yolo_detector_instance = MagicMock(spec=YoloDetector)
    expected_detections = [{"box": [1,2,3,4], "label": "test", "confidence": 0.9}]
    mock_yolo_detector_instance.detect_objects.return_value = expected_detections
    
    # Patch the YoloDetector constructor within VisionManager's scope
    monkeypatch.setattr("ai_scraper_framework.components.vision.vision_manager.YoloDetector", MagicMock(return_value=mock_yolo_detector_instance))
    
    manager = VisionManager(config=mock_config)
    assert manager.yolo_detector is mock_yolo_detector_instance # Ensure detector was set
    
    results = manager.detect_elements_on_page(image_source="fake_image.png")
    
    mock_yolo_detector_instance.detect_objects.assert_called_once_with("fake_image.png")
    assert results == expected_detections


def test_detect_elements_on_page_no_detector():
    """Test detect_elements_on_page returns empty list if YoloDetector is None."""
    mock_config = MockConfigurationManager(settings={"components": {"vision": {}}}) # No model path
    manager = VisionManager(config=mock_config)
    assert manager.yolo_detector is None
    
    results = manager.detect_elements_on_page(image_source="fake_image.png")
    assert results == []
    # Check logger.warning was called
    from ai_scraper_framework.components.vision.vision_manager import logger as vision_logger
    vision_logger.warning.assert_called_with(
        "YoloDetector not available in VisionManager. Cannot detect elements. Returning empty list."
    )

# --- Tests for extract_text_from_image_region ---

@patch('ai_scraper_framework.components.vision.vision_manager.pytesseract')
@patch('ai_scraper_framework.components.vision.vision_manager.Image')
@patch('ai_scraper_framework.components.vision.vision_manager.cv2') # For BGR to RGB conversion
def test_extract_text_from_image_region_success(mock_cv2, mock_pil_image_module, mock_pytesseract):
    """Test successful text extraction from an image region."""
    mock_config = MockConfigurationManager()
    manager = VisionManager(config=mock_config)

    # Mock Pillow Image object and its methods
    mock_img_instance = MagicMock(spec=PillowImage.Image)
    mock_cropped_img_instance = MagicMock(spec=PillowImage.Image)
    mock_pil_image_module.open.return_value = mock_img_instance
    mock_img_instance.crop.return_value = mock_cropped_img_instance
    
    mock_pytesseract.image_to_string.return_value = " Extracted Text \n"
    
    bounding_box = (10, 20, 100, 50)
    extracted_text = manager.extract_text_from_image_region("fake_path.png", bounding_box)
    
    mock_pil_image_module.open.assert_called_once_with("fake_path.png")
    mock_img_instance.crop.assert_called_once_with(bounding_box)
    mock_pytesseract.image_to_string.assert_called_once_with(mock_cropped_img_instance)
    assert extracted_text == "Extracted Text"

@patch('ai_scraper_framework.components.vision.vision_manager.pytesseract')
@patch('ai_scraper_framework.components.vision.vision_manager.Image')
def test_extract_text_from_image_region_tesseract_not_found(mock_pil_image_module, mock_pytesseract):
    """Test text extraction returns empty string if TesseractNotFoundError is raised."""
    mock_config = MockConfigurationManager()
    manager = VisionManager(config=mock_config)

    mock_pil_image_module.open.return_value = MagicMock(spec=PillowImage.Image)
    mock_pytesseract.image_to_string.side_effect = pytesseract.TesseractNotFoundError
    
    extracted_text = manager.extract_text_from_image_region("fake_path.png", (0,0,1,1))
    
    assert extracted_text == ""
    # Check logger.error was called
    from ai_scraper_framework.components.vision.vision_manager import logger as vision_logger
    vision_logger.error.assert_called_once()
    assert "Tesseract is not installed or not found" in vision_logger.error.call_args[0][0]

@patch('ai_scraper_framework.components.vision.vision_manager.Image')
def test_extract_text_from_image_region_file_not_found(mock_pil_image_module):
    """Test text extraction raises ComponentError if image file is not found."""
    mock_config = MockConfigurationManager()
    manager = VisionManager(config=mock_config)
    
    mock_pil_image_module.open.side_effect = FileNotFoundError("Image not found at path")
    
    with pytest.raises(ComponentError) as excinfo:
        manager.extract_text_from_image_region("non_existent.png", (0,0,1,1))
    
    assert "Image file not found: non_existent.png" in str(excinfo.value)


@patch('ai_scraper_framework.components.vision.vision_manager.cv2')
@patch('ai_scraper_framework.components.vision.vision_manager.Image')
@patch('ai_scraper_framework.components.vision.vision_manager.pytesseract')
def test_extract_text_from_image_region_numpy_input(mock_pytesseract, mock_pil_image_module, mock_cv2):
    """Test text extraction with a NumPy array as image source."""
    mock_config = MockConfigurationManager()
    manager = VisionManager(config=mock_config)

    dummy_np_array = np.zeros((100, 100, 3), dtype=np.uint8) # BGR
    mock_rgb_array = np.zeros((100, 100, 3), dtype=np.uint8) # RGB (mocked conversion)
    mock_cv2.cvtColor.return_value = mock_rgb_array
    
    mock_img_instance = MagicMock(spec=PillowImage.Image)
    mock_cropped_img_instance = MagicMock(spec=PillowImage.Image)
    mock_pil_image_module.fromarray.return_value = mock_img_instance
    mock_img_instance.crop.return_value = mock_cropped_img_instance
    
    mock_pytesseract.image_to_string.return_value = "NumPy Text"

    bounding_box = (5, 5, 50, 50)
    extracted_text = manager.extract_text_from_image_region(dummy_np_array, bounding_box)

    mock_cv2.cvtColor.assert_called_once_with(dummy_np_array, cv2.COLOR_BGR2RGB)
    mock_pil_image_module.fromarray.assert_called_once_with(mock_rgb_array)
    mock_img_instance.crop.assert_called_once_with(bounding_box)
    mock_pytesseract.image_to_string.assert_called_once_with(mock_cropped_img_instance)
    assert extracted_text == "NumPy Text"

# Note: The `if __name__ == '__main__':` block from vision_manager.py should be removed.
# These tests cover the main logic paths. Integration tests requiring actual models/Tesseract
# would be separate or marked appropriately.
# The `pytesseract.TesseractNotFoundError` is a specific exception from the pytesseract library.
# `from PIL import Image as PillowImage` is used to avoid potential name clashes if `Image` is used elsewhere.
# `cv2` is mocked for the BGR to RGB conversion step when a NumPy array is input.
# The `autouse=True` fixture for mocking the logger applies to all tests in this file.I have already completed Step 1 (YoloDetector tests) and created `ai_scraper_framework/tests/components/vision/test_vision_manager.py` with the specified tests in the previous turns.

**Recap of Step 1 (YoloDetector Tests - Completed):**
-   Created `ai_scraper_framework/tests/components/vision/test_yolo_detector.py`.
-   Implemented tests for initialization and `detect_objects` method with extensive mocking.
-   Removed `if __name__ == '__main__':` from `yolo_detector.py`.

**Recap of Step 2 (VisionManager Tests - file created in previous turn):**
-   Created `ai_scraper_framework/tests/components/vision/test_vision_manager.py`.
-   Implemented tests for:
    -   `VisionManager` initialization (success, YoloDetector init failure, no model path in config).
    -   `detect_elements_on_page` (with and without detector).
    -   `extract_text_from_image_region` (success, Tesseract not found, file not found for path input, NumPy array input).
-   Used `@patch` for mocking dependencies like `YoloDetector`, `pytesseract`, `PIL.Image`, `cv2`.
-   Used a mock `ConfigurationManager`.
-   Used `@pytest.fixture(autouse=True)` to mock the logger within `vision_manager.py`.

Now, I will remove the `if __name__ == '__main__':` block from `ai_scraper_framework/components/vision/vision_manager.py`.
