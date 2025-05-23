"""
Custom exception classes for the AI Scraper Framework.
"""

class AIScraperFrameworkError(Exception):
    """
    Base class for all custom exceptions in the AI Scraper Framework.

    Attributes:
        message (str): A human-readable description of the error.
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


# --- Configuration Related Exceptions ---
class ConfigurationError(AIScraperFrameworkError):
    """
    Raised for errors related to application configuration.
    This could include issues with loading, accessing, or validating configuration data.
    """
    def __init__(self, message: str):
        super().__init__(message)


# --- Task Management Related Exceptions ---
class TaskManagementError(AIScraperFrameworkError):
    """
    Raised for errors related to task management, such as queuing, execution, or scheduling.
    """
    def __init__(self, message: str):
        super().__init__(message)


# --- Component Related Exceptions ---
class ComponentError(AIScraperFrameworkError):
    """
    A general base class for errors originating from within a specific component
    (e.g., Renderer, Vision, Extractor, Storage, Scheduler).
    This class can be subclassed by individual components for more specific error reporting.

    Attributes:
        component_name (str): Name of the component where the error originated.
    """
    def __init__(self, component_name: str, message: str):
        full_message = f"Error in component '{component_name}': {message}"
        super().__init__(full_message)
        self.component_name = component_name


class RendererError(ComponentError):
    """Raised for errors specific to the Renderer component (e.g., page rendering, JavaScript execution)."""
    def __init__(self, message: str):
        super().__init__(component_name="Renderer", message=message)


class VisionError(ComponentError):
    """Raised for errors specific to the Vision component (e.g., image analysis, element detection)."""
    def __init__(self, message: str):
        super().__init__(component_name="Vision", message=message)


class ExtractorError(ComponentError):
    """Raised for errors specific to the Extractor component (e.g., parsing HTML, data extraction logic)."""
    def __init__(self, message: str):
        super().__init__(component_name="Extractor", message=message)


class StorageError(ComponentError):
    """Raised for errors specific to the Storage component (e.g., file system operations, database interactions)."""
    def __init__(self, message: str):
        super().__init__(component_name="Storage", message=message)


class SchedulerError(ComponentError):
    """Raised for errors specific to the Scheduler component (e.g., task scheduling, queue management)."""
    def __init__(self, message: str):
        super().__init__(component_name="Scheduler", message=message)


# --- Database Related Exceptions ---
class DatabaseError(AIScraperFrameworkError):
    """
    Raised for errors related to database operations, such as connection issues,
    query failures, or transaction problems.

    Attributes:
        original_exception (Optional[Exception]): The underlying database exception, if any.
    """
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.original_exception = original_exception
        full_message = f"{message}"
        if original_exception:
            full_message += f" (Original exception: {str(original_exception)})"
        super().__init__(full_message)


# --- Model Related Exceptions ---
class ModelError(AIScraperFrameworkError):
    """
    Raised for errors related to machine learning models.
    This includes issues like model loading failures, prediction errors,
    or problems with model artifacts.

    Attributes:
        model_name (str): The name or identifier of the model that caused the error.
    """
    def __init__(self, model_name: str, message: str):
        full_message = f"Error related to model '{model_name}': {message}"
        super().__init__(full_message)
        self.model_name = model_name

# The if __name__ == "__main__": block was removed as part of test formalization.
# Formal tests should reside in the tests/ directory.
