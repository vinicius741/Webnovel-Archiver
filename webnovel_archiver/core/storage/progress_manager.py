import json
import os
import re
import datetime
from typing import Dict, Optional, List, Any
from webnovel_archiver.core.storage.index_manager import IndexManager
from urllib.parse import urlparse

from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager

logger = get_logger(__name__)

PROGRESS_FILE_VERSION = "1.1"

class ProgressManager:
    def __init__(self, story_path: str):
        self.progress_file_path = os.path.join(story_path, 'progress.json')
        self.progress_data = self._load_progress()

    def _load_progress(self) -> Dict[str, Any]:
        if not os.path.exists(self.progress_file_path):
            return self._get_new_progress_structure()

        try:
            with open(self.progress_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Simple validation
            if 'story_id' not in data:
                return self._get_new_progress_structure()
            return data
        except (json.JSONDecodeError, IOError):
            return self._get_new_progress_structure()

    def _get_new_progress_structure(self) -> Dict[str, Any]:
        return {
            "version": PROGRESS_FILE_VERSION,
            "story_id": None,
            "story_url": None,
            "original_title": None,
            "original_author": None,
            "cover_image_url": None,
            "synopsis": None,
            "downloaded_chapters": [],
            "last_epub_processing": {},
        }

    def save(self):
        self.progress_data["last_updated_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.progress_data["version"] = PROGRESS_FILE_VERSION
        os.makedirs(os.path.dirname(self.progress_file_path), exist_ok=True)
        with open(self.progress_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.progress_data, f, indent=2, ensure_ascii=False)

    def get_url(self) -> Optional[str]:
        return self.progress_data.get('story_url')

    def progress_exists(self) -> bool:
        return os.path.exists(self.progress_file_path)

def load_progress(progress_file_path: str) -> Dict[str, Any]:
    if not os.path.exists(progress_file_path):
        return {}

    try:
        with open(progress_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_progress(progress_file_path: str, progress_data: Dict[str, Any]):
    os.makedirs(os.path.dirname(progress_file_path), exist_ok=True)
    progress_data["last_updated_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    progress_data["version"] = PROGRESS_FILE_VERSION
    with open(progress_file_path, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

def get_epub_file_details(progress_data: Dict[str, Any], story_id: str, path_manager: PathManager) -> List[Dict[str, str]]:
    workspace_root = path_manager.get_workspace_root()
    ebook_dir = os.path.join(workspace_root, PathManager.EBOOKS_DIR_NAME, story_id)

    epub_file_entries = progress_data.get("last_epub_processing", {}).get("generated_epub_files", [])
    resolved_epub_files = []

    if not os.path.isdir(ebook_dir):
        logger.warning(f"Ebook directory {ebook_dir} for story {story_id} not found. Cannot resolve relative EPUB paths.")

    for entry in epub_file_entries:
        path = None
        name = None

        if isinstance(entry, dict):
            path = entry.get("path")
            name = entry.get("name")
        elif isinstance(entry, str):
            name = os.path.basename(entry)
            if os.path.isabs(entry):
                path = entry
            else:
                if os.path.isdir(ebook_dir):
                    path = os.path.join(ebook_dir, entry)
                else:
                    path = entry
            logger.info(f"Processing old format EPUB entry for story {story_id}: '{entry}'. Derived name: '{name}', path: '{path}'")
        else:
            logger.warning(f"Skipping unknown EPUB entry type in {story_id}: {type(entry)} - {entry}")
            continue

        if not path or not name:
            logger.warning(f"Skipping malformed or unresolvable EPUB entry in {story_id}: {entry}")
            continue

        if not os.path.isabs(path):
            if os.path.isdir(ebook_dir):
                logger.warning(f"EPUB path '{path}' for story {story_id} was not absolute. Resolving against {ebook_dir}.")
                path = os.path.join(ebook_dir, os.path.basename(path))
            else:
                logger.error(f"Cannot resolve non-absolute EPUB path '{path}' for story {story_id} because ebook directory {ebook_dir} does not exist.")

        resolved_epub_files.append({"name": name, "path": os.path.normpath(path)})
    return resolved_epub_files