import unittest
import os
import json
import shutil
import time # For timestamp-based ID testing
import datetime # Added for timestamp manipulation
from unittest.mock import patch # Added for mocking
from webnovel_archiver.core.storage.progress_manager import (
    generate_story_id,
    load_progress,
    save_progress,
    get_progress_filepath,
    DEFAULT_WORKSPACE_ROOT,
    _get_new_progress_structure
)

# Define a temporary workspace for these tests
TEST_WORKSPACE_ROOT = os.path.join(DEFAULT_WORKSPACE_ROOT, "test_progress_manager_workspace")

class TestProgressManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary workspace for testing progress manager functions."""
        # Ensure the default workspace root exists, then create the test-specific subdirectory
        if not os.path.exists(DEFAULT_WORKSPACE_ROOT):
            os.makedirs(DEFAULT_WORKSPACE_ROOT)
        if os.path.exists(TEST_WORKSPACE_ROOT):
            shutil.rmtree(TEST_WORKSPACE_ROOT) # Clean up from previous runs if any
        os.makedirs(TEST_WORKSPACE_ROOT)

    def tearDown(self):
        """Clean up the temporary workspace after tests."""
        if os.path.exists(TEST_WORKSPACE_ROOT):
            shutil.rmtree(TEST_WORKSPACE_ROOT)

    def test_generate_story_id(self):
        # Test with RoyalRoad URLs - these should now be treated as generic URLs
        # The specific "royalroad-<id>" format is no longer handled by this function.
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/12345/some-story-title"), "some-story-title")
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/67890"), "67890")
        self.assertEqual(generate_story_id(url="http://royalroad.com/fiction/123/another"), "another")

        # Test with generic URLs (should use domain and path component, then slugified)
        self.assertEqual(generate_story_id(url="https://www.somesite.com/stories/my-awesome-story-123/"), "my-awesome-story-123")
        self.assertEqual(generate_story_id(url="https://example.org/a/b/c/"), "c")
        self.assertEqual(generate_story_id(url="https://example.org/a/b/c"), "c")

        # Test with titles (should be slugified)
        self.assertEqual(generate_story_id(title="My Super Awesome Story Title! With Punctuation?"), "my-super-awesome-story-title-with-punctuation")
        self.assertEqual(generate_story_id(title="Another Story: The Sequel - Part 2"), "another-story-the-sequel---part-2")

        # Test with URL and Title (URL should take precedence, generic parsing applies)
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/54321/priority-url", title="This Title Should Be Ignored"), "priority-url")
        self.assertEqual(generate_story_id(url="https://othersite.com/fic/generic", title="Generic Story Title"), "generic")

        # Assertion for title "Another Story: The Sequel - Part 2" (remains the same)
        self.assertEqual(generate_story_id(title="Another Story: The Sequel - Part 2"), "another-story-the-sequel---part-2")


        # Test with no URL and no title (should generate a timestamp-based ID)
        generated_id_unknown = generate_story_id() # Example: story_20231027123456789012
        self.assertTrue(generated_id_unknown.startswith("story_"))
        try:
            # Check if the part after "story_" is a valid datetime string format used by the function
            datetime_part = generated_id_unknown.split('_')[1]
            time.strptime(datetime_part, '%Y%m%d%H%M%S%f') # This will raise ValueError if format doesn't match
        except (IndexError, ValueError) as e:
            self.fail(f"Timestamp-based ID '{generated_id_unknown}' not in expected format story_YYYYMMDDHHMMSSffffff: {e}")


        # Test with URLs that might produce edge cases
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/12345/some-story-title?query=param#fragment"), "royalroad-12345")
        self.assertEqual(generate_story_id(url="https://www.somesite.com/stories/edge_case/?query=true"), "edge_case")
        # Corrected based on actual slugify logic: multiple slashes are handled by split, empty parts removed.
        self.assertEqual(generate_story_id(url="https://www.somesite.com/stories//multipleslashes//"), "multipleslashes")
        # Length truncation is handled by the function (default 50)
        long_path = "a-very-long-path-segment-that-might-be-problematic-for-some-systems-but-should-be-handled-gracefully-by-slugify-hopefully"
        self.assertEqual(generate_story_id(url=f"https://www.somesite.com/{long_path}"), long_path[:50])

        # Test with only domain in URL
        self.assertEqual(generate_story_id(url="https://justdomain.com"), "justdomaincom") # Slugify of domain, dot is removed
        self.assertEqual(generate_story_id(url="https://justdomain.com/"), "justdomaincom") # Slugify of domain, dot is removed


    def test_get_progress_filepath(self):
        story_id = "test_story_123"
        # Corrected: Added ARCHIVAL_STATUS_DIR to expected path
        expected_path = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id, "progress_status.json")
        # Test with explicit workspace
        self.assertEqual(get_progress_filepath(story_id, TEST_WORKSPACE_ROOT), expected_path)
        # Test with default workspace (by temporarily setting it for the purpose of this check)
        # This is a bit tricky as DEFAULT_WORKSPACE_ROOT is a global.
        # A better approach might be to allow passing workspace_root to all functions.
        # For now, we assume get_progress_filepath uses DEFAULT_WORKSPACE_ROOT if not provided.
        # To test this properly, we'd need to mock DEFAULT_WORKSPACE_ROOT or ensure it's used.
        # The current get_progress_filepath doesn't take workspace_root, it implies it.
        # Let's assume we are testing the path relative to where it *would* be created.
        # Re-evaluate if get_progress_filepath signature changes.

        # If get_progress_filepath is changed to accept workspace_root:
        # default_path = os.path.join(DEFAULT_WORKSPACE_ROOT, "archival_status", story_id, "progress_status.json")
        # self.assertEqual(get_progress_filepath(story_id), default_path) # Assuming it defaults to DEFAULT_WORKSPACE_ROOT


    def test_load_progress_new_story(self):
        story_id = "new_story_to_load"
        expected_initial_progress = _get_new_progress_structure(story_id)

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertEqual(loaded_data, expected_initial_progress)
        self.assertEqual(loaded_data['story_id'], story_id)
        self.assertIsNone(loaded_data['original_title']) # Check a few default fields
        # Corrected: check len of 'downloaded_chapters' list
        self.assertEqual(len(loaded_data['downloaded_chapters']), 0)

    def test_save_and_load_progress_existing_story(self):
        story_id = "existing_story_123"

        # 1. Create initial progress data
        progress_data = _get_new_progress_structure(story_id)
        progress_data['original_title'] = "My Awesome Novel"
        progress_data['story_url'] = "https://example.com/story/123"
        progress_data['estimated_total_chapters_source'] = 100
        # To simulate 10 chapters downloaded, add to the list
        progress_data['downloaded_chapters'] = [{"id": f"ch{i+1}", "title": f"Chapter {i+1}"} for i in range(10)]
        progress_data['original_author'] = "Test Author" # Corrected: 'original_author' instead of metadata

        # 2. Save progress
        # Corrected: save_progress needs story_id as first arg
        save_progress(story_id, progress_data, workspace_root=TEST_WORKSPACE_ROOT)

        # 3. Verify file was created
        filepath = get_progress_filepath(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertTrue(os.path.exists(filepath))

        # 4. Load progress and verify
        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertEqual(loaded_data, progress_data)

        # 5. Modify data, save again, and load again
        # Simulate 10 more chapters downloaded
        progress_data['downloaded_chapters'].extend([{"id": f"ch{i+11}", "title": f"Chapter {i+11}"} for i in range(10)])
        # Removed: 'metadata' doesn't exist. 'status' is not a field in current structure.
        # progress_data['metadata']['status'] = "Ongoing"
        progress_data['last_downloaded_chapter_url'] = "some_url/ch_20" # Use existing field

        save_progress(story_id, progress_data, workspace_root=TEST_WORKSPACE_ROOT)
        loaded_data_updated = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertEqual(loaded_data_updated, progress_data)
        self.assertEqual(len(loaded_data_updated['downloaded_chapters']), 20)
        # self.assertEqual(loaded_data_updated['metadata']['status'], "Ongoing") # Removed

    def test_load_progress_corrupted_json(self):
        story_id = "corrupted_story_json"
        filepath = get_progress_filepath(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # Ensure directory exists before writing file
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w') as f:
            f.write("{'invalid_json': True, this_is_not_quoted}") # Write invalid JSON

        # Expect load_progress to return a new, empty structure and log a warning (testing log is complex)
        expected_fallback_data = _get_new_progress_structure(story_id)

        # We might want to catch the warning if using a logger that can be asserted.
        # For now, just check the fallback behavior.
        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertEqual(loaded_data, expected_fallback_data)
        self.assertEqual(loaded_data['story_id'], story_id) # Ensure story_id is correctly set in fallback

    def test_save_progress_creates_directory(self):
        story_id = "story_needs_dir_creation"
        progress_data = _get_new_progress_structure(story_id)
        progress_data['original_title'] = "Auto Dir Creation Test"

        # Filepath and its directory
        filepath = get_progress_filepath(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        dirpath = os.path.dirname(filepath)

        self.assertFalse(os.path.exists(dirpath)) # Directory should not exist yet

        # Corrected: save_progress needs story_id as first arg
        save_progress(story_id, progress_data, workspace_root=TEST_WORKSPACE_ROOT)

        self.assertTrue(os.path.exists(filepath)) # File (and thus dir) should now exist
        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        self.assertEqual(loaded_data['original_title'], "Auto Dir Creation Test")

    def test_load_progress_migration_old_format_single_chapter(self):
        story_id = "test_story_migration_single"
        progress_dir = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id)
        os.makedirs(progress_dir, exist_ok=True)
        filepath = os.path.join(progress_dir, "progress_status.json")

        old_format_data = {
            "story_id": story_id,
            "original_title": "Test Story for Migration",
            "version": "1.0", # Simulate an older version
            "downloaded_chapters": [
                {
                    "source_chapter_id": "chap1",
                    "download_order": 1,
                    "chapter_url": "http://example.com/chap1",
                    "chapter_title": "Chapter 1",
                    "local_raw_filename": "chap1_raw.html",
                    "local_processed_filename": "chap1_processed.html"
                }
            ],
            "last_run_timestamp": "2023-01-01T00:00:00Z"
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_format_data, f, indent=2)

        # Set a specific modification time for the file BEFORE loading it for migration test
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        expected_mtime_unix = now_dt.timestamp()
        expected_iso_timestamp = now_dt.isoformat()
        os.utime(filepath, (expected_mtime_unix, expected_mtime_unix))
        # time.sleep(0.001) # Optional: ensure mtime is distinct if file system resolution is low, though utime should be precise.

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        self.assertTrue(len(loaded_data["downloaded_chapters"]) == 1)
        first_chapter = loaded_data["downloaded_chapters"][0]
        self.assertEqual(first_chapter.get("status"), "active")
        self.assertEqual(first_chapter.get("first_seen_on"), expected_iso_timestamp)
        self.assertEqual(first_chapter.get("last_checked_on"), expected_iso_timestamp)
        self.assertEqual(first_chapter.get("source_chapter_id"), "chap1") # Original data preserved

        backup_filepath = filepath + ".bak"
        self.assertTrue(os.path.exists(backup_filepath))
        with open(backup_filepath, 'r', encoding='utf-8') as bak_f:
            backup_data = json.load(bak_f)
        self.assertNotIn("status", backup_data["downloaded_chapters"][0])

    def test_load_progress_migration_empty_downloaded_chapters(self):
        story_id = "test_migration_empty_chapters"
        progress_dir = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id)
        os.makedirs(progress_dir, exist_ok=True)
        filepath = os.path.join(progress_dir, "progress_status.json")

        old_format_empty_chapters = {
            "story_id": story_id,
            "original_title": "Empty Chapters Migration Test",
            "version": "1.0",
            "downloaded_chapters": [] # Empty list
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_format_empty_chapters, f, indent=2)

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # Chapters list should still be empty
        self.assertEqual(len(loaded_data["downloaded_chapters"]), 0)

        # Backup should still be created due to "conformity" migration
        backup_filepath = filepath + ".bak"
        self.assertTrue(os.path.exists(backup_filepath))
        with open(backup_filepath, 'r', encoding='utf-8') as bak_f:
            backup_data = json.load(bak_f)
        self.assertEqual(len(backup_data["downloaded_chapters"]), 0)


    def test_load_progress_migration_missing_downloaded_chapters_key(self):
        story_id = "test_migration_missing_key"
        progress_dir = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id)
        os.makedirs(progress_dir, exist_ok=True)
        filepath = os.path.join(progress_dir, "progress_status.json")

        # Data where 'downloaded_chapters' key is entirely missing
        old_format_missing_key = {
            "story_id": story_id,
            "original_title": "Missing Key Migration Test",
            "version": "1.0"
            # "downloaded_chapters" key is absent
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_format_missing_key, f, indent=2)

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # 'downloaded_chapters' should be initialized as an empty list
        self.assertIn("downloaded_chapters", loaded_data)
        self.assertEqual(len(loaded_data["downloaded_chapters"]), 0)

        # Backup should be created because the structure was modified (key added)
        backup_filepath = filepath + ".bak"
        self.assertTrue(os.path.exists(backup_filepath))
        with open(backup_filepath, 'r', encoding='utf-8') as bak_f:
            backup_data = json.load(bak_f)
        self.assertNotIn("downloaded_chapters", backup_data) # Key was missing in original

    def test_load_progress_already_new_format_no_migration(self):
        story_id = "test_already_new_format"
        progress_dir = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id)
        os.makedirs(progress_dir, exist_ok=True)
        filepath = os.path.join(progress_dir, "progress_status.json")

        new_format_data = {
            "story_id": story_id,
            "original_title": "Already New Format Test",
            "version": "1.1", # Current version
            "downloaded_chapters": [
                {
                    "source_chapter_id": "chap1",
                    "download_order": 1,
                    "chapter_url": "http://example.com/chap1",
                    "chapter_title": "Chapter 1",
                    "local_raw_filename": "chap1_raw.html",
                    "local_processed_filename": "chap1_processed.html",
                    "status": "active", # Already has status
                    "first_seen_on": "2023-10-01T10:00:00Z",
                    "last_checked_on": "2023-10-28T10:00:00Z"
                }
            ]
        }
        # Fill with all other keys expected in a new structure for completeness
        base_new = _get_new_progress_structure(story_id)
        for key, value in base_new.items():
            if key not in new_format_data:
                new_format_data[key] = value
        new_format_data["downloaded_chapters"] = [ # ensure this specific part is set
             {
                "source_chapter_id": "chap1", "download_order": 1, "chapter_url": "http://example.com/chap1",
                "chapter_title": "Chapter 1", "local_raw_filename": "chap1_raw.html",
                "local_processed_filename": "chap1_processed.html", "status": "active",
                "first_seen_on": "2023-10-01T10:00:00Z", "last_checked_on": "2023-10-28T10:00:00Z"
            }
        ]


        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(new_format_data, f, indent=2)

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # Data should be loaded as is
        self.assertEqual(loaded_data["downloaded_chapters"][0]["status"], "active")
        self.assertEqual(loaded_data["downloaded_chapters"][0]["first_seen_on"], "2023-10-01T10:00:00Z")

        # No backup file should be created
        backup_filepath = filepath + ".bak"
        self.assertFalse(os.path.exists(backup_filepath))

    def test_load_progress_non_existent_file_no_migration_backup(self):
        story_id = "test_non_existent_file"
        # No file is created for this story_id

        # Ensure no progress file or backup exists initially
        filepath = get_progress_filepath(story_id, workspace_root=TEST_WORKSPACE_ROOT)
        backup_filepath = filepath + ".bak"
        self.assertFalse(os.path.exists(filepath))
        self.assertFalse(os.path.exists(backup_filepath))

        loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # Should return a new progress structure
        expected_new_structure = _get_new_progress_structure(story_id)
        self.assertEqual(loaded_data, expected_new_structure)
        self.assertEqual(loaded_data["story_id"], story_id)
        self.assertEqual(len(loaded_data["downloaded_chapters"]), 0) # New structure has empty chapters

        # No backup file should be created as no migration from an existing file happened
        self.assertFalse(os.path.exists(backup_filepath))

    def test_load_progress_migration_os_error_getmtime(self):
        story_id = "test_story_migration_oserror"
        progress_dir = os.path.join(TEST_WORKSPACE_ROOT, "archival_status", story_id)
        os.makedirs(progress_dir, exist_ok=True)
        filepath = os.path.join(progress_dir, "progress_status.json")

        old_format_data = {
            "story_id": story_id,
            "original_title": "Test Story for OSError Migration",
            "version": "1.0",
            "downloaded_chapters": [
                {
                    "source_chapter_id": "chap_err",
                    "download_order": 1,
                    "chapter_url": "http://example.com/chap_err",
                    "chapter_title": "Chapter Error",
                }
            ]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(old_format_data, f, indent=2)

        # Patch os.path.getmtime within the progress_manager module
        with patch('webnovel_archiver.core.storage.progress_manager.os.path.getmtime', side_effect=OSError("Simulated OSError")) as mock_getmtime:
            # Use assertLogs to capture warnings from the logger in progress_manager
            with self.assertLogs('webnovel_archiver.core.storage.progress_manager', level='WARNING') as cm:
                loaded_data = load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT)

        # Verify os.path.getmtime was called
        mock_getmtime.assert_called_once_with(filepath)

        # Verify the log message
        self.assertIn(f"Could not retrieve modification time for progress file {filepath} during migration. Using 'N/A' for timestamps. Error: Simulated OSError", cm.output[0])

        self.assertTrue(len(loaded_data["downloaded_chapters"]) == 1)
        first_chapter = loaded_data["downloaded_chapters"][0]
        self.assertEqual(first_chapter.get("status"), "active")
        self.assertEqual(first_chapter.get("first_seen_on"), "N/A") # Should fallback to N/A
        self.assertEqual(first_chapter.get("last_checked_on"), "N/A") # Should fallback to N/A
        self.assertEqual(first_chapter.get("source_chapter_id"), "chap_err")

        backup_filepath = filepath + ".bak"
        self.assertTrue(os.path.exists(backup_filepath)) # Backup should still occur


if __name__ == '__main__':
    unittest.main()
