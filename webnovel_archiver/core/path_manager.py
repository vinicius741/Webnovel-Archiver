import os
from typing import Optional

class PathManager:
    """
    Manages the construction of file and directory paths for a story's workspace.
    """
    RAW_CONTENT_DIR_NAME = "raw_content"
    PROCESSED_CONTENT_DIR_NAME = "processed_content"
    EBOOKS_DIR_NAME = "ebooks"
    ARCHIVAL_STATUS_DIR_NAME = "archival_status"
    TEMP_COVER_DIR_NAME = "temp_cover_images" # Subdirectory within EBOOKS_DIR_NAME/story_id
    PROGRESS_FILENAME = "progress_status.json"
    INDEX_FILENAME = "index.json"

    def __init__(self, workspace_root: str, story_id: Optional[str] = None):
        """
        Initializes PathManager with the root of the workspace and optionally a story ID.

        Args:
            workspace_root: The absolute or relative path to the workspace directory.
            story_id: The unique identifier for the story. Can be None for workspace-level paths.
        """
        if not workspace_root:
            raise ValueError("workspace_root cannot be empty.")
        if story_id is not None and not story_id:
            raise ValueError("story_id cannot be empty if provided.")

        self._workspace_root = workspace_root
        self._story_id = story_id

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    @property
    def index_path(self) -> str:
        """Returns the full path to the index.json file."""
        return os.path.join(self._workspace_root, self.INDEX_FILENAME)

    def get_workspace_root(self) -> str:
        """Returns the workspace root path."""
        return self._workspace_root

    def get_story_id(self) -> str:
        """Returns the story ID."""
        if not self._story_id:
            raise ValueError("story_id is not set.")
        return self._story_id

    # Raw Content Paths
    def get_raw_content_story_dir(self) -> str:
        """Returns the path to the raw content directory for the story."""
        return os.path.join(self._workspace_root, self.RAW_CONTENT_DIR_NAME, self.get_story_id())

    def get_raw_content_chapter_filepath(self, raw_filename: str) -> str:
        """Returns the full path to a specific raw chapter file."""
        if not raw_filename:
            raise ValueError("raw_filename cannot be empty.")
        return os.path.join(self.get_raw_content_story_dir(), raw_filename)

    # Processed Content Paths
    def get_processed_content_story_dir(self) -> str:
        """Returns the path to the processed content directory for the story."""
        return os.path.join(self._workspace_root, self.PROCESSED_CONTENT_DIR_NAME, self.get_story_id())

    def get_processed_content_chapter_filepath(self, processed_filename: str) -> str:
        """Returns the full path to a specific processed chapter file."""
        if not processed_filename:
            raise ValueError("processed_filename cannot be empty.")
        return os.path.join(self.get_processed_content_story_dir(), processed_filename)

    # Archival Status Paths
    def get_archival_status_story_dir(self) -> str:
        """Returns the path to the archival status directory for the story."""
        return os.path.join(self._workspace_root, self.ARCHIVAL_STATUS_DIR_NAME, self.get_story_id())

    def get_progress_filepath(self) -> str:
        """Returns the full path to the progress status file for the story."""
        return os.path.join(self.get_archival_status_story_dir(), self.PROGRESS_FILENAME)

    # Ebooks and Cover Paths
    def get_ebooks_story_dir(self) -> str:
        """Returns the path to the ebooks directory for the story."""
        return os.path.join(self._workspace_root, self.EBOOKS_DIR_NAME, self.get_story_id())

    def get_epub_filepath(self, epub_filename: str) -> str:
        """Returns the full path to a specific EPUB file."""
        if not epub_filename:
            raise ValueError("epub_filename cannot be empty.")
        return os.path.join(self.get_ebooks_story_dir(), epub_filename)

    def get_temp_cover_story_dir(self) -> str:
        """
        Returns the path to the temporary cover images directory for the story.
        This is a subdirectory within the story's ebook directory.
        """
        return os.path.join(self.get_ebooks_story_dir(), self.TEMP_COVER_DIR_NAME)

    def get_cover_image_filepath(self, cover_filename: str) -> str:
        """
        Returns the full path to a specific cover image file within the temp cover directory.
        """
        if not cover_filename:
            raise ValueError("cover_filename cannot be empty.")
        return os.path.join(self.get_temp_cover_story_dir(), cover_filename)

    # Generic directory getter for base directories (raw, processed, ebooks, archival_status)
    def get_base_directory(self, dir_type: str) -> str:
        """
        Returns the path to a base directory type within the workspace root.
        Example: get_base_directory(PathManager.RAW_CONTENT_DIR_NAME)
                 returns workspace_root/raw_content
        """
        if dir_type not in [self.RAW_CONTENT_DIR_NAME, self.PROCESSED_CONTENT_DIR_NAME,
                            self.EBOOKS_DIR_NAME, self.ARCHIVAL_STATUS_DIR_NAME]:
            raise ValueError(f"Invalid directory type: {dir_type}")
        return os.path.join(self._workspace_root, dir_type)
