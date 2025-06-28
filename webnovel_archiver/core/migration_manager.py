import logging
import os
import json
from slugify import slugify

from webnovel_archiver.core.storage.index_manager import IndexManager
from webnovel_archiver.core.storage.progress_manager import ProgressManager
from webnovel_archiver.core.fetchers.fetcher_factory import FetcherFactory

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Handles the one-time migration of existing archives to the new index-based system.
    """

    def __init__(self, workspace_path: str, index_manager: IndexManager):
        self.workspace_path = workspace_path
        self.index_manager = index_manager
        self.fetcher_factory = FetcherFactory()

    def migrate_if_needed(self):
        """
        Checks if a migration is needed and performs it if so.
        """
        if self.index_manager.index_exists():
            logger.debug("Index file already exists. No migration needed.")
            return

        logger.info("No index file found. Starting migration of existing archives.")
        self._perform_migration()

    def _perform_migration(self):
        """
        Scans the archival_status directory, extracts metadata, and builds the index.
        """
        archival_status_path = os.path.join(self.workspace_path, 'archival_status')
        if not os.path.isdir(archival_status_path):
            logger.info("Archival status directory not found. No stories to migrate.")
            return

        migrated_count = 0
        for folder_name in os.listdir(archival_status_path):
            story_path = os.path.join(archival_status_path, folder_name)
            if not os.path.isdir(story_path):
                continue

            progress_manager = ProgressManager(story_path)
            if not progress_manager.progress_exists():
                logger.warning(f"No progress file in '{folder_name}'. Skipping migration for this folder.")
                continue

            url = progress_manager.get_url()
            if not url:
                logger.warning(f"No URL found in progress file for '{folder_name}'. Skipping.")
                continue

            try:
                fetcher = self.fetcher_factory.get_fetcher(url)
                story_id = fetcher.get_source_specific_id(url)

                if not story_id:
                    logger.error(f"Could not extract a permanent ID for URL: {url}. Skipping folder '{folder_name}'.")
                    continue

                self.index_manager.add_story(story_id, folder_name)
                migrated_count += 1
                logger.info(f"Migrated '{folder_name}' to index with ID '{story_id}'.")

            except Exception as e:
                logger.error(f"Failed to migrate story from folder '{folder_name}' for URL {url}: {e}")

        if migrated_count > 0:
            logger.info(f"Successfully migrated {migrated_count} stories to the new index system.")
        else:
            logger.info("Migration complete. No stories were found to migrate.")
