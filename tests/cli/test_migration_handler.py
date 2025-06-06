import unittest
import os
import shutil
import json
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

# Adjust imports based on your project structure
from webnovel_archiver.cli.main import archiver # Assuming 'archiver' is your main click group
from webnovel_archiver.cli.handlers import migrate_royalroad_legacy_id_handler # Direct handler import for more focused test
from webnovel_archiver.core.storage.progress_manager import DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR, EBOOKS_DIR # Removed RAW_CONTENT_DIR, PROCESSED_CONTENT_DIR as they are locally defined in handler

# Define a temporary workspace for these tests
TEST_MIGRATION_WORKSPACE = os.path.join(DEFAULT_WORKSPACE_ROOT, "test_migration_workspace")
# Define constants for directory names used by tests, consistent with handler
RAW_CONTENT_DIR_TEST = "raw_content"
PROCESSED_CONTENT_DIR_TEST = "processed_content"


class TestMigrationHandler(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        # Clean up and create the test workspace
        if os.path.exists(TEST_MIGRATION_WORKSPACE):
            shutil.rmtree(TEST_MIGRATION_WORKSPACE)
        os.makedirs(TEST_MIGRATION_WORKSPACE)

        # Define paths to the subdirectories within the test workspace
        self.archival_status_path = os.path.join(TEST_MIGRATION_WORKSPACE, ARCHIVAL_STATUS_DIR)
        self.ebooks_path = os.path.join(TEST_MIGRATION_WORKSPACE, EBOOKS_DIR)
        self.raw_content_path = os.path.join(TEST_MIGRATION_WORKSPACE, RAW_CONTENT_DIR_TEST)
        self.processed_content_path = os.path.join(TEST_MIGRATION_WORKSPACE, PROCESSED_CONTENT_DIR_TEST)

        # Create these base directories
        os.makedirs(self.archival_status_path, exist_ok=True)
        os.makedirs(self.ebooks_path, exist_ok=True)
        os.makedirs(self.raw_content_path, exist_ok=True)
        os.makedirs(self.processed_content_path, exist_ok=True)

    def tearDown(self):
        # Clean up the test workspace
        if os.path.exists(TEST_MIGRATION_WORKSPACE):
            shutil.rmtree(TEST_MIGRATION_WORKSPACE)

    def _create_legacy_story_dirs(self, story_id, create_progress_file=False):
        # Helper to create dummy directories for a legacy story.
        dirs_to_create = [
            os.path.join(self.archival_status_path, story_id),
            os.path.join(self.ebooks_path, story_id),
            os.path.join(self.raw_content_path, story_id),
            os.path.join(self.processed_content_path, story_id)
        ]
        for d in dirs_to_create:
            os.makedirs(d, exist_ok=True)
            if create_progress_file and ARCHIVAL_STATUS_DIR in d: # Check if it's the archival_status subdir
                with open(os.path.join(d, "progress_status.json"), "w") as f:
                    json.dump({"story_id": story_id, "original_title": "Test Title"}, f)
        return dirs_to_create

    def _assert_migrated_dirs_exist(self, new_story_id, should_exist=True):
        # Helper to assert existence of migrated directories.
        expected_dirs = [
            os.path.join(self.archival_status_path, new_story_id),
            os.path.join(self.ebooks_path, new_story_id),
            os.path.join(self.raw_content_path, new_story_id),
            os.path.join(self.processed_content_path, new_story_id)
        ]
        for d in expected_dirs:
            self.assertEqual(os.path.exists(d), should_exist, f"Directory {d} existence check failed (should_exist={should_exist}).")
            if should_exist and ARCHIVAL_STATUS_DIR in d and os.path.exists(os.path.join(d, "progress_status.json")):
                 with open(os.path.join(d, "progress_status.json"), "r") as f:
                    progress_data = json.load(f)
                    # For now, just checking file presence.
                    # If the handler were to update the story_id within progress_status.json, that would be tested here.
                    self.assertIsNotNone(progress_data)


    def _assert_legacy_dirs_not_exist(self, legacy_story_id):
        # Helper to assert non-existence of legacy directories.
        legacy_dirs = [
            os.path.join(self.archival_status_path, legacy_story_id),
            os.path.join(self.ebooks_path, legacy_story_id),
            os.path.join(self.raw_content_path, legacy_story_id),
            os.path.join(self.processed_content_path, legacy_story_id)
        ]
        for d in legacy_dirs:
            self.assertFalse(os.path.exists(d), f"Legacy directory {d} should not exist.")

    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_single_story_migration_success(self, MockConfigManager):
        # Mock ConfigManager to return our test workspace path
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        legacy_id = "12345-my-old-story"
        new_id = "royalroad-12345"
        self._create_legacy_story_dirs(legacy_id, create_progress_file=True)

        # Directly call the handler for more control and easier mocking
        migrate_royalroad_legacy_id_handler(legacy_story_id=legacy_id, migration_type="royalroad-legacy-id")

        self._assert_migrated_dirs_exist(new_id)
        self._assert_legacy_dirs_not_exist(legacy_id)
        # Check if progress_status.json was moved
        self.assertTrue(os.path.exists(os.path.join(self.archival_status_path, new_id, "progress_status.json")))


    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_all_stories_migration(self, MockConfigManager):
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        legacy_rr_1 = "111-rr-story-one"
        new_rr_1 = "royalroad-111"
        self._create_legacy_story_dirs(legacy_rr_1, create_progress_file=True)

        legacy_rr_2 = "222-another-rr-fic"
        new_rr_2 = "royalroad-222"
        self._create_legacy_story_dirs(legacy_rr_2) # No progress file for this one

        non_rr_story = "other-site-story-abc" # Should not be migrated
        self._create_legacy_story_dirs(non_rr_story)

        already_migrated_story = "royalroad-777" # Should not be affected by rename logic but ensure it's still there
        self._create_legacy_story_dirs(already_migrated_story)


        migrate_royalroad_legacy_id_handler(legacy_story_id=None, migration_type="royalroad-legacy-id")

        self._assert_migrated_dirs_exist(new_rr_1)
        self._assert_legacy_dirs_not_exist(legacy_rr_1)
        self.assertTrue(os.path.exists(os.path.join(self.archival_status_path, new_rr_1, "progress_status.json")))


        self._assert_migrated_dirs_exist(new_rr_2)
        self._assert_legacy_dirs_not_exist(legacy_rr_2)

        # Assert non-RR story and already migrated story are untouched (still exist with their original names)
        self._assert_migrated_dirs_exist(non_rr_story, should_exist=True)
        self.assertTrue(os.path.exists(os.path.join(self.archival_status_path, non_rr_story)))

        self._assert_migrated_dirs_exist(already_migrated_story, should_exist=True)
        self.assertTrue(os.path.exists(os.path.join(self.archival_status_path, already_migrated_story)))


    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_migration_idempotency(self, MockConfigManager):
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        legacy_id = "54321-idempotent-test"
        new_id = "royalroad-54321"
        self._create_legacy_story_dirs(legacy_id, create_progress_file=True)

        # First migration
        migrate_royalroad_legacy_id_handler(legacy_story_id=legacy_id, migration_type="royalroad-legacy-id")
        self._assert_migrated_dirs_exist(new_id)
        self._assert_legacy_dirs_not_exist(legacy_id)
        progress_file_path = os.path.join(self.archival_status_path, new_id, "progress_status.json")
        self.assertTrue(os.path.exists(progress_file_path))
        with open(progress_file_path, "r") as f:
            content_after_first_migration = json.load(f)


        # Second migration attempt (should do nothing to this story, as the target new_id already exists)
        # Calling with legacy_story_id=None to simulate a full scan
        migrate_royalroad_legacy_id_handler(legacy_story_id=None, migration_type="royalroad-legacy-id")

        self._assert_migrated_dirs_exist(new_id) # Still there
        self._assert_legacy_dirs_not_exist(legacy_id) # Still gone
        self.assertTrue(os.path.exists(progress_file_path)) # Progress file still there
        with open(progress_file_path, "r") as f:
            content_after_second_migration = json.load(f)
        self.assertEqual(content_after_first_migration, content_after_second_migration, "Progress file content changed on second migration.")


    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_migrate_non_matching_story_id_provided(self, MockConfigManager):
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        non_legacy_id = "this-is-not-legacy-format"
        self._create_legacy_story_dirs(non_legacy_id) # Create dirs for it

        # Call handler with this non-matching ID
        migrate_royalroad_legacy_id_handler(legacy_story_id=non_legacy_id, migration_type="royalroad-legacy-id")

        # Assert that the directories are untouched
        self._assert_migrated_dirs_exist(non_legacy_id, should_exist=True)


    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_migration_of_story_with_missing_subfolders(self, MockConfigManager):
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        legacy_id = "999-partial-story"
        new_id = "royalroad-999"

        # Only create archival_status and ebooks for this one
        os.makedirs(os.path.join(self.archival_status_path, legacy_id), exist_ok=True)
        os.makedirs(os.path.join(self.ebooks_path, legacy_id), exist_ok=True)
        # raw_content and processed_content are missing for this legacy story

        migrate_royalroad_legacy_id_handler(legacy_story_id=legacy_id, migration_type="royalroad-legacy-id")

        # Check that the existing ones were moved
        self.assertTrue(os.path.exists(os.path.join(self.archival_status_path, new_id)))
        self.assertTrue(os.path.exists(os.path.join(self.ebooks_path, new_id)))
        self.assertFalse(os.path.exists(os.path.join(self.archival_status_path, legacy_id)))
        self.assertFalse(os.path.exists(os.path.join(self.ebooks_path, legacy_id)))

        # Check that the non-existing ones were not created (and didn't cause an error)
        self.assertFalse(os.path.exists(os.path.join(self.raw_content_path, new_id)))
        self.assertFalse(os.path.exists(os.path.join(self.processed_content_path, new_id)))


    @patch('webnovel_archiver.cli.handlers.ConfigManager')
    def test_cli_migrate_command_invocation(self, MockConfigManager):
        mock_config_instance = MockConfigManager.return_value
        mock_config_instance.get_workspace_path.return_value = TEST_MIGRATION_WORKSPACE

        legacy_id = "12300-cli-story"
        new_id = "royalroad-12300"
        self._create_legacy_story_dirs(legacy_id)

        result = self.runner.invoke(archiver, ['migrate', 'royalroad-legacy-id', legacy_id, '--type', 'royalroad-legacy-id'])

        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")
        self._assert_migrated_dirs_exist(new_id)
        self._assert_legacy_dirs_not_exist(legacy_id)
        self.assertIn(f"Attempting to migrate to '{new_id}'", result.output)
        self.assertIn(f"SUCCESS: Migration for '{new_id}'", result.output)


if __name__ == '__main__':
    unittest.main()
