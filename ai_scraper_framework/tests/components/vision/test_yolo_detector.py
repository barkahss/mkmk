import pytest
from unittest.mock import MagicMock, patch
import numpy as np

# Module to be tested
from ai_scraper_framework.components.vision.yolo_detector import YoloDetector
from ai_scraper_framework.core.exceptions import ModelError

# Mock the logger used in YoloDetector to prevent console output during tests
@pytest.fixture(autouse=True)
def mock_yolo_detector_logger():
    with patch('ai_scraper_framework.components.vision.yolo_detector.logger', MagicMock()) as mock_log:
        yield mock_log

@patch('ultralytics.YOLO') # Mock the YOLO class from ultralytics
def test_yolo_detector_initialization_success(mock_yolo_constructor):
    """Test YoloDetector initializes successfully when YOLO model loads."""
    mock_model_instance = MagicMock()
    mock_yolo_constructor.return_value = mock_model_instance
    model_path = "dummy/path/to/model.pt"
    
    detector = YoloDetector(model_path=model_path)
    
    mock_yolo_constructor.assert_called_once_with(model_path)
    assert detector.model is mock_model_instance
    assert detector.model_path == model_path
    # Check if logger.info was called (optional, depends on desired strictness)
    # from ai_scraper_framework.components.vision.yolo_detector import logger as yolo_logger
    # yolo_logger.info.assert_called_with(f"YOLO model loaded successfully from: {model_path}")


@patch('ultralytics.YOLO')
def test_yolo_detector_initialization_failure(mock_yolo_constructor):
    """Test YoloDetector raises ModelError when YOLO model fails to load."""
    mock_yolo_constructor.side_effect = Exception("Test YOLO load error")
    model_path = "dummy/path/to/invalid_model.pt"
    
    with pytest.raises(ModelError) as excinfo:
        YoloDetector(model_path=model_path)
    
    assert model_path in str(excinfo.value)
    assert "Failed to load YOLO model" in str(excinfo.value)
    assert "Test YOLO load error" in str(excinfo.value)


@patch('ultralytics.YOLO')
def test_detect_objects_empty_results(mock_yolo_constructor):
    """Test detect_objects returns an empty list when YOLO model yields no results."""
    mock_model_instance = MagicMock()
    # Simulate model call returning an empty list or a list with empty results object
    mock_model_instance.return_value = [] # Or [MagicMock(boxes=None)] 
    mock_yolo_constructor.return_value = mock_model_instance
    
    detector = YoloDetector(model_path="dummy.pt")
    
    # Test with a dummy image path (doesn't need to exist as model call is mocked)
    results = detector.detect_objects(image_source="dummy_image.png")
    
    assert results == []
    mock_model_instance.assert_called_once_with("dummy_image.png", verbose=False)

@patch('ultralytics.YOLO')
def test_detect_objects_with_results(mock_yolo_constructor):
    """Test detect_objects correctly parses and returns structured data from YOLO results."""
    mock_model_instance = MagicMock()
    
    # Mocking the structure of YOLO results
    # Create a mock for the box_data object and its attributes
    mock_box1 = MagicMock()
    mock_box1.xyxy = [MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])] # Simulate tensor-like behavior
    mock_box1.conf = [MagicMock(tolist=lambda: [0.95])] # Simulate tensor-like behavior for confidence
    mock_box1.cls = [MagicMock(tolist=lambda: [0])]     # Simulate tensor-like behavior for class ID

    mock_box2 = MagicMock()
    mock_box2.xyxy = [MagicMock(tolist=lambda: [50.0, 60.0, 70.0, 80.0])]
    mock_box2.conf = [MagicMock(tolist=lambda: [0.88])]
    mock_box2.cls = [MagicMock(tolist=lambda: [1])]

    # Mock the results object that the model call would return
    mock_yolo_result = MagicMock()
    mock_yolo_result.boxes = [mock_box1, mock_box2] # List of box_data objects
    mock_yolo_result.names = {0: "cat", 1: "dog"} # Class ID to name mapping
    
    mock_model_instance.return_value = [mock_yolo_result] # Model call returns a list of these results
    mock_yolo_constructor.return_value = mock_model_instance
    
    detector = YoloDetector(model_path="dummy.pt")
    
    dummy_image = np.zeros((100, 100, 3), dtype=np.uint8) # Dummy NumPy image
    results = detector.detect_objects(image_source=dummy_image)
    
    assert len(results) == 2
    
    # Check first object
    assert results[0]['box'] == [10, 20, 30, 40]
    assert results[0]['label'] == "cat"
    assert results[0]['confidence'] == pytest.approx(0.95)
    
    # Check second object
    assert results[1]['box'] == [50, 60, 70, 80]
    assert results[1]['label'] == "dog"
    assert results[1]['confidence'] == pytest.approx(0.88)

    mock_model_instance.assert_called_once_with(dummy_image, verbose=False)

@patch('ultralytics.YOLO')
def test_detect_objects_none_image_source(mock_yolo_constructor):
    """Test detect_objects returns an empty list if image_source is None."""
    detector = YoloDetector(model_path="dummy.pt") # Assuming successful init
    results = detector.detect_objects(image_source=None)
    assert results == []

@patch('ultralytics.YOLO')
def test_detect_objects_prediction_error(mock_yolo_constructor):
    """Test detect_objects returns empty list if model prediction raises an error."""
    mock_model_instance = MagicMock()
    mock_model_instance.side_effect = Exception("Prediction failed")
    mock_yolo_constructor.return_value = mock_model_instance

    detector = YoloDetector(model_path="dummy.pt")
    results = detector.detect_objects(image_source="dummy_image.png")
    assert results == []
    # Check if logger.error was called (optional)
    # from ai_scraper_framework.components.vision.yolo_detector import logger as yolo_logger
    # yolo_logger.error.assert_called_with("Error during YOLO model prediction: Prediction failed", exc_info=True)

@patch('ultralytics.YOLO')
def test_detect_objects_malformed_box_data(mock_yolo_constructor):
    """Test that malformed box_data entries are skipped."""
    mock_model_instance = MagicMock()
    
    # Correctly formed box
    mock_box1 = MagicMock()
    mock_box1.xyxy = [MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])]
    mock_box1.conf = [MagicMock(tolist=lambda: [0.95])]
    mock_box1.cls = [MagicMock(tolist=lambda: [0])]

    # Malformed box (e.g., xyxy list is empty or not as expected)
    mock_box_malformed = MagicMock()
    mock_box_malformed.xyxy = [MagicMock(tolist=lambda: [])] # Empty list for coordinates
    mock_box_malformed.conf = [MagicMock(tolist=lambda: [0.80])] 
    mock_box_malformed.cls = [MagicMock(tolist=lambda: [1])]

    mock_yolo_result = MagicMock()
    mock_yolo_result.boxes = [mock_box1, mock_box_malformed]
    mock_yolo_result.names = {0: "cat", 1: "dog"}
    
    mock_model_instance.return_value = [mock_yolo_result]
    mock_yolo_constructor.return_value = mock_model_instance
    
    detector = YoloDetector(model_path="dummy.pt")
    results = detector.detect_objects(image_source=np.zeros((100,100,3)))
    
    assert len(results) == 1 # Only the valid box should be processed
    assert results[0]['label'] == "cat"
    # Check if logger.warning was called (optional)
    # from ai_scraper_framework.components.vision.yolo_detector import logger as yolo_logger
    # yolo_logger.warning.assert_any_call(f"Skipping malformed detection result: {mock_box_malformed}", exc_info=True)

# Note: The `if __name__ == '__main__':` block from yolo_detector.py should be removed
# as its functionality is now covered by these pytest tests (or would be with actual image tests).
# These tests primarily focus on the YoloDetector class logic, mocking out the actual YOLO model.
# For integration tests (requiring model files and actual images), a separate test file or
# pytest markers (`@pytest.mark.integration`) would be used.I have created `ai_scraper_framework/tests/components/vision/test_yolo_detector.py` with the specified tests in the previous turn.

**Recap of `test_yolo_detector.py`:**
-   Includes tests for successful and failed initialization of `YoloDetector` (mocking `ultralytics.YOLO`).
-   Tests `detect_objects` for scenarios with empty results, valid results (mocking the structure of YOLO's output), `None` image source, prediction errors, and malformed box data.
-   Uses `@patch` from `unittest.mock` for mocking.
-   Uses `@pytest.fixture(autouse=True)` to mock the logger within `yolo_detector.py` to suppress log output during tests.

Now, I will proceed to remove the `if __name__ == '__main__':` block from `ai_scraper_framework/components/vision/yolo_detector.py`.
