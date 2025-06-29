import os
import shutil
import unittest
from unittest.mock import MagicMock, patch, call, mock_open
import datetime
import copy # For deepcopying progress data
import json

from webnovel_archiver.core.orchestrator import archive_story
from webnovel_archiver.core.fetchers.base_fetcher import StoryMetadata, ChapterInfo

class TestArchiveStory(unittest.TestCase):

    def setUp(self):
        self.mock_progress_callback = MagicMock()
        self.test_story_url = "https://www.test.com/fiction/123"
        self.test_workspace_root = os.path.join("workspace", "test_workspace_orchestrator")
        self.permanent_id = "royalroad-12345"
        self.story_folder_name = "a-test-story"

        # Mocked metadata and chapter info
        self.mock_metadata = StoryMetadata(
            original_title="Test Story",
            original_author="Test Author",
            cover_image_url="https://test.com/cover.jpg",
            synopsis="A test synopsis.",
            story_id=self.permanent_id, # Will be set by orchestrator
            estimated_total_chapters_source=2 # Default value
        )
        self.mock_chapters_info = [
            ChapterInfo(chapter_url="https://test.com/fiction/123/chapter/1", chapter_title="Chapter 1", download_order=1, source_chapter_id="c1"),
            ChapterInfo(chapter_url="https://test.com/fiction/123/chapter/2", chapter_title="Chapter 2", download_order=2, source_chapter_id="c2"),
        ]

        # Start patching common dependencies
        self.patchers = {
            'get_fetcher': patch('webnovel_archiver.core.orchestrator.FetcherFactory.get_fetcher').start(),
            'EPUBGenerator': patch('webnovel_archiver.core.orchestrator.EPUBGenerator').start(),
            'os.makedirs': patch('os.makedirs').start(),
            'os.path.exists': patch('os.path.exists', return_value=True).start(), # Default to True, override per test if needed
            'open': patch('builtins.open', mock_open()).start(),
            'shutil.rmtree': patch('shutil.rmtree').start(),
            'load_progress': patch('webnovel_archiver.core.orchestrator.load_progress').start(), # Return value set per test
            'save_progress': patch('webnovel_archiver.core.orchestrator.save_progress').start(),
            'PathManager': patch('webnovel_archiver.core.orchestrator.PathManager').start(),
            'logger': patch('webnovel_archiver.core.orchestrator.logger').start(), # Mock logger to suppress output
            'datetime': patch('webnovel_archiver.core.orchestrator.datetime').start(), # Mock datetime
        }

        # Configure mock for datetime.datetime.utcnow()
        self.mock_datetime = self.patchers['datetime']
        self.mock_utcnow = MagicMock()
        self.mock_datetime.datetime.utcnow.return_value = self.mock_utcnow
        self.FROZEN_TIME_STR = "2023-01-01T12:00:00Z"
        self.mock_utcnow.isoformat.return_value = "2023-01-01T12:00:00" # .isoformat() is called before adding 'Z'

        # Configure Fetcher mock instance
        self.mock_fetcher_instance = self.patchers['get_fetcher'].return_value
        self.mock_fetcher_instance.get_permanent_id.return_value = self.permanent_id
        self.mock_fetcher_instance.get_story_metadata.return_value = self.mock_metadata
        self.mock_fetcher_instance.get_chapter_urls.return_value = self.mock_chapters_info
        self.mock_fetcher_instance.download_chapter_content.side_effect = lambda url: f"<html><body>Content for {url}</body></html>"

        # Configure EPUBGenerator mock instance
        self.mock_epub_generator_instance = self.patchers['EPUBGenerator'].return_value
        self.mock_epub_generator_instance.generate_epub.return_value = [
            os.path.join(self.test_workspace_root, "ebooks", self.story_folder_name, "Test_Story_Vol_1.epub")
        ]

    def tearDown(self):
        patch.stopall()

    def test_uses_index_to_find_story_folder(self):
        # Arrange
        mock_index_data = {self.permanent_id: self.story_folder_name}
        self.patchers['open'].side_effect = [
            mock_open(read_data=json.dumps(mock_index_data)).return_value,
            mock_open().return_value, # for subsequent open calls
        ]
        self.patchers['load_progress'].return_value = {}

        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
        )

        # Assert
        self.patchers['PathManager'].assert_any_call(self.test_workspace_root, self.story_folder_name)

if __name__ == '__main__':
    unittest.main()
