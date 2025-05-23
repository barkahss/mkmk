"""
File system storage component for saving and loading data, primarily JSON.

This module provides the `FileStorage` class, which handles operations
like saving Python dictionaries/lists to JSON files and loading them back.
It integrates with the `ConfigurationManager` to determine the base storage
path and supports automatic filename generation.
"""
import json
import os
# shutil is no longer used in the main code after __main__ block removal.
# from typing import Union, Dict, List, Optional # Optional already imported
from typing import Union, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime
import uuid

from ai_scraper_framework.core.exceptions import StorageError
if TYPE_CHECKING: # To avoid circular import issues, only import for type hinting.
    from ai_scraper_framework.core.config import ConfigurationManager
from ai_scraper_framework.core.logger import get_logger

logger = get_logger(__name__)

# --- Custom Storage-Specific Exceptions ---
# These inherit from the core StorageError defined in core.exceptions.

class FilePathError(StorageError):
    """Raised for errors related to file paths, such as an empty filename."""
    def __init__(self, message: str):
        # StorageError (which is a ComponentError) handles component_name="Storage"
        super().__init__(message=message)

class FileExistsError(FilePathError):
    """
    Raised when attempting to save a file that already exists, and `overwrite` is False.

    Attributes:
        path (str): The full path to the file that already exists.
    """
    def __init__(self, path: str):
        super().__init__(f"File already exists at path: {path}. Set overwrite=True to replace it.")
        self.path = path

class FileNotFound(FilePathError): # More specific, standard library also has FileNotFoundError
    """Raised when a file is not found."""
    def __init__(self, path: str):
        super().__init__(f"File not found at path: {path}.")
        self.path = path

class SerializationError(StorageError):
    """Raised for errors during data serialization (e.g., JSON encoding/decoding issues)."""
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        full_message = f"Serialization error: {message}"
        if original_exception:
            full_message += f" (Original exception: {str(original_exception)})"
        # StorageError's constructor expects only 'message'.
        # StorageError itself will call super().__init__(component_name="Storage", message=full_message)
        super().__init__(message=full_message)
        self.original_exception = original_exception


class FileStorage:
    """
    Manages saving and loading data (primarily JSON) to the local file system.
    """
    DEFAULT_STORAGE_PATH = "scraped_data" # Default if not in config and config not provided.

    def __init__(self, config: Optional['ConfigurationManager'] = None):
        """
        Initializes the FileStorage.

        Args:
            config (Optional[ConfigurationManager]): ConfigurationManager instance to fetch settings.
                                                     If None, uses default settings.
        Raises:
            StorageError: If the base path cannot be created or accessed.
        """
        configured_base_path = None
        if config:
            configured_base_path = config.get('components.file_storage.base_path')
        
        # Determine project root to resolve relative paths
        # components/storage/file_storage.py -> components -> ai_scraper_framework (project_root)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        if configured_base_path:
            if not os.path.isabs(configured_base_path):
                self.base_path = os.path.join(project_root, configured_base_path)
            else:
                self.base_path = configured_base_path
            logger.info(f"FileStorage initialized with configured base_path: {self.base_path}")
        else:
            self.base_path = os.path.join(project_root, self.DEFAULT_STORAGE_PATH)
            logger.info(f"FileStorage initialized with default base_path: {self.base_path} (config not provided or key missing)")
            
        try:
            os.makedirs(self.base_path, exist_ok=True)
            logger.debug(f"Ensured base directory exists: {self.base_path}")
        except OSError as e:
            logger.error(f"Failed to create or access base directory '{self.base_path}': {e}", exc_info=True)
            # Re-raise as a StorageError consistent with the component's exceptions
            raise StorageError(message=f"Failed to create or access base directory '{self.base_path}': {e}")


    def _get_full_path(self, filename: str, extension: str = ".json") -> str:
        """Helper to construct the full file path and ensure filename ends with extension."""
        if not filename:
            raise FilePathError("Filename cannot be empty.")
        
        # Ensure the filename doesn't already contain the extension in a way that would duplicate it
        # e.g. if filename is "data.json" and extension is ".json"
        name, ext = os.path.splitext(filename)
        if ext.lower() == extension.lower():
            actual_filename = filename
        else:
            actual_filename = filename + extension
            
        return os.path.join(self.base_path, actual_filename)

    def save_json(self, data: Union[Dict, List], filename: Optional[str] = None, filename_prefix: Optional[str] = "item", overwrite: bool = False) -> str:
        """
        Saves the given data to a JSON file within the base_path.

        Args:
            data (Union[Dict, List]): The dictionary or list to save.
            filename (Optional[str]): The specific name of the file (extension handled). 
                                      If None or empty, a unique name is generated using filename_prefix.
            filename_prefix (Optional[str]): Prefix for generated filenames if 'filename' is not provided.
                                             Defaults to "item".
            overwrite (bool): If True, overwrite the file if it exists. Defaults to False.

        Returns:
            str: The full path to the saved file.

        Raises:
            FileExistsError: If overwrite is False and the file already exists.
            SerializationError: If there's an error during JSON serialization.
            StorageError: For other IO/OS errors.
        """
        resolved_filename: str
        if filename and filename.strip():
            resolved_filename = filename.strip()
            logger.debug(f"Using provided filename: {resolved_filename}")
        else:
            prefix = filename_prefix if filename_prefix and filename_prefix.strip() else "item"
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            unique_id = uuid.uuid4().hex[:6]
            resolved_filename = f"{prefix}_{timestamp}_{unique_id}"
            logger.debug(f"Generated filename: {resolved_filename} using prefix: {prefix}")

        full_path = self._get_full_path(resolved_filename, extension=".json")

        if not overwrite and os.path.exists(full_path):
            logger.warning(f"File already exists at {full_path} and overwrite is False.")
            raise FileExistsError(path=full_path)

        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Data successfully saved to {full_path}")
            return full_path
        except TypeError as e: # More specific for json.dump errors with non-serializable types
            logger.error(f"TypeError during JSON serialization for file '{resolved_filename}': {e}", exc_info=True)
            raise SerializationError(message=f"Failed to serialize data to JSON for file '{resolved_filename}' due to data type issue.", original_exception=e)
        except (IOError, OSError) as e:
            logger.error(f"Failed to save JSON to file '{full_path}': {e}", exc_info=True)
            raise StorageError(message=f"Failed to save JSON to file '{full_path}': {e}")


    def load_json(self, filename: str) -> Union[Dict, List]:
        """
        Loads and returns data from a JSON file named filename within the base_path.

        Args:
            filename (str): The name of the file (without .json extension, or with it).

        Returns:
            Union[Dict, List]: The data loaded from the JSON file.

        Raises:
            FileNotFound: If the file does not exist.
            SerializationError: If there's an error during JSON decoding.
            StorageError: For other IO/OS errors.
        """
        full_path = self._get_full_path(filename, extension=".json")

        if not os.path.exists(full_path):
            raise FileNotFound(path=full_path)

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            raise SerializationError(message=f"Failed to decode JSON from file '{full_path}'", original_exception=e)
        except (IOError, OSError) as e:
            raise StorageError(component_name="Storage", message=f"Failed to load JSON from file '{full_path}': {e}")

    def delete_file(self, filename: str, extension: str = ".json") -> bool:
        """
        Deletes a file within the base_path.

        Args:
            filename (str): The name of the file.
            extension (str): The file extension (e.g., ".json").

        Returns:
            bool: True if deletion was successful, False if file not found.
        
        Raises:
            StorageError: For permission errors or other OS issues.
        """
        full_path = self._get_full_path(filename, extension=extension)
        try:
            if os.path.exists(full_path):
                os.remove(full_path)
                return True
            return False
        except OSError as e:
            raise StorageError(component_name="Storage", message=f"Error deleting file '{full_path}': {e}")


if __name__ == '__main__':
    print("Testing FileStorage...")

    # Determine project root for consistent test_base_path
    # This script is in ai_scraper_framework/components/storage/file_storage.py
    # Project root is ../../ from here
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_for_test = os.path.abspath(os.path.join(current_script_dir, "..", ".."))
    
    # Test with default base_path (should be ai_scraper_framework/scraped_data if no config)
    print(f"\n--- Test 1: Default base_path (no config passed) ---")
    fs_default_no_config = None
    # DEFAULT_STORAGE_PATH is used when config is None or key is missing
    default_test_base_path_val = os.path.join(project_root_for_test, FileStorage.DEFAULT_STORAGE_PATH) 
    try:
        fs_default_no_config = FileStorage(config=None) # Explicitly pass None
        print(f"Default FileStorage (no config) initialized with base_path: {fs_default_no_config.base_path}")
        assert fs_default_no_config.base_path == default_test_base_path_val
        assert os.path.isdir(fs_default_no_config.base_path)

        sample_data = {"name": "Test Product", "id": 123, "tags": ["test", "json"]}
        
        # Save
        saved_path = fs_default_no_config.save_json(sample_data, "test_data_default")
        print(f"Saved JSON to: {saved_path}")
        assert saved_path == os.path.join(fs_default_no_config.base_path, "test_data_default.json")
        assert os.path.exists(saved_path)

        # Load
        loaded_data = fs_default_no_config.load_json("test_data_default")
        print(f"Loaded data: {loaded_data}")
        assert loaded_data == sample_data

        # Test filename with extension provided
        loaded_data_ext = fs_default_no_config.load_json("test_data_default.json")
        assert loaded_data_ext == sample_data
        saved_path_ext = fs_default_no_config.save_json(sample_data, "test_data_default_ext.json", overwrite=True)
        assert os.path.exists(os.path.join(fs_default_no_config.base_path, "test_data_default_ext.json"))

    except StorageError as e:
        print(f"StorageError in Test 1: {e}")
    finally:
        if fs_default_no_config and os.path.exists(default_test_base_path_val):
            print(f"Cleaning up default test directory: {default_test_base_path_val}")
            shutil.rmtree(default_test_base_path_val)

    # Mock ConfigurationManager for further tests
    class MockConfigManager:
        def __init__(self, settings):
            self.settings = settings
        def get(self, key, default=None):
            try:
                value = self.settings
                for k in key.split('.'): value = value[k]
                return value
            except KeyError: return default

    # Test 2: Custom relative base_path from mock config
    print(f"\n--- Test 2: Custom relative base_path (from mock config) ---")
    custom_relative_path_val = "custom_test_storage_mock"
    mock_config_relative = MockConfigManager({"components": {"file_storage": {"base_path": custom_relative_path_val}}})
    fs_custom_relative_mock = None
    full_custom_relative_path_val = os.path.join(project_root_for_test, custom_relative_path_val)
    try:
        fs_custom_relative_mock = FileStorage(config=mock_config_relative)
        print(f"Custom relative FileStorage (mock config) initialized with base_path: {fs_custom_relative_mock.base_path}")
        assert fs_custom_relative_mock.base_path == full_custom_relative_path_val
        assert os.path.isdir(fs_custom_relative_mock.base_path)
        
        data_rel = {"key": "value_relative_mock"}
        fs_custom_relative_mock.save_json(data_rel, "data_relative_mock")
        loaded_rel = fs_custom_relative_mock.load_json("data_relative_mock.json")
        assert loaded_rel == data_rel
    except StorageError as e:
        print(f"StorageError in Test 2: {e}")
    finally:
        if fs_custom_relative_mock and os.path.exists(fs_custom_relative_mock.base_path):
            print(f"Cleaning up custom relative mock test directory: {fs_custom_relative_mock.base_path}")
            shutil.rmtree(fs_custom_relative_mock.base_path)

    # Test 3: Custom absolute base_path from mock config
    temp_abs_dir_name_val = "temp_abs_storage_test_mock"
    custom_absolute_path_val = os.path.join(project_root_for_test, temp_abs_dir_name_val)
    mock_config_absolute = MockConfigManager({"components": {"file_storage": {"base_path": custom_absolute_path_val}}})
    fs_custom_absolute_mock = None
    print(f"\n--- Test 3: Custom absolute base_path (from mock config: {custom_absolute_path_val}) ---")
    try:
        fs_custom_absolute_mock = FileStorage(config=mock_config_absolute)
        print(f"Custom absolute FileStorage (mock config) initialized with base_path: {fs_custom_absolute_mock.base_path}")
        assert fs_custom_absolute_mock.base_path == custom_absolute_path_val
        assert os.path.isdir(fs_custom_absolute_mock.base_path)
        
        data_abs = {"key": "value_absolute_mock"}
        fs_custom_absolute_mock.save_json(data_abs, "data_absolute_mock")
        loaded_abs = fs_custom_absolute_mock.load_json("data_absolute_mock.json")
        assert loaded_abs == data_abs
    except StorageError as e:
        print(f"StorageError in Test 3: {e}")
    finally:
        if os.path.exists(custom_absolute_path_val):
            print(f"Cleaning up custom absolute mock test directory: {custom_absolute_path_val}")
            shutil.rmtree(custom_absolute_path_val)

    # Test 4: Error Handling (using default path via no config)
    print(f"\n--- Test 4: Error Handling (no config) ---")
    error_test_path_val = os.path.join(project_root_for_test, "error_storage_test_no_config")
    fs_error_no_config = FileStorage(config=None)
    # Manually set base_path for this test to isolate it, as default might have been cleaned up
    # Also, ensure the logger is available for the FileStorage instance if it wasn't through global setup
    if not hasattr(fs_error_no_config, 'logger'): # Basic check
        fs_error_no_config.logger = get_logger("FileStorage_ErrorTest")
        
    fs_error_no_config.base_path = error_test_path_val
    os.makedirs(fs_error_no_config.base_path, exist_ok=True)
    try:
        sample_data_err = {"error_test": True} # Renamed to avoid clash
        path_err = fs_error_no_config.save_json(sample_data_err, filename="error_file")

        # Test FileExistsError
        try:
            fs_error_no_config.save_json(sample_data_err, filename="error_file", overwrite=False)
        except FileExistsError as e:
            print(f"Caught expected FileExistsError: {e}")
            assert e.path == path_err
        
        # Test overwrite
        fs_error_no_config.save_json(sample_data_err, filename="error_file", overwrite=True)
        print("Overwrite successful.")

        # Test FileNotFound
        try:
            fs_error_no_config.load_json("non_existent_file")
        except FileNotFound as e:
            print(f"Caught expected FileNotFound: {e}")
            assert "non_existent_file.json" in e.path

        # Test SerializationError on load (manual creation of bad JSON)
        bad_json_path = os.path.join(fs_error_no_config.base_path, "bad_json.json")
        with open(bad_json_path, 'w') as f:
            f.write("{'bad_json': True,}") # Invalid JSON (trailing comma, single quotes)
        try:
            fs_error_no_config.load_json("bad_json")
        except SerializationError as e:
            print(f"Caught expected SerializationError on load: {e}")
            assert "Failed to decode JSON" in e.message

        # Test delete_file
        assert fs_error_no_config.delete_file("error_file") is True
        assert os.path.exists(path_err) is False
        assert fs_error_no_config.delete_file("error_file") is False # Already deleted

    except StorageError as e:
        print(f"StorageError during error handling tests (Test 4): {e}")
    finally:
        if os.path.exists(error_test_path_val): # Use the specific path for this test
            print(f"Cleaning up error test directory: {error_test_path_val}")
            shutil.rmtree(error_test_path_val)
            
    # Test 5: Filename Generation Logic (no config)
    print(f"\n--- Test 5: Filename Generation Logic (no config) ---")
    fs_gen_fn_no_config = FileStorage(config=None)
    gen_fn_test_dir_val = os.path.join(project_root_for_test, "gen_fn_test_dir_no_config")
    fs_gen_fn_no_config.base_path = gen_fn_test_dir_val # Isolate test
    os.makedirs(fs_gen_fn_no_config.base_path, exist_ok=True)
    try:
        # Test 1: filename=None, default prefix "item"
        path1 = fs_gen_fn_no_config.save_json({"data": "test1"})
        assert "item_" in os.path.basename(path1)
        assert ".json" in os.path.basename(path1)
        print(f"Generated filename (default prefix): {os.path.basename(path1)}")

        # Test 2: filename=None, custom prefix
        path2 = fs_gen_fn_no_config.save_json({"data": "test2"}, filename_prefix="custom_data")
        assert "custom_data_" in os.path.basename(path2)
        print(f"Generated filename (custom prefix): {os.path.basename(path2)}")

        # Test 3: filename="", custom prefix (should still generate)
        path3 = fs_gen_fn_no_config.save_json({"data": "test3"}, filename="", filename_prefix="another")
        assert "another_" in os.path.basename(path3)
        print(f"Generated filename (empty filename, custom prefix): {os.path.basename(path3)}")
        
        # Test 4: filename provided (should use it)
        path4 = fs_gen_fn_no_config.save_json({"data": "test4"}, filename="specific_name.json")
        assert os.path.basename(path4) == "specific_name.json"
        print(f"Used specific filename: {os.path.basename(path4)}")
        
        path5 = fs_gen_fn_no_config.save_json({"data": "test5"}, filename="specific_name_no_ext")
        assert os.path.basename(path5) == "specific_name_no_ext.json"
        print(f"Used specific filename (no ext): {os.path.basename(path5)}")

    except StorageError as e:
        print(f"StorageError during filename generation tests (Test 5): {e}")
    finally:
        if os.path.exists(gen_fn_test_dir_val):
            print(f"Cleaning up filename generation test directory: {gen_fn_test_dir_val}")
            shutil.rmtree(gen_fn_test_dir_val)

    print("\nFileStorage tests completed.")

# The if __name__ == '__main__': block was for demonstration and testing.
# Formal tests for this class should be in 'tests/components/storage/test_file_storage.py'.
# This block should have been removed as part of test formalization in Phase 9, Subtask 1.
