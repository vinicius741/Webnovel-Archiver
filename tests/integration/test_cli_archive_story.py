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
# To control workspace for tests and construct paths for verification
from webnovel_archiver.core.storage.index_manager import IndexManager
from webnovel_archiver.core.path_manager import PathManager


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
        epub_contents: Optional[str] = 'all'
    ):
        story_id = "royalroad-117255"
        effective_title = ebook_title_override if ebook_title_override else "Original Mock Title"
        
        index_manager = IndexManager(workspace_root)
        if not index_manager.index_exists():
            if progress_callback:
                progress_callback({"status": "info", "message": "No index file found. Starting migration of existing archives."})
            archival_status_path = os.path.join(workspace_root, 'archival_status')
            if os.path.exists(archival_status_path):
                for folder_name in os.listdir(archival_status_path):
                    if progress_callback:
                        progress_callback({"status": "info", "message": f"Migrated '{folder_name}' to index with ID 'royalroad-117255'"})
                    index_manager.add_story("royalroad-117255", folder_name)

        path_manager = PathManager(workspace_root, index_manager)
        path_manager.set_story(story_id, effective_title)

        if progress_callback:
            progress_callback({"status": "info", "message": "Starting archival process..."})
            progress_callback({"status": "info", "message": f"Successfully fetched metadata: {effective_title}"})
            progress_callback({"status": "info", "message": "Found 1 chapters."})
            progress_callback({"status": "info", "message": "Processing chapter: Mock Chapter 1 (1/1)"})
            progress_callback({"status": "info", "message": "Starting EPUB generation..."})
            progress_callback({"status": "info", "message": "Archival process completed."})

        progress_path = path_manager.get_archival_status_story_dir()
        os.makedirs(progress_path, exist_ok=True)

        if keep_temp_files:
             os.makedirs(path_manager.get_raw_content_story_dir(), exist_ok=True)
             os.makedirs(path_manager.get_processed_content_story_dir(), exist_ok=True)

        progress_data = {
            "story_id": story_id,
            "story_url": story_url,
            "original_title": "Original Mock Title",
            "effective_title": effective_title,
            "downloaded_chapters": [{"chapter_title": "Mock Chapter 1"}],
        }
        with open(path_manager.get_progress_filepath(), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f)

        summary = {
            "story_id": story_id,
            "title": effective_title,
            "chapters_processed": 1,
            "epub_files": [os.path.abspath(os.path.join(path_manager.get_ebooks_story_dir(), f"{effective_title}.epub"))],
            "workspace_root": os.path.abspath(workspace_root)
        }
        return summary

    mock_orchestrator_func.side_effect = side_effect_for_orchestrator
    monkeypatch.setattr(MOCK_ORCHESTRATOR_HANDLER_PATH, mock_orchestrator_func)
    return mock_orchestrator_func

def test_archive_story_successful_run_default_workspace(runner, mock_successful_orchestrator, temp_workspace, monkeypatch):
    """Test basic successful run using a temporary default workspace."""
    mock_cm_instance = mock.Mock(spec=ConfigManager)
    mock_cm_instance.get_workspace_path.return_value = temp_workspace
    mock_cm_instance.get_default_sentence_removal_file.return_value = None
    mock_cm_constructor = mock.Mock(return_value=mock_cm_instance)
    monkeypatch.setattr("webnovel_archiver.cli.contexts.ConfigManager", mock_cm_constructor)

    story_url = "http://example.com/mockstory"
    result = runner.invoke(archiver, ['archive-story', story_url])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    assert "✓ Archival process completed successfully!" in result.output
    assert "Title: Original Mock Title" in result.output
    assert "Story ID: royalroad-117255" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == temp_workspace

    index_path = os.path.join(temp_workspace, "index.json")
    assert os.path.exists(index_path)
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
        assert index_data["royalroad-117255"] == "original-mock-title"

    progress_file = os.path.join(temp_workspace, PathManager.ARCHIVAL_STATUS_DIR_NAME, "original-mock-title", "progress.json")
    assert os.path.exists(progress_file)

def test_archive_story_with_output_dir_and_options(runner, mock_successful_orchestrator, temp_workspace):
    story_url = "http://example.com/anothermock"
    custom_output_dir = os.path.join(temp_workspace, "custom_out")

    title_override = "My Awesome Mock Novel"
    chapters_vol = 20

    result = runner.invoke(archiver, [
        'archive-story', story_url,
        '--output-dir', custom_output_dir,
        '--ebook-title-override', title_override,
        '--chapters-per-volume', str(chapters_vol),
        '--keep-temp-files',
        '--force-reprocessing'
    ])

    assert result.exit_code == 0, f"CLI errored: {result.output}"
    assert f"Workspace directory: {custom_output_dir}" in result.output
    assert "✓ Archival process completed successfully!" in result.output
    assert f"Title: {title_override}" in result.output

    mock_successful_orchestrator.assert_called_once()
    args, kwargs = mock_successful_orchestrator.call_args
    assert kwargs['story_url'] == story_url
    assert kwargs['workspace_root'] == custom_output_dir
    assert kwargs['ebook_title_override'] == title_override

    index_path = os.path.join(custom_output_dir, "index.json")
    assert os.path.exists(index_path)
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
        assert index_data["royalroad-117255"] == "my-awesome-mock-novel"

    # Now, run again with a different title to trigger rename
    new_title_override = "My Awesome Mock Novel V2"
    runner.invoke(archiver, [
        'archive-story', story_url,
        '--output-dir', custom_output_dir,
        '--ebook-title-override', new_title_override,
    ])

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
        assert index_data["royalroad-117255"] == "my-awesome-mock-novel-v2"

    assert not os.path.exists(os.path.join(custom_output_dir, PathManager.ARCHIVAL_STATUS_DIR_NAME, "my-awesome-mock-novel"))
    assert os.path.exists(os.path.join(custom_output_dir, PathManager.ARCHIVAL_STATUS_DIR_NAME, "my-awesome-mock-novel-v2"))

def test_migration_of_existing_archive(runner, mock_successful_orchestrator, temp_workspace):
    """Test that an existing, unmigrated archive is correctly migrated."""
    story_url = "https://www.royalroad.com/fiction/117255/rend"
    old_folder_name = "rend"

    # 1. Create a pre-migration folder structure
    archival_status_dir = os.path.join(temp_workspace, PathManager.ARCHIVAL_STATUS_DIR_NAME, old_folder_name)
    os.makedirs(archival_status_dir)

    progress_data = {
        "story_url": story_url,
        "original_title": "Rend",
    }
    with open(os.path.join(archival_status_dir, "progress.json"), 'w', encoding='utf-8') as f:
        json.dump(progress_data, f)

    # 2. Run the archiver
    result = runner.invoke(archiver, ['archive-story', story_url, '--output-dir', temp_workspace])

    # 3. Verify the results
    assert result.exit_code == 0, f"CLI errored: {result.output}"
    assert "No index file found. Starting migration of existing archives." in result.output
    assert "Migrated 'rend' to index with ID 'royalroad-117255'" in result.output

    index_path = os.path.join(temp_workspace, "index.json")
    assert os.path.exists(index_path)
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
        assert index_data["royalroad-117255"] == "rend"
