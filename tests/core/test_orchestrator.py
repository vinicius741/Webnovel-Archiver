import os
import shutil
import unittest
from unittest.mock import MagicMock, patch, call, mock_open
import datetime
import copy # For deepcopying progress data

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
            'load_progress': patch('webnovel_archiver.core.orchestrator.load_progress').start(), # Return value set per test
            'save_progress': patch('webnovel_archiver.core.orchestrator.save_progress').start(),
            'generate_story_id': patch('webnovel_archiver.core.orchestrator.generate_story_id', return_value=self.story_id).start(),
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
        # This test now also serves as a "first-time archival" test
        # Arrange
        self.patchers['os.path.exists'].return_value = False # Simulate no existing files for full processing
        self.patchers['load_progress'].return_value = {} # Ensure it's a first-time run

        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert Callbacks (simplified for brevity, focus on save_progress for detailed checks)
        self.mock_progress_callback.assert_any_call({"status": "info", "message": "Starting archival process..."})
        self.mock_progress_callback.assert_any_call({"status": "info", "message": f"Successfully fetched metadata: {self.mock_metadata.original_title}"})
        self.mock_progress_callback.assert_any_call({"status": "info", "message": f"Found {len(self.mock_chapters_info)} chapters."})
        # Check processing for first chapter
        self.mock_progress_callback.assert_any_call({ # This is the "Checking chapter" call
            "status": "info", "message": f"Checking chapter: {self.mock_chapters_info[0].chapter_title} (1/{len(self.mock_chapters_info)})",
            "current_chapter_num": 1, "total_chapters": len(self.mock_chapters_info), "chapter_title": self.mock_chapters_info[0].chapter_title
        })
        self.mock_progress_callback.assert_any_call({ # This is the "Processing chapter" call after "Checking"
            "status": "info", "message": f"Processing chapter: {self.mock_chapters_info[0].chapter_title}",
             "chapter_title": self.mock_chapters_info[0].chapter_title
        })


        # Assert Summary
        self.assertIsNotNone(summary)
        self.assertEqual(summary['story_id'], self.story_id)
        self.assertEqual(summary['title'], self.mock_metadata.original_title)
        # chapters_processed in summary now reflects chapters that were actually downloaded/updated in this run.
        # For a first run, this is all chapters.
        self.assertEqual(summary['chapters_processed'], len(self.mock_chapters_info))
        expected_epub_paths = [os.path.abspath(p) for p in self.mock_epub_generator_instance.generate_epub.return_value]
        self.assertEqual(summary['epub_files'], expected_epub_paths)
        self.assertEqual(summary['workspace_root'], os.path.abspath(self.test_workspace_root))

        # Assert save_progress call for first-time archival
        self.patchers['save_progress'].assert_called_once()
        saved_progress_data = self.patchers['save_progress'].call_args[0][1]
        self.assertEqual(len(saved_progress_data["downloaded_chapters"]), len(self.mock_chapters_info))
        for chapter_entry in saved_progress_data["downloaded_chapters"]:
            self.assertEqual(chapter_entry["status"], "active")
            self.assertEqual(chapter_entry["first_seen_on"], self.FROZEN_TIME_STR)
            self.assertEqual(chapter_entry["last_checked_on"], self.FROZEN_TIME_STR)
            self.assertEqual(chapter_entry["download_timestamp"], self.FROZEN_TIME_STR)
            self.assertIn("local_raw_filename", chapter_entry)
            self.assertIn("local_processed_filename", chapter_entry)

    def test_metadata_fetch_failure(self):
        # Arrange
        self.mock_fetcher_instance.get_story_metadata.side_effect = Exception("Network error")
        self.patchers['load_progress'].return_value = {} # Still need to mock this

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
        self.patchers['load_progress'].return_value = {}

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
        self.patchers['load_progress'].return_value = {}

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
        self.patchers['load_progress'].return_value = {}


        # Act
        summary = archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        # Check that error callback for chapter 1 was called
        self.mock_progress_callback.assert_any_call({
            "status": "error", # This is the new error message format
            "message": f"Failed to download chapter: {failing_chapter_title}. HTTP Error: Download failed for chapter 1", # Assuming the error is re-raised as HTTPError or similar
            "chapter_title": failing_chapter_title
        })
        # Check that chapter 2 (successful one) was processed (checking and processing steps)
        self.mock_progress_callback.assert_any_call({
            "status": "info", "message": f"Checking chapter: {self.mock_chapters_info[1].chapter_title} (2/{len(self.mock_chapters_info)})",
            "current_chapter_num": 2, "total_chapters": len(self.mock_chapters_info), "chapter_title": self.mock_chapters_info[1].chapter_title
        })
        self.mock_progress_callback.assert_any_call({
            "status": "info",
            "message": f"Processing chapter: {self.mock_chapters_info[1].chapter_title}",
            "chapter_title": self.mock_chapters_info[1].chapter_title
        })


        self.assertIsNotNone(summary)
        # Check save_progress data for accuracy
        self.patchers['save_progress'].assert_called_once()
        saved_data = self.patchers['save_progress'].call_args[0][1]

        # Only the successfully processed chapter should be in 'downloaded_chapters' with full data
        self.assertEqual(len(saved_data["downloaded_chapters"]), 1)
        successful_chapter_entry = saved_data["downloaded_chapters"][0]
        self.assertEqual(successful_chapter_entry["chapter_title"], self.mock_chapters_info[1].chapter_title)
        self.assertEqual(successful_chapter_entry["status"], "active")
        self.assertEqual(successful_chapter_entry["first_seen_on"], self.FROZEN_TIME_STR)
        self.assertEqual(successful_chapter_entry["last_checked_on"], self.FROZEN_TIME_STR)
        self.assertEqual(successful_chapter_entry["download_timestamp"], self.FROZEN_TIME_STR)

        # The summary['chapters_processed'] should reflect the count from save_progress
        self.assertEqual(summary['chapters_processed'], 1)
        self.assertEqual(summary['title'], self.mock_metadata.original_title)
        self.assertTrue(len(summary['epub_files']) > 0) # EPUB with 1 chapter


    def test_keep_temp_files_true(self):
        # Arrange
        self.patchers['os.path.exists'].return_value = False # Process all
        self.patchers['load_progress'].return_value = {}

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

    def test_new_chapters_added_and_processed(self):
        # Arrange
        OLD_TIME_STR = "2022-12-31T12:00:00Z"
        existing_chapter_info_obj = self.mock_chapters_info[0] # Chapter 1
        new_chapter_info_obj = self.mock_chapters_info[1]     # Chapter 2

        initial_progress = {
            "story_id": self.story_id,
            "downloaded_chapters": [{
                "source_chapter_id": existing_chapter_info_obj.source_chapter_id,
                "chapter_url": existing_chapter_info_obj.chapter_url,
                "chapter_title": existing_chapter_info_obj.chapter_title,
                "download_order": existing_chapter_info_obj.download_order,
                "local_raw_filename": "ch1_raw.html",
                "local_processed_filename": "ch1_proc.html",
                "status": "active",
                "first_seen_on": OLD_TIME_STR,
                "last_checked_on": OLD_TIME_STR,
                "download_timestamp": OLD_TIME_STR,
            }]
        }
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress)
        # Files for existing chapter 1 exist, new chapter 2 files do not.
        self.patchers['os.path.exists'].side_effect = lambda path: \
            ("ch1_raw.html" in path or "ch1_proc.html" in path) or \
            not ("chapter_00002" in path) # True for existing, False for new chapter files to trigger download

        # Fetcher returns both chapters (one old, one new)
        self.mock_fetcher_instance.get_chapter_urls.return_value = [existing_chapter_info_obj, new_chapter_info_obj]

        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.patchers['save_progress'].assert_called_once()
        saved_data = self.patchers['save_progress'].call_args[0][1]

        self.assertEqual(len(saved_data["downloaded_chapters"]), 2)

        ch1_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == existing_chapter_info_obj.chapter_url)
        ch2_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == new_chapter_info_obj.chapter_url)

        # Chapter 1 (existing)
        self.assertEqual(ch1_entry["status"], "active")
        self.assertEqual(ch1_entry["first_seen_on"], OLD_TIME_STR) # Preserved
        self.assertEqual(ch1_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated
        self.assertEqual(ch1_entry["download_timestamp"], OLD_TIME_STR) # Preserved, not re-downloaded
        self.assertEqual(ch1_entry["local_raw_filename"], "ch1_raw.html") # Preserved

        # Chapter 2 (new)
        self.assertEqual(ch2_entry["status"], "active")
        self.assertEqual(ch2_entry["first_seen_on"], self.FROZEN_TIME_STR) # New
        self.assertEqual(ch2_entry["last_checked_on"], self.FROZEN_TIME_STR) # New
        self.assertEqual(ch2_entry["download_timestamp"], self.FROZEN_TIME_STR) # New
        self.assertTrue(ch2_entry["local_raw_filename"].startswith(f"chapter_{str(new_chapter_info_obj.download_order).zfill(5)}"))

        # Ensure download_chapter_content was called only for the new chapter
        self.mock_fetcher_instance.download_chapter_content.assert_called_once_with(new_chapter_info_obj.chapter_url)


    def test_chapters_removed_are_archived(self):
        # Arrange
        OLD_TIME_STR_CH1 = "2022-12-31T10:00:00Z"
        OLD_TIME_STR_CH2 = "2022-12-31T11:00:00Z" # To be removed
        OLD_TIME_STR_CH3 = "2022-12-31T12:00:00Z"

        chapter_infos_initial = [
            ChapterInfo(chapter_url="https://test.com/ch1", chapter_title="Chapter 1", download_order=1, source_chapter_id="c1id"),
            ChapterInfo(chapter_url="https://test.com/ch2", chapter_title="Chapter 2", download_order=2, source_chapter_id="c2id"), # This one will be removed from source
            ChapterInfo(chapter_url="https://test.com/ch3", chapter_title="Chapter 3", download_order=3, source_chapter_id="c3id"),
        ]
        # self.mock_metadata.estimated_total_chapters_source = len(chapter_infos_initial) # Not strictly needed for this test's focus


        initial_progress = {
            "story_id": self.story_id,
            "downloaded_chapters": [
                {
                    "source_chapter_id": "c1id", "chapter_url": "https://test.com/ch1", "chapter_title": "Chapter 1", "download_order": 1,
                    "local_raw_filename": "c1_raw.html", "local_processed_filename": "c1_proc.html", "status": "active",
                    "first_seen_on": OLD_TIME_STR_CH1, "last_checked_on": OLD_TIME_STR_CH1, "download_timestamp": OLD_TIME_STR_CH1
                },
                {
                    "source_chapter_id": "c2id", "chapter_url": "https://test.com/ch2", "chapter_title": "Chapter 2", "download_order": 2,
                    "local_raw_filename": "c2_raw.html", "local_processed_filename": "c2_proc.html", "status": "active",
                    "first_seen_on": OLD_TIME_STR_CH2, "last_checked_on": OLD_TIME_STR_CH2, "download_timestamp": OLD_TIME_STR_CH2
                },
                {
                    "source_chapter_id": "c3id", "chapter_url": "https://test.com/ch3", "chapter_title": "Chapter 3", "download_order": 3,
                    "local_raw_filename": "c3_raw.html", "local_processed_filename": "c3_proc.html", "status": "active",
                    "first_seen_on": OLD_TIME_STR_CH3, "last_checked_on": OLD_TIME_STR_CH3, "download_timestamp": OLD_TIME_STR_CH3
                }
            ]
        }
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress)
        self.patchers['os.path.exists'].return_value = True # All files exist, no reprocessing

        # Fetcher returns only chapter 1 and 3 (chapter 2 removed)
        chapters_from_source_after_removal = [chapter_infos_initial[0], chapter_infos_initial[2]]
        self.mock_fetcher_instance.get_chapter_urls.return_value = chapters_from_source_after_removal
        # self.mock_metadata.estimated_total_chapters_source = len(chapters_from_source_after_removal)


        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.patchers['save_progress'].assert_called_once()
        saved_data = self.patchers['save_progress'].call_args[0][1]

        self.assertEqual(len(saved_data["downloaded_chapters"]), 3) # All 3 chapters should still be in progress

        ch1_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == "https://test.com/ch1")
        ch2_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == "https://test.com/ch2")
        ch3_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == "https://test.com/ch3")

        # Chapter 1 (still active)
        self.assertEqual(ch1_entry["status"], "active")
        self.assertEqual(ch1_entry["first_seen_on"], OLD_TIME_STR_CH1) # Preserved
        self.assertEqual(ch1_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated

        # Chapter 2 (removed from source, now archived)
        self.assertEqual(ch2_entry["status"], "archived")
        self.assertEqual(ch2_entry["first_seen_on"], OLD_TIME_STR_CH2) # Preserved
        self.assertEqual(ch2_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated

        # Chapter 3 (still active)
        self.assertEqual(ch3_entry["status"], "active")
        self.assertEqual(ch3_entry["first_seen_on"], OLD_TIME_STR_CH3) # Preserved
        self.assertEqual(ch3_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated

        self.mock_fetcher_instance.download_chapter_content.assert_not_called() # No downloads as files exist


    def test_rearchive_no_changes_updates_timestamps(self):
        # Arrange
        OLD_TIME_CH1 = "2022-01-01T10:00:00Z"
        OLD_TIME_CH2 = "2022-01-01T11:00:00Z"

        # Use self.mock_chapters_info which is already set up with 2 chapters
        # Ensure fetcher returns these same chapters
        self.mock_fetcher_instance.get_chapter_urls.return_value = self.mock_chapters_info
        # self.mock_metadata.estimated_total_chapters_source = len(self.mock_chapters_info)


        initial_progress = {
            "story_id": self.story_id,
            "downloaded_chapters": [
                {
                    "source_chapter_id": self.mock_chapters_info[0].source_chapter_id,
                    "chapter_url": self.mock_chapters_info[0].chapter_url,
                    "chapter_title": self.mock_chapters_info[0].chapter_title,
                    "download_order": self.mock_chapters_info[0].download_order,
                    "local_raw_filename": "c1_raw.html", "local_processed_filename": "c1_proc.html", "status": "active",
                    "first_seen_on": OLD_TIME_CH1, "last_checked_on": OLD_TIME_CH1, "download_timestamp": OLD_TIME_CH1
                },
                {
                    "source_chapter_id": self.mock_chapters_info[1].source_chapter_id,
                    "chapter_url": self.mock_chapters_info[1].chapter_url,
                    "chapter_title": self.mock_chapters_info[1].chapter_title,
                    "download_order": self.mock_chapters_info[1].download_order,
                    "local_raw_filename": "c2_raw.html", "local_processed_filename": "c2_proc.html", "status": "active",
                    "first_seen_on": OLD_TIME_CH2, "last_checked_on": OLD_TIME_CH2, "download_timestamp": OLD_TIME_CH2
                }
            ]
        }
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress)
        self.patchers['os.path.exists'].return_value = True # All files exist, no reprocessing needed

        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.patchers['save_progress'].assert_called_once()
        saved_data = self.patchers['save_progress'].call_args[0][1]

        self.assertEqual(len(saved_data["downloaded_chapters"]), 2)

        ch1_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == self.mock_chapters_info[0].chapter_url)
        ch2_entry = next(ch for ch in saved_data["downloaded_chapters"] if ch["chapter_url"] == self.mock_chapters_info[1].chapter_url)

        # Chapter 1
        self.assertEqual(ch1_entry["status"], "active")
        self.assertEqual(ch1_entry["first_seen_on"], OLD_TIME_CH1) # Preserved
        self.assertEqual(ch1_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated
        self.assertEqual(ch1_entry["download_timestamp"], OLD_TIME_CH1) # Preserved
        self.assertEqual(ch1_entry["local_raw_filename"], "c1_raw.html") # Preserved

        # Chapter 2
        self.assertEqual(ch2_entry["status"], "active")
        self.assertEqual(ch2_entry["first_seen_on"], OLD_TIME_CH2) # Preserved
        self.assertEqual(ch2_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated
        self.assertEqual(ch2_entry["download_timestamp"], OLD_TIME_CH2) # Preserved
        self.assertEqual(ch2_entry["local_processed_filename"], "c2_proc.html") # Preserved

        self.mock_fetcher_instance.download_chapter_content.assert_not_called() # No downloads


    def test_archived_chapter_reappears_becomes_active(self):
        # Arrange
        OLD_FIRST_SEEN = "2022-10-01T12:00:00Z"
        OLD_LAST_CHECKED = "2022-11-01T12:00:00Z"
        OLD_DOWNLOAD_TS = "2022-10-01T13:00:00Z"

        reappearing_chapter_info = ChapterInfo(
            chapter_url="https://test.com/fiction/123/chapter/1",
            chapter_title="Chapter 1 Reappears",
            download_order=1,
            source_chapter_id="c1_reappears"
        )

        initial_progress = {
            "story_id": self.story_id,
            "downloaded_chapters": [{
                "source_chapter_id": reappearing_chapter_info.source_chapter_id,
                "chapter_url": reappearing_chapter_info.chapter_url,
                "chapter_title": reappearing_chapter_info.chapter_title,
                "download_order": reappearing_chapter_info.download_order,
                "local_raw_filename": "c1_reappears_raw.html",
                "local_processed_filename": "c1_reappears_proc.html",
                "status": "archived", # Initially archived
                "first_seen_on": OLD_FIRST_SEEN,
                "last_checked_on": OLD_LAST_CHECKED,
                "download_timestamp": OLD_DOWNLOAD_TS,
            }]
        }
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress)

        # Mock fetcher to return this chapter as if it reappeared on the source
        self.mock_fetcher_instance.get_chapter_urls.return_value = [reappearing_chapter_info]
        self.mock_metadata.estimated_total_chapters_source = 1 # Update metadata to reflect chapter count

        # Mock os.path.exists to return False for this chapter's files to trigger reprocessing/re-download
        self.patchers['os.path.exists'].return_value = False

        # Act
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback
        )

        # Assert
        self.patchers['save_progress'].assert_called_once()
        saved_data = self.patchers['save_progress'].call_args[0][1]

        self.assertEqual(len(saved_data["downloaded_chapters"]), 1)
        chapter_entry = saved_data["downloaded_chapters"][0]

        self.assertEqual(chapter_entry["status"], "active") # Status updated to active
        self.assertEqual(chapter_entry["first_seen_on"], OLD_FIRST_SEEN) # Preserved
        self.assertEqual(chapter_entry["last_checked_on"], self.FROZEN_TIME_STR) # Updated
        self.assertEqual(chapter_entry["download_timestamp"], self.FROZEN_TIME_STR) # Updated due to re-download

        # Verify download_chapter_content was called for this chapter
        self.mock_fetcher_instance.download_chapter_content.assert_called_once_with(reappearing_chapter_info.chapter_url)
        # Verify EPUBGenerator was called (even with one chapter)
        self.mock_epub_generator_instance.generate_epub.assert_called_once()


    def test_orchestrator_filters_chapters_for_epub_generator(self):
        # Arrange
        OLD_TIME_CH1 = "2022-01-01T10:00:00Z"
        OLD_TIME_CH2 = "2022-01-01T11:00:00Z"
        OLD_TIME_CH3 = "2022-01-01T12:00:00Z"

        chapters_info_for_epub_test = [
            ChapterInfo(chapter_url="https://test.com/epub/ch1", chapter_title="Active Chapter 1", download_order=1, source_chapter_id="ec1"),
            ChapterInfo(chapter_url="https://test.com/epub/ch2", chapter_title="Archived Chapter 2", download_order=2, source_chapter_id="ec2"),
            ChapterInfo(chapter_url="https://test.com/epub/ch3", chapter_title="Active Chapter 3", download_order=3, source_chapter_id="ec3"),
        ]

        initial_progress_for_epub = {
            "story_id": self.story_id,
            "original_title": "EPUB Filter Test Story", # Added for EPUB generation
            "downloaded_chapters": [
                {
                    "source_chapter_id": "ec1", "chapter_url": "https://test.com/epub/ch1", "chapter_title": "Active Chapter 1",
                    "download_order": 1, "local_raw_filename": "ec1_raw.html", "local_processed_filename": "ec1_proc.html",
                    "status": "active", "first_seen_on": OLD_TIME_CH1, "last_checked_on": OLD_TIME_CH1, "download_timestamp": OLD_TIME_CH1
                },
                {
                    "source_chapter_id": "ec2", "chapter_url": "https://test.com/epub/ch2", "chapter_title": "Archived Chapter 2",
                    "download_order": 2, "local_raw_filename": "ec2_raw.html", "local_processed_filename": "ec2_proc.html",
                    "status": "archived", "first_seen_on": OLD_TIME_CH2, "last_checked_on": OLD_TIME_CH2, "download_timestamp": OLD_TIME_CH2
                },
                {
                    "source_chapter_id": "ec3", "chapter_url": "https://test.com/epub/ch3", "chapter_title": "Active Chapter 3",
                    "download_order": 3, "local_raw_filename": "ec3_raw.html", "local_processed_filename": "ec3_proc.html",
                    "status": "active", "first_seen_on": OLD_TIME_CH3, "last_checked_on": OLD_TIME_CH3, "download_timestamp": OLD_TIME_CH3
                }
            ]
        }
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress_for_epub)
        self.patchers['os.path.exists'].return_value = True # All files exist, no reprocessing
        self.mock_fetcher_instance.get_chapter_urls.return_value = chapters_info_for_epub_test
        self.mock_metadata.estimated_total_chapters_source = len(chapters_info_for_epub_test)


        # --- Part 1: epub_contents='active-only' ---
        self.mock_epub_generator_instance.reset_mock() # Reset mock before the first call
        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback,
            epub_contents='active-only'
        )

        self.mock_epub_generator_instance.generate_epub.assert_called_once()
        call_args_active_only = self.mock_epub_generator_instance.generate_epub.call_args
        progress_data_for_epub_active = call_args_active_only[0][0] # First positional argument

        self.assertEqual(len(progress_data_for_epub_active['downloaded_chapters']), 2)
        self.assertEqual(progress_data_for_epub_active['downloaded_chapters'][0]['chapter_title'], "Active Chapter 1")
        self.assertEqual(progress_data_for_epub_active['downloaded_chapters'][1]['chapter_title'], "Active Chapter 3")

        # --- Part 2: epub_contents='all' ---
        # Need to reload progress as it's modified by the orchestrator (last_checked_on timestamps)
        self.patchers['load_progress'].return_value = copy.deepcopy(initial_progress_for_epub)
        self.mock_fetcher_instance.get_chapter_urls.return_value = chapters_info_for_epub_test # Re-set mock
        self.mock_epub_generator_instance.reset_mock() # Reset mock before the second call
        self.patchers['save_progress'].reset_mock() # Reset this as well for the second run

        archive_story(
            story_url=self.test_story_url,
            workspace_root=self.test_workspace_root,
            progress_callback=self.mock_progress_callback,
            epub_contents='all'
        )

        self.mock_epub_generator_instance.generate_epub.assert_called_once()
        call_args_all = self.mock_epub_generator_instance.generate_epub.call_args
        progress_data_for_epub_all = call_args_all[0][0]

        self.assertEqual(len(progress_data_for_epub_all['downloaded_chapters']), 3)
        self.assertEqual(progress_data_for_epub_all['downloaded_chapters'][0]['chapter_title'], "Active Chapter 1")
        self.assertEqual(progress_data_for_epub_all['downloaded_chapters'][1]['chapter_title'], "Archived Chapter 2")
        self.assertEqual(progress_data_for_epub_all['downloaded_chapters'][2]['chapter_title'], "Active Chapter 3")


if __name__ == '__main__':
    unittest.main()
