"""
Configuration management for the AI Scraper Framework.

This module provides a singleton `ConfigurationManager` class to load and access
configuration settings from YAML files. It supports environment-specific
configurations (e.g., development, production) and allows easy access to
nested configuration values.

Key Features:
- Loads settings from YAML files based on APP_ENV environment variable.
- Defaults to 'development' environment if APP_ENV is not set.
- Provides a global `config_manager` instance for easy access.
- Supports dot notation for accessing nested keys (e.g., "database.host").
- Custom exceptions for configuration-related errors.
"""
import os
import yaml
from typing import Any, Dict, Optional

# CONFIG_DIR: Path to the directory containing configuration YAML files.
# Assumes config files (e.g., development.yaml, production.yaml) are in a 'config'
# directory at the root of the project (one level up from 'core').
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config")

# DEFAULT_ENV: The default environment to use if APP_ENV is not set.
DEFAULT_ENV = "development"

class ConfigError(Exception):
    """Base class for all configuration-related errors."""
    pass

class ConfigFileNotFoundError(ConfigError):
    """Raised when a specific configuration file (e.g., development.yaml) cannot be found."""
    pass

class InvalidYamlError(ConfigError):
    """Raised when a configuration file contains invalid YAML syntax or is not a dictionary."""
    pass

class ConfigurationManager:
    """
    Manages loading and accessing configuration settings from YAML files.

    This class is implemented as a singleton. The first time an instance is created,
    it loads the configuration. Subsequent instantiations return the existing instance.
    """
    _instance: Optional['ConfigurationManager'] = None
    _config: Dict[str, Any] = {}
    _current_env: str = ""

    def __new__(cls) -> 'ConfigurationManager':
        """
        Ensures that only one instance of ConfigurationManager is created (Singleton pattern).
        Loads configuration upon first instantiation.
        """
        if cls._instance is None:
            cls._instance = super(ConfigurationManager, cls).__new__(cls)
            # Initial load attempt. If APP_ENV is not set, loads DEFAULT_ENV.
            # Errors during this initial load (e.g., file not found for default env) will propagate.
            cls._instance.load_config() 
        return cls._instance

    def load_config(self, env: Optional[str] = None) -> None:
        """
        Loads configuration from a YAML file corresponding to the specified environment.

        The environment is determined in the following order of precedence:
        1. The `env` parameter passed to this method.
        2. The `APP_ENV` environment variable.
        3. `DEFAULT_ENV` (if neither of the above is set).

        Args:
            env (Optional[str]): The specific environment name (e.g., "production") to load.
                                 If None, uses APP_ENV or DEFAULT_ENV.

        Raises:
            ConfigFileNotFoundError: If the YAML file for the target environment is not found.
            InvalidYamlError: If the YAML file is malformed or not a dictionary.
        """
        self._current_env = env or os.getenv("APP_ENV", DEFAULT_ENV)
        config_file_path = os.path.join(CONFIG_DIR, f"{self._current_env}.yaml")

        try:
            with open(config_file_path, "r") as f:
                self._config = yaml.safe_load(f)
        except FileNotFoundError:
            raise ConfigFileNotFoundError(
                f"Configuration file not found for environment '{self._current_env}' at '{config_file_path}'. "
                f"Ensure '{self._current_env}.yaml' exists in the '{CONFIG_DIR}' directory."
            )
        except yaml.YAMLError as e:
            raise InvalidYamlError(
                f"Error parsing YAML in configuration file '{config_file_path}': {e}"
            )
        if not isinstance(self._config, dict):
             raise InvalidYamlError(
                f"Configuration file '{config_file_path}' does not contain a valid YAML dictionary."
            )


    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Retrieves a configuration value for the given key.

        Supports accessing nested values using dot notation (e.g., "database.host").
        If the key is not found, returns the provided default value.

        Args:
            key (str): The configuration key to retrieve. Can use dot notation
                       for nested structures (e.g., "parent.child.key").
            default (Optional[Any]): The value to return if the key is not found.
                                     Defaults to None.

        Returns:
            Any: The configuration value if found, otherwise the default value.
        """
        keys = key.split(".")
        value = self._config # Start with the full configuration dictionary
        try:
            for k_part in keys:
                if isinstance(value, dict):
                    value = value[k_part]  # Traverse into the nested dictionary
                else:
                    # Current value is not a dictionary, so cannot traverse further.
                    # This happens if a key for a non-dict item is part of a longer path.
                    return default
            return value
        except (KeyError, TypeError):
            # KeyError if a part of the key is not found.
            # TypeError if trying to access a non-dictionary value with further key parts.
            return default

    def reload_config(self, env: Optional[str] = None) -> None:
        """
        Reloads the configuration, potentially for a different environment.

        This method re-runs the `load_config` process. It's useful if configuration
        files have been updated externally or if switching environments dynamically (rarely needed).

        Args:
            env (Optional[str]): The environment to reload. If None, reloads the
                                 currently active environment.
        """
        # Note: Dynamic reloading by just re-calling load_config is basic.
        # More advanced scenarios might involve file system monitoring (e.g., using watchdog)
        # or pub/sub mechanisms for configuration updates in distributed systems.
        # This simple reload is primarily for testing or specific manual refresh needs.
        old_env = self._current_env
        self.load_config(env)
        # TODO: Replace print with logger call (e.g., logger.info) once logger is integrated.
        # This print statement is kept for now as per original code but should be updated.
        print(f"Configuration reloaded. Switched from '{old_env}' to '{self._current_env}' if env was specified, otherwise refreshed '{self._current_env}'.")


    @property
    def current_environment(self) -> str:
        """
        Returns the name of the currently loaded configuration environment.

        Returns:
            str: The name of the current environment (e.g., "development", "production").
        """
        return self._current_env

# Global instance of ConfigurationManager to be used by other modules.
# This instance is created when the module is first imported, triggering the initial
# configuration load via __new__ and load_config().
config_manager = ConfigurationManager()

def get_config(key: str, default: Optional[Any] = None) -> Any:
    """
    A convenience function to access configuration values via the global `config_manager`.

    Args:
        key (str): The configuration key (dot notation for nested values).
        default (Optional[Any]): Default value if the key is not found.

    Returns:
        Any: The configuration value or the default.
    """
    return config_manager.get(key, default)

# The if __name__ == "__main__": block has been migrated to tests/core/test_config.py
# and was removed in a previous step.
