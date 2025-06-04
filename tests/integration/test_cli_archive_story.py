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
        progress_callback: Optional[callable] = None
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
            }
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
    mock_cm_instance = mock.Mock()
    mock_cm_instance.get_workspace_path.return_value = temp_workspace
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

# Add more tests:
# - Invalid story URL (if CLI does any pre-validation, though likely orchestrator handles this)
# - Non-existent sentence_removal_file (click handles this with type=click.Path(exists=True))
# - Other combinations of flags.
