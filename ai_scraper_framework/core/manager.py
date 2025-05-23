import asyncio
import os
import shutil # For cleanup in test
import logging # Keep for __main__ block if needed, or remove if get_logger is sufficient
from typing import Optional # Added import for Optional
from ai_scraper_framework.core.logger import get_logger

from ai_scraper_framework.components.renderer.playwright_manager import PlaywrightManager
from ai_scraper_framework.components.extractor.basic_parser import BasicParser
from ai_scraper_framework.components.extractor.extractor_manager import ExtractorManager
from ai_scraper_framework.components.vision.vision_manager import VisionManager
from ai_scraper_framework.components.storage.file_storage import FileStorage, StorageError as FileStorageErrorSubclass # For screenshot cleanup if needed
from ai_scraper_framework.components.storage.db_manager import DatabaseManager # Added
from ai_scraper_framework.components.storage.database_models import ScrapingResult, ScrapingTask # Added for type hinting
from ai_scraper_framework.core.exceptions import RendererError, ExtractorError, TaskManagementError, ComponentError, DatabaseError

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

        try:
            # Initialize DatabaseManager
            self.db_manager = DatabaseManager(config=self.config)
            logger.info("DatabaseManager initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing DatabaseManager: {e}", exc_info=True)
            # Database is critical, so re-raise as TaskManagementError if it fails.
            raise TaskManagementError(f"Failed to initialize DatabaseManager: {e}")

        logger.info("ScrapingManager initialized successfully.")


    async def scrape_single_url_basic(self, url: str, task_id: Optional[uuid.UUID] = None) -> ScrapingResult:
        """
        Performs a basic scraping workflow for a single URL, including screenshot and OCR,
        and saves the result to the database.

        Args:
            url (str): The URL of the webpage to scrape.
            task_id (Optional[uuid.UUID]): The ID of the parent ScrapingTask. If None, a new task
                                           will be created. (This behavior will be refined later;
                                           for now, assume task_id is provided or handled by API layer).

        Returns:
            ScrapingResult: The ScrapingResult object containing the outcome.

        Raises:
            TaskManagementError: If a critical stage of the scraping process fails (e.g., page rendering).
                                 Other errors (like OCR or specific extraction issues) might be logged
                                 and included in the ScrapingResult's error_info.
        """
        logger.info(f"Starting basic scraping for URL: {url}. Associated Task ID: {task_id}")

        # Ensure a task_id is available. For this integration step, we'll create a task if not provided.
        # In a full system, task creation would likely be handled by the API layer or a task scheduler.
        current_task: Optional[ScrapingTask] = None
        if task_id:
            current_task = await self.db_manager.get_task(task_id)
            if not current_task:
                logger.error(f"Task with ID {task_id} not found for URL {url}.")
                raise TaskManagementError(f"Task {task_id} not found.")
            await self.db_manager.update_task_status(task_id, "running")
        else:
            # This is a simplified approach for now.
            logger.warning(f"No task_id provided for URL {url}. Creating a new task. This flow might change.")
            try:
                current_task = await self.db_manager.add_task(url=url)
                task_id = current_task.id
                await self.db_manager.update_task_status(task_id, "running")
            except DatabaseError as e_db_task:
                logger.error(f"Failed to create initial task for URL {url}: {e_db_task}", exc_info=True)
                raise TaskManagementError(f"Database error creating task for {url}: {e_db_task.message}")


        page_snapshot: Dict[str, Optional[str]] = {}
        html_content: Optional[str] = None
        screenshot_path_temp: Optional[str] = None # Temporary path from PlaywrightManager
        ocr_text: Optional[str] = None
        final_error_info: Optional[str] = None
        
        try:
            # Step 1: Fetch HTML content and take a screenshot using PlaywrightManager.
            try:
                async with self.playwright_manager as pm:
                    snapshot_options = {'full_page': True} 
                    page_snapshot = await pm.get_page_snapshot(url, screenshot_options=snapshot_options)
                
                html_content = page_snapshot.get("html")
                screenshot_path_temp = page_snapshot.get("screenshot_path")

                if not html_content:
                     logger.error(f"Failed to retrieve HTML content for {url}.")
                     raise TaskManagementError(f"HTML content missing for {url} after snapshot.")
                logger.info(f"Successfully fetched snapshot for {url}. Screenshot temp path: {screenshot_path_temp}")

            except RendererError as e:
                logger.error(f"RendererError while fetching snapshot for {url}: {e.message}", exc_info=True)
                final_error_info = f"RendererError: {e.message}"
                raise # Re-raise to be caught by outer try-except for DB logging
            except Exception as e: # Catch other snapshot errors
                logger.error(f"Unexpected error during page snapshot for {url}: {str(e)}", exc_info=True)
                final_error_info = f"Snapshot Error: {str(e)}"
                raise TaskManagementError(f"Unexpected error during page snapshot for {url}: {str(e)}")

            # Step 2: OCR (if screenshot_path_temp was successfully obtained and VisionManager is available)
            if screenshot_path_temp and self.vision_manager:
                try:
                    from PIL import Image # Using Pillow to get image dimensions
                    with Image.open(screenshot_path_temp) as img:
                        width, height = img.size
                    full_image_bbox = (0, 0, width, height)
                    ocr_text = self.vision_manager.extract_text_from_image_region(screenshot_path_temp, full_image_bbox)
                    logger.info(f"OCR extracted text (first 100 chars): '{ocr_text[:100]}...'")
                except ImportError:
                    logger.warning("Pillow not installed, cannot get image dimensions for full image OCR. Skipping OCR.")
                except ComponentError as e_ocr_comp:
                    logger.error(f"ComponentError during OCR for {url}: {e_ocr_comp.message}", exc_info=True)
                    final_error_info = (final_error_info + "; " if final_error_info else "") + f"OCR Error: {e_ocr_comp.message}"
                except Exception as e_ocr_generic:
                    logger.error(f"Unexpected error during OCR for {url}: {e_ocr_generic}", exc_info=True)
                    final_error_info = (final_error_info + "; " if final_error_info else "") + f"OCR Unexpected Error: {str(e_ocr_generic)}"
            # If screenshot_path_temp is None but self.vision_manager exists, this block is skipped.
            
            # Step 3: Parse HTML and process text with ExtractorManager
            extracted_details: Dict = {}
            if self.extractor_manager:
                try:
                    ocr_text_regions = [ocr_text] if ocr_text else None
                    extracted_details = self.extractor_manager.extract_product_details(
                        html_content=html_content, 
                        text_regions=ocr_text_regions
                    )
                    logger.info(f"ExtractorManager processed content for {url}.")
                except ComponentError as e_extract_comp:
                    logger.error(f"ComponentError during extraction for {url}: {e_extract_comp.message}", exc_info=True)
                    final_error_info = (final_error_info + "; " if final_error_info else "") + f"Extraction Error: {e_extract_comp.message}"
                    # Use basic parsing as fallback for title if extraction fails
                    if not extracted_details.get("raw_title"):
                        try:
                            parser = BasicParser(html_content=html_content)
                            extracted_details["raw_title"] = parser.get_title() or "Title extraction failed"
                            extracted_details["cleaned_title"] = extracted_details["raw_title"]
                        except Exception as e_bp_fallback:
                            logger.error(f"Fallback BasicParser failed for title: {e_bp_fallback}", exc_info=True)
                            extracted_details["raw_title"] = "Title extraction critically failed"
                except Exception as e_extract_generic:
                    logger.error(f"Unexpected error during extraction for {url}: {e_extract_generic}", exc_info=True)
                    final_error_info = (final_error_info + "; " if final_error_info else "") + f"Extraction Unexpected Error: {str(e_extract_generic)}"
            else: # Fallback if ExtractorManager is not available
                logger.warning("ExtractorManager not available. Performing basic parsing only for title.")
                try:
                    parser = BasicParser(html_content=html_content)
                    extracted_details["raw_title"] = parser.get_title() or ""
                    extracted_details["cleaned_title"] = extracted_details["raw_title"]
                except Exception as e_basic_parse:
                    logger.error(f"Error during fallback basic parsing for {url}: {e_basic_parse}", exc_info=True)
                    extracted_details["raw_title"] = "Basic Parsing Failed"
                    final_error_info = (final_error_info + "; " if final_error_info else "") + f"Basic Parsing Error: {str(e_basic_parse)}"
            
            # Step 4: Compile final output data for DB
            db_data_payload = {
                "url": url,
                "raw_title": extracted_details.get("raw_title", "N/A"),
                "cleaned_title": extracted_details.get("cleaned_title", extracted_details.get("raw_title", "N/A")), # Fallback for cleaned_title
                "main_text_entities": extracted_details.get("main_text_entities", []),
                "regional_text_entities": extracted_details.get("regional_text_entities", []),
                "links": extracted_details.get("links", []),
                "links_count": extracted_details.get("links_count", 0),
                # Note: Storing full HTML in JSONB might be large. Consider if needed or if a summary/key parts are better.
                # "html_content": html_content, 
            }
            
            # Update task status to completed (even if some non-critical parts like OCR failed)
            if task_id: await self.db_manager.update_task_status(task_id, "completed") # Removed error_info

        except TaskManagementError as e_task_mgmt: # Catch errors from snapshot stage that were re-raised
            final_error_info = str(e_task_mgmt.message) # This final_error_info will be saved in ScrapingResult
            if task_id: await self.db_manager.update_task_status(task_id, "failed") # Removed error_info
            raise # Re-raise critical TaskManagementError

        finally:
            # Step 5: Save the scraping result to the database
            # This runs whether the main try block succeeded or a caught error occurred (final_error_info set)
            if task_id: # Only save result if we have a task_id
                try:
                    scraping_result_obj = await self.db_manager.add_scraping_result(
                        task_id=task_id,
                        data=db_data_payload if not final_error_info else None, # Store data only if no critical error
                        error_info=final_error_info,
                        screenshot_path=screenshot_path_temp, # Store temp path, final path TBD by FileStorage if moved
                        ocr_text=ocr_text
                    )
                    logger.info(f"Scraping result saved to DB for task {task_id}, Result ID: {scraping_result_obj.id}")
                except DatabaseError as e_db_result:
                    logger.error(f"DatabaseError saving result for task {task_id}: {e_db_result}", exc_info=True)
                    # If saving result fails, this is a critical issue.
                    # Original TaskManagementError (if any) should probably take precedence.
                    if not final_error_info: # If no prior error, this is the main error
                        raise TaskManagementError(f"Failed to save scraping result for {url}: {e_db_result.message}")
            else:
                logger.error(f"No task_id available, cannot save result for URL {url}.")


            # Step 6: Cleanup temporary screenshot
            if screenshot_path_temp and os.path.exists(screenshot_path_temp):
                try:
                    os.remove(screenshot_path_temp)
                    logger.info(f"Temporary screenshot cleaned up: {screenshot_path_temp}")
                except OSError as e_clean:
                    logger.error(f"Error cleaning up temporary screenshot {screenshot_path_temp}: {e_clean}", exc_info=True)
            
            # Return the result object (or handle its absence if task_id was missing)
            if 'scraping_result_obj' in locals() and scraping_result_obj:
                return scraping_result_obj
            elif final_error_info: # If there was an error and result saving failed or wasn't attempted
                # Construct a temporary ScrapingResult-like object for return if needed, or just re-raise
                # For now, if final_error_info is set, a TaskManagementError was already raised or will be.
                # This path should ideally not be reached if error handling above is complete.
                logger.warning(f"Scraping for {url} concluded with errors but no DB result object to return.")
                # Create a dummy error result if needed by API, or ensure API handles prior exception.
                # This part depends on how the API layer expects to handle failures if DB write itself fails.
                # For now, assume prior exceptions cover this.
                # If we are here, it means a critical error happened AND saving that error to DB also failed.
                # This implies a major issue, so the original TaskManagementError should have been propagated.
                # This path is more of a safeguard.
                raise TaskManagementError(f"Scraping for {url} failed: {final_error_info}. Result saving also failed or was skipped.")
            else: # Should not happen if task_id logic is correct
                raise TaskManagementError(f"Scraping for {url} completed but no result object available (task_id issue?).")


# The if __name__ == '__main__': block has been migrated to
# tests/core/test_manager.py
