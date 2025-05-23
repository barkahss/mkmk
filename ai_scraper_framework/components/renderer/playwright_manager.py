"""
Manages Playwright browser instances for web page rendering.

This module provides the `PlaywrightManager` class, an asynchronous context manager
that simplifies the use of Playwright for launching browsers, creating pages,
and fetching page content. It integrates with the application's configuration
system to determine browser types and other settings.
"""
import asyncio
import os # For path operations
import uuid # For unique filenames
from playwright.async_api import async_playwright, Playwright, Browser, Page
from typing import Optional, TYPE_CHECKING, Dict

from ai_scraper_framework.core.exceptions import RendererError
from ai_scraper_framework.core.logger import get_logger

if TYPE_CHECKING:
    from ai_scraper_framework.core.config import ConfigurationManager # For type hinting

logger = get_logger(__name__)

# Determine project root for placing temp_screenshots directory
# ai_scraper_framework/components/renderer/playwright_manager.py -> ai_scraper_framework/
PROJECT_ROOT_FOR_RENDERER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_TEMP_SCREENSHOT_DIR = os.path.join(PROJECT_ROOT_FOR_RENDERER, "temp_playwright_screenshots")


class PlaywrightManager:
    """
    Asynchronous context manager for Playwright browser instances.

    This class handles the lifecycle of Playwright, including starting the
    Playwright engine, launching a browser instance (Chromium, Firefox, or WebKit),
    and ensuring resources are properly closed upon exit. It's configured via
    the application's `ConfigurationManager`.

    Attributes:
        browser_type (str): The type of browser to launch (e.g., 'chromium').
        playwright (Optional[Playwright]): The Playwright engine instance.
        browser (Optional[Browser]): The launched Playwright browser instance.
    """
    DEFAULT_BROWSER_TYPE = 'chromium'
    DEFAULT_PAGE_LOAD_TIMEOUT = 30000 # Milliseconds

    def __init__(self, config: Optional['ConfigurationManager'] = None):
        """
        Initializes the PlaywrightManager.

        Args:
            config (Optional[ConfigurationManager]): An instance of `ConfigurationManager`
                to fetch settings like `components.playwright_manager.browser_type`.
                If None, defaults will be used.

        Raises:
            RendererError: If an unsupported browser type is specified in the configuration
                           or as a default.
        """
        if config:
            self.browser_type = config.get('components.playwright_manager.browser_type', self.DEFAULT_BROWSER_TYPE)
            # Example for future extension: load other Playwright options from config
            # self.launch_options = config.get('components.playwright_manager.launch_options', {})
            # self.page_load_timeout = config.get('components.playwright_manager.page_timeout', self.DEFAULT_PAGE_LOAD_TIMEOUT)
        else:
            self.browser_type = self.DEFAULT_BROWSER_TYPE
            # self.launch_options = {}
            # self.page_load_timeout = self.DEFAULT_PAGE_LOAD_TIMEOUT
        
        logger.info(f"PlaywrightManager configured to use browser: {self.browser_type}")

        if self.browser_type not in ['chromium', 'firefox', 'webkit']:
            logger.error(f"Unsupported browser type configured: {self.browser_type}")
            raise RendererError(f"Unsupported browser type: {self.browser_type}. Must be 'chromium', 'firefox', or 'webkit'.")
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        # self.page_load_timeout is not yet used, but shown as example for config extension
        self.temp_screenshot_dir = DEFAULT_TEMP_SCREENSHOT_DIR # Can be made configurable later
        # Ensure the temp directory exists
        try:
            os.makedirs(self.temp_screenshot_dir, exist_ok=True)
            logger.info(f"Temporary screenshot directory ensured at: {self.temp_screenshot_dir}")
        except OSError as e:
            logger.error(f"Failed to create temporary screenshot directory '{self.temp_screenshot_dir}': {e}", exc_info=True)
            # Depending on strictness, could raise an error or proceed without screenshot capability.
            # For now, log and proceed; screenshot attempts will fail later if dir is unusable.

    async def __aenter__(self) -> 'PlaywrightManager':
        """
        Initializes the Playwright engine and launches the configured browser.
        This method is called when entering an 'async with' block.

        Returns:
            PlaywrightManager: The instance of itself.

        Raises:
            RendererError: If Playwright fails to start or the browser fails to launch.
                           This can happen if browser binaries are not installed.
        """
        logger.debug(f"Entering PlaywrightManager context: Starting Playwright and launching {self.browser_type} browser.")
        try:
            self.playwright = await async_playwright().start()
            # Dynamically get the browser launcher (e.g., playwright.chromium)
            browser_launcher_method = getattr(self.playwright, self.browser_type)
            # Launch the browser (add self.launch_options here if using them)
            self.browser = await browser_launcher_method.launch() 
            logger.info(f"{self.browser_type} browser launched successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright or launch browser {self.browser_type}: {e}", exc_info=True)
            # Attempt to clean up Playwright if it started but browser launch failed
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as stop_e:
                    logger.error(f"Error stopping Playwright during __aenter__ cleanup: {stop_e}", exc_info=True)
                self.playwright = None
            raise RendererError(f"Failed to initialize Playwright or launch browser {self.browser_type}: {e}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the browser and stops the Playwright engine.
        This method is called when exiting an 'async with' block.

        Args:
            exc_type: The type of exception that caused the context to be exited (if any).
            exc_val: The exception instance that caused the context to be exited (if any).
            exc_tb: A traceback object for the exception (if any).
        """
        logger.debug("Exiting PlaywrightManager context: Closing browser and stopping Playwright.")
        if self.browser:
            try:
                await self.browser.close()
                logger.info("Browser closed successfully.")
            except Exception as e:
                logger.error(f"Error closing browser: {e}", exc_info=True)
        if self.playwright:
            try:
                await self.playwright.stop()
                logger.info("Playwright stopped successfully.")
            except Exception as e:
                logger.error(f"Error stopping Playwright: {e}", exc_info=True)
        
        # Reset state
        self.browser = None
        self.playwright = None

    async def get_page_content(self, url: str, timeout: Optional[int] = None) -> str:
        """
        Navigates to a given URL in a new browser page and returns its HTML content.

        Args:
            url (str): The URL of the webpage to scrape.
            timeout (Optional[int]): Specific timeout in milliseconds for page navigation (page.goto).
                                     If None, a default timeout (e.g., 30000ms) is used.

        Returns:
            str: The full HTML content of the page.

        Raises:
            RendererError: If the browser is not initialized (e.g., not used within 'async with'),
                           or if page navigation or content retrieval fails.
        """
        if not self.browser:
            # This typically means the manager wasn't entered using 'async with'.
            logger.error("get_page_content called but browser is not initialized.")
            raise RendererError("Browser is not initialized. Ensure PlaywrightManager is used within an 'async with' statement.")

        page: Optional[Page] = None
        effective_timeout = timeout if timeout is not None else self.DEFAULT_PAGE_LOAD_TIMEOUT
        logger.debug(f"Fetching content for URL: {url} with timeout {effective_timeout}ms.")

        try:
            page = await self.browser.new_page()
            # `wait_until='domcontentloaded'` waits until the DOM is ready, but not necessarily all resources.
            # Other options: 'load' (waits for all resources), 'networkidle'.
            await page.goto(url, wait_until='domcontentloaded', timeout=effective_timeout)
            content = await page.content()
            logger.info(f"Successfully retrieved content from {url}.")
            return content
        except Exception as e:
            logger.error(f"Failed to get content from URL '{url}': {e}", exc_info=True)
            raise RendererError(f"Failed to get content from URL '{url}': {e}")
        finally:
            if page:
                try:
                    await page.close()
                    logger.debug(f"Page for URL {url} closed.")
                except Exception as e:
                    logger.error(f"Error closing page for URL '{url}': {e}", exc_info=True)

    async def take_screenshot(self, page: Page, path: str, full_page: bool = True, timeout: Optional[int] = 30000) -> None:
        """
        Takes a screenshot of the given Playwright Page.

        Args:
            page (Page): The active Playwright Page object to screenshot.
            path (str): The file path where the screenshot will be saved.
            full_page (bool, optional): Whether to capture the full scrollable page.
                                        Defaults to True.
            timeout (Optional[int]): Timeout for the screenshot operation in milliseconds.
                                     Defaults to 30000ms.
        Raises:
            RendererError: If the screenshot operation fails.
        """
        logger.debug(f"Taking screenshot. Path: '{path}', Full page: {full_page}, Timeout: {timeout}ms.")
        try:
            await page.screenshot(path=path, full_page=full_page, timeout=timeout)
            logger.info(f"Screenshot saved successfully to: {path}")
        except Exception as e:
            logger.error(f"Failed to take screenshot to path '{path}': {e}", exc_info=True)
            raise RendererError(f"Failed to take screenshot: {e}")

    async def get_page_snapshot(
        self,
        url: str,
        page_load_timeout: Optional[int] = None,
        screenshot_options: Optional[Dict] = None
    ) -> Dict[str, Optional[str]]:
        """
        Navigates to a URL, gets its HTML content, and optionally takes a screenshot.

        Args:
            url (str): The URL to scrape.
            page_load_timeout (Optional[int]): Timeout for page loading in milliseconds.
                                               Uses `self.DEFAULT_PAGE_LOAD_TIMEOUT` if None.
            screenshot_options (Optional[Dict]): Options for taking a screenshot.
                Example: {'path': 'custom/path/screenshot.png', 'full_page': True, 'timeout': 30000}
                If 'path' is not provided, a temporary path will be generated in `self.temp_screenshot_dir`.
                If `screenshot_options` is None, no screenshot is taken.

        Returns:
            Dict[str, Optional[str]]: A dictionary containing:
                - 'html' (str): The HTML content of the page.
                - 'screenshot_path' (Optional[str]): Absolute path to the saved screenshot file,
                                                     or None if no screenshot was taken or if it failed.
        Raises:
            RendererError: If page navigation or HTML content retrieval fails.
                           Screenshot errors are logged but do not raise RendererError from this method;
                           `screenshot_path` will be None in case of screenshot failure.
        """
        if not self.browser:
            logger.error("get_page_snapshot called but browser is not initialized.")
            raise RendererError("Browser not initialized. Use 'async with PlaywrightManager()'.")

        html_content: Optional[str] = None
        screenshot_file_path: Optional[str] = None
        page: Optional[Page] = None
        
        effective_page_load_timeout = page_load_timeout if page_load_timeout is not None else self.DEFAULT_PAGE_LOAD_TIMEOUT
        logger.info(f"Getting page snapshot for URL: {url} (page_load_timeout: {effective_page_load_timeout}ms)")

        try:
            page = await self.browser.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=effective_page_load_timeout)
            html_content = await page.content()
            logger.info(f"HTML content retrieved for {url}.")

            if screenshot_options is not None:
                # Determine screenshot path
                custom_path = screenshot_options.get('path')
                if custom_path:
                    # Ensure directory for custom_path exists if it's relative
                    if not os.path.isabs(custom_path):
                        # Assume custom_path is relative to project root if not absolute.
                        # Or, define behavior: relative to current working dir or a specific base dir from config.
                        # For now, let's assume if relative, it's relative to where script is run, or manager handles it.
                        # A safer approach: make it always absolute or relative to a known base.
                        # For this implementation, if custom_path is relative, it's relative to CWD.
                        # Let's refine to make it relative to temp_screenshot_dir if not absolute.
                        if not os.path.isabs(custom_path):
                             logger.warning(f"Provided screenshot path '{custom_path}' is relative. It will be resolved relative to CWD or a pre-defined base if not absolute.")
                             # For consistency, could force it into temp_screenshot_dir or error if not absolute.
                             # Path(custom_path).mkdir(parents=True, exist_ok=True) # For Pathlib
                             os.makedirs(os.path.dirname(custom_path), exist_ok=True) # For os.path
                        screenshot_file_path = custom_path
                    else:
                        screenshot_file_path = custom_path
                else:
                    # Generate a unique filename in the default temp directory
                    unique_filename = f"snapshot_{uuid.uuid4().hex[:8]}.png"
                    screenshot_file_path = os.path.join(self.temp_screenshot_dir, unique_filename)
                
                # Ensure directory for screenshot_file_path exists
                os.makedirs(os.path.dirname(screenshot_file_path), exist_ok=True)

                # Get screenshot options
                ss_full_page = screenshot_options.get('full_page', True)
                ss_timeout = screenshot_options.get('timeout', 30000) # Default 30s for screenshot
                
                try:
                    await self.take_screenshot(page, path=screenshot_file_path, full_page=ss_full_page, timeout=ss_timeout)
                except RendererError as e_ss: # Errors from take_screenshot are already logged there
                    logger.error(f"Screenshot failed for {url}, but HTML content was retrieved. Error: {e_ss}")
                    screenshot_file_path = None # Ensure path is None if screenshot fails

        except Exception as e_page_load: # Handles errors from goto() or content()
            logger.error(f"Failed to get page snapshot for URL '{url}': {e_page_load}", exc_info=True)
            # If page load/HTML fails, we usually want to propagate this as a critical error.
            raise RendererError(f"Failed to get page content for URL '{url}': {e_page_load}")
        finally:
            if page:
                try:
                    await page.close()
                    logger.debug(f"Page for URL {url} closed after snapshot attempt.")
                except Exception as e_close:
                    logger.error(f"Error closing page for URL '{url}' after snapshot: {e_close}", exc_info=True)
        
        return {"html": html_content, "screenshot_path": screenshot_file_path}

# The if __name__ == '__main__': block has been migrated to tests/components/renderer/test_playwright_manager.py
# and was removed in a previous step.
