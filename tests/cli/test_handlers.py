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
MOCK_OS_PATH_EXISTS = "webnovel_archiver.cli.handlers.os.path.exists" # Used for files
MOCK_OS_PATH_ISDIR = "webnovel_archiver.cli.handlers.os.path.isdir" # Used for directories
MOCK_OS_LISTDIR = "webnovel_archiver.cli.handlers.os.listdir"
MOCK_LOGGER_PATH = "webnovel_archiver.cli.handlers.logger" # Already present
MOCK_CLICK_ECHO_PATH = "webnovel_archiver.cli.handlers.click.echo" # For capturing user messages

# Mocks for cloud_backup_handler specific dependencies
MOCK_GDRIVE_SYNC_PATH = "webnovel_archiver.cli.handlers.GDriveSync"
MOCK_PM_PATH = "webnovel_archiver.cli.handlers.pm" # For progress_manager module


# Import the handler to be tested
from webnovel_archiver.cli.handlers import cloud_backup_handler


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


# Tests for cloud_backup_handler HTML report upload

@pytest.fixture
def mock_cloud_backup_common_deps(monkeypatch):
    """Fixture to mock common dependencies for cloud_backup_handler tests."""
    mock_cm_instance = mock.Mock(spec=ConfigManager)
    mock_cm_instance.get_workspace_path.return_value = "/mocked/workspace"
    monkeypatch.setattr(MOCK_CONFIG_MANAGER_PATH, mock.Mock(return_value=mock_cm_instance))

    mock_gdrive_sync_instance = mock.Mock(spec_set=["create_folder_if_not_exists", "upload_file", "get_file_metadata", "is_remote_older"])
    mock_gdrive_sync_instance.create_folder_if_not_exists.return_value = "dummy_root_folder_id"
    # upload_file mock will be configured per test as needed
    monkeypatch.setattr(MOCK_GDRIVE_SYNC_PATH, mock.Mock(return_value=mock_gdrive_sync_instance))

    # Mock progress_manager functions
    monkeypatch.setattr(f"{MOCK_PM_PATH}.get_progress_filepath", mock.Mock(return_value="/mocked/workspace/archival_status/story1/progress_status.json"))
    monkeypatch.setattr(f"{MOCK_PM_PATH}.load_progress", mock.Mock(return_value={"story_id": "story1", "title": "Test Story"}))
    monkeypatch.setattr(f"{MOCK_PM_PATH}.get_epub_file_details", mock.Mock(return_value=[])) # No epubs by default
    monkeypatch.setattr(f"{MOCK_PM_PATH}.update_cloud_backup_status", mock.Mock())
    monkeypatch.setattr(f"{MOCK_PM_PATH}.save_progress", mock.Mock())


    # Mock os.path.isdir to simulate that archival_status and ebooks_base_dir exist
    # and that story_id directories exist if os.listdir returns them.
    def mock_isdir_logic(path):
        if path in ["/mocked/workspace/archival_status", "/mocked/workspace/ebooks", "/mocked/workspace/archival_status/story1"]:
            return True
        return False
    monkeypatch.setattr(MOCK_OS_PATH_ISDIR, mock.Mock(side_effect=mock_isdir_logic))

    # Mock os.listdir to return no stories by default to simplify tests not focused on story processing loop
    monkeypatch.setattr(MOCK_OS_LISTDIR, mock.Mock(return_value=[]))

    # Mock click.echo to check output
    mock_echo = mock.Mock()
    monkeypatch.setattr(MOCK_CLICK_ECHO_PATH, mock_echo)

    # Mock logger
    mock_logger_instance = mock.Mock(spec_set=["info", "warning", "error", "debug"])
    monkeypatch.setattr(MOCK_LOGGER_PATH, mock_logger_instance)


    return {
        "config_manager": mock_cm_instance,
        "gdrive_sync": mock_gdrive_sync_instance,
        "logger": mock_logger_instance,
        "click_echo": mock_echo,
        "os_path_exists_mock": monkeypatch.getattr(MOCK_OS_PATH_EXISTS) # Return this if needed for modification
    }


def test_cloud_backup_handler_uploads_html_report_if_exists(mock_cloud_backup_common_deps, monkeypatch):
    """Test HTML report is uploaded if it exists."""
    mock_gdrive_sync = mock_cloud_backup_common_deps["gdrive_sync"]
    mock_logger = mock_cloud_backup_common_deps["logger"]
    mock_click_echo = mock_cloud_backup_common_deps["click_echo"]

    report_path = "/mocked/workspace/reports/archive_report.html"
    # Ensure os.path.exists returns True only for the report path in this test's context
    monkeypatch.setattr(MOCK_OS_PATH_EXISTS, lambda path: path == report_path)

    # Call the handler
    cloud_backup_handler(
        story_id=None,
        cloud_service_name='gdrive',
        force_full_upload=False,
        gdrive_credentials_path='dummy_creds.json',
        gdrive_token_path='dummy_token.json'
    )

    # Assert upload_file was called for the report
    mock_gdrive_sync.upload_file.assert_called_once_with(
        local_file_path=report_path,
        remote_folder_id="dummy_root_folder_id",
        remote_file_name="archive_report.html"
    )

    mock_logger.info.assert_any_call(f"Checking for HTML report at: {report_path}")
    mock_logger.info.assert_any_call("Attempting to upload HTML report...")
    mock_logger.info.assert_any_call(f"Uploading report '{report_path}' to cloud folder ID 'dummy_root_folder_id'.")
    assert any("Successfully uploaded HTML report" in str(call_args) for call_args in mock_click_echo.call_args_list)


def test_cloud_backup_handler_skips_html_report_if_not_exists(mock_cloud_backup_common_deps, monkeypatch):
    """Test HTML report is skipped if it does not exist."""
    mock_gdrive_sync = mock_cloud_backup_common_deps["gdrive_sync"]
    mock_logger = mock_cloud_backup_common_deps["logger"]
    mock_click_echo = mock_cloud_backup_common_deps["click_echo"]

    report_path = "/mocked/workspace/reports/archive_report.html"
    monkeypatch.setattr(MOCK_OS_PATH_EXISTS, lambda path: path != report_path and path != 'dummy_creds.json' and path != 'dummy_token.json')


    cloud_backup_handler(
        story_id=None,
        cloud_service_name='gdrive',
        force_full_upload=False,
        gdrive_credentials_path='dummy_creds.json',
        gdrive_token_path='dummy_token.json'
    )

    mock_gdrive_sync.upload_file.assert_not_called()
    mock_logger.info.assert_any_call(f"HTML report not found at {report_path}, skipping upload.")
    assert any(f"HTML report not found at {report_path}, skipping upload." in str(call_args) for call_args in mock_click_echo.call_args_list)


def test_cloud_backup_handler_handles_report_upload_failure(mock_cloud_backup_common_deps, monkeypatch):
    """Test graceful handling of report upload failure."""
    mock_gdrive_sync = mock_cloud_backup_common_deps["gdrive_sync"]
    mock_logger = mock_cloud_backup_common_deps["logger"]
    mock_click_echo = mock_cloud_backup_common_deps["click_echo"]

    report_path = "/mocked/workspace/reports/archive_report.html"
    monkeypatch.setattr(MOCK_OS_PATH_EXISTS, lambda path: path == report_path)

    mock_gdrive_sync.upload_file.side_effect = ConnectionError("Simulated upload error")

    cloud_backup_handler(
        story_id=None,
        cloud_service_name='gdrive',
        force_full_upload=False,
        gdrive_credentials_path='dummy_creds.json',
        gdrive_token_path='dummy_token.json'
    )

    mock_gdrive_sync.upload_file.assert_called_once_with(
        local_file_path=report_path,
        remote_folder_id="dummy_root_folder_id",
        remote_file_name="archive_report.html"
    )

    mock_logger.error.assert_any_call("Connection error during HTML report upload: Simulated upload error", exc_info=True)
    assert any("Error uploading HTML report: Simulated upload error" in str(call_args) for call_args in mock_click_echo.call_args_list)


def test_cloud_backup_uses_existing_cloud_base_id_for_report(mock_cloud_backup_common_deps, monkeypatch):
    """Test report uses cloud_base_folder_id set during story processing."""
    mock_gdrive_sync = mock_cloud_backup_common_deps["gdrive_sync"]
    mock_logger = mock_cloud_backup_common_deps["logger"]

    # Simulate one story being processed
    monkeypatch.setattr(MOCK_OS_LISTDIR, mock.Mock(return_value=["story1"]))

    # Mock GDriveSync's create_folder_if_not_exists for story processing
    # First call for base "Webnovel Archiver Backups", second for "story1" folder
    # This first call's return value should be used by the report logic later.
    mock_gdrive_sync.create_folder_if_not_exists.side_effect = [
        "story_proc_root_id", # ID for "Webnovel Archiver Backups"
        "story1_folder_id"    # ID for "story1"
    ]
    # Mock get_file_metadata to make story file appear non-existent or older, forcing upload attempt
    mock_gdrive_sync.get_file_metadata.return_value = None

    report_path = "/mocked/workspace/reports/archive_report.html"
    story_progress_file = "/mocked/workspace/archival_status/story1/progress_status.json"

    # os.path.exists needs to return True for:
    # - report_path
    # - story_progress_file (to enter the story processing block)
    # - gdrive_credentials_path / gdrive_token_path (if they are checked by GDriveSync init, though GDriveSync itself is mocked)
    # For simplicity, we assume GDriveSync init doesn't hit os.path.exists for creds/token in this unit test context.
    def selective_os_path_exists(path_to_check):
        if path_to_check == report_path: return True
        if path_to_check == story_progress_file: return True
        if path_to_check == 'dummy_creds.json': return True # Added to handle GDriveSync init if it checks
        if path_to_check == 'dummy_token.json': return True # Added
        return False
    monkeypatch.setattr(MOCK_OS_PATH_EXISTS, mock.Mock(side_effect=selective_os_path_exists))

    cloud_backup_handler(
        story_id=None,
        cloud_service_name='gdrive',
        force_full_upload=True, # Force story file upload to simplify mocking
        gdrive_credentials_path='dummy_creds.json',
        gdrive_token_path='dummy_token.json'
    )

    # Check calls to upload_file
    # Expected: one for story1's progress_status.json, one for archive_report.html
    report_upload_call_args = None
    story_file_upload_call_args = None

    for call_args_tuple in mock_gdrive_sync.upload_file.call_args_list:
        kwargs = call_args_tuple.kwargs
        if kwargs.get('remote_file_name') == "archive_report.html":
            report_upload_call_args = kwargs
        elif kwargs.get('remote_file_name') == "progress_status.json": # Name used in handler
            story_file_upload_call_args = kwargs

    assert story_file_upload_call_args is not None, "progress_status.json for story1 was not uploaded"
    assert story_file_upload_call_args['remote_folder_id'] == "story1_folder_id"

    assert report_upload_call_args is not None, "archive_report.html was not uploaded"
    assert report_upload_call_args['local_file_path'] == report_path
    assert report_upload_call_args['remote_folder_id'] == "story_proc_root_id" # Key assertion

    # Verify create_folder_if_not_exists was called for "Webnovel Archiver Backups" only ONCE
    base_folder_creation_calls = [
        args for args, kwargs in mock_gdrive_sync.create_folder_if_not_exists.call_args_list
        if args[0] == "Webnovel Archiver Backups"
    ]
    assert len(base_folder_creation_calls) == 1, \
        "create_folder_if_not_exists for 'Webnovel Archiver Backups' should only be called once (during story processing)"

    mock_logger.info.assert_any_call(f"Uploading report '{report_path}' to cloud folder ID 'story_proc_root_id'.")
