import pytest
import os
import yaml

from ai_scraper_framework.core.config import ConfigurationManager, ConfigFileNotFoundError, InvalidYamlError, DEFAULT_ENV
from ai_scraper_framework.core.exceptions import ConfigurationError # For broader exception if needed

# Define the base directory for temporary config files relative to this test file.
# tests/core/test_config.py -> tests/core -> tests -> ai_scraper_framework
TEST_CONFIG_DIR_NAME = "test_config_temp"
CURRENT_TEST_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
# Place TEST_CONFIG_DIR inside tests/core for organization during testing
TEST_CONFIG_DIR = os.path.join(CURRENT_TEST_FILE_DIR, TEST_CONFIG_DIR_NAME)


@pytest.fixture(scope="function") # Use function scope to ensure clean state for each test
def temp_config_files():
    """
    Pytest fixture to create temporary YAML config files for testing.
    Also temporarily overrides the ConfigurationManager's CONFIG_DIR.
    """
    original_config_dir = ConfigurationManager._instance.CONFIG_DIR if ConfigurationManager._instance else None
    
    # Create a clean ConfigurationManager instance for each test
    # This is important because ConfigurationManager is a singleton.
    # We need to reset its internal state for isolated tests.
    if ConfigurationManager._instance:
        ConfigurationManager._instance._config = {}
        ConfigurationManager._instance._current_env = ""
        # ConfigurationManager._instance = None # More aggressive reset if needed

    if not os.path.exists(TEST_CONFIG_DIR):
        os.makedirs(TEST_CONFIG_DIR)

    # Set the CONFIG_DIR for ConfigurationManager to our temporary directory
    # This requires careful handling as ConfigurationManager is a singleton.
    # We'll patch it for the duration of the test.
    # Directly modifying class variable for test purposes.
    ConfigurationManager.CONFIG_DIR = TEST_CONFIG_DIR
    
    # Create dummy config files
    dev_config_content = {
        "database": {"host": "localhost_dev", "port": 5432},
        "feature_flags": {"new_search": True},
        "services": ["service1", "service2"]
    }
    prod_config_content = {
        "database": {"host": "prod_db", "port": 1234},
        "feature_flags": {"new_search": False}
    }
    invalid_yaml_content = "database: {host: 'bad_host', port: 1000" # Missing closing brace

    with open(os.path.join(TEST_CONFIG_DIR, "development.yaml"), "w") as f:
        yaml.dump(dev_config_content, f)
    with open(os.path.join(TEST_CONFIG_DIR, "production.yaml"), "w") as f:
        yaml.dump(prod_config_content, f)
    with open(os.path.join(TEST_CONFIG_DIR, "invalid.yaml"), "w") as f:
        f.write(invalid_yaml_content)
    # Non-dict YAML content
    with open(os.path.join(TEST_CONFIG_DIR, "not_dict.yaml"), "w") as f:
        yaml.dump(["list", "instead", "of", "dict"], f)


    yield TEST_CONFIG_DIR # provide the path to the test functions

    # Teardown: remove temporary files and directory, restore CONFIG_DIR
    for item in os.listdir(TEST_CONFIG_DIR):
        os.remove(os.path.join(TEST_CONFIG_DIR, item))
    os.rmdir(TEST_CONFIG_DIR)
    
    if original_config_dir and ConfigurationManager._instance:
        ConfigurationManager.CONFIG_DIR = original_config_dir
    
    # Clean up the singleton instance's state after test
    if ConfigurationManager._instance:
        ConfigurationManager._instance._config = {}
        ConfigurationManager._instance._current_env = ""
        # ConfigurationManager._instance = None # To force re-creation on next access if desired


def test_load_development_config_default(temp_config_files, monkeypatch):
    """Test loading development configuration by default (APP_ENV not set)."""
    monkeypatch.delenv("APP_ENV", raising=False) # Ensure APP_ENV is not set
    
    # Create a new instance to ensure it loads fresh based on current (patched) CONFIG_DIR and APP_ENV
    config_manager = ConfigurationManager()
    config_manager.load_config() # Explicitly call load_config

    assert config_manager.current_environment == "development"
    assert config_manager.get("database.host") == "localhost_dev"
    assert config_manager.get("database.port") == 5432
    assert config_manager.get("non_existent_key") is None
    assert config_manager.get("non_existent_key", "default_val") == "default_val"

def test_load_production_config_env_var(temp_config_files, monkeypatch):
    """Test loading production configuration using APP_ENV."""
    monkeypatch.setenv("APP_ENV", "production")
    
    config_manager = ConfigurationManager()
    config_manager.load_config()

    assert config_manager.current_environment == "production"
    assert config_manager.get("database.host") == "prod_db"
    assert config_manager.get("feature_flags.new_search") is False

def test_load_config_explicit_env_param(temp_config_files, monkeypatch):
    """Test loading configuration by passing 'env' parameter to load_config."""
    monkeypatch.delenv("APP_ENV", raising=False) # Ensure APP_ENV is not set to conflict

    config_manager = ConfigurationManager()
    config_manager.load_config(env="production") # Explicitly load production

    assert config_manager.current_environment == "production"
    assert config_manager.get("database.host") == "prod_db"

def test_get_nested_value(temp_config_files):
    """Test getting nested configuration values."""
    config_manager = ConfigurationManager()
    config_manager.load_config("development") # Load development config

    assert config_manager.get("feature_flags.new_search") is True
    assert config_manager.get("database") == {"host": "localhost_dev", "port": 5432}
    assert config_manager.get("services") == ["service1", "service2"]

def test_get_non_existent_nested_value(temp_config_files):
    """Test getting non-existent nested values returns default."""
    config_manager = ConfigurationManager()
    config_manager.load_config("development")
    
    assert config_manager.get("database.non_existent_sub_key") is None
    assert config_manager.get("feature_flags.another_flag", "default_flag_val") == "default_flag_val"
    assert config_manager.get("completely.made.up.path", "fallback") == "fallback"

def test_reload_config(temp_config_files, monkeypatch):
    """Test reloading configuration."""
    monkeypatch.setenv("APP_ENV", "development")
    config_manager = ConfigurationManager()
    config_manager.load_config() # Initial load (development)
    assert config_manager.get("database.host") == "localhost_dev"

    # Modify the development.yaml content directly for testing reload
    new_dev_content = {"database": {"host": "reloaded_dev_host"}}
    with open(os.path.join(TEST_CONFIG_DIR, "development.yaml"), "w") as f:
        yaml.dump(new_dev_content, f)

    config_manager.reload_config() # Reload the current environment (development)
    assert config_manager.get("database.host") == "reloaded_dev_host"

    # Test reloading with a different environment specified
    config_manager.reload_config(env="production")
    assert config_manager.current_environment == "production"
    assert config_manager.get("database.host") == "prod_db"


def test_config_file_not_found_error(temp_config_files, monkeypatch):
    """Test ConfigFileNotFoundError for non-existent environment."""
    monkeypatch.setenv("APP_ENV", "staging") # Assuming staging.yaml does not exist
    config_manager = ConfigurationManager()
    
    with pytest.raises(ConfigFileNotFoundError) as excinfo:
        config_manager.load_config()
    assert "Configuration file not found for environment 'staging'" in str(excinfo.value)
    assert "staging.yaml" in str(excinfo.value)

def test_invalid_yaml_error(temp_config_files, monkeypatch):
    """Test InvalidYamlError for malformed YAML file."""
    monkeypatch.setenv("APP_ENV", "invalid") # invalid.yaml is malformed
    config_manager = ConfigurationManager()

    with pytest.raises(InvalidYamlError) as excinfo:
        config_manager.load_config()
    assert "Error parsing YAML" in str(excinfo.value)
    assert "invalid.yaml" in str(excinfo.value)

def test_yaml_not_dict_error(temp_config_files, monkeypatch):
    """Test InvalidYamlError if YAML content is not a dictionary."""
    monkeypatch.setenv("APP_ENV", "not_dict") # not_dict.yaml contains a list
    config_manager = ConfigurationManager()

    with pytest.raises(InvalidYamlError) as excinfo:
        config_manager.load_config()
    assert "does not contain a valid YAML dictionary" in str(excinfo.value)
    assert "not_dict.yaml" in str(excinfo.value)

def test_singleton_behavior(temp_config_files):
    """Test that ConfigurationManager is a singleton."""
    config_manager1 = ConfigurationManager()
    config_manager1.load_config("development")
    
    config_manager2 = ConfigurationManager() # Should be the same instance
    
    assert config_manager1 is config_manager2
    assert config_manager2.get("database.host") == "localhost_dev" # State is preserved

    # Ensure that even if load_config is called on the second reference, it affects the first.
    config_manager2.load_config("production")
    assert config_manager1.get("database.host") == "prod_db"
    assert config_manager1.current_environment == "production"

# Note: The `if __name__ == "__main__":` block from core/config.py is now fully migrated
# to these pytest functions.
# The old block in core/config.py should be removed.
# PyYAML is needed for these tests to run (used by config.py and to create test files).
# Ensure it's in requirements.txt (which it is).
# Ensure pytest is in requirements.txt (will be added).
# Run with `pytest tests/core/test_config.py` from `ai_scraper_framework` directory.
# Add `ai_scraper_framework/tests/core/__init__.py` (empty file) if not present.
# The fixture `temp_config_files` handles cleanup of temporary YAML files.
# The fixture also handles resetting ConfigurationManager's CONFIG_DIR and instance state for each test.
# This is crucial because ConfigurationManager is a singleton.
# Forcing a new instance or fully resetting the singleton's state for each test function
# ensures test isolation. The current fixture approach resets key internal state (_config, _current_env)
# and patches CONFIG_DIR.
# The `ConfigurationManager._instance = None` line in the fixture's teardown
# would be a more aggressive way to ensure a fresh instance if simple state reset isn't enough.
# However, it can be tricky with how Python imports and caches modules.
# The current approach of resetting _config and _current_env, plus patching CONFIG_DIR,
# should be sufficient for these tests.
# The `ConfigurationManager()` call in each test will return the same singleton instance,
# but its internal config state and target directory are managed by the fixture.
# The load_config() call within each test then loads the appropriate config into this instance.
# The `scope="function"` for the fixture ensures this setup/teardown happens for each test.
# The `monkeypatch.delenv("APP_ENV", raising=False)` is important to ensure tests
# are not affected by APP_ENV set in the environment they run in, unless explicitly set by a test.
# The `monkeypatch.setenv` is used to simulate different APP_ENV settings.
# The direct patching of `ConfigurationManager.CONFIG_DIR` is a common way to redirect
# file access in tests when dependency injection for the path isn't available or is too complex.
# For a singleton, ensuring it's reset or its state is controlled per test is key.
# The current `temp_config_files` fixture attempts to manage this by:
# 1. Clearing internal state (`_config`, `_current_env`) of the singleton if it exists.
# 2. Patching `CONFIG_DIR` to point to a temporary directory.
# 3. In teardown, restoring `CONFIG_DIR` and clearing internal state again.
# This method works because subsequent calls to `ConfigurationManager()` in tests will get the
# same instance, but `load_config()` will operate on the patched `CONFIG_DIR` and update the
# now-cleared internal state.

# It's good practice to make sure the __init__.py files are present in test directories
# so pytest can discover them properly.
# ai_scraper_framework/tests/__init__.py
# ai_scraper_framework/tests/core/__init__.py
# These are usually empty.
# The `tests/__init__.py` was created in Phase 1.
# `tests/core/__init__.py` will be created by the `create_file_with_block` for `test_config.py`
# if the path implies directory creation.
# I will add an explicit step to create tests/core/__init__.py if needed.
# (Assuming the tool creates parent directories for files if they don't exist)
# If not, I would add:
# create_file_with_block
# ai_scraper_framework/tests/core/__init__.py
# # (empty content)
# This is typically handled by the agent's file creation tools.
# The prompt for this step was to create "ai_scraper_framework/tests/core/test_config.py",
# which implies the "core" directory under "tests" would be made.
# The `tests` directory itself should exist from previous phases.
# `ConfigurationManager._instance.CONFIG_DIR if ConfigurationManager._instance else None` in fixture.
# This is to handle the very first time the fixture runs when _instance might truly be None.
# After the first test using the manager, _instance will exist.
# The class variable `ConfigurationManager.CONFIG_DIR` is patched. This is a direct but effective way
# to control where the singleton looks for files during tests.
# The `ConfigurationManager()` calls within test functions will always return the same instance,
# but the fixture ensures that before each test, this instance's state is reset, and its
# `CONFIG_DIR` points to the test-specific directory. `load_config()` then repopulates the state.
# This ensures test isolation with respect to configuration loading.Okay, I will start by formalizing the `ConfigurationManager` tests.

**1. Formalize `ConfigurationManager` Tests:**
    *   Create `ai_scraper_framework/tests/core/test_config.py`.
    *   Migrate test logic from `if __name__ == '__main__':` in `ai_scraper_framework/core/config.py` to this new file.
    *   Structure tests using `pytest` conventions.
    *   Use `pytest.raises` for exceptions.
    *   Manage test YAML files dynamically or as strings.
    *   Remove the `if __name__ == '__main__':` block from `core/config.py`.

First, I'll create the directory `ai_scraper_framework/tests/core/` and an `__init__.py` file within it to ensure it's treated as a package. Then, I'll create `test_config.py`.
