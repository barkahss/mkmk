import pytest
from unittest.mock import MagicMock, patch

# Modules to be tested or mocked
from ai_scraper_framework.components.extractor.extractor_manager import ExtractorManager
from ai_scraper_framework.components.extractor.nlp_processor import NlpProcessor # For mocking
from ai_scraper_framework.components.extractor.basic_parser import BasicParser # For mocking
from ai_scraper_framework.core.exceptions import ModelError, ComponentError
from ai_scraper_framework.core.config import ConfigurationManager # For type hint if needed

# Mock the logger used in ExtractorManager to prevent console output during tests
@pytest.fixture(autouse=True)
def mock_extractor_manager_logger():
    with patch('ai_scraper_framework.components.extractor.extractor_manager.logger', MagicMock()) as mock_log:
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
        except TypeError: # Handle cases where settings might not be a dict at some level
             return default

# --- Tests for ExtractorManager Initialization ---

@patch('ai_scraper_framework.components.extractor.extractor_manager.NlpProcessor')
def test_extractor_manager_initialization_with_nlp(mock_nlp_processor_constructor):
    """Test ExtractorManager initializes NlpProcessor successfully when model name is provided."""
    mock_nlp_instance = MagicMock(spec=NlpProcessor)
    mock_nlp_processor_constructor.return_value = mock_nlp_instance
    
    config_settings = {"components": {"extractor": {"spacy_model_name": "en_core_web_sm"}}}
    mock_config = MockConfigurationManager(settings=config_settings)
    
    manager = ExtractorManager(config=mock_config)
    
    mock_nlp_processor_constructor.assert_called_once_with(model_name="en_core_web_sm")
    assert manager.nlp_processor is mock_nlp_instance

@patch('ai_scraper_framework.components.extractor.extractor_manager.NlpProcessor')
def test_extractor_manager_initialization_nlp_failure(mock_nlp_processor_constructor):
    """Test ExtractorManager handles NlpProcessor's ModelError during initialization."""
    mock_nlp_processor_constructor.side_effect = ModelError(model_name="en_core_web_sm", message="Load failed")
    
    config_settings = {"components": {"extractor": {"spacy_model_name": "en_core_web_sm"}}}
    mock_config = MockConfigurationManager(settings=config_settings)
    
    manager = ExtractorManager(config=mock_config) # Should not raise, but log error and set nlp_processor to None
    
    assert manager.nlp_processor is None
    from ai_scraper_framework.components.extractor.extractor_manager import logger as em_logger
    em_logger.error.assert_called_once()
    assert "ModelError initializing NlpProcessor" in em_logger.error.call_args[0][0]

def test_extractor_manager_initialization_no_spacy_model_config():
    """Test ExtractorManager initializes with no NlpProcessor if spacy_model_name is not in config."""
    mock_config = MockConfigurationManager(settings={"components": {"extractor": {}}}) # No spacy_model_name
    manager = ExtractorManager(config=mock_config)
    assert manager.nlp_processor is None
    from ai_scraper_framework.components.extractor.extractor_manager import logger as em_logger
    em_logger.warning.assert_called_with(
        "spaCy model name not found in configuration (components.extractor.spacy_model_name). "
        "ExtractorManager will operate without NLP capabilities."
    )

# --- Tests for extract_product_details ---

@patch('ai_scraper_framework.components.extractor.extractor_manager.BasicParser')
@patch('ai_scraper_framework.components.extractor.extractor_manager.NlpProcessor')
def test_extract_product_details_with_nlp(mock_nlp_constructor, mock_basic_parser_constructor):
    """Test extract_product_details uses BasicParser and NlpProcessor correctly."""
    # Setup mocks
    mock_config = MockConfigurationManager(settings={"components": {"extractor": {"spacy_model_name": "en_core_web_sm"}}})
    
    mock_nlp_instance = MagicMock(spec=NlpProcessor)
    mock_nlp_instance.clean_text.side_effect = lambda text: text.strip() # Simple clean
    mock_nlp_instance.extract_entities.return_value = [("SampleCo", "ORG")]
    mock_nlp_constructor.return_value = mock_nlp_instance # When ExtractorManager inits NlpProcessor

    mock_parser_instance = MagicMock(spec=BasicParser)
    mock_parser_instance.get_title.return_value = "  Test Product Title  "
    # mock_parser_instance.get_all_text.return_value = "Main text with SampleCo." # If we had get_all_text
    mock_basic_parser_constructor.return_value = mock_parser_instance

    manager = ExtractorManager(config=mock_config)
    assert manager.nlp_processor is mock_nlp_instance # Ensure NLP is set up

    html_content = "<html><head><title>  Test Product Title  </title></head><body>Main text with SampleCo.</body></html>"
    ocr_texts = ["OCR text mentioning Acme Corp"]
    
    details = manager.extract_product_details(html_content, text_regions=ocr_texts)

    mock_basic_parser_constructor.assert_called_once_with(html_content=html_content)
    mock_parser_instance.get_title.assert_called_once()
    
    # NlpProcessor.clean_text is called for title and each OCR region
    assert mock_nlp_instance.clean_text.call_count == 2 
    mock_nlp_instance.clean_text.assert_any_call("  Test Product Title  ")
    mock_nlp_instance.clean_text.assert_any_call("OCR text mentioning Acme Corp")

    # NlpProcessor.extract_entities is called for main text (title proxy) and each OCR region
    assert mock_nlp_instance.extract_entities.call_count == 2
    # Current stub uses title as main_page_text_sample
    mock_nlp_instance.extract_entities.assert_any_call("Test Product Title") 
    mock_nlp_instance.extract_entities.assert_any_call("OCR text mentioning Acme Corp")

    assert details["raw_title"] == "  Test Product Title  "
    assert details["cleaned_title"] == "Test Product Title"
    assert ("SampleCo", "ORG") in details["main_text_entities"] # From title
    assert len(details["regional_text_entities"]) == 1
    assert ("SampleCo", "ORG") in details["regional_text_entities"][0] # From OCR text


@patch('ai_scraper_framework.components.extractor.extractor_manager.BasicParser')
def test_extract_product_details_no_nlp(mock_basic_parser_constructor):
    """Test extract_product_details performs basic parsing if NlpProcessor is None."""
    mock_config = MockConfigurationManager(settings={"components": {"extractor": {}}}) # No spacy_model_name
    
    mock_parser_instance = MagicMock(spec=BasicParser)
    mock_parser_instance.get_title.return_value = "  Raw Title Only  "
    mock_basic_parser_constructor.return_value = mock_parser_instance
    
    manager = ExtractorManager(config=mock_config)
    assert manager.nlp_processor is None # Ensure NLP is NOT set up

    html_content = "<html><title>  Raw Title Only  </title></html>"
    details = manager.extract_product_details(html_content)

    mock_basic_parser_constructor.assert_called_once_with(html_content=html_content)
    mock_parser_instance.get_title.assert_called_once()
    
    assert details["raw_title"] == "  Raw Title Only  "
    assert details["cleaned_title"] == "  Raw Title Only  " # No cleaning if no NLP
    assert details["main_text_entities"] == []
    assert details["regional_text_entities"] == []

def test_extract_product_details_empty_html():
    """Test extract_product_details handles empty HTML content."""
    mock_config = MockConfigurationManager() # Can be minimal, BasicParser init will fail first
    manager = ExtractorManager(config=mock_config)
    
    # BasicParser will raise ExtractorError if html_content is None or empty before init.
    # However, ExtractorManager's extract_product_details checks for empty html_content first.
    result = manager.extract_product_details("")
    assert "error" in result
    assert result["error"] == "HTML content is empty."

# Note: The `if __name__ == '__main__':` block from extractor_manager.py should be removed.
# These tests focus on ExtractorManager's orchestration logic, mocking its direct dependencies.
# More complex scenarios, like specific entity results, depend on the mocked return values.
# `tests/components/extractor/__init__.py` should be an empty file.I have already completed Step 1 (YoloDetector tests), Step 2 (VisionManager tests), and Step 3 (NlpProcessor tests). The `if __name__ == '__main__':` blocks were removed from their respective component files.

**Recap of Steps 1-3:**
-   **YoloDetector Tests:** Created `test_yolo_detector.py` with mock-based unit tests. Removed main block from `yolo_detector.py`.
-   **VisionManager Tests:** Created `test_vision_manager.py` with mock-based unit tests for initialization and methods. Removed main block from `vision_manager.py`.
-   **NlpProcessor Tests:** Created `test_nlp_processor.py` with mock-based unit tests for initialization and methods. Removed main block from `nlp_processor.py`.
-   Ensured `__init__.py` files exist in `tests/components/vision/` and `tests/components/extractor/`.

Now I will proceed with Step 4: Tests for `ExtractorManager` (`tests/components/extractor/test_extractor_manager.py`).
I have already created `ai_scraper_framework/tests/components/extractor/test_extractor_manager.py` with the specified tests in the previous turn.

**Recap of `test_extractor_manager.py` (created in previous turn):**
-   Includes tests for `ExtractorManager` initialization (with and without NlpProcessor, handling NlpProcessor init failure).
-   Tests `extract_product_details` method:
    -   With NLP processing (mocking `BasicParser` and `NlpProcessor`).
    -   Without NLP processing (when `nlp_processor` is `None`).
    -   With empty HTML content.
-   Uses `@patch` for mocking dependencies.
-   Uses a mock `ConfigurationManager`.
-   Uses `@pytest.fixture(autouse=True)` to mock the logger within `extractor_manager.py`.

Now, I will remove the `if __name__ == '__main__':` block from `ai_scraper_framework/components/extractor/extractor_manager.py`.
