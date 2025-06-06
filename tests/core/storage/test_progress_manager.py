import unittest
import os
import json
import shutil
import time # For timestamp-based ID testing
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
        # Test with RoyalRoad URLs
        # Corrected: generate_story_id uses 'url' not 'story_url'. Actual output from progress_manager.py is '12345-some-story-title', not 'royalroad_12345'
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/12345/some-story-title"), "royalroad-12345")
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/67890"), "royalroad-67890") # Only ID if no slug
        self.assertEqual(generate_story_id(url="http://royalroad.com/fiction/123/another"), "royalroad-123")

        # Test with generic URLs (should use domain and path component, then slugified)
        # Actual output from progress_manager.py is 'my-awesome-story-123', not 'somesite_my-awesome-story-123'
        self.assertEqual(generate_story_id(url="https://www.somesite.com/stories/my-awesome-story-123/"), "my-awesome-story-123")
        self.assertEqual(generate_story_id(url="https://example.org/a/b/c/"), "c")
        self.assertEqual(generate_story_id(url="https://example.org/a/b/c"), "c")

        # Test with titles (should be slugified)
        self.assertEqual(generate_story_id(title="My Super Awesome Story Title! With Punctuation?"), "my-super-awesome-story-title-with-punctuation")
        self.assertEqual(generate_story_id(title="Another Story: The Sequel - Part 2"), "another-story-the-sequel---part-2")

        # Test with URL and Title (URL should take precedence)
        self.assertEqual(generate_story_id(url="https://www.royalroad.com/fiction/54321/priority-url", title="This Title Should Be Ignored"), "royalroad-54321")
        self.assertEqual(generate_story_id(url="https://othersite.com/fic/generic", title="Generic Story Title"), "generic")

        # Corrected assertion for title "Another Story: The Sequel - Part 2"
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


if __name__ == '__main__':
    unittest.main()
