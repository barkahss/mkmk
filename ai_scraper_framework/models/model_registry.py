from typing import Optional, TYPE_CHECKING

from ai_scraper_framework.core.logger import get_logger

if TYPE_CHECKING: # To avoid circular import issues, only import for type hinting.
    from ai_scraper_framework.core.config import ConfigurationManager

logger = get_logger(__name__)

class ModelRegistry:
    """
    Manages access to configured model paths and names for various AI models
    used within the framework (e.g., CV, NLP).
    """
    def __init__(self, config: 'ConfigurationManager'):
        """
        Initializes the ModelRegistry.

        Args:
            config (ConfigurationManager): The application's configuration manager instance,
                                           used to fetch model path/name configurations.
        """
        self.config = config
        logger.info("ModelRegistry initialized.")

    def get_cv_model_path(self, model_name: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the configured path for a Computer Vision (CV) model.

        Currently, it primarily returns the path specified in
        `components.vision.yolo_model_path` from the configuration.
        The `model_name` parameter is for future expansion to support multiple CV models.

        Args:
            model_name (Optional[str]): The specific name of the CV model. (Currently unused,
                                        reserved for future enhancements).

        Returns:
            Optional[str]: The configured path to the CV model file.
                           Returns `None` if the path is not found in the configuration,
                           and logs a warning.
        """
        if model_name:
            # Future: Implement logic to fetch specific model path based on model_name.
            # e.g., key = f'components.vision.models.{model_name}.path'
            # For now, log that it's not used.
            logger.debug(f"get_cv_model_path called with model_name='{model_name}', but specific model lookup is not yet implemented. Using default CV model path.")
        
        cv_model_path_key = 'components.vision.yolo_model_path'
        model_path = self.config.get(cv_model_path_key)

        if model_path:
            logger.info(f"CV model path retrieved: '{model_path}' using key '{cv_model_path_key}'.")
            return model_path
        else:
            logger.warning(f"CV model path not found in configuration using key: '{cv_model_path_key}'.")
            return None

    def get_nlp_model_name_or_path(self, model_identifier: Optional[str] = None) -> Optional[str]:
        """
        Retrieves the configured name or path for an NLP (spaCy) model.

        Currently, it primarily returns the name/path specified in
        `components.extractor.spacy_model_name` from the configuration.
        The `model_identifier` parameter is for future expansion.

        Args:
            model_identifier (Optional[str]): The specific identifier of the NLP model.
                                              (Currently unused, reserved for future enhancements).

        Returns:
            Optional[str]: The configured spaCy model name or path.
                           Returns `None` if not found in the configuration,
                           and logs a warning.
        """
        if model_identifier:
            logger.debug(f"get_nlp_model_name_or_path called with model_identifier='{model_identifier}', but specific model lookup is not yet implemented. Using default NLP model identifier.")

        nlp_model_key = 'components.extractor.spacy_model_name'
        model_id = self.config.get(nlp_model_key)

        if model_id:
            logger.info(f"NLP model identifier retrieved: '{model_id}' using key '{nlp_model_key}'.")
            return model_id
        else:
            logger.warning(f"NLP model identifier not found in configuration using key: '{nlp_model_key}'.")
            return None

# The if __name__ == '__main__': block was for demonstration and testing.
# Formal tests for this class should be in 'tests/models/test_model_registry.py'.
