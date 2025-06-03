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

@pytest.fixture
def mock_config_manager(monkeypatch): # Added monkeypatch here
    mock_cm_instance = mock.Mock(spec=ConfigManager)
    mock_cm_instance.get_workspace_path.return_value = "/mocked/workspace/from/config"

    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr(MOCK_CONFIG_MANAGER_PATH, mock_cm_constructor)
    return mock_cm_constructor, mock_cm_instance

def test_archive_story_handler_basic_call(mock_config_manager): # Added mock_config_manager fixture
    """Test with minimal arguments, expecting orchestrator to be called."""
    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator:
        story_url = "http://example.com/story"
        archive_story_handler(
            story_url=story_url,
            output_dir=None,
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root="/mocked/workspace/from/config", # From mock_config_manager
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None
        )

def test_archive_story_handler_with_output_dir(mock_config_manager): # Added mock_config_manager fixture
    """Test that output_dir overrides config_manager."""
    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator:
        story_url = "http://example.com/story"
        custom_output_dir = "/custom/output"
        archive_story_handler(
            story_url=story_url,
            output_dir=custom_output_dir,
            # ... other options ...
            ebook_title_override="Title",
            keep_temp_files=True,
            force_reprocessing=True,
            sentence_removal_file="/path/to/rules.json",
            no_sentence_removal=True, # This should mean sentence_removal_file is passed but orchestrator handles the 'no'
            chapters_per_volume=50
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root=custom_output_dir, # Custom output dir is used
            ebook_title_override="Title",
            keep_temp_files=True,
            force_reprocessing=True,
            sentence_removal_file="/path/to/rules.json",
            no_sentence_removal=True,
            chapters_per_volume=50
        )
        # Ensure ConfigManager was NOT called to get path if output_dir is provided
        mock_constructor, mock_instance = mock_config_manager
        mock_instance.get_workspace_path.assert_not_called()


def test_archive_story_handler_config_manager_failure(monkeypatch):
    """Test fallback to DEFAULT_WORKSPACE_PATH if ConfigManager fails."""
    # Mock ConfigManager to raise an exception
    mock_cm_constructor = mock.Mock(side_effect=Exception("ConfigManager boom!"))
    monkeypatch.setattr(MOCK_CONFIG_MANAGER_PATH, mock_cm_constructor)

    with mock.patch(MOCK_ORCHESTRATOR_PATH) as mock_orchestrator:
        story_url = "http://example.com/story"
        archive_story_handler(
            story_url=story_url,
            output_dir=None, # Ensure fallback is triggered
            # ... other defaults ...
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None
        )
        mock_orchestrator.assert_called_once_with(
            story_url=story_url,
            workspace_root=DEFAULT_WORKSPACE_PATH, # Should use default
            # ... other defaults ...
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None
        )

# Add more tests for other option combinations if necessary
