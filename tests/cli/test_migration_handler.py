import unittest
import os
import shutil
import json
import re # Not strictly needed for these tests yet, but good for consistency
from unittest.mock import patch, MagicMock, call # Added call for checking multiple echo calls

from webnovel_archiver.cli.handlers import migration_handler
import webnovel_archiver.core.storage.progress_manager as pm
from webnovel_archiver.core.storage.progress_manager import (
    PROGRESS_FILE_VERSION # For verifying progress file structure if needed
)
from webnovel_archiver.core.path_manager import PathManager # Import PathManager

# Define a specific test workspace to avoid conflicts
# TEST_MIGRATION_WORKSPACE will be defined in setUp using a base path.
# For consistency, let's use a simple name that will be joined with a temp base path if needed,
# or assume it's created in the current directory for isolated testing if not using a global temp path.
# For now, let's assume the test runner or a fixture provides a base temp path.
# If not, this will be relative to where tests are run.
TEST_MIGRATION_WORKSPACE_NAME = "test_migration_workspace_cli_handler"

class TestMigrationHandler(unittest.TestCase):
    def setUp(self):
        # Using a simpler workspace name, assuming it's created relative to the test execution directory
        # or a temp directory provided by a test runner if integrated with one like pytest's tmp_path.
        # For unittest, this will be in the current working directory.
        self.base_dir = "temp_test_cli_migration_handler" # Base temporary directory for this test class
        self.test_workspace = os.path.join(self.base_dir, TEST_MIGRATION_WORKSPACE_NAME)
        if os.path.exists(self.base_dir): # Clean up the whole base_dir for this test class
            shutil.rmtree(self.base_dir)
        os.makedirs(self.test_workspace, exist_ok=True)

        self.archival_status_path = os.path.join(self.test_workspace, PathManager.ARCHIVAL_STATUS_DIR_NAME)
        self.ebooks_path = os.path.join(self.test_workspace, PathManager.EBOOKS_DIR_NAME)

        os.makedirs(self.archival_status_path, exist_ok=True)
        os.makedirs(self.ebooks_path, exist_ok=True)

        # Patch ConfigManager for all tests in this class
        # Target ConfigManager where it's instantiated by MigrationContext
        self.config_manager_patch = patch('webnovel_archiver.cli.contexts.ConfigManager')
        self.mock_config_manager_constructor = self.config_manager_patch.start()
        self.mock_config_instance = self.mock_config_manager_constructor.return_value
        self.mock_config_instance.get_workspace_path.return_value = self.test_workspace

    def tearDown(self):
        self.config_manager_patch.stop()
        if os.path.exists(self.base_dir): # Clean up the base_dir
            shutil.rmtree(self.base_dir)

    def _create_legacy_story(self, legacy_id: str, numerical_id: str, json_story_id_override: str = None, create_ebook_dir: bool = True, story_url_segment: str = None):
        story_archival_path = os.path.join(self.archival_status_path, legacy_id)
        os.makedirs(story_archival_path, exist_ok=True)

        # Determine the story_id to be written into the JSON file
        actual_json_story_id = json_story_id_override if json_story_id_override else legacy_id

        progress_data = pm._get_new_progress_structure(actual_json_story_id) # Use the determined ID for the structure

        # Use a consistent or provided slug for the URL
        slug_for_url = story_url_segment if story_url_segment else legacy_id.split('-', 1)[1] if '-' in legacy_id else "test-slug"
        progress_data["story_url"] = f"https://www.royalroad.com/fiction/{numerical_id}/{slug_for_url}"
        progress_data["original_title"] = f"Title for {legacy_id}"

        progress_file_path = os.path.join(story_archival_path, "progress_status.json")
        with open(progress_file_path, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2)

        if create_ebook_dir:
            story_ebook_path = os.path.join(self.ebooks_path, legacy_id)
            os.makedirs(story_ebook_path, exist_ok=True)
            # Create a dummy file in ebook dir to check if it's moved
            with open(os.path.join(story_ebook_path, "dummy.epub"), 'w') as f:
                 f.write("dummy content")

        return story_archival_path, progress_file_path

    @patch('click.echo')
    def test_single_story_migration_success(self, mock_click_echo):
        legacy_id = "12345-old-title"
        numerical_id = "12345"
        new_id = f"royalroad-{numerical_id}"
        self._create_legacy_story(legacy_id, numerical_id)

        migration_handler(story_id=legacy_id, migration_type="royalroad-legacy-id")

        self.assertFalse(os.path.exists(os.path.join(self.archival_status_path, legacy_id)), "Legacy archival directory should be removed.")
        self.assertFalse(os.path.exists(os.path.join(self.ebooks_path, legacy_id)), "Legacy ebooks directory should be removed.")

        new_archival_path = os.path.join(self.archival_status_path, new_id)
        new_ebook_path = os.path.join(self.ebooks_path, new_id)
        self.assertTrue(os.path.isdir(new_archival_path), "New archival directory should exist.")
        self.assertTrue(os.path.isdir(new_ebook_path), "New ebooks directory should exist.")
        self.assertTrue(os.path.exists(os.path.join(new_ebook_path, "dummy.epub")), "Dummy epub file should be in new ebook path.")


        progress_file_in_new_dir = os.path.join(new_archival_path, "progress_status.json")
        self.assertTrue(os.path.exists(progress_file_in_new_dir), "Progress file should exist in new directory.")
        with open(progress_file_in_new_dir, 'r') as f:
            content = json.load(f)
        self.assertEqual(content.get("story_id"), new_id, "Story ID in progress file should be updated.")
        mock_click_echo.assert_any_call(f"\nSuccessfully completed full migration for 1 story/stories.")


    @patch('click.echo')
    def test_all_stories_migration_success(self, mock_click_echo):
        # Story 1: Standard legacy
        self._create_legacy_story("111-one", "111", story_url_segment="one")
        # Story 2: Another standard legacy
        self._create_legacy_story("222-two", "222", story_url_segment="two")
        # Story 3: Non-matching format (should be ignored by scan)
        self._create_legacy_story("other-source-story", "000", story_url_segment="other-source") # Numerical ID 000 for consistency
        # Story 4: Already migrated format (should be ignored by scan, or if processed, handled gracefully)
        self._create_legacy_story("royalroad-777", "777", json_story_id_override="royalroad-777", story_url_segment="already-migrated")

        migration_handler(story_id=None, migration_type="royalroad-legacy-id")

        # Assert Story 1 migrated
        self.assertFalse(os.path.exists(os.path.join(self.archival_status_path, "111-one")))
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, "royalroad-111")))
        with open(os.path.join(self.archival_status_path, "royalroad-111", "progress_status.json"), 'r') as f:
            self.assertEqual(json.load(f).get("story_id"), "royalroad-111")

        # Assert Story 2 migrated
        self.assertFalse(os.path.exists(os.path.join(self.archival_status_path, "222-two")))
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, "royalroad-222")))
        with open(os.path.join(self.archival_status_path, "royalroad-222", "progress_status.json"), 'r') as f:
            self.assertEqual(json.load(f).get("story_id"), "royalroad-222")

        # Assert Story 3 (non-matching) is untouched
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, "other-source-story")))
        with open(os.path.join(self.archival_status_path, "other-source-story", "progress_status.json"), 'r') as f:
            self.assertEqual(json.load(f).get("story_id"), "other-source-story") # Should remain original

        # Assert Story 4 (already migrated) is untouched (or handled gracefully)
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, "royalroad-777")))
        with open(os.path.join(self.archival_status_path, "royalroad-777", "progress_status.json"), 'r') as f:
            self.assertEqual(json.load(f).get("story_id"), "royalroad-777")

        mock_click_echo.assert_any_call(f"\nSuccessfully completed full migration for 2 story/stories.")


    @patch('click.echo')
    def test_migration_non_existent_story_id(self, mock_click_echo):
        migration_handler(story_id="99999-non-existent", migration_type="royalroad-legacy-id")
        # Check for specific message indicating it's skipped due to not matching legacy format, or not found
        # The current handler logic for a specific story_id first checks format, then existence.
        # If format is "99999-non-existent", it's valid legacy format. So it would proceed to not find it.
        # Let's refine this to test what happens if it *would* be a valid ID but dir doesn't exist.
        # The handler currently doesn't explicitly check os.path.exists for a single story_id before trying to process it,
        # it relies on the os.listdir scan for `story_id=None` or direct processing.
        # For a single story_id, the loop `for legacy_id in legacy_story_ids_to_process:` will run once.
        # Then `os.path.isdir(old_dir_path)` will be false.

        # The MigrationContext will add an error if the directory for the story_id is not found,
        # because "99999-non-existent" matches the legacy ID format.
        # The handler will then print this error from context.error_messages and exit.
        expected_error_message = (
            f"Error: Specified legacy story ID directory '99999-non-existent' "
            f"not found in {self.archival_status_path}."
        )
        # mock_click_echo.assert_any_call(expected_error_message, err=True) # Original assertion
        # Custom check for styled output, stripping ANSI codes
        ansi_escape_pattern = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        found_non_existent_error = False
        for call_args_tuple in mock_click_echo.call_args_list:
            args, kwargs = call_args_tuple
            if len(args) > 0:
                actual_message = ansi_escape_pattern.sub('', str(args[0]))
                if actual_message == expected_error_message and kwargs.get('err') is True:
                    found_non_existent_error = True
                    break
        self.assertTrue(found_non_existent_error, f"Expected echo call for non-existent story ID ('{expected_error_message}') not found.")

        # Ensure "Processing legacy story ID..." was NOT called because context validation failed early.
        processing_message_found = False
        for call_args_tuple in mock_click_echo.call_args_list:
            args, kwargs = call_args_tuple
            # Check the first argument of the call, which is args[0]
            if len(args) > 0: # Ensure there is an argument
                actual_message = ansi_escape_pattern.sub('', str(args[0]))
                if actual_message == "Processing legacy story ID: 99999-non-existent":
                    processing_message_found = True
                    break
        self.assertFalse(processing_message_found, "'Processing legacy story ID...' should not have been called.")


    @patch('click.echo')
    def test_migration_invalid_migration_type(self, mock_click_echo):
        self._create_legacy_story("123-to-ignore", "123")
        migration_handler(story_id="123-to-ignore", migration_type="invalid-type")

        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, "123-to-ignore")), "Story directory should not be changed.")

        expected_error_message = f"Error: Migration type 'invalid-type' is not supported. Currently, only 'royalroad-legacy-id' is available."
        # mock_click_echo.assert_any_call(expected_error_message, err=True) # Original assertion
        # Custom check for styled output, stripping ANSI codes
        ansi_escape_pattern = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        found_invalid_type_error = False
        for call_args_tuple in mock_click_echo.call_args_list:
            args, kwargs = call_args_tuple
            if len(args) > 0:
                actual_message = ansi_escape_pattern.sub('', str(args[0]))
                if actual_message == expected_error_message and kwargs.get('err') is True:
                    found_invalid_type_error = True
                    break
        self.assertTrue(found_invalid_type_error, f"Expected echo call for invalid migration type ('{expected_error_message}') not found.")

    @patch('click.echo')
    def test_migration_idempotency(self, mock_click_echo):
        legacy_id = "333-idem-test"
        numerical_id = "333"
        new_id = f"royalroad-{numerical_id}"
        self._create_legacy_story(legacy_id, numerical_id)

        # First migration
        migration_handler(story_id=legacy_id, migration_type="royalroad-legacy-id")
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, new_id)))
        self.assertFalse(os.path.isdir(os.path.join(self.archival_status_path, legacy_id)))
        mock_click_echo.assert_any_call(f"\nSuccessfully completed full migration for 1 story/stories.")

        # Call again with the old ID (should find nothing to process with this ID)
        migration_handler(story_id=legacy_id, migration_type="royalroad-legacy-id")
        # Check that the already migrated story is fine and no "0 stories migrated for this ID" error for the *new* ID.
        # The second call with `legacy_id` should effectively do nothing as the path is gone.
        # The output will be "Migration for story ID '333-idem-test' was not completed..."

        # Call again with story_id=None (scan mode)
        migration_handler(story_id=None, migration_type="royalroad-legacy-id")
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, new_id))) # Still there
        # Scan should report "No legacy RoyalRoad stories requiring migration were found." or similar if only new format exists.
        # mock_click_echo.assert_any_call("No legacy RoyalRoad stories requiring directory migration were found.")

        # Call with the new ID (should be skipped gracefully)
        migration_handler(story_id=new_id, migration_type="royalroad-legacy-id")
        # This will trigger the "Provided story ID 'royalroad-333' does not match the expected legacy RoyalRoad format"
        expected_warning_message = (
            f"Provided story ID '{new_id}' does not match the expected "
            "legacy RoyalRoad format (e.g., '12345-some-title'). Skipping this ID."
        )
        # mock_click_echo.assert_any_call(expected_warning_message, err=True) # Original assertion
        # Custom check for styled output, stripping ANSI codes
        ansi_escape_pattern = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        found_idempotency_warning = False
        for call_args_tuple in mock_click_echo.call_args_list:
            args, kwargs = call_args_tuple
            if len(args) > 0:
                actual_message = ansi_escape_pattern.sub('', str(args[0]))
                if actual_message == expected_warning_message and kwargs.get('err') is True:
                    found_idempotency_warning = True
                    break
        # Print all calls to diagnose if not found
        if not found_idempotency_warning:
            print("\n=== test_migration_idempotency: mock_click_echo calls (ANSI stripped) ===")
            for i, call_args_tuple in enumerate(mock_click_echo.call_args_list):
                p_args, p_kwargs = call_args_tuple
                actual_msg_raw = str(p_args[0]) if len(p_args)>0 else ''
                actual_msg_stripped = ansi_escape_pattern.sub('', actual_msg_raw)
                print(f"Call {i}: args={p_args}, kwargs={p_kwargs}, stripped_msg='{actual_msg_stripped}'")
            print("=======================================================================")
        self.assertTrue(found_idempotency_warning, f"Expected echo call for idempotency warning ('{expected_warning_message}') not found.")


    @patch('click.echo')
    def test_migration_target_exists_warning(self, mock_click_echo):
        legacy_id = "444-conflict"
        numerical_id = "444"
        new_id = f"royalroad-{numerical_id}"

        self._create_legacy_story(legacy_id, numerical_id)
        # Manually create the target directory for archival_status
        os.makedirs(os.path.join(self.archival_status_path, new_id), exist_ok=True)
        # Also for ebooks to make the test consistent
        os.makedirs(os.path.join(self.ebooks_path, new_id), exist_ok=True)


        migration_handler(story_id=legacy_id, migration_type="royalroad-legacy-id")

        # Assert legacy archival path still exists because target existed
        self.assertTrue(os.path.isdir(os.path.join(self.archival_status_path, legacy_id)))
        # Assert legacy ebook path might also exist if that rename was also skipped
        self.assertTrue(os.path.isdir(os.path.join(self.ebooks_path, legacy_id)))

        # Check for specific warning message about target existing for archival_status
        expected_warning_archival = (
            f"  Warning: Target directory '{os.path.join(self.archival_status_path, new_id)}' "
            "already exists. Skipping rename for this path. Manual check may be required."
        )
        mock_click_echo.assert_any_call(expected_warning_archival, err=True)

        # Check for specific warning message about target existing for ebooks
        expected_warning_ebooks = (
            f"  Warning: Target directory '{os.path.join(self.ebooks_path, new_id)}' "
            "already exists. Skipping rename for this path. Manual check may be required."
        )
        mock_click_echo.assert_any_call(expected_warning_ebooks, err=True)

        # Check for the final summary message
        expected_summary_message = (
            f"Migration for story ID '{legacy_id}' was not completed. Check previous "
            "messages for details (e.g., if it was invalid, not found, or failed during processing)."
        )
        # This summary might not be printed if the handler logic has changed.
        # The handler logic: if migrated_count == 0 and story_id_option is set: print summary.
        # In this case, migrated_count will be 0.
        mock_click_echo.assert_any_call(expected_summary_message)


    @patch('click.echo')
    def test_migration_story_id_in_json_already_correct(self, mock_click_echo):
        legacy_id = "555-json-ok"
        numerical_id = "555"
        new_id = f"royalroad-{numerical_id}"

        # Create legacy story but override the story_id in its progress.json to be the *new* ID
        self._create_legacy_story(legacy_id, numerical_id, json_story_id_override=new_id)

        migration_handler(story_id=legacy_id, migration_type="royalroad-legacy-id")

        # Directories should be renamed
        self.assertFalse(os.path.exists(os.path.join(self.archival_status_path, legacy_id)))
        new_archival_path = os.path.join(self.archival_status_path, new_id)
        self.assertTrue(os.path.isdir(new_archival_path))

        # JSON story_id should remain new_id, and handler should indicate no update was needed for JSON content
        progress_file_in_new_dir = os.path.join(new_archival_path, "progress_status.json")
        with open(progress_file_in_new_dir, 'r') as f:
            content = json.load(f)
        self.assertEqual(content.get("story_id"), new_id)

        mock_click_echo.assert_any_call(f"  INFO: Story ID in '{progress_file_in_new_dir}' is already '{new_id}'. No update needed.")
        mock_click_echo.assert_any_call(f"\nSuccessfully completed full migration for 1 story/stories.")


if __name__ == '__main__':
    unittest.main()
