import os
import logging
from slugify import slugify

from .storage.index_manager import IndexManager

logger = logging.getLogger(__name__)


class PathManager:
    RAW_CONTENT_DIR_NAME = "raw_content"
    PROCESSED_CONTENT_DIR_NAME = "processed_content"
    EBOOKS_DIR_NAME = "ebooks"
    ARCHIVAL_STATUS_DIR_NAME = "archival_status"
    TEMP_COVER_DIR_NAME = "temp_cover_images"
    PROGRESS_FILENAME = "progress.json"

    def __init__(self, workspace_root: str, index_manager: IndexManager):
        if not workspace_root:
            raise ValueError("workspace_root cannot be empty.")

        self._workspace_root = workspace_root
        self._index_manager = index_manager
        self._story_id: str = ""
        self._folder_name: str = ""

    def _get_story_folder_name(self) -> str:
        if not self._story_id:
            raise ValueError("Story ID has not been set. Call set_story first.")
        if not self._folder_name:
            folder_name = self._index_manager.get_folder_name(self._story_id)
            if not folder_name:
                raise ValueError(f"Folder name for story ID '{self._story_id}' not found in index.")
            self._folder_name = folder_name
        return self._folder_name

    def set_story(self, story_id: str, story_title: str):
        self._story_id = story_id
        new_slug = slugify(story_title)

        existing_folder_name = self._index_manager.get_folder_name(story_id)

        if existing_folder_name:
            if existing_folder_name != new_slug:
                self._rename_story_folders(existing_folder_name, new_slug)
                self._index_manager.update_folder_name(story_id, new_slug)
            self._folder_name = new_slug
        else:
            self._folder_name = new_slug
            self._index_manager.add_story(story_id, new_slug)

    def _rename_story_folders(self, old_slug: str, new_slug: str):
        logger.info(f"Renaming story folders from '{old_slug}' to '{new_slug}'.")
        for dir_name in [self.RAW_CONTENT_DIR_NAME, self.PROCESSED_CONTENT_DIR_NAME, self.EBOOKS_DIR_NAME, self.ARCHIVAL_STATUS_DIR_NAME]:
            base_dir = os.path.join(self._workspace_root, dir_name)
            old_path = os.path.join(base_dir, old_slug)
            new_path = os.path.join(base_dir, new_slug)

            if os.path.exists(old_path):
                try:
                    os.rename(old_path, new_path)
                    logger.debug(f"Renamed '{old_path}' to '{new_path}'.")
                except OSError as e:
                    logger.error(f"Failed to rename directory {old_path} to {new_path}: {e}")

    def get_workspace_root(self) -> str:
        return self._workspace_root

    def get_story_id(self) -> str:
        return self._story_id

    def get_raw_content_story_dir(self) -> str:
        return os.path.join(self._workspace_root, self.RAW_CONTENT_DIR_NAME, self._get_story_folder_name())

    def get_raw_content_chapter_filepath(self, raw_filename: str) -> str:
        if not raw_filename:
            raise ValueError("raw_filename cannot be empty.")
        return os.path.join(self.get_raw_content_story_dir(), raw_filename)

    def get_processed_content_story_dir(self) -> str:
        return os.path.join(self._workspace_root, self.PROCESSED_CONTENT_DIR_NAME, self._get_story_folder_name())

    def get_processed_content_chapter_filepath(self, processed_filename: str) -> str:
        if not processed_filename:
            raise ValueError("processed_filename cannot be empty.")
        return os.path.join(self.get_processed_content_story_dir(), processed_filename)

    def get_archival_status_story_dir(self) -> str:
        return os.path.join(self._workspace_root, self.ARCHIVAL_STATUS_DIR_NAME, self._get_story_folder_name())

    def get_progress_filepath(self) -> str:
        return os.path.join(self.get_archival_status_story_dir(), self.PROGRESS_FILENAME)

    def get_ebooks_story_dir(self) -> str:
        return os.path.join(self._workspace_root, self.EBOOKS_DIR_NAME, self._get_story_folder_name())

    def get_epub_filepath(self, epub_filename: str) -> str:
        if not epub_filename:
            raise ValueError("epub_filename cannot be empty.")
        return os.path.join(self.get_ebooks_story_dir(), epub_filename)

    def get_temp_cover_story_dir(self) -> str:
        return os.path.join(self.get_ebooks_story_dir(), self.TEMP_COVER_DIR_NAME)

    def get_cover_image_filepath(self, cover_filename: str) -> str:
        if not cover_filename:
            raise ValueError("cover_filename cannot be empty.")
        return os.path.join(self.get_temp_cover_story_dir(), cover_filename)

    def get_base_directory(self, dir_type: str) -> str:
        if dir_type not in [self.RAW_CONTENT_DIR_NAME, self.PROCESSED_CONTENT_DIR_NAME,
                            self.EBOOKS_DIR_NAME, self.ARCHIVAL_STATUS_DIR_NAME]:
            raise ValueError(f"Invalid directory type: {dir_type}")
        return os.path.join(self._workspace_root, dir_type)