import asyncio
import os
import shutil # For cleanup in test
import logging # Keep for __main__ block if needed, or remove if get_logger is sufficient
from typing import Optional # Added import for Optional
from ai_scraper_framework.core.logger import get_logger

from ai_scraper_framework.components.renderer.playwright_manager import PlaywrightManager
from ai_scraper_framework.components.extractor.basic_parser import BasicParser
from ai_scraper_framework.components.extractor.extractor_manager import ExtractorManager # Added
from ai_scraper_framework.components.vision.vision_manager import VisionManager # Added
from ai_scraper_framework.components.storage.file_storage import FileStorage, StorageError as FileStorageErrorSubclass
from ai_scraper_framework.core.exceptions import RendererError, ExtractorError, TaskManagementError, ComponentError
# Removed StorageError from core.exceptions as it's not directly used here, FileStorageErrorSubclass is.

# from ai_scraper_framework.core.config import get_config # Example of a self-note

logger = get_logger(__name__) # Module-level logger

class ScrapingManager:
    """
    Orchestrates the scraping process by coordinating various components
    like web page rendering, content parsing, and data storage.

    This manager is responsible for executing scraping tasks, handling the
    workflow between different components, and managing errors that may occur
    during the process.
    """
    def __init__(self, config: 'ConfigurationManager'):
        """
        Initializes the ScrapingManager and its underlying components.

        The manager relies on a `ConfigurationManager` instance to configure
        its components (PlaywrightManager, FileStorage).

        Args:
            config (ConfigurationManager): The application's configuration manager instance.
                                           This is used to initialize and configure
                                           the rendering and storage components.

        Raises:
            TaskManagementError: If initialization of critical components like
                                 PlaywrightManager or FileStorage fails. This indicates
                                 a setup or configuration issue preventing the manager
                                 from operating.
        """
        self.config = config
        logger.info("ScrapingManager initializing with provided configuration.")

        try:
            # Initialize the PlaywrightManager for browser interactions, configured via the central config.
            self.playwright_manager = PlaywrightManager(config=self.config)
            # PlaywrightManager's own __init__ logs its effective browser_type.
        except Exception as e:
            logger.error(f"Error initializing PlaywrightManager in ScrapingManager: {e}", exc_info=True)
            raise TaskManagementError(f"Failed to initialize PlaywrightManager: {e}")

        try:
            # Initialize the FileStorage for saving scraped data, configured via the central config.
            self.file_storage = FileStorage(config=self.config)
            # FileStorage's own __init__ logs its effective base_path.
        except FileStorageErrorSubclass as e: # Catching specific StorageError from FileStorage
            logger.error(f"Error initializing FileStorage in ScrapingManager: {e}", exc_info=True)
            raise TaskManagementError(f"Failed to initialize FileStorage: {e}")
        except Exception as e: # Catch any other unexpected errors during FileStorage initialization
            logger.error(f"Unexpected error initializing FileStorage in ScrapingManager: {e}", exc_info=True)
            raise TaskManagementError(f"Unexpected error initializing FileStorage: {e}")

        try:
            # Initialize VisionManager
            self.vision_manager = VisionManager(config=self.config)
            logger.info("VisionManager initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing VisionManager: {e}", exc_info=True)
            # Non-critical if VisionManager fails for basic scraping, but log it.
            # Depending on requirements, this could raise TaskManagementError.
            self.vision_manager = None 
            logger.warning("VisionManager initialization failed. OCR capabilities will be unavailable.")
        
        try:
            # Initialize ExtractorManager
            self.extractor_manager = ExtractorManager(config=self.config)
            logger.info("ExtractorManager initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing ExtractorManager: {e}", exc_info=True)
            self.extractor_manager = None
            logger.warning("ExtractorManager initialization failed. NLP capabilities might be limited.")


        logger.info("ScrapingManager initialized successfully.")


    async def scrape_single_url_basic(self, url: str, output_filename: Optional[str] = None, output_filename_prefix: Optional[str] = "scraped_item") -> str:
        """
        Performs a basic scraping workflow for a single URL.

        The workflow involves:
        1. Fetching the HTML content of the given URL using `PlaywrightManager`.
        2. Parsing the HTML to extract the page title and all hyperlinks using `BasicParser`.
        3. Saving the extracted data (URL, title, links) into a JSON file via `FileStorage`.

        Args:
            url (str): The URL of the webpage to scrape.
            output_filename (Optional[str]): The specific filename to save the output JSON.
                                             If None, a unique filename will be generated by
                                             `FileStorage` using the `output_filename_prefix`.
                                             Defaults to None.
            output_filename_prefix (Optional[str]): The prefix to use for the generated filename
                                                    if `output_filename` is not provided.
                                                    Defaults to "scraped_item".

        Returns:
            str: The absolute path to the saved JSON file containing the scraped data.

        Raises:
            TaskManagementError: If any stage of the scraping process (rendering, parsing, or storage)
                                 fails. The original error will be logged and included in the
                                 `TaskManagementError` message.
        """
        # Determine how the output file will be named for logging purposes.
        log_msg_output_part = f"output filename: {output_filename}" if output_filename else f"output filename prefix: {output_filename_prefix}"
        logger.info(f"Starting basic scraping for URL: {url}, {log_msg_output_part}")

        page_snapshot: Dict[str, Optional[str]] = {}
        html_content: Optional[str] = None
        screenshot_path: Optional[str] = None
        ocr_text: Optional[str] = None

        # Step 1: Fetch HTML content and take a screenshot using PlaywrightManager.
        try:
            async with self.playwright_manager as pm:
                # Define screenshot options. For now, save to PM's default temp dir.
                # Path can be omitted to let PM generate one.
                snapshot_options = {'full_page': True} 
                page_snapshot = await pm.get_page_snapshot(url, screenshot_options=snapshot_options)
            
            html_content = page_snapshot.get("html")
            screenshot_path = page_snapshot.get("screenshot_path")

            if not html_content: # Should not happen if get_page_snapshot succeeds without error
                 logger.error(f"Failed to retrieve HTML content for {url}, but no exception from PlaywrightManager.")
                 raise TaskManagementError(f"HTML content missing for {url} after snapshot.")

            logger.info(f"Successfully fetched snapshot for {url}. Screenshot at: {screenshot_path}")

        except RendererError as e:
            logger.error(f"RendererError while fetching snapshot for {url}: {e.message}", exc_info=True)
            raise TaskManagementError(f"Failed to render page snapshot for {url}: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error during page snapshot for {url}: {str(e)}", exc_info=True)
            raise TaskManagementError(f"Unexpected error during page snapshot for {url}: {str(e)}")

        # Step 2: OCR (if screenshot was taken and VisionManager is available)
        if screenshot_path and self.vision_manager:
            try:
                # For basic integration, OCR the whole image.
                # To get image dimensions for bounding_box=(0,0,width,height):
                from PIL import Image # Using Pillow to get image dimensions
                with Image.open(screenshot_path) as img:
                    width, height = img.size
                
                full_image_bbox = (0, 0, width, height)
                logger.debug(f"Performing OCR on full image: {screenshot_path} with dimensions {width}x{height}")
                ocr_text = self.vision_manager.extract_text_from_image_region(screenshot_path, full_image_bbox)
                logger.info(f"OCR extracted text (first 100 chars): '{ocr_text[:100]}...' from {screenshot_path}")
            except ImportError:
                logger.warning("Pillow not installed, cannot get image dimensions for full image OCR. Skipping OCR.")
            except ComponentError as e: # Catch errors from VisionManager
                logger.error(f"ComponentError during OCR processing for {screenshot_path}: {e.message}", exc_info=True)
                # Non-fatal for now, OCR text will remain None
            except Exception as e_ocr:
                logger.error(f"Unexpected error during OCR processing for {screenshot_path}: {e_ocr}", exc_info=True)
                # Non-fatal for now

        # Step 3: Parse HTML and process text with ExtractorManager
        extracted_details: Dict = {}
        if self.extractor_manager:
            try:
                # Pass HTML and any OCR'd text regions to ExtractorManager
                # For this basic integration, we pass the full OCR text as a single "region".
                ocr_text_regions = [ocr_text] if ocr_text else None
                extracted_details = self.extractor_manager.extract_product_details(
                    html_content=html_content, 
                    text_regions=ocr_text_regions
                )
                logger.info(f"ExtractorManager processed content for {url}.")
            except ComponentError as e: # Catch errors from ExtractorManager
                logger.error(f"ComponentError during extraction for {url}: {e.message}", exc_info=True)
                # Populate with basic info if extraction fails partially
                extracted_details = {"raw_title": "Extraction Failed", "cleaned_title": "Extraction Failed", "main_text_entities": [], "regional_text_entities": []}
            except Exception as e_extract:
                 logger.error(f"Unexpected error during extraction for {url}: {e_extract}", exc_info=True)
                 extracted_details = {"raw_title": "Extraction Error", "cleaned_title": "Extraction Error", "main_text_entities": [], "regional_text_entities": []}
        else: # Fallback if ExtractorManager is not available
            logger.warning("ExtractorManager not available. Performing basic parsing only.")
            try:
                parser = BasicParser(html_content=html_content) # Use BasicParser directly
                extracted_details["raw_title"] = parser.get_title() or ""
                extracted_details["cleaned_title"] = extracted_details["raw_title"] # No NLP cleaning
                # BasicParser doesn't provide main_text_entities or regional_text_entities
            except Exception as e_basic_parse:
                logger.error(f"Error during fallback basic parsing for {url}: {e_basic_parse}", exc_info=True)
                extracted_details["raw_title"] = "Basic Parsing Failed"
                extracted_details["cleaned_title"] = "Basic Parsing Failed"


        # Step 4: Compile final output data
        output_data = {
            "url": url,
            "raw_title": extracted_details.get("raw_title", "N/A"),
            "cleaned_title": extracted_details.get("cleaned_title", "N/A"),
            "main_text_entities": extracted_details.get("main_text_entities", []),
            "ocr_extracted_text": ocr_text,
            "regional_text_entities": extracted_details.get("regional_text_entities", []), # From ExtractorManager
            "screenshot_file_path": screenshot_path, # Could be temporary path or final stored path if moved
            # "links_count": len(links), # This was from old direct BasicParser use.
            # "links": links,           # ExtractorManager might provide this differently.
        }
        # If ExtractorManager provides link data, it should be in extracted_details
        if "links" in extracted_details:
            output_data["links"] = extracted_details["links"]
            output_data["links_count"] = len(extracted_details["links"])


        # Step 5: Save the extracted data
        saved_file_path: str = ""
        try:
            saved_file_path = self.file_storage.save_json(
                data=output_data,
                filename=output_filename,
                filename_prefix=output_filename_prefix,
                overwrite=True 
            )
            logger.info(f"Successfully saved enriched data for {url} to: {saved_file_path}")
        except FileStorageErrorSubclass as e:
            logger.error(f"FileStorage error while saving enriched data for {url}: {e.message}", exc_info=True)
            raise TaskManagementError(f"Failed to save enriched data for {url}: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error during file storage of enriched data for {url}: {str(e)}", exc_info=True)
            raise TaskManagementError(f"Unexpected error saving enriched data for {url}: {str(e)}")
        
        # Step 6: Cleanup temporary screenshot if one was taken and not moved by FileStorage
        if screenshot_path and os.path.exists(screenshot_path):
            # Check if screenshot_path is in a temp location managed by PlaywrightManager
            # For now, assume PlaywrightManager.temp_screenshot_dir is where these are.
            # A more robust check would be if screenshot_path starts with pm.temp_screenshot_dir
            # and if the final saved data should store a relative path or if FileStorage moves it.
            # For this subtask, assume screenshot_path is a temp path that needs cleanup.
            try:
                os.remove(screenshot_path)
                logger.info(f"Temporary screenshot cleaned up: {screenshot_path}")
            except OSError as e_clean:
                logger.error(f"Error cleaning up temporary screenshot {screenshot_path}: {e_clean}", exc_info=True)

        return saved_file_path

# The if __name__ == '__main__': block has been migrated to
# tests/core/test_manager.py
