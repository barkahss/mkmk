import pytest
from unittest.mock import MagicMock, patch

# Module to be tested
from ai_scraper_framework.components.extractor.nlp_processor import NlpProcessor
from ai_scraper_framework.core.exceptions import ModelError

# Mock the logger used in NlpProcessor to prevent console output during tests
@pytest.fixture(autouse=True)
def mock_nlp_processor_logger():
    with patch('ai_scraper_framework.components.extractor.nlp_processor.logger', MagicMock()) as mock_log:
        yield mock_log

@patch('spacy.load') # Mock spacy.load
def test_nlp_processor_initialization_success(mock_spacy_load):
    """Test NlpProcessor initializes successfully when spaCy model loads."""
    mock_nlp_instance = MagicMock() # This is the mock for the loaded spaCy model
    mock_spacy_load.return_value = mock_nlp_instance
    model_name = "en_core_web_sm"
    
    processor = NlpProcessor(model_name=model_name)
    
    mock_spacy_load.assert_called_once_with(model_name)
    assert processor.nlp is mock_nlp_instance
    assert processor.model_name == model_name
    # from ai_scraper_framework.components.extractor.nlp_processor import logger as nlp_logger
    # nlp_logger.info.assert_called_with(f"spaCy model '{model_name}' loaded successfully.")

@patch('spacy.load')
def test_nlp_processor_initialization_failure_os_error(mock_spacy_load):
    """Test NlpProcessor raises ModelError when spaCy model fails to load with OSError."""
    mock_spacy_load.side_effect = OSError("Test spaCy load OSError (e.g., model not found)")
    model_name = "non_existent_model"
    
    with pytest.raises(ModelError) as excinfo:
        NlpProcessor(model_name=model_name)
    
    assert model_name in str(excinfo.value)
    assert "Failed to load spaCy model" in str(excinfo.value)
    assert "model not found" in str(excinfo.value) # Check original error is part of message

@patch('spacy.load')
def test_nlp_processor_initialization_failure_other_exception(mock_spacy_load):
    """Test NlpProcessor raises ModelError for other exceptions during spaCy model load."""
    mock_spacy_load.side_effect = Exception("Some other spaCy error")
    model_name = "another_model"

    with pytest.raises(ModelError) as excinfo:
        NlpProcessor(model_name=model_name)

    assert model_name in str(excinfo.value)
    assert "Unexpected error loading spaCy model" in str(excinfo.value)
    assert "Some other spaCy error" in str(excinfo.value)


def test_clean_text():
    """Test text cleaning functionality."""
    # Assuming NlpProcessor can be instantiated without a model for this test,
    # or we mock the model loading if clean_text doesn't depend on self.nlp.
    # NlpProcessor's clean_text does not use self.nlp, so direct instantiation is fine.
    
    # Create a dummy NlpProcessor; model loading won't happen if spacy.load is not called.
    # To make this a true unit test of clean_text, we can bypass __init__'s model loading.
    with patch.object(NlpProcessor, '__init__', lambda x, y: None) as mock_init:
        processor = NlpProcessor(model_name="dummy_model_for_clean_text_test")
        processor.model_name = "dummy_model_for_clean_text_test" # Set manually if needed

    assert processor.clean_text("  Hello\nWorld  \t Test  ") == "Hello World Test"
    assert processor.clean_text("Multiple   spaces") == "Multiple spaces"
    assert processor.clean_text("\n\t Leading and trailing\n\t ") == "Leading and trailing"
    assert processor.clean_text("") == ""
    assert processor.clean_text("   ") == ""
    assert processor.clean_text("AlreadyClean") == "AlreadyClean"


@patch('spacy.load')
def test_extract_entities_no_entities(mock_spacy_load):
    """Test entity extraction returns empty list when no entities are found."""
    mock_nlp_model = MagicMock()
    mock_doc = MagicMock()
    mock_doc.ents = [] # Simulate no entities
    mock_nlp_model.return_value = mock_doc # nlp(text) returns this doc
    mock_spacy_load.return_value = mock_nlp_model
    
    processor = NlpProcessor(model_name="en_core_web_sm")
    entities = processor.extract_entities("Some simple text with no entities.")
    
    assert entities == []
    mock_nlp_model.assert_called_once_with("Some simple text with no entities.")

@patch('spacy.load')
def test_extract_entities_with_entities(mock_spacy_load):
    """Test entity extraction correctly parses and returns entities."""
    mock_nlp_model = MagicMock()
    mock_doc = MagicMock()
    
    # Mock entity objects
    mock_ent1 = MagicMock()
    mock_ent1.text = "Apple"
    mock_ent1.label_ = "ORG"
    
    mock_ent2 = MagicMock()
    mock_ent2.text = "London"
    mock_ent2.label_ = "GPE"
    
    mock_doc.ents = [mock_ent1, mock_ent2] # Simulate found entities
    mock_nlp_model.return_value = mock_doc
    mock_spacy_load.return_value = mock_nlp_model
    
    processor = NlpProcessor(model_name="en_core_web_sm")
    sample_text = "Apple is looking at buying a startup in London."
    entities = processor.extract_entities(sample_text)
    
    assert len(entities) == 2
    assert ("Apple", "ORG") in entities
    assert ("London", "GPE") in entities
    mock_nlp_model.assert_called_once_with(sample_text)

@patch('spacy.load')
def test_extract_entities_empty_text(mock_spacy_load):
    """Test entity extraction returns empty list for empty input text."""
    # Model loading needs to be mocked even if not directly used by this path,
    # due to __init__ trying to load it.
    mock_spacy_load.return_value = MagicMock() 
    processor = NlpProcessor(model_name="en_core_web_sm")
    
    entities = processor.extract_entities("")
    assert entities == []

# Note: The `if __name__ == '__main__':` block from nlp_processor.py should be removed.
# These tests mock out the spaCy library's behavior to focus on NlpProcessor's logic.
# Integration tests would require actual spaCy models to be downloaded and loaded.
# The clean_text test bypasses __init__ to be a pure unit test of that method.
# `tests/components/extractor/__init__.py` should be an empty file.I have already completed Step 1 (YoloDetector tests) and Step 2 (VisionManager tests).

**Recap of Step 1 (YoloDetector Tests - Completed):**
-   Created `ai_scraper_framework/tests/components/vision/test_yolo_detector.py`.
-   Implemented tests for initialization and `detect_objects` method with extensive mocking.
-   Removed `if __name__ == '__main__':` from `yolo_detector.py`.

**Recap of Step 2 (VisionManager Tests - Completed):**
-   Created `ai_scraper_framework/tests/components/vision/test_vision_manager.py`.
-   Implemented tests for initialization, `detect_elements_on_page`, and `extract_text_from_image_region` with extensive mocking.
-   Removed `if __name__ == '__main__':` from `vision_manager.py`.
-   Ensured `tests/components/vision/__init__.py` exists.

Now I will proceed with Step 3: Tests for `NlpProcessor` (`tests/components/extractor/test_nlp_processor.py`).
I have already created `ai_scraper_framework/tests/components/extractor/test_nlp_processor.py` with the specified tests in the previous turn.

**Recap of `test_nlp_processor.py` (created in previous turn):**
-   Includes tests for successful and failed initialization of `NlpProcessor` (mocking `spacy.load`).
-   Tests `clean_text` method for various inputs.
-   Tests `extract_entities` for scenarios with no entities, with entities (mocking spaCy `doc.ents`), and empty input text.
-   Uses `@patch` from `unittest.mock` for mocking.
-   Uses `@pytest.fixture(autouse=True)` to mock the logger within `nlp_processor.py`.

Now, I will remove the `if __name__ == '__main__':` block from `ai_scraper_framework/components/extractor/nlp_processor.py`.
