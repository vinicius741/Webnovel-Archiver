import json
import os
import re
import datetime
from typing import Dict, Optional, List, Any
from urllib.parse import urlparse

from webnovel_archiver.utils.logger import get_logger # Added logger

logger = get_logger(__name__) # Added logger

# Define constants for directory names
DEFAULT_WORKSPACE_ROOT = "workspace"
ARCHIVAL_STATUS_DIR = "archival_status"
EBOOKS_DIR = "ebooks" # Added for constructing epub paths
PROGRESS_FILE_VERSION = "1.1" # Version for the progress file structure

def get_progress_filepath(story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> str:
    return os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, story_id, "progress_status.json")

def _get_new_progress_structure(story_id: str, story_url: Optional[str] = None) -> Dict[str, Any]:
    """Returns a new, empty structure for progress_status.json."""
    return {
        "version": PROGRESS_FILE_VERSION, # Added version
        "story_id": story_id,
        "story_url": story_url,
        "original_title": None,
        "original_author": None,
        "cover_image_url": None,
        "synopsis": None,
        "tags": [], # Added tags
        "story_id_from_source": None, # Added story_id_from_source
        "estimated_total_chapters_source": None,
        "last_downloaded_chapter_url": None,
        "next_chapter_to_download_url": None,
        "downloaded_chapters": [],
        "last_epub_processing": {
            "timestamp": None,
            "chapters_included_in_last_volume": None,
            "generated_epub_files": [] # List of dicts: {'name': 'filename.epub', 'path': 'absolute_path_on_disk_when_created'}
                                      # This structure is now aligned with what ProgressManager class had for epub_files
        },
        "sentence_removal_config_used": None,
        "cloud_backup_status": { # Updated structure for cloud_backup_status
            "last_backup_attempt_timestamp": None,
            "last_successful_backup_timestamp": None,
            "service": None,
            "base_cloud_folder_name": None,
            "story_cloud_folder_name": None,
            "cloud_base_folder_id": None,
            "story_cloud_folder_id": None,
            "backed_up_files": []
            # List of dicts:
            # {
            #   'local_path': "abs/path/to/file",
            #   'cloud_file_name': "filename_in_cloud",
            #   'cloud_file_id': "...",
            #   'last_backed_up_timestamp': "ISO_TIMESTAMP",
            #   'status': "uploaded/skipped_up_to_date/failed",
            #   'error': "error message if failed"
            # }
        },
        "last_updated_timestamp": None # Added last_updated_timestamp
    }

def load_progress(story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> Dict[str, Any]:
    """
    Loads progress_status.json for a story_id.
    If it doesn't exist or is corrupted, returns a new structure.
    """
    filepath = get_progress_filepath(story_id, workspace_root)
    new_structure = _get_new_progress_structure(story_id) # For default values and key checks

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("version") != PROGRESS_FILE_VERSION:
                    logger.warning(f"Progress file version mismatch for story {story_id}. "
                                   f"Expected {PROGRESS_FILE_VERSION}, found {data.get('version')}. "
                                   "Data might be read/written unexpectedly. Consider migration.")
                # Ensure all top-level keys from new structure exist
                for key in new_structure.keys():
                    if key not in data:
                        data[key] = new_structure[key]
                # Specifically ensure cloud_backup_status and its sub-keys are present
                if "cloud_backup_status" not in data or not isinstance(data["cloud_backup_status"], dict):
                     data["cloud_backup_status"] = new_structure["cloud_backup_status"]
                else:
                    for sub_key in new_structure["cloud_backup_status"].keys():
                        if sub_key not in data["cloud_backup_status"]:
                            data["cloud_backup_status"][sub_key] = new_structure["cloud_backup_status"][sub_key]

                return data
        except json.JSONDecodeError:
            logger.error(f"Progress file for {story_id} at {filepath} is corrupted. Initializing new one.")
            return new_structure
        except Exception as e:
            logger.error(f"Unexpected error loading progress for story {story_id} from {filepath}: {e}", exc_info=True)
            return new_structure
    else:
        logger.info(f"Progress file not found for story {story_id} at {filepath}. Initializing new one.")
        return new_structure


def save_progress(story_id: str, progress_data: Dict[str, Any], workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> None:
    """Saves the progress_data to progress_status.json for a story_id."""
    filepath = get_progress_filepath(story_id, workspace_root)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    progress_data["last_updated_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    progress_data["version"] = PROGRESS_FILE_VERSION # Ensure version is current

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Progress saved for story {story_id} to {filepath}")
    except IOError as e:
        logger.error(f"Could not write progress file {filepath}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error saving progress for story {story_id} to {filepath}: {e}", exc_info=True)


def generate_story_id(url: Optional[str] = None, title: Optional[str] = None) -> str:
    """
    Generates a URL-safe/filename-safe ID from the story URL or title.
    Prefers URL for uniqueness if available.
    """
    if url:
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]

        if "royalroad.com" in parsed_url.netloc and len(path_parts) >= 2 and path_parts[0] == "fiction":
            numerical_id = path_parts[1]
            # Ensure numerical_id is actually a number before creating the story_id
            if numerical_id.isdigit():
                return f"royalroad-{numerical_id}"

        if path_parts:
            base_id = path_parts[-1]
        else:
            base_id = parsed_url.netloc
            base_id = base_id.replace("www.", "")
    elif title:
        base_id = title
    else:
        return f"story_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    s_id = base_id.lower()
    s_id = re.sub(r'\s+', '-', s_id)
    s_id = re.sub(r'[^a-z0-9_-]', '', s_id)
    s_id = s_id[:50]
    if not s_id:
        return f"story_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    return s_id.strip('-_')

# --- Methods for EPUB files ---
def add_epub_file_to_progress(progress_data: Dict[str, Any], file_name: str, file_path: str, story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> None:
    """Adds an EPUB file to the progress data. Ensures path is absolute."""
    if not os.path.isabs(file_path):
        ebook_dir = os.path.join(workspace_root, EBOOKS_DIR, story_id)
        logger.warning(f"EPUB file path '{file_path}' for '{file_name}' was not absolute. Converting based on ebook_dir: {ebook_dir}")
        file_path = os.path.join(ebook_dir, file_path)

    epub_files_list = progress_data["last_epub_processing"].get("generated_epub_files", [])
    if not any(ep_file['path'] == file_path for ep_file in epub_files_list):
        epub_files_list.append({"name": file_name, "path": file_path})
        progress_data["last_epub_processing"]["generated_epub_files"] = epub_files_list
        logger.debug(f"EPUB file '{file_name}' added for story {story_id}")

def get_epub_file_details(progress_data: Dict[str, Any], story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> List[Dict[str, str]]:
    """
    Retrieves a list of EPUB file details (name, absolute path) from progress data.
    Handles both old (string list) and new (list of dicts) formats for generated_epub_files.
    """
    epub_file_entries = progress_data.get("last_epub_processing", {}).get("generated_epub_files", [])
    resolved_epub_files = []
    ebook_dir = os.path.join(workspace_root, EBOOKS_DIR, story_id) # EBOOKS_DIR is 'ebooks'

    if not os.path.isdir(ebook_dir):
        logger.warning(f"Ebook directory {ebook_dir} for story {story_id} not found. Cannot resolve relative EPUB paths.")
        # Depending on desired strictness, could return empty list or raise error.
        # For now, will try to process absolute paths if any, but relative ones will fail.

    for entry in epub_file_entries:
        path = None
        name = None

        if isinstance(entry, dict):
            path = entry.get("path")
            name = entry.get("name")
        elif isinstance(entry, str):
            # Old format: entry is a filename or relative path string
            name = os.path.basename(entry)
            if os.path.isabs(entry):
                path = entry
            else:
                # Only try to join if ebook_dir exists, otherwise path remains None or relative
                if os.path.isdir(ebook_dir):
                    path = os.path.join(ebook_dir, entry)
                else:
                    path = entry # Keep it as is, likely will fail os.path.exists check later if relative
            logger.info(f"Processing old format EPUB entry for story {story_id}: '{entry}'. Derived name: '{name}', path: '{path}'")
        else:
            logger.warning(f"Skipping unknown EPUB entry type in {story_id}: {type(entry)} - {entry}")
            continue

        if not path or not name:
            logger.warning(f"Skipping malformed or unresolvable EPUB entry in {story_id}: {entry}")
            continue

        # Ensure path is absolute if it was derived from a relative string entry
        # or if a dict entry somehow had a relative path.
        if not os.path.isabs(path):
            if os.path.isdir(ebook_dir):
                 # This re-confirms abs path for string entries if they were relative,
                 # and attempts to fix dict entries that might have stored relative paths.
                logger.warning(f"EPUB path '{path}' for story {story_id} was not absolute. Resolving against {ebook_dir}.")
                path = os.path.join(ebook_dir, os.path.basename(path)) # Use basename to be safe
            else:
                # If ebook_dir doesn't exist and path is not absolute, we can't make it absolute.
                logger.error(f"Cannot resolve non-absolute EPUB path '{path}' for story {story_id} because ebook directory {ebook_dir} does not exist.")
                # Depending on strictness, could skip this entry. For now, it will pass through
                # and likely fail later checks like os.path.exists in the handler.
                # To be safer, we could 'continue' here.

        resolved_epub_files.append({"name": name, "path": os.path.normpath(path)}) # Normalize path
    return resolved_epub_files

# --- Methods for cloud backup status ---
def get_cloud_backup_status(progress_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves the cloud backup status data from progress_data.
    Initializes with default structure if not present or incomplete.
    """
    default_backup_status = _get_new_progress_structure("dummy")["cloud_backup_status"]

    current_backup_status = progress_data.get("cloud_backup_status")
    if not isinstance(current_backup_status, dict):
        progress_data["cloud_backup_status"] = default_backup_status
        return default_backup_status

    # Ensure all keys from default structure are present
    updated = False
    for key, default_value in default_backup_status.items():
        if key not in current_backup_status:
            current_backup_status[key] = default_value
            updated = True

    # if updated: # No, this function should not modify progress_data directly unless it's the one loading it.
    #    logger.info("Initialized missing keys in cloud_backup_status.")

    return current_backup_status

def update_cloud_backup_status(progress_data: Dict[str, Any], backup_info: Dict[str, Any]) -> None:
    """
    Updates the cloud backup status in progress_data.
    `backup_info` should be a dictionary matching the structure defined
    for `cloud_backup_status`.
    """
    # Ensure the cloud_backup_status key exists and is a dict.
    if "cloud_backup_status" not in progress_data or not isinstance(progress_data["cloud_backup_status"], dict):
        progress_data["cloud_backup_status"] = _get_new_progress_structure("dummy")["cloud_backup_status"]

    progress_data["cloud_backup_status"].update(backup_info)
    logger.debug(f"Cloud backup status updated for story {progress_data.get('story_id', 'N/A')}")


if __name__ == '__main__':
    logger.info("--- Testing ProgressManager functions ---") # Use logger

    rr_url = "https://www.royalroad.com/fiction/117255/rend-a-tale-of-something"
    test_story_id = generate_story_id(url=rr_url)
    test_workspace = "_test_pm_workspace"

    logger.info(f"Test Story ID: {test_story_id}, Workspace: {test_workspace}")

    # Clean up any previous test file for this ID
    test_filepath = get_progress_filepath(test_story_id, test_workspace)
    if os.path.exists(test_filepath):
        os.remove(test_filepath)

    story_status_dir = os.path.dirname(test_filepath)
    if os.path.exists(story_status_dir):
        if not os.listdir(story_status_dir):
            os.rmdir(story_status_dir)

    # Create ebook dir for test
    ebook_dir_for_test = os.path.join(test_workspace, EBOOKS_DIR, test_story_id)
    os.makedirs(ebook_dir_for_test, exist_ok=True)


    # Load (should create new)
    progress = load_progress(test_story_id, workspace_root=test_workspace)
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
    story_archival_dir = os.path.join(test_workspace, ARCHIVAL_STATUS_DIR, test_story_id)
    if os.path.exists(story_archival_dir) and not os.listdir(story_archival_dir): os.rmdir(story_archival_dir)

    # Clean up parent directories if they are empty and created by this test
    for parent_dir_name in [EBOOKS_DIR, ARCHIVAL_STATUS_DIR]:
        parent_path = os.path.join(test_workspace, parent_dir_name)
        if os.path.exists(parent_path) and not os.listdir(parent_path):
            os.rmdir(parent_path)
    if os.path.exists(test_workspace) and not os.listdir(test_workspace):
        os.rmdir(test_workspace)
    logger.info(f"Test workspace {test_workspace} cleaned up.")

    logger.info("--- Testing get_epub_file_details backward compatibility ---")

    # 1. Setup progress_data with old format epub entries
    old_format_story_id = "story_with_old_epubs"
    old_format_workspace = "_test_pm_old_format_workspace"

    # Ensure workspace and ebook directory exist for this test
    old_format_ebook_dir = os.path.join(old_format_workspace, EBOOKS_DIR, old_format_story_id)
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

    old_format_story_archival_dir = os.path.join(old_format_workspace, ARCHIVAL_STATUS_DIR, old_format_story_id)
    if os.path.exists(old_format_story_archival_dir) and not os.listdir(old_format_story_archival_dir): os.rmdir(old_format_story_archival_dir)

    for parent_dir_name in [EBOOKS_DIR, ARCHIVAL_STATUS_DIR]:
        parent_path = os.path.join(old_format_workspace, parent_dir_name)
        if os.path.exists(parent_path) and not os.listdir(parent_path):
            os.rmdir(parent_path)
    if os.path.exists(old_format_workspace) and not os.listdir(old_format_workspace):
        os.rmdir(old_format_workspace)
    logger.info(f"Old format test workspace {old_format_workspace} cleaned up.")
