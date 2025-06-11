import pytest
import os
import json
from click.testing import CliRunner
from unittest import mock

from typing import Optional # Added Optional for type hints in mock signatures

# CLI entry point
from webnovel_archiver.cli.main import archiver
# For mocking the actual work if needed, to avoid network calls etc.
# The target for patching should be where the function is looked up (i.e., in the handlers module)
from webnovel_archiver.core.config_manager import ConfigManager # Corrected import
MOCK_ORCHESTRATOR_HANDLER_PATH = "webnovel_archiver.cli.handlers.call_orchestrator_archive_story"
# To control workspace for tests
from webnovel_archiver.core.storage.progress_manager import DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR
# RAW_CONTENT_DIR and PROCESSED_CONTENT_DIR are in orchestrator, not progress_manager
from webnovel_archiver.core.orchestrator import RAW_CONTENT_DIR, PROCESSED_CONTENT_DIR


@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def temp_workspace(tmp_path_factory):
    # Create a temporary workspace for each test that needs it
    # tmp_path_factory is session-scoped, so each test gets a fresh dir
    workspace_dir = tmp_path_factory.mktemp("integration_test_workspace")
    return str(workspace_dir)

@pytest.fixture
def mock_successful_orchestrator(monkeypatch):
    """Mocks the core orchestrator function to simulate a successful run
       without performing actual fetching or heavy processing."""
    """Mocks the core orchestrator function to simulate a successful run,
       including invoking callbacks and returning a summary."""

    # This list will store the expected sequence of calls for the orchestrator mock itself.
    # We are not checking callbacks here, but what the CLI passes to the orchestrator.
    # The callback testing is part of the orchestrator's unit tests.
    # Here, we ensure the CLI uses the callback.

    # The actual mock for the orchestrator function
    mock_orchestrator_func = mock.Mock()

    def side_effect_for_orchestrator(
        story_url: str,
        workspace_root: str,
        chapters_per_volume: Optional[int] = None,
        ebook_title_override: Optional[str] = None,
        keep_temp_files: bool = False,
        force_reprocessing: bool = False,
        sentence_removal_file: Optional[str] = None,
        no_sentence_removal: bool = False,
        progress_callback: Optional[callable] = None,
        epub_contents: Optional[str] = 'all' # Added for new option
    ):
        story_id = "test_story_id_123" # Simplified story_id generation
        effective_title = ebook_title_override if ebook_title_override else "Original Mock Title"

        # Simulate progress by calling the callback
        if progress_callback:
            progress_callback({"status": "info", "message": "Starting archival process..."})
            progress_callback({"status": "info", "message": "Fetching story metadata..."})
            progress_callback({"status": "info", "message": f"Successfully fetched metadata: {effective_title}"})
            progress_callback({"status": "info", "message": "Fetching chapter list..."})
            progress_callback({"status": "info", "message": "Found 1 chapters."}) # Simplified
            progress_callback({
                "status": "info", "message": "Processing chapter: Mock Chapter 1 (1/1)",
                "current_chapter_num": 1, "total_chapters": 1, "chapter_title": "Mock Chapter 1"
            })
            progress_callback({"status": "info", "message": "Successfully saved raw content for chapter: Mock Chapter 1", "chapter_title": "Mock Chapter 1"})
            progress_callback({"status": "info", "message": "Successfully saved processed content for chapter: Mock Chapter 1", "chapter_title": "Mock Chapter 1"})
            progress_callback({"status": "info", "message": "Starting EPUB generation..."})
            progress_callback({"status": "info", "message": f"Successfully generated EPUB file(s): ['{os.path.join(workspace_root, 'ebooks', story_id, effective_title + '.epub')}']"})
            if not keep_temp_files:
                progress_callback({"status": "info", "message": "Cleaning up temporary files..."})
                progress_callback({"status": "info", "message": "Successfully cleaned up temporary files."})
            progress_callback({"status": "info", "message": "Archival process completed."})

        # Simulate creation of progress file and some dirs
        progress_path = os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, story_id)
        os.makedirs(progress_path, exist_ok=True)

        # Simulate some content directories being made
        # In a real scenario, orchestrator creates these based on its internal logic.
        # Mock should reflect what CLI options might influence, e.g. keep_temp_files.
        if keep_temp_files:
             os.makedirs(os.path.join(workspace_root, RAW_CONTENT_DIR, story_id), exist_ok=True)
             os.makedirs(os.path.join(workspace_root, PROCESSED_CONTENT_DIR, story_id), exist_ok=True)


        progress_data = { # This is what would be saved by the real orchestrator
            "story_id": story_id,
            "story_url": story_url,
            "original_title": "Original Mock Title", # Base title
            "effective_title": effective_title,
            "downloaded_chapters": [{"chapter_title": "Mock Chapter 1", "local_raw_filename": "chap1_raw.html", "local_processed_filename": "chap1_proc.html"}],
            "force_reprocessing_used": force_reprocessing,
            "sentence_removal_config_used": sentence_removal_file if sentence_removal_file and not no_sentence_removal else \
                                            ("Disabled via --no-sentence-removal" if no_sentence_removal else None),
            "chapters_per_volume_setting": chapters_per_volume,
            "last_epub_processing": {
                "generated_epub_files": [os.path.join(workspace_root, "ebooks", story_id, effective_title + ".epub")]
            },
            "epub_contents_setting": epub_contents # Added for new option
        }
        # Simulate saving this progress data by the orchestrator
        with open(os.path.join(progress_path, "progress_status.json"), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)

        # Simulate what the real orchestrator returns
        summary = {
            "story_id": story_id,
            "title": effective_title,
            "chapters_processed": 1, # Simplified for mock
            "epub_files": [os.path.abspath(os.path.join(workspace_root, "ebooks", story_id, effective_title + ".epub"))],
            "workspace_root": os.path.abspath(workspace_root)
        }
        return summary

    mock_orchestrator_func.side_effect = side_effect_for_orchestrator
    monkeypatch.setattr(MOCK_ORCHESTRATOR_HANDLER_PATH, mock_orchestrator_func)
    return mock_orchestrator_func

def test_archive_story_successful_run_default_workspace(runner, mock_successful_orchestrator, temp_workspace, monkeypatch):
    """Test basic successful run using a temporary default workspace."""
    # Patch ConfigManager to use temp_workspace as default
    mock_cm_instance = mock.Mock(spec=ConfigManager) # Use spec for better mocking
    mock_cm_instance.get_workspace_path.return_value = temp_workspace
    mock_cm_instance.get_default_sentence_removal_file.return_value = None # Ensure it returns a valid path or None
    # get_gdrive_credentials_path and get_gdrive_token_path are not methods of ConfigManager, so remove attempts to mock them.
    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr("webnovel_archiver.cli.handlers.ConfigManager", mock_cm_constructor)

    story_url = "http://example.com/mockstory"
    result = runner.invoke(archiver, ['archive-story', story_url])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    # Check for some key progress messages
    assert "[INFO] Starting archival process..." in result.output
    assert "[INFO] Fetching story metadata..." in result.output
    assert "[INFO] Successfully fetched metadata: Original Mock Title" in result.output
    assert "[INFO] Processing chapter: Mock Chapter 1 (1/1)" in result.output
    assert "[INFO] Starting EPUB generation..." in result.output
    assert "[INFO] Cleaning up temporary files..." in result.output # Default is to clean

    # Check for the new detailed success message
    assert "✓ Archival process completed successfully!" in result.output
    assert "Title: Original Mock Title" in result.output
    assert "Story ID: test_story_id_123" in result.output
    assert "Chapters processed in this run: 1" in result.output
    assert "Generated EPUB file(s):" in result.output
    mock_epub_path = os.path.abspath(os.path.join(temp_workspace, "ebooks", "test_story_id_123", "Original Mock Title.epub"))
    assert f"- {mock_epub_path}" in result.output
    assert f"Workspace: {os.path.abspath(temp_workspace)}" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == temp_workspace
    assert callable(kwargs['progress_callback']) # Ensure callback was passed

    # Verify progress file was created by the mock
    progress_file = os.path.join(temp_workspace, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['story_url'] == story_url

    # Verify temp dirs are NOT present (default behavior, as keep_temp_files=False)
    # The mock orchestrator's side_effect does not create these if keep_temp_files is False
    # and it simulates the cleanup callback.
    # The actual deletion is mocked via shutil.rmtree in orchestrator unit tests.
    # Here we rely on the mock orchestrator to have simulated the correct callback for cleanup.

def test_archive_story_with_output_dir_and_options(runner, mock_successful_orchestrator, temp_workspace):
    story_url = "http://example.com/anothermock"
    custom_output_dir = os.path.join(temp_workspace, "custom_out")
    # os.makedirs(custom_output_dir) # CLI/Orchestrator should handle creation

    title_override = "My Awesome Mock Novel"
    chapters_vol = 20

    result = runner.invoke(archiver, [
        'archive-story', story_url,
        '--output-dir', custom_output_dir,
        '--ebook-title-override', title_override,
        '--chapters-per-volume', str(chapters_vol),
        '--keep-temp-files', # Flag
        '--force-reprocessing' # Flag
    ])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    assert f"Using provided output directory: {custom_output_dir}" in result.output

    # Check for some key progress messages (keep_temp_files=True means no cleanup messages)
    assert "[INFO] Starting archival process..." in result.output
    assert f"[INFO] Successfully fetched metadata: {title_override}" in result.output
    assert "Cleaning up temporary files..." not in result.output

    # Check for the new detailed success message
    assert "✓ Archival process completed successfully!" in result.output
    assert f"Title: {title_override}" in result.output
    assert "Story ID: test_story_id_123" in result.output
    assert "Chapters processed in this run: 1" in result.output # Mock processes 1 chapter
    assert "Generated EPUB file(s):" in result.output
    mock_epub_path = os.path.abspath(os.path.join(custom_output_dir, "ebooks", "test_story_id_123", f"{title_override}.epub"))
    assert f"- {mock_epub_path}" in result.output
    assert f"Workspace: {os.path.abspath(custom_output_dir)}" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == custom_output_dir
    assert kwargs['ebook_title_override'] == title_override
    assert kwargs['chapters_per_volume'] == chapters_vol
    assert kwargs['keep_temp_files'] is True
    assert kwargs['force_reprocessing'] is True
    assert callable(kwargs['progress_callback'])

    # Verify progress file reflects options
    progress_file = os.path.join(custom_output_dir, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['effective_title'] == title_override
        assert data['force_reprocessing_used'] is True
        assert data['chapters_per_volume_setting'] == chapters_vol

    # For integration tests, we rely on the mock orchestrator's `keep_temp_files` logic for callbacks.
    # The actual file system state for temp files is unit-tested in orchestrator tests.
    # Here, the mock was simplified and doesn't create temp files on disk.
    # If we wanted to assert their presence, the mock would need to create them.


def test_archive_story_sentence_removal_options(runner, mock_successful_orchestrator, temp_workspace):
    story_url = "http://example.com/sentenceremovaltest"

    # Workspace for first call
    workspace1 = os.path.join(temp_workspace, "ws1")
    os.makedirs(workspace1, exist_ok=True)
    rules_path1 = os.path.join(workspace1, "rules.json")
    with open(rules_path1, 'w', encoding='utf-8') as f: # Create dummy rules file
        json.dump({"remove_sentences": ["test"]}, f)

    # Test with sentence removal file
    result1 = runner.invoke(archiver, [
        'archive-story', story_url, '--output-dir', workspace1,
        '--sentence-removal-file', rules_path1
    ])
    assert result1.exit_code == 0, f"CLI errored (run1): {result1.output}"
    progress_file1 = os.path.join(workspace1, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file1)
    with open(progress_file1, 'r', encoding='utf-8') as f: data1 = json.load(f)
    assert data1['sentence_removal_config_used'] == rules_path1

    # Workspace for second call to ensure mock orchestrator can be called multiple times cleanly
    # The mock_successful_orchestrator is function-scoped, so it's fresh.
    # Filesystem changes from previous call might interfere if not using separate workspaces for outputs.
    workspace2 = os.path.join(temp_workspace, "ws2")
    os.makedirs(workspace2, exist_ok=True)
    rules_path2 = os.path.join(workspace2, "rules.json") # Can be same name, different dir
    with open(rules_path2, 'w', encoding='utf-8') as f:
        json.dump({"remove_sentences": ["test more"]}, f)

    # Test with --no-sentence-removal
    result2 = runner.invoke(archiver, [
        'archive-story', story_url, '--output-dir', workspace2,
        '--sentence-removal-file', rules_path2, # Provide file
        '--no-sentence-removal' # But disable it
    ])
    assert result2.exit_code == 0, f"CLI errored (run2): {result2.output}"
    progress_file2 = os.path.join(workspace2, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file2)
    with open(progress_file2, 'r', encoding='utf-8') as f: data2 = json.load(f)
    assert data2['sentence_removal_config_used'] == "Disabled via --no-sentence-removal"


def test_archive_story_orchestrator_failure(runner, monkeypatch, temp_workspace):
    """Test CLI handling when the call to the orchestrator itself raises an exception."""
    # Mock orchestrator to raise an error directly when it's called.
    # This simulates an issue with the call to the orchestrator itself,
    # or an uncaught exception within it that bypasses its normal error handling (which would return None).
    mock_orchestrator_call_itself = mock.Mock(side_effect=Exception("Core Orchestrator Call Failed Unexpectedly!"))
    monkeypatch.setattr(MOCK_ORCHESTRATOR_HANDLER_PATH, mock_orchestrator_call_itself)

    story_url = "http://example.com/failstory_direct_exception"
    # When an exception bubbles up to the CliRunner, it catches it.
    # result.exit_code will be 0 by default unless sys.exit is called or an unhandled exception occurs
    # that Click's default exception handler turns into a non-zero exit.
    result = runner.invoke(archiver, ['archive-story', story_url, '--output-dir', temp_workspace])

    # The CLI handler currently catches the exception, prints to stderr, and exits 0.
    # Since the handler catches the exception, result.exception will be None.
    assert result.exit_code == 0, f"CLI should exit with code 0 as the handler catches the exception. Output: {result.output}"
    assert result.exception is None, "Exception should be handled by the CLI handler, not propagated to CliRunner"

    # Check for the CLI handler's specific error message for unhandled exceptions (printed to stderr)
    # result.output contains both stdout and stderr if not separated.
    assert "An unexpected error occurred in the CLI handler: Core Orchestrator Call Failed Unexpectedly!" in result.output

    # In this scenario, the orchestrator mock fails immediately when called.
    # The `display_progress` function in the handler is passed to the orchestrator,
    # but the orchestrator call itself fails, so none of the orchestrator's
    # simulated callback calls (like "Starting archival process...") would occur.
    # We should check that the initial messages from the handler (before the call) are there.
    assert f"Received story URL: {story_url}" in result.output
    assert f"Using provided output directory: {temp_workspace}" in result.output # or from config
    # And that later orchestrator-driven progress messages are NOT there.
    assert "[INFO] Starting archival process..." not in result.output
    assert "[INFO] Fetching story metadata..." not in result.output


def test_archive_story_orchestrator_returns_none(runner, monkeypatch, temp_workspace):
    """Test CLI handling when the orchestrator returns None (simulating handled error)."""

    def mock_orchestrator_returns_none_side_effect(
        story_url: str,
        workspace_root: str,
        progress_callback: Optional[callable] = None,
        **kwargs # Catch other args
    ):
        if progress_callback:
            progress_callback({"status": "info", "message": "Starting archival process..."})
            progress_callback({"status": "info", "message": "Fetching story metadata..."})
            # Simulate a failure during metadata fetch reported via callback
            progress_callback({"status": "error", "message": "Simulated metadata fetch network error."})
        return None # Orchestrator returns None

    mock_orchestrator_returns_none = mock.Mock(side_effect=mock_orchestrator_returns_none_side_effect)
    monkeypatch.setattr(MOCK_ORCHESTRATOR_HANDLER_PATH, mock_orchestrator_returns_none)

    story_url = "http://example.com/orchestrator_none_story"
    result = runner.invoke(archiver, ['archive-story', story_url, '--output-dir', temp_workspace])

    assert result.exit_code == 0 # CLI handler itself doesn't fail if orchestrator returns None
    assert "[INFO] Starting archival process..." in result.output
    assert "[INFO] Fetching story metadata..." in result.output
    assert "[ERROR] Simulated metadata fetch network error." in result.output
    # Crucially, the green success message should NOT be present
    assert "✓ Archival process completed successfully!" not in result.output
    # The warning message "Archival process for ... concluded without a summary" is a log message,
    # not directly echoed to CLI output by default. If it were echoed, we'd assert it here.
    # For now, ensuring the error from callback is shown and success is not, is key.


def test_archive_story_deletion_with_other_options(runner, mock_successful_orchestrator, temp_workspace):
    """Test that temp files are deleted by default even with other options like title override."""
    story_url = "http://example.com/deletetest"
    custom_output_dir = os.path.join(temp_workspace, "delete_out")
    title_override = "Deletion Test Novel"

    result = runner.invoke(archiver, [
        'archive-story', story_url,
        '--output-dir', custom_output_dir,
        '--ebook-title-override', title_override
        # Note: --keep-temp-files is NOT passed, so it's False
    ])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    assert f"Using provided output directory: {custom_output_dir}" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == custom_output_dir
    assert kwargs['ebook_title_override'] == title_override
    assert kwargs['keep_temp_files'] is False # Explicitly check it's passed as False

    # Verify progress file was created by the mock
    progress_file = os.path.join(custom_output_dir, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['effective_title'] == title_override

    # Check for cleanup callback message
    assert "[INFO] Cleaning up temporary files..." in result.output
    assert "[INFO] Successfully cleaned up temporary files." in result.output

# --- New tests for default sentence removal feature ---
import configparser # Added for new tests
from pathlib import Path # Added for new tests
import logging # Added for caplog.set_level

@pytest.fixture
def setup_config_manager_for_temp_workspace(monkeypatch, temp_workspace):
    """
    Mocks ConfigManager to use a settings.ini within the temp_workspace.
    Returns the path to the config dir for easy access.
    """
    mock_cm_instance = mock.Mock(spec=ConfigManager)

    temp_config_dir = Path(temp_workspace) / "config"
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    temp_settings_ini_path = temp_config_dir / "settings.ini"

    # Actual ConfigManager will be created, but its _load_config will read from our temp file
    # We need to ensure that when ConfigManager() is called in the handler,
    # it uses this specific path.

    original_init = ConfigManager.__init__
    original_load_config = ConfigManager._load_config

    def mock_init(self_cm, config_file_path=None):
        # If no path is given (handler's case), force it to our temp settings.ini
        # This is a bit more direct than trying to mock DEFAULT_CONFIG_PATH
        if config_file_path is None:
            self_cm.config_file_path = str(temp_settings_ini_path)
        else: # pragma: no cover (should not happen in these tests)
            self_cm.config_file_path = config_file_path

        self_cm.config = configparser.ConfigParser()
        # We need to call the original _load_config logic so it actually reads our temp file
        # but it needs to be bound to the instance.
        # Directly calling self_cm._load_config() might not work if it was also patched.
        # So, we use a trick: setattr to instance, then call.
        # setattr(self_cm, '_load_config_original', original_load_config.__get__(self_cm, ConfigManager))
        # self_cm._load_config_original()
        # This got complicated. Simpler: let _load_config be called naturally after init.
        # The key is that self.config_file_path is set correctly before _load_config is called by constructor.
        ConfigManager._load_config(self_cm) # Call original _load_config with the instance

    # We are patching the __init__ to set the config_file_path correctly.
    # The _load_config method will then use this path.
    # The get_workspace_path and get_default_sentence_removal_file will work on the loaded config.

    # Patch __init__ to control config_file_path, then let the original _load_config work.
    # This means ConfigManager will actually parse the temp_settings_ini_path.
    def patched_init(self, config_file_path=None):
        # If the handler calls ConfigManager() without args, force our path
        effective_path = config_file_path if config_file_path is not None else str(temp_settings_ini_path)
        # Call the original __init__ but ensure it uses our path for loading.
        # This is tricky because __init__ itself calls _load_config.
        # Best to control the path it uses for _load_config.

        # Simplified approach: just ensure the instance uses temp_workspace for get_workspace_path
        # and that it can load the temp_settings_ini_path for get_default_sentence_removal_file.

        # Let's make the mock ConfigManager behave as if it loaded our temp settings.ini
        # We will write to temp_settings_ini_path, then have the mock methods use it.

        # This fixture will return a function to create settings.ini and the path to it.
        # The test will then mock specific ConfigManager methods as needed.
        # This is simpler than deeply patching ConfigManager's loading behavior.
        pass # No, this fixture should do the patching of ConfigManager

    # Patch ConfigManager constructor to return a pre-configured mock instance
    # that "reads" from our temp_settings_ini_path.
    # This avoids complex patching of file loading logic.

    # Create a real ConfigParser object that reads the temp file
    # This will be the 'self.config' of the ConfigManager instance used by the handler
    config_parser_that_reads_temp_ini = configparser.ConfigParser()
    if temp_settings_ini_path.exists(): # pragma: no cover (should exist by the time this is called by ConfigManager)
        config_parser_that_reads_temp_ini.read(str(temp_settings_ini_path))

    # Mock the instance methods
    mock_cm_instance.config = config_parser_that_reads_temp_ini
    mock_cm_instance.config_file_path = str(temp_settings_ini_path)

    # Define how get_workspace_path and get_default_sentence_removal_file behave
    # These will now correctly use the 'config_parser_that_reads_temp_ini'
    def get_workspace_path_impl():
        return mock_cm_instance.config.get('General', 'workspace_path', fallback=temp_workspace)

    def get_default_sentence_removal_file_impl():
        return mock_cm_instance.config.get('SentenceRemoval', 'default_sentence_removal_file', fallback=None)

    mock_cm_instance.get_workspace_path = mock.Mock(side_effect=get_workspace_path_impl)
    mock_cm_instance.get_default_sentence_removal_file = mock.Mock(side_effect=get_default_sentence_removal_file_impl)

    # This is needed if the actual _load_config is to be tested with a temp file
    # For now, mocking get_default_sentence_removal_file directly based on a parsed temp file is safer.

    # The mock constructor for ConfigManager
    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr("webnovel_archiver.cli.handlers.ConfigManager", mock_cm_constructor)

    return temp_config_dir, temp_settings_ini_path, mock_cm_instance, config_parser_that_reads_temp_ini


def test_scenario_1_use_default_sentence_removal(
    runner, mock_successful_orchestrator, temp_workspace,
    setup_config_manager_for_temp_workspace, caplog
):
    story_url = "http://example.com/story-default-sr"
    caplog.set_level(logging.INFO) # Set caplog level
    config_dir, settings_ini_path, _, live_config_parser = setup_config_manager_for_temp_workspace

    # Create default_rules.json
    default_rules_content = {"remove_sentences": ["Default rule."]}
    default_rules_path = config_dir / "default_rules.json"
    with open(default_rules_path, 'w') as f:
        json.dump(default_rules_content, f)

    # Create settings.ini specifying the default sentence removal file
    config = configparser.ConfigParser()
    config['General'] = {'workspace_path': temp_workspace} # Needs to resolve workspace
    config['SentenceRemoval'] = {'default_sentence_removal_file': str(default_rules_path)}
    with open(settings_ini_path, 'w') as f:
        config.write(f)

    # Update the live_config_parser that the mock ConfigManager instance uses
    live_config_parser.read(str(settings_ini_path))

    result = runner.invoke(archiver, ['archive-story', story_url]) # No --output-dir, should use from mocked ConfigManager

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['sentence_removal_file'] == str(default_rules_path)
    assert not kwargs['no_sentence_removal']
    assert f"Using default sentence removal file from config: {str(default_rules_path)}" in caplog.text # Check log in caplog

def test_scenario_2_cli_overrides_default(
    runner, mock_successful_orchestrator, temp_workspace,
    setup_config_manager_for_temp_workspace, caplog
):
    story_url = "http://example.com/story-cli-overrides"
    caplog.set_level(logging.INFO) # Set caplog level
    config_dir, settings_ini_path, _, live_config_parser = setup_config_manager_for_temp_workspace

    # Create default_rules.json (configured but should be overridden)
    default_rules_content = {"remove_sentences": ["Default rule."]}
    default_rules_path = config_dir / "default_rules.json"
    with open(default_rules_path, 'w') as f:
        json.dump(default_rules_content, f)

    # Create cli_rules.json (this one should be used)
    cli_rules_content = {"remove_sentences": ["CLI rule."]}
    cli_rules_path = Path(temp_workspace) / "cli_rules.json" # Place it in workspace root for simplicity
    with open(cli_rules_path, 'w') as f:
        json.dump(cli_rules_content, f)

    # Create settings.ini specifying the default
    config = configparser.ConfigParser()
    config['General'] = {'workspace_path': temp_workspace}
    config['SentenceRemoval'] = {'default_sentence_removal_file': str(default_rules_path)}
    with open(settings_ini_path, 'w') as f:
        config.write(f)
    live_config_parser.read(str(settings_ini_path))

    result = runner.invoke(archiver, [
        'archive-story', story_url,
        '--sentence-removal-file', str(cli_rules_path)
    ])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['sentence_removal_file'] == str(cli_rules_path)
    assert not kwargs['no_sentence_removal']
    assert f"Using sentence removal file provided via CLI: {str(cli_rules_path)}" in caplog.text # Check log in caplog

def test_scenario_3_no_sentence_removal_overrides_default(
    runner, mock_successful_orchestrator, temp_workspace,
    setup_config_manager_for_temp_workspace, caplog
):
    story_url = "http://example.com/story-no-sr-overrides"
    caplog.set_level(logging.INFO) # Set caplog level
    config_dir, settings_ini_path, _, live_config_parser = setup_config_manager_for_temp_workspace

    # Create default_rules.json (configured but should be overridden by --no-sentence-removal)
    default_rules_content = {"remove_sentences": ["Default rule."]}
    default_rules_path = config_dir / "default_rules.json"
    with open(default_rules_path, 'w') as f:
        json.dump(default_rules_content, f)

    # Create settings.ini specifying the default
    config = configparser.ConfigParser()
    config['General'] = {'workspace_path': temp_workspace}
    config['SentenceRemoval'] = {'default_sentence_removal_file': str(default_rules_path)}
    with open(settings_ini_path, 'w') as f:
        config.write(f)
    live_config_parser.read(str(settings_ini_path))

    result = runner.invoke(archiver, [
        'archive-story', story_url,
        '--no-sentence-removal'
    ])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['sentence_removal_file'] is None
    assert kwargs['no_sentence_removal'] is True
    assert "Sentence removal explicitly disabled via --no-sentence-removal flag." in caplog.text # Check log in caplog

def test_scenario_4_default_file_configured_but_not_found(
    runner, mock_successful_orchestrator, temp_workspace,
    setup_config_manager_for_temp_workspace, caplog
):
    story_url = "http://example.com/story-default-not-found"
    caplog.set_level(logging.INFO) # Set caplog level
    config_dir, settings_ini_path, _, live_config_parser = setup_config_manager_for_temp_workspace

    # Path to a non-existent default rules file
    non_existent_default_rules_path = config_dir / "non_existent_rules.json"

    # Create settings.ini specifying this non-existent file
    config = configparser.ConfigParser()
    config['General'] = {'workspace_path': temp_workspace}
    config['SentenceRemoval'] = {'default_sentence_removal_file': str(non_existent_default_rules_path)}
    with open(settings_ini_path, 'w') as f:
        config.write(f)
    live_config_parser.read(str(settings_ini_path))

    result = runner.invoke(archiver, ['archive-story', story_url])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['sentence_removal_file'] is None
    assert not kwargs['no_sentence_removal']
    assert f"Default sentence removal file configured at '{str(non_existent_default_rules_path)}' not found. Proceeding without sentence removal." in caplog.text # Check log in caplog

# Add more tests:
# - Invalid story URL (if CLI does any pre-validation, though likely orchestrator handles this)
# - Non-existent sentence_removal_file (click handles this with type=click.Path(exists=True))
# - Other combinations of flags.


def test_archive_story_epub_contents_option(runner, mock_successful_orchestrator, temp_workspace):
    """Test the --epub-contents CLI option."""

    # Test Case 1: --epub-contents active-only
    story_url_active_only = "http://example.com/epub_active_only"
    workspace_active_only = os.path.join(temp_workspace, "ws_active_only")
    # No need to os.makedirs for workspace, CLI/orchestrator mock should handle it

    result_active = runner.invoke(archiver, [
        'archive-story', story_url_active_only,
        '--output-dir', workspace_active_only,
        '--epub-contents', 'active-only'
    ])
    assert result_active.exit_code == 0, f"CLI errored (active-only): {result_active.output}"

    # Get the call arguments for this specific call
    # If mock is called multiple times, call_args_list[-1] gets the last one
    # Or, if the mock is reset/recreated per test, call_args is fine.
    # Assuming mock_successful_orchestrator is fresh or we check the right call.
    # For this test structure, mock is fresh per test_... function, but we make multiple invokes.
    # So, need to check call_args_list.

    # Let's clear mock before the next call to ensure we are checking the right one,
    # or check the call_args_list. For simplicity here, let's check the last call.
    # However, it's better practice to reset or use call_args_list.
    # Since we have multiple calls to the same mock instance within one test function,
    # we need to inspect call_args_list.

    # Call 1 assertions
    args_active, kwargs_active = mock_successful_orchestrator.call_args_list[0] # First call
    assert kwargs_active['story_url'] == story_url_active_only
    assert kwargs_active['epub_contents'] == 'active-only'
    progress_file_active = os.path.join(workspace_active_only, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file_active)
    with open(progress_file_active, 'r', encoding='utf-8') as f:
        data_active = json.load(f)
        assert data_active['epub_contents_setting'] == 'active-only'

    # Test Case 2: --epub-contents all
    story_url_all = "http://example.com/epub_all"
    workspace_all = os.path.join(temp_workspace, "ws_all")
    result_all = runner.invoke(archiver, [
        'archive-story', story_url_all,
        '--output-dir', workspace_all,
        '--epub-contents', 'all'
    ])
    assert result_all.exit_code == 0, f"CLI errored (all): {result_all.output}"

    args_all, kwargs_all = mock_successful_orchestrator.call_args_list[1] # Second call
    assert kwargs_all['story_url'] == story_url_all
    assert kwargs_all['epub_contents'] == 'all'
    progress_file_all = os.path.join(workspace_all, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file_all)
    with open(progress_file_all, 'r', encoding='utf-8') as f:
        data_all = json.load(f)
        assert data_all['epub_contents_setting'] == 'all'

    # Test Case 3: Default behavior (no --epub-contents flag)
    story_url_default = "http://example.com/epub_default"
    workspace_default = os.path.join(temp_workspace, "ws_default")
    result_default = runner.invoke(archiver, [
        'archive-story', story_url_default,
        '--output-dir', workspace_default
    ])
    assert result_default.exit_code == 0, f"CLI errored (default): {result_default.output}"

    args_default, kwargs_default = mock_successful_orchestrator.call_args_list[2] # Third call
    assert kwargs_default['story_url'] == story_url_default
    assert kwargs_default['epub_contents'] == 'all' # Default should be 'all'
    progress_file_default = os.path.join(workspace_default, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file_default)
    with open(progress_file_default, 'r', encoding='utf-8') as f:
        data_default = json.load(f)
        assert data_default['epub_contents_setting'] == 'all'

    # Ensure the mock was called three times in total for this test
    assert mock_successful_orchestrator.call_count == 3
