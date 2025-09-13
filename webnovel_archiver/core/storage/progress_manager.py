import json
import os
import re
import datetime
from typing import Dict, Optional, List, Any
from urllib.parse import urlparse

from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager
from .progress_epub import add_epub_file_to_progress, get_epub_file_details

logger = get_logger(__name__)

# Define constants for directory names
# DEFAULT_WORKSPACE_ROOT = "workspace" # Removed
# ARCHIVAL_STATUS_DIR = "archival_status" # Removed
# EBOOKS_DIR = "ebooks" # Removed
PROGRESS_FILE_VERSION = "1.1" # Version for the progress file structure

def get_progress_filepath(story_id: str, workspace_root: str) -> str: # Removed DEFAULT_WORKSPACE_ROOT default
    # workspace_root must be provided
    pm = PathManager(workspace_root, story_id)
    return pm.get_progress_filepath()

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
        # List of dicts, where each dict represents a chapter and its status.
        # New chapter schema:
        # {
        #   "source_chapter_id": "...",  // Unique ID for the chapter from the source website
        #   "download_order": 1,         // Sequential order in which the chapter was downloaded or should appear
        #   "chapter_url": "...",        // Full URL to the chapter
        #   "chapter_title": "...",      // Title of the chapter
        #   "status": "active",          // 'active' (exists on source) or 'archived' (removed from source)
        #   "first_seen_on": "YYYY-MM-DDTHH:MM:SSZ", // ISO 8601 timestamp when chapter was first recorded
        #   "last_checked_on": "YYYY-MM-DDTHH:MM:SSZ",// ISO 8601 timestamp when chapter status was last verified
        #   "local_raw_filename": "...", // Filename of the raw downloaded chapter content (e.g., .html)
        #   "local_processed_filename": "..." // Filename of the processed chapter content (e.g., .txt, .xhtml)
        # }
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
        "last_updated_timestamp": None, # Added last_updated_timestamp
        "last_archived_timestamp": None # Added last_archived_timestamp for cloud backup logic
    }

def load_progress(story_id: str, workspace_root: str) -> Dict[str, Any]: # Removed DEFAULT_WORKSPACE_ROOT default
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

            # Migration logic for chapter status fields
            # This should be done *before* other structural checks like version or missing top-level keys,
            # as the migration addresses a specific part (downloaded_chapters structure).
            downloaded_chapters_list = data.get("downloaded_chapters")
            migration_required = False

            if downloaded_chapters_list is None: # Key 'downloaded_chapters' is missing
                logger.info(f"'downloaded_chapters' key missing in progress file for story '{story_id}' at {filepath}. Initializing key and marking for migration.")
                data["downloaded_chapters"] = [] # Initialize the key with an empty list
                migration_required = True # File exists, but this key is missing, treat as old format needing this structure
            elif not isinstance(downloaded_chapters_list, list):
                logger.warning(f"'downloaded_chapters' in progress file for story '{story_id}' at {filepath} is not a list. Re-initializing key and marking for migration.")
                data["downloaded_chapters"] = [] # Reset to empty list if malformed
                migration_required = True
            else: # It is a list
                if not downloaded_chapters_list: # List is empty
                    # As per requirement: "if downloaded_chapters is empty but the file exists... proceed with migration."
                    # This means logging and backup will occur. The chapter modification loop won't run.
                    migration_required = True
                elif not downloaded_chapters_list[0].get("status"): # Non-empty list, check first chapter for "status" field
                    migration_required = True

            if migration_required:
                logger.info(f"Migrating progress file for story '{story_id}' at {filepath} to new format with status fields in chapters.")

                # Get file modification time for chapter timestamps
                file_mod_time_iso = "N/A"
                try:
                    mtime = os.path.getmtime(filepath)
                    file_mod_time_iso = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).isoformat()
                except OSError as e:
                    logger.warning(f"Could not retrieve modification time for progress file {filepath} during migration. Using 'N/A' for timestamps. Error: {e}")

                backup_filepath = filepath + ".bak"
                try:
                    import shutil # Import here for focused change, though top-level is conventional
                    shutil.copy2(filepath, backup_filepath)
                    logger.info(f"Backed up original progress file for story '{story_id}' to {backup_filepath}")
                except Exception as e_backup:
                    logger.error(f"Failed to create backup {backup_filepath} for story '{story_id}': {e_backup}. Proceeding with migration without backup.")

                current_chapters_data = data.get("downloaded_chapters", []) # Get potentially reset list
                migrated_chapters_list = []
                if isinstance(current_chapters_data, list): # Iterate only if it's a list
                    for chapter in current_chapters_data:
                        if isinstance(chapter, dict): # Process only if chapter is a dictionary
                            chapter_copy = chapter.copy()
                            chapter_copy["status"] = "active"
                            chapter_copy["first_seen_on"] = file_mod_time_iso
                            chapter_copy["last_checked_on"] = file_mod_time_iso
                            migrated_chapters_list.append(chapter_copy)
                        else:
                            logger.warning(f"Skipping non-dict chapter entry during migration for story '{story_id}' in {filepath}: {chapter}")
                            migrated_chapters_list.append(chapter) # Preserve non-dict items
                data["downloaded_chapters"] = migrated_chapters_list

            # Existing checks for version and ensuring all top-level keys
            if data.get("version") != PROGRESS_FILE_VERSION:
                logger.warning(f"Progress file version mismatch for story {story_id}. "
                               f"Expected {PROGRESS_FILE_VERSION}, found {data.get('version')}. "
                               "Data might be read/written unexpectedly. Consider migration.")

            # Ensure all keys from the new_structure are present in the loaded data
            for key, default_value in new_structure.items():
                if key not in data:
                    logger.info(f"Adding missing key '{key}' with default value to progress data for story {story_id}.")
                    data[key] = default_value
                # Ensure sub-dictionaries like cloud_backup_status also have all their keys
                elif isinstance(default_value, dict) and isinstance(data.get(key), dict):
                    for sub_key, sub_default_value in default_value.items():
                        if sub_key not in data[key]:
                            logger.info(f"Adding missing sub-key '{key}.{sub_key}' with default value to progress data for story {story_id}.")
                            data[key][sub_key] = sub_default_value


            # This specific check for cloud_backup_status structure might be redundant now with the generic loop above,
            # but keeping it for explicitness or if more complex logic was intended.
            # if "cloud_backup_status" not in data or not isinstance(data["cloud_backup_status"], dict):
            #      data["cloud_backup_status"] = new_structure["cloud_backup_status"]
            # else:
            #     for sub_key in new_structure["cloud_backup_status"].keys():
            #         if sub_key not in data["cloud_backup_status"]:
            #             data["cloud_backup_status"][sub_key] = new_structure["cloud_backup_status"][sub_key]

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


def save_progress(story_id: str, progress_data: Dict[str, Any], workspace_root: str) -> None: # Removed DEFAULT_WORKSPACE_ROOT default
    """Saves the progress_data to progress_status.json for a story_id."""
    # workspace_root must be provided
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




