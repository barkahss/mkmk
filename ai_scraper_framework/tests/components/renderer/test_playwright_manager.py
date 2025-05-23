import pytest
from unittest.mock import MagicMock

from ai_scraper_framework.components.renderer.playwright_manager import PlaywrightManager
from ai_scraper_framework.core.exceptions import RendererError
# from ai_scraper_framework.core.config import ConfigurationManager # Only if using real one

# Mock ConfigurationManager for testing PlaywrightManager's config handling
class MockConfigurationManager:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else {}

    def get(self, key, default=None):
        # Simplified get for dot notation used in PlaywrightManager
        try:
            value = self.settings
            for k_part in key.split('.'):
                value = value[k_part]
            return value
        except KeyError:
            return default
        except TypeError: # Handle cases where settings might not be a dict at some level
             return default


@pytest.mark.asyncio
async def test_playwright_manager_init_default():
    """Test PlaywrightManager initializes with default browser type (chromium) when no config."""
    manager = PlaywrightManager(config=None)
    assert manager.browser_type == PlaywrightManager.DEFAULT_BROWSER_TYPE # 'chromium'
    # Test __aenter__ and __aexit__ for basic startup/shutdown (will fail if binaries not installed)
    try:
        async with manager:
            assert manager.browser is not None # Check if browser was launched
    except RendererError as e:
        # This is expected if browser binaries are not installed.
        # The error message should indicate failure to launch.
        assert "Failed to initialize Playwright or launch browser" in str(e)
        print(f"\nInit default test: Caught expected RendererError (no binaries?): {e}")
    except Exception as e:
        pytest.fail(f"Init default test: Unexpected exception during __aenter__/__aexit__: {e}")


@pytest.mark.asyncio
async def test_playwright_manager_init_with_config():
    """Test PlaywrightManager initializes with browser type from mock ConfigurationManager."""
    mock_config = MockConfigurationManager(settings={"components": {"playwright_manager": {"browser_type": "firefox"}}})
    manager = PlaywrightManager(config=mock_config)
    assert manager.browser_type == "firefox"
    try:
        async with manager: # Attempt to launch firefox
            pass # If it enters and exits, basic launch is ok
    except RendererError as e:
        assert "Failed to initialize Playwright or launch browser" in str(e)
        print(f"\nInit with config (firefox) test: Caught expected RendererError (no binaries?): {e}")
    except Exception as e:
        pytest.fail(f"Init with config (firefox) test: Unexpected exception: {e}")


@pytest.mark.asyncio
async def test_playwright_manager_init_invalid_browser_type_config():
    """Test PlaywrightManager raises RendererError for invalid browser type from config."""
    mock_config = MockConfigurationManager(settings={"components": {"playwright_manager": {"browser_type": "explorer"}}})
    with pytest.raises(RendererError) as excinfo:
        PlaywrightManager(config=mock_config)
    assert "Unsupported browser type: explorer" in str(excinfo.value)


@pytest.mark.asyncio
async def test_playwright_manager_init_invalid_browser_type_no_config_default_override_bad():
    """Test PlaywrightManager raises RendererError if its DEFAULT_BROWSER_TYPE was somehow bad."""
    # This tests internal consistency more than config.
    original_default = PlaywrightManager.DEFAULT_BROWSER_TYPE
    PlaywrightManager.DEFAULT_BROWSER_TYPE = "netscape" # Temporarily set to an invalid one
    with pytest.raises(RendererError) as excinfo:
        PlaywrightManager(config=None)
    assert "Unsupported browser type: netscape" in str(excinfo.value)
    PlaywrightManager.DEFAULT_BROWSER_TYPE = original_default # Restore


@pytest.mark.asyncio
async def test_get_page_content_success(monkeypatch):
    """
    Test get_page_content successfully fetches content.
    This is an integration test and requires browser binaries.
    If binaries are not present, PlaywrightManager's __aenter__ will raise RendererError.
    """
    # Mock successful browser launch and page operations
    mock_playwright_instance = MagicMock()
    mock_browser_instance = MagicMock()
    mock_page_instance = MagicMock()

    async def mock_start(): return mock_playwright_instance
    async def mock_launch(*args, **kwargs): return mock_browser_instance
    async def mock_new_page(*args, **kwargs): return mock_page_instance
    async def mock_goto(*args, **kwargs): pass
    async def mock_content(*args, **kwargs): return "<html><body><h1>Test Page</h1></body></html>"
    async def mock_close_page(*args, **kwargs): pass
    async def mock_close_browser(*args, **kwargs): pass
    async def mock_stop_playwright(*args, **kwargs): pass

    monkeypatch.setattr("playwright.async_api.async_playwright.start", mock_start)
    
    manager = PlaywrightManager(config=None) # Uses default chromium
    # We need to mock the specific browser launcher, e.g., chromium.launch()
    # This is getting complicated due to the dynamic getattr(self.playwright, self.browser_type)
    # For a true unit test of get_page_content, we'd assume __aenter__ worked.
    # Let's simplify by directly mocking parts of an already "entered" manager for this unit-like test.

    manager.playwright = mock_playwright_instance
    manager.browser = mock_browser_instance
    
    # Mock the browser type specific launcher if __aenter__ was real
    mock_browser_launcher = MagicMock()
    mock_browser_launcher.launch = mock_launch
    # setattr(mock_playwright_instance, manager.browser_type, mock_browser_launcher) # This would be for full __aenter__

    mock_browser_instance.new_page = mock_new_page
    mock_page_instance.goto = mock_goto
    mock_page_instance.content = mock_content
    mock_page_instance.close = mock_close_page
    mock_browser_instance.close = mock_close_browser
    mock_playwright_instance.stop = mock_stop_playwright
    
    # Test get_page_content directly, assuming manager is already "entered"
    # This bypasses __aenter__ for a more focused unit test on get_page_content logic
    content = await manager.get_page_content("http://example.com")
    assert "<h1>Test Page</h1>" in content
    mock_page_instance.goto.assert_called_once_with("http://example.com", wait_until='domcontentloaded', timeout=30000)


@pytest.mark.asyncio
async def test_get_page_content_navigation_error(monkeypatch):
    """
    Test get_page_content raises RendererError on navigation failure.
    Similar to above, this unit-like test bypasses __aenter__.
    """
    mock_playwright_instance = MagicMock()
    mock_browser_instance = MagicMock()
    mock_page_instance = MagicMock()

    async def mock_new_page(*args, **kwargs): return mock_page_instance
    async def mock_goto_fail(*args, **kwargs): raise Exception("Navigation Timeout") # Simulate Playwright error
    async def mock_close_page(*args, **kwargs): pass

    manager = PlaywrightManager(config=None)
    manager.playwright = mock_playwright_instance # Assume __aenter__ part 1 succeeded
    manager.browser = mock_browser_instance    # Assume browser launched in __aenter__

    mock_browser_instance.new_page = mock_new_page
    mock_page_instance.goto = mock_goto_fail
    mock_page_instance.close = mock_close_page

    with pytest.raises(RendererError) as excinfo:
        await manager.get_page_content("http://nonexistentdomain123.com")
    assert "Failed to get content from URL 'http://nonexistentdomain123.com'" in str(excinfo.value)
    assert "Navigation Timeout" in str(excinfo.value) # Check original error is part of message


@pytest.mark.integration # Mark as integration test, can be skipped if no env with browsers
@pytest.mark.asyncio
async def test_playwright_manager_integration_example_com():
    """Full integration test for example.com (requires browser binaries)."""
    manager = PlaywrightManager(config=None) # Default chromium
    try:
        async with manager:
            content = await manager.get_page_content("http://example.com")
            assert "<h1>Example Domain</h1>" in content
    except RendererError as e:
        # This is the expected path if browser binaries are not installed
        print(f"\nIntegration test (example.com) failed as expected (no binaries?): {e}")
        assert "Failed to initialize Playwright or launch browser" in str(e) or \
               "Executable doesn't exist" in str(e) # Possible error messages
    except Exception as e:
        pytest.fail(f"Integration test (example.com) failed with unexpected error: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_playwright_manager_integration_navigation_error():
    """Full integration test for navigation error (requires browser binaries)."""
    manager = PlaywrightManager(config=None) # Default chromium
    try:
        async with manager:
            with pytest.raises(RendererError) as excinfo:
                await manager.get_page_content("http://thisdomaindefinitelydoesnotexist12345abc.com")
            assert "Failed to get content" in str(excinfo.value)
    except RendererError as e:
        # This path is taken if browser launch itself fails (no binaries)
        print(f"\nIntegration test (nav error) failed during manager setup (no binaries?): {e}")
        assert "Failed to initialize Playwright or launch browser" in str(e) or \
               "Executable doesn't exist" in str(e)
    except Exception as e:
        pytest.fail(f"Integration test (nav error) failed with unexpected error: {e}")

# Note: To run integration tests, use: pytest -m integration
# To skip them: pytest -m "not integration"
# The mocking setup for get_page_content_success and _navigation_error provides more of a unit test feel
# for the get_page_content method's internal logic, assuming the browser and page objects are valid.
# The __init__ tests focus on configuration and basic browser type validation.
# The integration tests provide end-to-end validation if the environment supports it.
# The `if __name__ == '__main__':` block from playwright_manager.py should be removed.
