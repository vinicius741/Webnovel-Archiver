import pytest
from unittest import mock
import os

# Modules to test
from webnovel_archiver.cli.handlers import archive_story_handler
from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH

# Mock the core orchestrator function directly where it's imported in handlers
MOCK_ORCHESTRATOR_PATH = "webnovel_archiver.cli.handlers.call_orchestrator_archive_story"

# Mock ConfigManager if it's used for default path
MOCK_CONFIG_MANAGER_PATH = "webnovel_archiver.cli.handlers.ConfigManager"
MOCK_OS_PATH_EXISTS = "webnovel_archiver.cli.handlers.os.path.exists"
MOCK_LOGGER_PATH = "webnovel_archiver.cli.handlers.logger"


@pytest.fixture
def mock_config_manager_instance(monkeypatch):
    """Mocks the ConfigManager instance and its constructor."""
    mock_cm_instance = mock.Mock(spec=ConfigManager)
    # Set default return values for methods that might be called
    mock_cm_instance.get_workspace_path.return_value = "/mocked/workspace/from/config"
    # This will be overridden in specific tests if needed
    mock_cm_instance.get_default_sentence_removal_file.return_value = None

    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr(MOCK_CONFIG_MANAGER_PATH, mock_cm_constructor)
    return mock_cm_instance # Return the instance for easy modification in tests

def test_archive_story_handler_basic_call(mock_config_manager_instance):
    """Test with minimal arguments, expecting orchestrator to be called."""
    # Ensure default sentence removal is None if not configured
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = None

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=False): # Default to false for os.path.exists
        story_url = "http://example.com/story"
        archive_story_handler(
            story_url=story_url,
            output_dir=None,
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None, # Renamed in handler
            no_sentence_removal=False,
            chapters_per_volume=None
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root="/mocked/workspace/from/config",
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None, # Expect None as per new logic
            no_sentence_removal=False,
            chapters_per_volume=None,
            progress_callback=mock.ANY # Added to match actual call
        )

def test_archive_story_handler_with_output_dir(mock_config_manager_instance):
    """Test that output_dir overrides config_manager for workspace_root."""
    # This test now focuses on output_dir overriding workspace_root.
    # Sentence removal aspects will be covered by new dedicated tests.
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = None # Default behavior

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=True): # Assume files exist unless specified
        story_url = "http://example.com/story"
        custom_output_dir = "/custom/output"
        cli_sr_file = "/path/to/cli_rules.json"

        archive_story_handler(
            story_url=story_url,
            output_dir=custom_output_dir,
            ebook_title_override="Title",
            keep_temp_files=True,
            force_reprocessing=True,
            cli_sentence_removal_file=cli_sr_file, # Provide a CLI SR file
            no_sentence_removal=False,             # Explicitly not disabling SR
            chapters_per_volume=50
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root=custom_output_dir, # Custom output dir is used
            ebook_title_override="Title",
            keep_temp_files=True,
            force_reprocessing=True,
            sentence_removal_file=cli_sr_file, # Expect CLI file to be used
            no_sentence_removal=False,
            chapters_per_volume=50,
            progress_callback=mock.ANY # Added
        )
        # Ensure ConfigManager.get_workspace_path was NOT called
        mock_config_manager_instance.get_workspace_path.assert_not_called()
        # ConfigManager IS called for sentence removal file, so get_default_sentence_removal_file might be.
        # We are not asserting on get_default_sentence_removal_file calls here, focusing on workspace_root.

def test_archive_story_handler_config_manager_workspace_failure(monkeypatch):
    """Test fallback to DEFAULT_WORKSPACE_PATH if ConfigManager fails for workspace path."""
    # Mock ConfigManager constructor to raise an exception for get_workspace_path
    # but allow get_default_sentence_removal_file to work.
    mock_cm_instance = mock.Mock(spec=ConfigManager)
    mock_cm_instance.get_workspace_path.side_effect = Exception("ConfigManager workspace boom!")
    mock_cm_instance.get_default_sentence_removal_file.return_value = None # Default SR behavior

    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr(MOCK_CONFIG_MANAGER_PATH, mock_cm_constructor)

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=False):
        story_url = "http://example.com/story"
        archive_story_handler(
            story_url=story_url,
            output_dir=None, # Ensure fallback is triggered for workspace
            # ... other defaults ...
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root=DEFAULT_WORKSPACE_PATH, # Should use default
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None,
            progress_callback=mock.ANY # Added
        )

# New tests for sentence removal logic

def test_archive_story_uses_default_sentence_removal_file(mock_config_manager_instance, caplog):
    """Test handler uses default sentence removal file if configured and exists."""
    default_sr_path = "/path/to/default_rules.json"
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = default_sr_path

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=True) as mock_exists:

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            # other args as None or False
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None
        )

        mock_exists.assert_any_call(default_sr_path) # Check that existence of default path was tested
        mock_orchestrator.assert_called_once_with(
            story_url="http://example.com/story",
            workspace_root=mock_config_manager_instance.get_workspace_path(),
            sentence_removal_file=default_sr_path,
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None, progress_callback=mock.ANY
        )
        assert f"Using default sentence removal file from config: {default_sr_path}" in caplog.text

def test_archive_story_prioritizes_cli_sentence_removal_file(mock_config_manager_instance, caplog):
    """Test CLI SR file is prioritized over default."""
    default_sr_path = "/path/to/default_rules.json"
    cli_sr_path = "/path/to/cli_rules.json"
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = default_sr_path

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=True) as mock_exists:

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            cli_sentence_removal_file=cli_sr_path,
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None
        )

        mock_exists.assert_any_call(cli_sr_path)
        mock_orchestrator.assert_called_once_with(
            story_url="http://example.com/story",
            workspace_root=mock_config_manager_instance.get_workspace_path(),
            sentence_removal_file=cli_sr_path,
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None, progress_callback=mock.ANY
        )
        assert f"Using sentence removal file provided via CLI: {cli_sr_path}" in caplog.text
        # Ensure default is not checked if CLI is provided and exists
        mock_config_manager_instance.get_default_sentence_removal_file.assert_not_called()


def test_archive_story_respects_no_sentence_removal_flag(mock_config_manager_instance, caplog):
    """Test --no-sentence-removal disables SR even if default/CLI is set."""
    default_sr_path = "/path/to/default_rules.json"
    cli_sr_path = "/path/to/cli_rules.json" # This won't be used
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = default_sr_path

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=True): # Assume files exist

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            cli_sentence_removal_file=cli_sr_path, # Provide CLI one
            no_sentence_removal=True, # Explicitly disable
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None
        )

        mock_orchestrator.assert_called_once_with(
            story_url="http://example.com/story",
            workspace_root=mock_config_manager_instance.get_workspace_path(),
            sentence_removal_file=None, # Should be None
            no_sentence_removal=True,   # Should be True
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None, progress_callback=mock.ANY
        )
        assert "Sentence removal explicitly disabled" in caplog.text
        mock_config_manager_instance.get_default_sentence_removal_file.assert_not_called()


def test_archive_story_warns_if_default_sr_file_not_found(mock_config_manager_instance, caplog):
    """Test warning if default SR file is configured but not found."""
    non_existent_default_sr_path = "/path/to/non_existent_default.json"
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = non_existent_default_sr_path

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=False) as mock_exists: # Mock os.path.exists to return False

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None
        )

        mock_exists.assert_any_call(non_existent_default_sr_path)
        mock_orchestrator.assert_called_once_with(
            story_url="http://example.com/story",
            workspace_root=mock_config_manager_instance.get_workspace_path(),
            sentence_removal_file=None, # Should be None as file not found
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None, progress_callback=mock.ANY
        )
        assert f"Default sentence removal file configured at '{non_existent_default_sr_path}' not found." in caplog.text

def test_archive_story_warns_if_cli_sr_file_not_found(mock_config_manager_instance, caplog):
    """Test warning if CLI SR file is provided but not found."""
    non_existent_cli_sr_path = "/path/to/non_existent_cli.json"
    # Default config shouldn't matter here, but let's ensure it's not called
    mock_config_manager_instance.get_default_sentence_removal_file.return_value = "/path/to/some_default.json"

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator, \
         mock.patch(MOCK_OS_PATH_EXISTS, return_value=False) as mock_exists: # Mock os.path.exists to return False

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            cli_sentence_removal_file=non_existent_cli_sr_path,
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None
        )

        mock_exists.assert_any_call(non_existent_cli_sr_path)
        mock_orchestrator.assert_called_once_with(
            story_url="http://example.com/story",
            workspace_root=mock_config_manager_instance.get_workspace_path(),
            sentence_removal_file=None, # Should be None as file not found
            no_sentence_removal=False,
            ebook_title_override=None, keep_temp_files=False, force_reprocessing=False, chapters_per_volume=None, progress_callback=mock.ANY
        )
        assert f"Sentence removal file provided via CLI not found: {non_existent_cli_sr_path}" in caplog.text
        mock_config_manager_instance.get_default_sentence_removal_file.assert_not_called()
