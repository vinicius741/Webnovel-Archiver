import pytest
import os
import json
from click.testing import CliRunner
from unittest import mock

# CLI entry point
from webnovel_archiver.cli.main import archiver
# For mocking the actual work if needed, to avoid network calls etc.
MOCK_ORCHESTRATOR_CORE_PATH = "webnovel_archiver.core.orchestrator.archive_story"
# To control workspace for tests
from webnovel_archiver.core.storage.progress_manager import DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR, RAW_CONTENT_DIR, PROCESSED_CONTENT_DIR

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
    mock_orchestrator = mock.Mock(return_value=None) # Simulate successful completion

    def side_effect_for_orchestrator(
        story_url,
        workspace_root,
        chapters_per_volume=None,
        ebook_title_override=None,
        keep_temp_files=False,
        force_reprocessing=False,
        sentence_removal_file=None,
        no_sentence_removal=False
    ):
        # Simulate creation of progress file and some dirs based on params
        story_id = "test_story_id_123" # Simplified story_id generation for mock
        progress_path = os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, story_id)
        os.makedirs(progress_path, exist_ok=True)

        # Simulate some content directories being made
        # In a real scenario, orchestrator creates these based on its internal logic.
        # Mock should reflect what CLI options might influence, e.g. keep_temp_files.
        if keep_temp_files:
             os.makedirs(os.path.join(workspace_root, RAW_CONTENT_DIR, story_id), exist_ok=True)
             os.makedirs(os.path.join(workspace_root, PROCESSED_CONTENT_DIR, story_id), exist_ok=True)


        progress_data = {
            "story_id": story_id,
            "story_url": story_url,
            "original_title": "Original Mock Title",
            "effective_title": ebook_title_override if ebook_title_override else "Original Mock Title",
            "downloaded_chapters": [{"chapter_title": "Mock Chapter 1"}], # Simulate some chapters
            "force_reprocessing_used": force_reprocessing, # Custom key for testing
            "sentence_removal_config_used": sentence_removal_file if sentence_removal_file and not no_sentence_removal else \
                                            ("Disabled via --no-sentence-removal" if no_sentence_removal else None),
            "chapters_per_volume_setting": chapters_per_volume
        }
        with open(os.path.join(progress_path, "progress_status.json"), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)

        return None # Successful run

    mock_orchestrator.side_effect = side_effect_for_orchestrator
    monkeypatch.setattr(MOCK_ORCHESTRATOR_CORE_PATH, mock_orchestrator)
    return mock_orchestrator

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
    assert f"Received story URL: {story_url}" in result.output
    assert f"Using workspace directory from config: {temp_workspace}" in result.output
    assert f"Archival process completed for: {story_url}" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == temp_workspace

    # Verify progress file was created by the mock
    progress_file = os.path.join(temp_workspace, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['story_url'] == story_url

    # Verify temp dirs are NOT present (default behavior)
    raw_dir_path = os.path.join(temp_workspace, RAW_CONTENT_DIR, "test_story_id_123")
    processed_dir_path = os.path.join(temp_workspace, PROCESSED_CONTENT_DIR, "test_story_id_123")
    assert not os.path.exists(raw_dir_path), f"Raw directory {raw_dir_path} should have been deleted."
    assert not os.path.exists(processed_dir_path), f"Processed directory {processed_dir_path} should have been deleted."

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

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == custom_output_dir
    assert kwargs['ebook_title_override'] == title_override
    assert kwargs['chapters_per_volume'] == chapters_vol
    assert kwargs['keep_temp_files'] is True
    assert kwargs['force_reprocessing'] is True

    # Verify progress file reflects options
    progress_file = os.path.join(custom_output_dir, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['effective_title'] == title_override
        assert data['force_reprocessing_used'] is True # From our mock's logic
        assert data['chapters_per_volume_setting'] == chapters_vol

    # Verify temp dirs created by mock due to keep_temp_files
    assert os.path.exists(os.path.join(custom_output_dir, RAW_CONTENT_DIR, "test_story_id_123"))
    assert os.path.exists(os.path.join(custom_output_dir, PROCESSED_CONTENT_DIR, "test_story_id_123"))


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
    """Test CLI handling when the orchestrator itself raises an exception."""
    # Mock orchestrator to raise an error
    mock_orchestrator = mock.Mock(side_effect=Exception("Core Orchestrator Failed!"))
    monkeypatch.setattr(MOCK_ORCHESTRATOR_CORE_PATH, mock_orchestrator)

    story_url = "http://example.com/failstory"
    result = runner.invoke(archiver, ['archive-story', story_url, '--output-dir', temp_workspace])

    assert result.exit_code != 0 # Expect non-zero exit code on error
    assert "Starting archival process..." in result.output # It should start
    assert "An error occurred during the archival process: Core Orchestrator Failed!" in result.output
    # Click by default exits with 1 on unhandled exceptions. If specific exit codes are desired,
    # the handler's except block would need to sys.exit(code).

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

    # Verify progress file was created
    progress_file = os.path.join(custom_output_dir, ARCHIVAL_STATUS_DIR, "test_story_id_123", "progress_status.json")
    assert os.path.exists(progress_file)
    with open(progress_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        assert data['effective_title'] == title_override

    # Verify temp dirs are NOT present
    raw_dir_path = os.path.join(custom_output_dir, RAW_CONTENT_DIR, "test_story_id_123")
    processed_dir_path = os.path.join(custom_output_dir, PROCESSED_CONTENT_DIR, "test_story_id_123")
    assert not os.path.exists(raw_dir_path), f"Raw directory {raw_dir_path} should have been deleted."
    assert not os.path.exists(processed_dir_path), f"Processed directory {processed_dir_path} should have been deleted."

# Add more tests:
# - Invalid story URL (if CLI does any pre-validation, though likely orchestrator handles this)
# - Non-existent sentence_removal_file (click handles this with type=click.Path(exists=True))
# - Other combinations of flags.
