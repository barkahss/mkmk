"""
Centralized logging setup for the AI Scraper Framework.

This module provides functions to configure and obtain logger instances
throughout the application. It leverages the `ConfigurationManager` to
load logging settings from YAML configuration files, supporting
console and rotating file handlers.

Key Functions:
- `setup_logging()`: Initializes the logging system based on external configuration.
                     Should be called once at application startup.
- `get_logger(name)`: Returns a logger instance for the specified module name.
                      Ensures logging is initialized with fallback if needed.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any

# Assuming ConfigurationManager might not be fully initialized when this module is imported.
# We'll use a forward reference or Optional type for it in function signatures.
from ai_scraper_framework.core.config import ConfigurationManager

# PROJECT_ROOT: Absolute path to the project's root directory.
# Used to resolve relative log file paths from the configuration.
# Assumes this file (logger.py) is in ai_scraper_framework/core/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# _logging_initialized: Global flag to prevent multiple initializations of the logging system.
_logging_initialized = False

def setup_logging(config: Optional[ConfigurationManager] = None) -> None:
    """
    Sets up centralized logging for the application using settings from the
    provided `ConfigurationManager` instance.

    This function configures the root logger with handlers (console, rotating file)
    and formatting as specified in the 'logging' section of the configuration.
    It includes fallbacks to basic logging if the configuration is missing
    or incomplete.

    It's designed to be called once at application startup (e.g., in `api/main.py`).

    Args:
        config (Optional[ConfigurationManager]): The application's configuration manager instance.
            If None, it attempts to import and use the global `config_manager`
            from `ai_scraper_framework.core.config`. If that also fails,
            basic logging is configured.
    """
    global _logging_initialized
    if _logging_initialized:
        # Using standard logging here, as this indicates a programming error or unexpected re-entry.
        # A logger obtained via get_logger() might not be fully configured if this is re-entered problematically.
        logging.getLogger(__name__).debug("Logging setup_logging: Already initialized.")
        return

    current_config = config
    if current_config is None:
        # Attempt to use the global config_manager if no specific config is passed.
        # This allows flexibility if setup_logging is called from different contexts.
        try:
            from ai_scraper_framework.core.config import config_manager as global_config_manager
            current_config = global_config_manager
        except ImportError: # Should not happen if project structure is correct
            logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - CRITICAL - Logger setup: Global config_manager import failed. %(message)s")
            logging.critical("Logging setup: Could not import global_config_manager. Using basicConfig.", exc_info=True)
            _logging_initialized = True # Mark as initialized to prevent loops
            return
        
        if current_config is None or not current_config._config: # Check if global_config_manager was usable
            # Fallback to basic logging if ConfigurationManager is not available or not loaded.
            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            logging.warning("Logging setup: ConfigurationManager not available, not provided, or not loaded. Using basicConfig.")
            _logging_initialized = True
            return
    
    log_settings: Optional[Dict[str, Any]] = current_config.get("logging")

    if not log_settings:
        # Fallback to basic logging if 'logging' section is entirely missing.
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        logging.warning("Logging setup: 'logging' section not found in configuration. Using basicConfig.")
        _logging_initialized = True
        return

    # Determine log level, default to INFO if not specified.
    log_level_str = log_settings.get("level", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Determine log format, use a standard default if not specified.
    log_format = log_settings.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s")

    root_logger = logging.getLogger() # Get the root logger to configure.
    
    # Clear any existing handlers from the root logger.
    # This prevents duplicate log messages if setup_logging is inadvertently called multiple times
    # or if other libraries (or basicConfig) have already added handlers.
    if root_logger.hasHandlers():
        for handler in root_logger.handlers[:]: # Iterate over a copy of the list.
            root_logger.removeHandler(handler)
            handler.close() # Properly close the handler to release resources.

    root_logger.setLevel(log_level)
    formatter = logging.Formatter(log_format)

    # Configure Console Handler if enabled in config.
    console_handler_settings = log_settings.get("handlers", {}).get("console", {})
    if console_handler_settings.get("enabled", False): # Default to False if 'console' or 'enabled' is missing
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Configure Rotating File Handler if enabled in config.
    file_handler_settings = log_settings.get("handlers", {}).get("file", {})
    if file_handler_settings.get("enabled", False): # Default to False
        log_file_path_relative = file_handler_settings.get("path", "logs/ai_scraper_framework.log") # Default path
        log_file_path_absolute = os.path.join(PROJECT_ROOT, log_file_path_relative)
        
        max_bytes = int(file_handler_settings.get("max_bytes", 10 * 1024 * 1024)) # Default 10MB
        backup_count = int(file_handler_settings.get("backup_count", 5)) # Default 5 backups

        try:
            # Ensure the log directory exists before creating the file handler.
            log_dir = os.path.dirname(log_file_path_absolute)
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            file_handler = RotatingFileHandler(
                filename=log_file_path_absolute,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8' # Explicitly set encoding for broader compatibility.
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            # If file handler setup fails (e.g., permission issues), log an error to basicConfig/console.
            # This ensures the application doesn't crash due to logging setup failure.
            logging.error(f"Logging setup: Failed to configure file logging at '{log_file_path_absolute}': {e}. File logging disabled.", exc_info=True)

    _logging_initialized = True
    # Log initialization status using the now-configured logger.
    # These messages will go to the configured handlers.
    logging.info(f"Logging system initialized. Level: {log_level_str}. Format: '{log_format}'.")
    if console_handler_settings.get("enabled", False):
        logging.debug("Console logging handler enabled.")
    if file_handler_settings.get("enabled", False):
        logging.debug(f"File logging handler enabled at path: {log_file_path_absolute}")


def get_logger(name: str) -> logging.Logger:
    """
    Retrieves a logger instance with the specified name.

    This function acts as a wrapper around `logging.getLogger(name)`.
    It also ensures that `setup_logging()` has been called at least once
    (using fallback settings if necessary) before a logger is dispensed. This
    makes it safer to call `get_logger()` from any module at import time.

    Args:
        name (str): The name for the logger, typically `__name__` of the calling module.

    Returns:
        logging.Logger: An instance of `logging.Logger`.
    """
    if not _logging_initialized:
        # This fallback is crucial if get_logger() is called by a module
        # before the main application entry point has explicitly called setup_logging().
        # Using print here as a last resort if logging itself is not even basically configured.
        print(f"Warning: get_logger('{name}') called before explicit logging setup. Attempting default setup_logging().")
        setup_logging() # Attempts to use global config_manager or falls back to basicConfig.

    return logging.getLogger(name)

# The if __name__ == "__main__": block was for demonstration and testing.
# Proper tests for logger setup would typically involve:
# - Mocking the ConfigurationManager.
# - Checking if logging handlers are added/configured as expected.
# - Verifying log output (e.g., by capturing logs or checking file content).
# This block should have been removed as part of test formalization in Phase 9, Subtask 1.
