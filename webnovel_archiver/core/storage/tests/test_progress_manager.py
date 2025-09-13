import os
import json
import datetime

from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager
from webnovel_archiver.core.storage.progress_manager import (
    load_progress,
    save_progress,
    get_progress_filepath,
    _get_new_progress_structure
)
from webnovel_archiver.core.storage.progress_cloud import (
    get_cloud_backup_status,
    update_cloud_backup_status,
)
from webnovel_archiver.core.storage.progress_epub import (
    add_epub_file_to_progress,
    get_epub_file_details,
)

logger = get_logger(__name__)

def test_progress_manager():
    logger.info("--- Testing ProgressManager functions ---") # Use logger

    rr_url = "https://www.royalroad.com/fiction/117255/rend-a-tale-of-something"
    test_story_id = "royalroad-117255"
    test_workspace = os.path.abspath("_test_pm_workspace") # Make workspace path absolute
    pm_for_test = PathManager(test_workspace, test_story_id) # PathManager for test setup

    logger.info(f"Test Story ID: {test_story_id}, Workspace: {test_workspace}")

    # Clean up any previous test file for this ID
    test_filepath = pm_for_test.get_progress_filepath() # Use PathManager
    if os.path.exists(test_filepath):
        os.remove(test_filepath)

    story_status_dir = os.path.dirname(test_filepath)
    if os.path.exists(story_status_dir):
        if not os.listdir(story_status_dir):
            os.rmdir(story_status_dir)

    # Create ebook dir for test
    ebook_dir_for_test = pm_for_test.get_ebooks_story_dir()
    os.makedirs(ebook_dir_for_test, exist_ok=True)


    # Load (should create new)
    progress = load_progress(test_story_id, workspace_root=test_workspace) # workspace_root is required
    progress["story_url"] = rr_url # Set story_url for new progress
    logger.info(f"Initial progress for {test_story_id}: {json.dumps(progress, indent=2)}")

    # Modify progress
    progress["original_title"] = "REND"
    progress["original_author"] = "Temple"

    # Add dummy epub files (paths should be absolute for storage after this point)
    epub1_name = "REND_Vol_1.epub"
    epub1_abs_path = os.path.abspath(os.path.join(ebook_dir_for_test, epub1_name))
    with open(epub1_abs_path, 'w') as f: f.write("dummy epub1") # Simulate file creation

    add_epub_file_to_progress(progress, epub1_name, epub1_abs_path, test_story_id, workspace_root=test_workspace)
    save_progress(test_story_id, progress, workspace_root=test_workspace)

    # Load again
    loaded_progress = load_progress(test_story_id, workspace_root=test_workspace)
    logger.info(f"Loaded progress after adding EPUB: {json.dumps(loaded_progress, indent=2)}")
    retrieved_epubs = get_epub_file_details(loaded_progress, test_story_id, workspace_root=test_workspace)
    logger.info(f"Retrieved EPUBs: {retrieved_epubs}")
    assert len(retrieved_epubs) == 1
    assert retrieved_epubs[0]['path'] == epub1_abs_path

    # --- Test downloaded_chapters ---
    logger.info(f"--- Testing downloaded_chapters section for story {test_story_id} ---")
    sample_chapter = {
        "source_chapter_id": "ch123",
        "download_order": 1,
        "chapter_url": "http://example.com/chapter/123",
        "chapter_title": "The First Chapter",
        "status": "active",
        "first_seen_on": "2023-01-15T10:00:00Z",
        "last_checked_on": "2023-01-16T12:00:00Z",
        "local_raw_filename": "raw_chapter_1.html",
        "local_processed_filename": "processed_chapter_1.xhtml"
    }
    loaded_progress['downloaded_chapters'].append(sample_chapter)
    save_progress(test_story_id, loaded_progress, workspace_root=test_workspace)

    progress_with_chapter = load_progress(test_story_id, workspace_root=test_workspace)
    logger.info(f"Progress after adding chapter: {json.dumps(progress_with_chapter['downloaded_chapters'], indent=2)}")
    assert len(progress_with_chapter['downloaded_chapters']) == 1
    retrieved_chapter = progress_with_chapter['downloaded_chapters'][0]
    assert retrieved_chapter['source_chapter_id'] == sample_chapter['source_chapter_id']
    assert retrieved_chapter['download_order'] == sample_chapter['download_order']
    assert retrieved_chapter['chapter_url'] == sample_chapter['chapter_url']
    assert retrieved_chapter['chapter_title'] == sample_chapter['chapter_title']
    assert retrieved_chapter['status'] == sample_chapter['status']
    assert retrieved_chapter['first_seen_on'] == sample_chapter['first_seen_on']
    assert retrieved_chapter['last_checked_on'] == sample_chapter['last_checked_on']
    assert retrieved_chapter['local_raw_filename'] == sample_chapter['local_raw_filename']
    assert retrieved_chapter['local_processed_filename'] == sample_chapter['local_processed_filename']
    logger.info(f"--- Successfully tested downloaded_chapters section for story {test_story_id} ---")
    # --- End Test downloaded_chapters ---

    # Simulate a cloud backup operation
    backup_status_update = {
        'last_backup_attempt_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'last_successful_backup_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'service': 'gdrive',
        'base_cloud_folder_name': 'Webnovel Archiver Backups Test',
        'story_cloud_folder_name': test_story_id,
        'cloud_base_folder_id': 'gdrive_base_folder_id_test123',
        'story_cloud_folder_id': 'gdrive_story_folder_id_test456',
        'backed_up_files': [
            {
                'local_path': epub1_abs_path,
                'cloud_file_name': epub1_name,
                'cloud_file_id': 'gdrive_file_id_vol1_test',
                'last_backed_up_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'status': 'uploaded'
            },
            {
                'local_path': get_progress_filepath(test_story_id, test_workspace), # Path to progress file itself
                'cloud_file_name': "progress_status.json",
                'cloud_file_id': 'gdrive_file_id_progress_test',
                'last_backed_up_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'status': 'uploaded'
            }
        ]
    }
    update_cloud_backup_status(loaded_progress, backup_status_update)
    save_progress(test_story_id, loaded_progress, workspace_root=test_workspace)

    # Verify cloud backup status
    final_progress = load_progress(test_story_id, workspace_root=test_workspace)
    cloud_status = get_cloud_backup_status(final_progress) # Use the getter
    logger.info(f"Final Cloud Backup Status: {json.dumps(cloud_status, indent=2)}")
    assert cloud_status['service'] == 'gdrive'
    assert len(cloud_status['backed_up_files']) == 2
    assert cloud_status['backed_up_files'][0]['cloud_file_id'] == 'gdrive_file_id_vol1_test'

    logger.info("All tests passed (basic assertions).")

    # Clean up
    if os.path.exists(epub1_abs_path): os.remove(epub1_abs_path)
    if os.path.exists(test_filepath): os.remove(test_filepath)
    if os.path.exists(ebook_dir_for_test) and not os.listdir(ebook_dir_for_test): os.rmdir(ebook_dir_for_test)

    story_archival_dir = pm_for_test.get_archival_status_story_dir()
    if os.path.exists(story_archival_dir) and not os.listdir(story_archival_dir): os.rmdir(story_archival_dir)

    # Clean up parent directories if they are empty and created by this test
    for dir_type_name in [PathManager.EBOOKS_DIR_NAME, PathManager.ARCHIVAL_STATUS_DIR_NAME]:
        parent_path = pm_for_test.get_base_directory(dir_type_name) # Use PathManager
        if os.path.exists(parent_path) and not os.listdir(parent_path):
            os.rmdir(parent_path)
    if os.path.exists(test_workspace) and not os.listdir(test_workspace):
        os.rmdir(test_workspace)
    logger.info(f"Test workspace {test_workspace} cleaned up.")

def test_get_epub_file_details_backward_compatibility():
    logger.info("--- Testing get_epub_file_details backward compatibility ---")

    # 1. Setup progress_data with old format epub entries
    old_format_story_id = "story_with_old_epubs"
    old_format_workspace = os.path.abspath("_test_pm_old_format_workspace") # Make workspace path absolute
    old_format_pm = PathManager(old_format_workspace, old_format_story_id)

    # Ensure workspace and ebook directory exist for this test
    old_format_ebook_dir = old_format_pm.get_ebooks_story_dir()
    os.makedirs(old_format_ebook_dir, exist_ok=True)

    # Simulate creation of one of the files for path resolution testing
    relative_epub_name = "old_relative_book.epub"
    abs_path_for_relative_epub = os.path.abspath(os.path.join(old_format_ebook_dir, relative_epub_name))
    with open(abs_path_for_relative_epub, 'w') as f: f.write("dummy old relative epub")

    # Absolute path for another dummy file (no actual file creation needed for this one in test)
    abs_path_epub_name = "old_absolute_book.epub" # Name if derived from path
    abs_path_epub_string = os.path.abspath(os.path.join(old_format_ebook_dir, abs_path_epub_name))


    progress_old_format = _get_new_progress_structure(old_format_story_id) # Start with a base structure
    progress_old_format['last_epub_processing']['generated_epub_files'] = [
        relative_epub_name, # A relative path / filename
        abs_path_epub_string  # An absolute path string
    ]
    # Optionally save and reload to ensure it's processed by load_progress if desired,
    # but for direct testing of get_epub_file_details, this is fine.
    # save_progress(old_format_story_id, progress_old_format, workspace_root=old_format_workspace)
    # loaded_progress_old_format = load_progress(old_format_story_id, workspace_root=old_format_workspace)


    # 2. Call get_epub_file_details
    retrieved_old_format_epubs = get_epub_file_details(progress_old_format, old_format_story_id, workspace_root=old_format_workspace)
    logger.info(f"Retrieved EPUBs from old format data: {retrieved_old_format_epubs}")

    # 3. Assertions
    assert len(retrieved_old_format_epubs) == 2

    found_relative_as_dict = False
    found_absolute_as_dict = False

    for item in retrieved_old_format_epubs:
        assert isinstance(item, dict)
        assert "name" in item
        assert "path" in item
        assert os.path.isabs(item["path"]) # Ensure all paths are absolute

        if item["name"] == relative_epub_name:
            # Path comparison needs to be careful about normalization (e.g. slashes)
            # os.path.normpath was used in get_epub_file_details
            assert os.path.normpath(item["path"]) == os.path.normpath(abs_path_for_relative_epub)
            found_relative_as_dict = True
        elif item["name"] == abs_path_epub_name: # Name is derived from basename of the path string
            assert os.path.normpath(item["path"]) == os.path.normpath(abs_path_epub_string)
            found_absolute_as_dict = True

    assert found_relative_as_dict, f"Did not find processed entry for '{relative_epub_name}'"
    assert found_absolute_as_dict, f"Did not find processed entry for '{abs_path_epub_string}'"

    logger.info("get_epub_file_details backward compatibility test passed.")

    # Clean up test files and directories for this specific test
    if os.path.exists(abs_path_for_relative_epub): os.remove(abs_path_for_relative_epub)
    # No progress file was saved for old_format_story_id in this direct test of get_epub_file_details
    # so no progress file to remove for old_format_story_id
    if os.path.exists(old_format_ebook_dir) and not os.listdir(old_format_ebook_dir): os.rmdir(old_format_ebook_dir)

    # old_format_story_archival_dir = os.path.join(old_format_workspace, ARCHIVAL_STATUS_DIR, old_format_story_id) # Replaced
    old_format_story_archival_dir = old_format_pm.get_archival_status_story_dir()
    if os.path.exists(old_format_story_archival_dir) and not os.listdir(old_format_story_archival_dir): os.rmdir(old_format_story_archival_dir)

    for dir_type_name in [PathManager.EBOOKS_DIR_NAME, PathManager.ARCHIVAL_STATUS_DIR_NAME]:
        parent_path = old_format_pm.get_base_directory(dir_type_name) # Use PathManager
        if os.path.exists(parent_path) and not os.listdir(parent_path):
            os.rmdir(parent_path)
    if os.path.exists(old_format_workspace) and not os.listdir(old_format_workspace):
        os.rmdir(old_format_workspace)
    logger.info(f"Old format test workspace {old_format_workspace} cleaned up.")

if __name__ == '__main__':
    test_progress_manager()
    test_get_epub_file_details_backward_compatibility()
