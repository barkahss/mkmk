import spacy
# from spacy.cli.download import download as spacy_download # No longer needed after __main__ removal
from typing import List, Tuple

from ai_scraper_framework.core.exceptions import ModelError
from ai_scraper_framework.core.logger import get_logger

logger = get_logger(__name__)

class NlpProcessor:
    """
    Processes text using a spaCy NLP model for tasks like cleaning
    and named entity recognition (NER).
    """
    def __init__(self, model_name: str):
        """
        Initializes the NlpProcessor by loading a spaCy model.

        Args:
            model_name (str): The name of the spaCy model to load (e.g., "en_core_web_sm").

        Raises:
            ModelError: If the spaCy model fails to load (e.g., not downloaded or invalid name).
        """
        self.model_name = model_name
        try:
            self.nlp = spacy.load(self.model_name)
            logger.info(f"spaCy model '{self.model_name}' loaded successfully.")
        except OSError as e:
            # This error often occurs if the model is not downloaded.
            logger.error(
                f"Failed to load spaCy model '{self.model_name}'. "
                f"Ensure the model is downloaded (e.g., 'python -m spacy download {self.model_name}'). "
                f"Error: {e}",
                exc_info=True
            )
            raise ModelError(
                model_name=self.model_name,
                message=f"Failed to load spaCy model '{self.model_name}'. It might not be downloaded. Original error: {e}"
            )
        except Exception as e: # Catch any other unexpected errors during model loading
            logger.error(f"An unexpected error occurred while loading spaCy model '{self.model_name}': {e}", exc_info=True)
            raise ModelError(model_name=self.model_name, message=f"Unexpected error loading spaCy model: {e}")

    def clean_text(self, text: str) -> str:
        """
        Performs basic text cleaning.

        Currently, this involves:
        - Replacing multiple whitespace characters (including newlines, tabs) with a single space.
        - Stripping leading/trailing whitespace.

        Args:
            text (str): The input text to clean.

        Returns:
            str: The cleaned text.
        """
        if not text:
            return ""
        
        # Replace multiple whitespace characters (including newlines, tabs) with a single space
        cleaned_text = " ".join(text.split())
        
        # Strip leading/trailing whitespace that might remain or be introduced
        return cleaned_text.strip()

    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extracts named entities from the given text using the loaded spaCy model.

        Args:
            text (str): The text to process for named entity recognition.

        Returns:
            List[Tuple[str, str]]: A list of tuples, where each tuple contains
                                    the entity text and its label (e.g., ("Apple", "ORG")).
                                    Returns an empty list if no entities are found or text is empty.
        """
        if not text or not self.nlp: # Ensure text is not empty and NLP model is loaded
            return []

        doc = self.nlp(text)
        entities = [(entity.text, entity.label_) for entity in doc.ents]
        
        if entities:
            logger.debug(f"Extracted entities: {entities} from text snippet: '{text[:100]}...'")
        else:
            logger.debug(f"No entities found in text snippet: '{text[:100]}...'")
            
        return entities

# The if __name__ == '__main__': block has been migrated to
# tests/components/extractor/test_nlp_processor.py
