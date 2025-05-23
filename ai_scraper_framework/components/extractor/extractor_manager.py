from typing import List, Dict, Optional, TYPE_CHECKING

from ai_scraper_framework.components.extractor.basic_parser import BasicParser
from ai_scraper_framework.components.extractor.nlp_processor import NlpProcessor
from ai_scraper_framework.core.exceptions import ComponentError, ModelError
from ai_scraper_framework.core.logger import get_logger

if TYPE_CHECKING:
    from ai_scraper_framework.core.config import ConfigurationManager

logger = get_logger(__name__)

class ExtractorManager:
    """
    Manages data extraction from HTML content by coordinating various parsing
    and NLP processing components.
    """
    def __init__(self, config: 'ConfigurationManager'):
        """
        Initializes the ExtractorManager.

        It sets up a BasicParser for initial HTML parsing and attempts to initialize
        an NlpProcessor based on the spaCy model specified in the configuration.
        If the spaCy model is not configured or fails to load, NLP capabilities
        will be limited.

        Args:
            config (ConfigurationManager): The application's configuration manager instance,
                                           used to fetch the spaCy model name.
        """
        self.config = config
        self.basic_parser: Optional[BasicParser] = None # Will be instantiated per use
        self.nlp_processor: Optional[NlpProcessor] = None

        spacy_model_name: Optional[str] = self.config.get('components.extractor.spacy_model_name')

        if spacy_model_name:
            logger.info(f"spaCy model name found in configuration: {spacy_model_name}")
            try:
                self.nlp_processor = NlpProcessor(model_name=spacy_model_name)
                logger.info("NlpProcessor initialized successfully in ExtractorManager.")
            except ModelError as e:
                logger.error(f"ModelError initializing NlpProcessor in ExtractorManager: {e.message}. NLP tasks will be disabled.")
                # NlpProcessor is already None by default if model loading fails
            except Exception as e:
                logger.error(f"Unexpected error initializing NlpProcessor: {e}. NLP tasks will be disabled.", exc_info=True)
        else:
            logger.warning("spaCy model name not found in configuration (components.extractor.spacy_model_name). ExtractorManager will operate without NLP capabilities.")
            
        # BasicParser does not require pre-initialization with config, it's instantiated with HTML content.
        # self.basic_parser = BasicParser() # Incorrect: BasicParser takes html_content in __init__

    def extract_product_details(self, html_content: str, text_regions: Optional[List[str]] = None) -> Dict:
        """
        Extracts product details from HTML content and optional text regions.

        This method uses BasicParser to get title and all text from HTML.
        If NlpProcessor is available, it cleans the title and extracts entities
        from the main text content and any provided text regions (e.g., from OCR).

        Args:
            html_content (str): The HTML content of the product page.
            text_regions (Optional[List[str]]): A list of additional text strings
                                                (e.g., extracted from specific image regions by OCR)
                                                to process for entities. Defaults to None.

        Returns:
            Dict: A dictionary containing extracted and processed data.
                  Example: {'raw_title': '...', 'cleaned_title': '...',
                            'main_text_entities': [...], 'regional_text_entities': [...]}
        """
        if not html_content:
            logger.warning("extract_product_details called with empty html_content.")
            return {"error": "HTML content is empty."}

        logger.info("Starting product detail extraction.")
        
        # Step 1: Basic HTML Parsing
        try:
            # Instantiate BasicParser with the HTML content for this specific extraction task
            self.basic_parser = BasicParser(html_content=html_content)
            raw_title = self.basic_parser.get_title() or ""
            # For main text, one strategy is to get all text and then process it.
            # More sophisticated strategies might select specific content blocks.
            # For now, let's assume get_links() could be a proxy for "all text" if we join link texts,
            # or better, add a get_all_text() method to BasicParser.
            # For this stub, let's just use the title as a proxy for "main text".
            main_page_text_sample = raw_title # Placeholder for more comprehensive text extraction
            
            logger.debug(f"Basic parsing: Raw title='{raw_title}'")
        except Exception as e:
            logger.error(f"Error during basic HTML parsing: {e}", exc_info=True)
            raise ComponentError("ExtractorManager", f"Basic HTML parsing failed: {e}")

        # Step 2: NLP Processing (if NlpProcessor is available)
        cleaned_title = raw_title # Default if no NLP
        main_text_entities: List[Tuple[str, str]] = []
        regional_text_entities: List[List[Tuple[str, str]]] = [] # List of entity lists for each region

        if self.nlp_processor:
            logger.debug("NlpProcessor available, performing NLP tasks.")
            cleaned_title = self.nlp_processor.clean_text(raw_title)
            logger.debug(f"Cleaned title: '{cleaned_title}'")
            
            if main_page_text_sample: # Process main text sample if available
                main_text_entities = self.nlp_processor.extract_entities(main_page_text_sample)
                logger.debug(f"Entities from main text sample: {main_text_entities}")

            if text_regions:
                logger.debug(f"Processing {len(text_regions)} additional text regions for entities.")
                for i, region_text in enumerate(text_regions):
                    cleaned_region_text = self.nlp_processor.clean_text(region_text)
                    entities_in_region = self.nlp_processor.extract_entities(cleaned_region_text)
                    regional_text_entities.append(entities_in_region)
                    logger.debug(f"Entities from text region {i}: {entities_in_region}")
        else:
            logger.warning("NlpProcessor not available. Skipping NLP tasks (title cleaning, entity extraction).")

        # Step 3: Compile results
        # This is a stub; more sophisticated logic would structure this data better.
        extracted_data = {
            "raw_title": raw_title,
            "cleaned_title": cleaned_title,
            "main_text_entities": main_text_entities,
            "regional_text_entities": regional_text_entities,
            # Placeholder for other details that might be extracted
            # "price": None, 
            # "description_summary": None,
        }
        
        logger.info("Product detail extraction completed.")
        return extracted_data

# The if __name__ == '__main__': block has been migrated to
# tests/components/extractor/test_extractor_manager.py
