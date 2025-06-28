import json
import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IndexManager:
    """
    Manages the master index of stories, mapping permanent story IDs to folder names.
    """

    def __init__(self, workspace_path: str):
        """
        Initializes the IndexManager.

        Args:
            workspace_path: The absolute path to the workspace directory.
        """
        self.index_path = os.path.join(workspace_path, 'index.json')
        self._index_cache: Optional[Dict[str, str]] = None

    def _load_index(self) -> Dict[str, str]:
        """
        Loads the index file from disk.

        Returns:
            A dictionary representing the index.
        """
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_exists():
            self._index_cache = {}
            return {}

        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                self._index_cache = json.load(f)
                return self._index_cache
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load index file at {self.index_path}: {e}")
            # Return an empty dict on error to prevent crashing, but log the issue.
            return {}

    def _save_index(self):
        """
        Saves the current index cache to the index.json file.
        """
        if self._index_cache is None:
            return

        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(self._index_cache, f, indent=2, sort_keys=True)
        except IOError as e:
            logger.error(f"Failed to save index file to {self.index_path}: {e}")

    def index_exists(self) -> bool:
        """
        Checks if the index.json file exists.

        Returns:
            True if the index file exists, False otherwise.
        """
        return os.path.exists(self.index_path)

    def get_folder_name(self, story_id: str) -> Optional[str]:
        """
        Gets the folder name for a given permanent story ID.

        Args:
            story_id: The permanent, source-specific ID of the story.

        Returns:
            The folder name if the story is in the index, otherwise None.
        """
        index = self._load_index()
        return index.get(story_id)

    def add_story(self, story_id: str, folder_name: str):
        """
        Adds a new story to the index.

        Args:
            story_id: The permanent, source-specific ID of the story.
            folder_name: The slugified folder name for the story.
        """
        index = self._load_index()
        if story_id in index:
            logger.warning(f"Attempted to add story ID '{story_id}' which already exists in the index.")
            return

        index[story_id] = folder_name
        self._save_index()
        logger.debug(f"Added new story to index: '{story_id}' -> '{folder_name}'")

    def update_folder_name(self, story_id: str, new_folder_name: str):
        """
        Updates the folder name for an existing story.

        Args:
            story_id: The permanent, source-specific ID of the story.
            new_folder_name: The new slugified folder name.
        """
        index = self._load_index()
        if story_id not in index:
            logger.warning(f"Attempted to update folder name for story ID '{story_id}' which does not exist.")
            return

        if index[story_id] != new_folder_name:
            logger.info(f"Updating folder name for story '{story_id}' from '{index[story_id]}' to '{new_folder_name}'.")
            index[story_id] = new_folder_name
            self._save_index()

    def get_all_stories(self) -> Dict[str, str]:
        """
        Returns a copy of the entire story index.

        Returns:
            A dictionary containing all story ID to folder name mappings.
        """
        return self._load_index().copy()
