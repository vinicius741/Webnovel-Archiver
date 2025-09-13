import os
from typing import Dict, List, Any
from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager

logger = get_logger(__name__)

def add_epub_file_to_progress(progress_data: Dict[str, Any], file_name: str, file_path: str, story_id: str, workspace_root: str) -> Dict[str, Any]: # Removed DEFAULT_WORKSPACE_ROOT default
    """Adds an EPUB file to the progress data. Ensures path is absolute."""
    # workspace_root must be provided
    pm = PathManager(workspace_root, story_id)
    ebook_dir = pm.get_ebooks_story_dir()


    if "last_epub_processing" not in progress_data or progress_data["last_epub_processing"] is None:
        progress_data["last_epub_processing"] = {"timestamp": None, "chapters_included_in_last_volume": None, "generated_epub_files": []}

    epub_files_list = progress_data["last_epub_processing"].get("generated_epub_files", [])
    if not os.path.isabs(file_path):
        logger.warning(f"EPUB file path '{file_path}' for '{file_name}' was not absolute. Converting based on ebook_dir: {ebook_dir}")
        # PathManager's get_epub_filepath would be ideal if we always construct from filename,
        # but here file_path might already be a relative path we want to make absolute.
        file_path = os.path.join(ebook_dir, os.path.basename(file_path)) # Use basename to ensure it's just the file in the target dir

    if not any(ep_file['path'] == file_path for ep_file in epub_files_list):
        epub_files_list.append({"name": file_name, "path": file_path})
        progress_data["last_epub_processing"]["generated_epub_files"] = epub_files_list
        logger.debug(f"EPUB file '{file_name}' added for story {story_id}")
    else:
        logger.debug(f"EPUB file '{file_name}' with path '{file_path}' already exists in progress data. Skipping add.")
    return progress_data

def get_epub_file_details(progress_data: Dict[str, Any], story_id: str, workspace_root: str) -> List[Dict[str, str]]: # Removed DEFAULT_WORKSPACE_ROOT default
    """
    Retrieves a list of EPUB file details (name, absolute path) from progress data.
    Handles both old (string list) and new (list of dicts) formats for generated_epub_files.
    """
    # workspace_root must be provided
    pm = PathManager(workspace_root, story_id)
    ebook_dir = pm.get_ebooks_story_dir()

    epub_file_entries = progress_data.get("last_epub_processing", {}).get("generated_epub_files", [])
    resolved_epub_files = []
    # ebook_dir = os.path.join(workspace_root, EBOOKS_DIR, story_id) # EBOOKS_DIR is 'ebooks' # Replaced by PathManager

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
