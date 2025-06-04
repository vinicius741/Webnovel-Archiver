import os
import shutil
import unittest
from unittest.mock import MagicMock, patch, call, mock_open

from webnovel_archiver.core.orchestrator import archive_story
from webnovel_archiver.core.fetchers.base_fetcher import StoryMetadata, ChapterInfo
from webnovel_archiver.core.storage.progress_manager import DEFAULT_WORKSPACE_ROOT


class TestArchiveStory(unittest.TestCase):

    def setUp(self):
        self.mock_progress_callback = MagicMock()
        self.test_story_url = "https://www.test.com/fiction/123"
        self.test_workspace_root = os.path.join(DEFAULT_WORKSPACE_ROOT, "test_workspace_orchestrator")
        self.story_id = "test_story_id_123"

        # Mocked metadata and chapter info
        self.mock_metadata = StoryMetadata(
            original_title="Test Story",
            original_author="Test Author",
            cover_image_url="https://test.com/cover.jpg",
            synopsis="A test synopsis.",
            story_id=self.story_id, # Will be set by orchestrator
            estimated_total_chapters_source=2 # Default value
        )
        self.mock_chapters_info = [
            ChapterInfo(chapter_url="https://test.com/fiction/123/chapter/1", chapter_title="Chapter 1", download_order=1, source_chapter_id="c1"),
            ChapterInfo(chapter_url="https://test.com/fiction/123/chapter/2", chapter_title="Chapter 2", download_order=2, source_chapter_id="c2"),
        ]

        # Start patching common dependencies
        self.patchers = {
            'RoyalRoadFetcher': patch('webnovel_archiver.core.orchestrator.RoyalRoadFetcher').start(),
            'EPUBGenerator': patch('webnovel_archiver.core.orchestrator.EPUBGenerator').start(),
            'os.makedirs': patch('os.makedirs').start(),
            'os.path.exists': patch('os.path.exists', return_value=True).start(), # Default to True, override per test if needed
            'open': patch('builtins.open', mock_open()).start(),
            'shutil.rmtree': patch('shutil.rmtree').start(),
            'load_progress': patch('webnovel_archiver.core.orchestrator.load_progress', return_value={}).start(),
            'save_progress': patch('webnovel_archiver.core.orchestrator.save_progress').start(),
            'generate_story_id': patch('webnovel_archiver.core.orchestrator.generate_story_id', return_value=self.story_id).start(),
            'logger': patch('webnovel_archiver.core.orchestrator.logger').start(), # Mock logger to suppress output
        }

        # Configure Fetcher mock instance
        self.mock_fetcher_instance = self.patchers['RoyalRoadFetcher'].return_value
        self.mock_fetcher_instance.get_story_metadata.return_value = self.mock_metadata
        self.mock_fetcher_instance.get_chapter_urls.return_value = self.mock_chapters_info
        self.mock_fetcher_instance.download_chapter_content.side_effect = lambda url: f"<html><body>Content for {url}</body></html>"

        # Configure EPUBGenerator mock instance
        self.mock_epub_generator_instance = self.patchers['EPUBGenerator'].return_value
        self.mock_epub_generator_instance.generate_epub.return_value = [
            os.path.join(self.test_workspace_root, "ebooks", self.story_id, "Test_Story_Vol_1.epub")
        ]


    def tearDown(self):
        patch.stopall()
        if os.path.exists(self.test_workspace_root):
             # In case a test fails and doesn't clean up, or if actual FS ops were accidentally done
            shutil.rmtree(self.test_workspace_root, ignore_errors=True)


    def test_successful_run_callbacks_and_summary(self):
        # Arrange
        self.patchers['os.path.exists'].return_value = False # Simulate no existing files for full processing

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert Callbacks
        expected_calls = [
            # Initial
            call({"status": "info", "message": "Starting archival process..."}),
            # Metadata
            call({"status": "info", "message": "Fetching story metadata..."}),
            call({"status": "info", "message": f"Successfully fetched metadata: {self.mock_metadata.original_title}"}),
            # Chapter List
            call({"status": "info", "message": "Fetching chapter list..."}),
            call({"status": "info", "message": f"Found {len(self.mock_chapters_info)} chapters."}),
            # Chapter 1
            call({
                "status": "info", "message": f"Processing chapter: {self.mock_chapters_info[0].chapter_title} (1/{len(self.mock_chapters_info)})",
                "current_chapter_num": 1, "total_chapters": len(self.mock_chapters_info), "chapter_title": self.mock_chapters_info[0].chapter_title
            }),
            call({"status": "info", "message": f"Successfully saved raw content for chapter: {self.mock_chapters_info[0].chapter_title}", "chapter_title": self.mock_chapters_info[0].chapter_title}),
            call({"status": "info", "message": f"Successfully saved processed content for chapter: {self.mock_chapters_info[0].chapter_title}", "chapter_title": self.mock_chapters_info[0].chapter_title}),
            # Chapter 2
            call({
                "status": "info", "message": f"Processing chapter: {self.mock_chapters_info[1].chapter_title} (2/{len(self.mock_chapters_info)})",
                "current_chapter_num": 2, "total_chapters": len(self.mock_chapters_info), "chapter_title": self.mock_chapters_info[1].chapter_title
            }),
            call({"status": "info", "message": f"Successfully saved raw content for chapter: {self.mock_chapters_info[1].chapter_title}", "chapter_title": self.mock_chapters_info[1].chapter_title}),
            call({"status": "info", "message": f"Successfully saved processed content for chapter: {self.mock_chapters_info[1].chapter_title}", "chapter_title": self.mock_chapters_info[1].chapter_title}),
            # EPUB Generation
            call({"status": "info", "message": "Starting EPUB generation..."}),
            call({"status": "info", "message": f"Successfully generated EPUB file(s): {self.mock_epub_generator_instance.generate_epub.return_value}", "file_paths": self.mock_epub_generator_instance.generate_epub.return_value}),
            # Cleanup (default is keep_temp_files=False)
            call({"status": "info", "message": "Cleaning up temporary files..."}),
            call({"status": "info", "message": "Successfully cleaned up temporary files."}),
            # Completion
            call({"status": "info", "message": "Archival process completed."})
        ]

        # Filter out __bool__ calls from the actual calls list
        actual_calls = [c for c in self.mock_progress_callback.call_args_list if c != call.__bool__()]
        self.assertEqual(actual_calls, expected_calls)

        # Assert Summary
        self.assertIsNotNone(summary)
        self.assertEqual(summary['story_id'], self.story_id)
        self.assertEqual(summary['title'], self.mock_metadata.original_title)
        self.assertEqual(summary['chapters_processed'], len(self.mock_chapters_info))
        # Convert to abspath for comparison as orchestrator does
        expected_epub_paths = [os.path.abspath(p) for p in self.mock_epub_generator_instance.generate_epub.return_value]
        self.assertEqual(summary['epub_files'], expected_epub_paths)
        self.assertEqual(summary['workspace_root'], os.path.abspath(self.test_workspace_root))

    def test_metadata_fetch_failure(self):
        # Arrange
        self.mock_fetcher_instance.get_story_metadata.side_effect = Exception("Network error")

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.mock_progress_callback.assert_any_call({"status": "error", "message": "An unexpected error occurred while fetching story metadata: Network error"})
        self.assertIsNone(summary)

    def test_chapter_list_fetch_failure(self):
        # Arrange
        self.mock_fetcher_instance.get_chapter_urls.side_effect = Exception("Chapter list error")

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.mock_progress_callback.assert_any_call({"status": "error", "message": "An unexpected error occurred while fetching chapter list: Chapter list error"})
        self.assertIsNone(summary)

    def test_no_chapters_found(self):
        # Arrange
        self.mock_fetcher_instance.get_chapter_urls.return_value = []

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.mock_progress_callback.assert_any_call({"status": "warning", "message": "No chapters found. Aborting archival."})
        self.assertIsNone(summary)

    def test_chapter_download_failure_skips_chapter_and_continues(self):
        # Arrange
        failing_chapter_title = self.mock_chapters_info[0].chapter_title
        self.mock_fetcher_instance.download_chapter_content.side_effect = [
            Exception("Download failed for chapter 1"), # Fails for first chapter
            "<html><body>Content for Chapter 2</body></html>" # Succeeds for second
        ]
        self.patchers['os.path.exists'].return_value = False # Process all

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        # Check that error callback for chapter 1 was called
        self.mock_progress_callback.assert_any_call({
            "status": "error",
            "message": f"An unexpected error occurred while downloading chapter: {failing_chapter_title}. Error: Download failed for chapter 1",
            "chapter_title": failing_chapter_title
        })
        # Check that chapter 2 (successful one) was processed
        self.mock_progress_callback.assert_any_call({
            "status": "info",
            "message": f"Successfully saved processed content for chapter: {self.mock_chapters_info[1].chapter_title}",
            "chapter_title": self.mock_chapters_info[1].chapter_title
        })

        self.assertIsNotNone(summary)
        self.assertEqual(summary['chapters_processed'], 1) # Only one chapter successfully processed
        self.assertEqual(summary['title'], self.mock_metadata.original_title)
        # EPUB should still be generated with the chapter that succeeded
        self.assertTrue(len(summary['epub_files']) > 0)


    def test_keep_temp_files_true(self):
        # Arrange
        self.patchers['os.path.exists'].return_value = False # Process all

        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback,
            keep_temp_files=True
        )

        # Assert
        # Check that rmtree was NOT called
        self.patchers['shutil.rmtree'].assert_not_called()
        # Check that "Cleaning up" message was NOT sent
        cleanup_call_found = False
        for call_item in self.mock_progress_callback.call_args_list:
            args, _ = call_item
            if isinstance(args[0], dict) and "Cleaning up temporary files..." in args[0].get("message", ""):
                cleanup_call_found = True
                break
        self.assertFalse(cleanup_call_found, "Cleanup callback should not have been called when keep_temp_files is True")
        # Final completion message should still be there
        self.mock_progress_callback.assert_any_call({"status": "info", "message": "Archival process completed."})


if __name__ == '__main__':
    unittest.main()
