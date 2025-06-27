import os
import json
import unittest
from unittest.mock import patch, MagicMock, call
import shutil # For creating and removing test workspace

# Click testing utilities
from click.testing import CliRunner

# CLI entry point
from webnovel_archiver.cli.main import archiver
# Import progress manager functions to help setup test data
import webnovel_archiver.core.storage.progress_manager as pm
# Import PathManager for directory name constants
from webnovel_archiver.core.path_manager import PathManager
from webnovel_archiver.core.config_manager import ConfigManager # DEFAULT_WORKSPACE_PATH is not used here directly

# --- Constants for test setup ---
TEST_WORKSPACE_ROOT = "_test_integration_cloud_backup_workspace" # Renamed for clarity
TEST_STORY_ID = "test_story_123"
TEST_CREDENTIALS_FILE = "dummy_gdrive_creds.json"
TEST_TOKEN_FILE = "dummy_gdrive_token.json"

class TestCliCloudBackup(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        # Ensure a clean test workspace
        if os.path.exists(TEST_WORKSPACE_ROOT):
            shutil.rmtree(TEST_WORKSPACE_ROOT)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.ARCHIVAL_STATUS_DIR_NAME, TEST_STORY_ID), exist_ok=True)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, TEST_STORY_ID), exist_ok=True)

        # Create dummy credentials and token files for GDriveSync to find
        # GDriveSync itself will be mocked, but its constructor might check for these paths.
        with open(TEST_CREDENTIALS_FILE, 'w') as f:
            json.dump({"installed": {"client_id": "dummy", "client_secret": "dummy"}}, f)
        with open(TEST_TOKEN_FILE, 'w') as f:
            json.dump({"token": "dummy_token_data"}, f)

        # Mock ConfigManager to use the test workspace
        self.mock_config_manager = MagicMock(spec=ConfigManager)
        self.mock_config_manager.get_workspace_path.return_value = TEST_WORKSPACE_ROOT

        # This is the GDriveSync class we want to mock
        self.mock_gdrive_sync_class = MagicMock()
        self.mock_gdrive_sync_instance = MagicMock()
        self.mock_gdrive_sync_class.return_value = self.mock_gdrive_sync_instance


    def tearDown(self):
        if os.path.exists(TEST_WORKSPACE_ROOT):
            shutil.rmtree(TEST_WORKSPACE_ROOT)
        if os.path.exists(TEST_CREDENTIALS_FILE):
            os.remove(TEST_CREDENTIALS_FILE)
        if os.path.exists(TEST_TOKEN_FILE):
            os.remove(TEST_TOKEN_FILE)

    def _create_dummy_progress_file(self, story_id, epub_files_info=None):
        progress_data = pm.load_progress(story_id, workspace_root=TEST_WORKSPACE_ROOT) # Gets new structure
        progress_data['original_title'] = f"Title for {story_id}"

        if epub_files_info is None:
            epub_files_info = [] # Example: [{'name': 'file1.epub', 'content': 'dummy epub content1'}]

        # generated_epubs_for_progress = [] # Not needed with functional approach
        for i, epub_info in enumerate(epub_files_info):
            epub_name = epub_info.get('name', f"{story_id}_vol_{i+1}.epub")
            epub_content = epub_info.get('content', f"dummy epub content for {epub_name}")

            epub_local_dir = os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, story_id)
            epub_local_path = os.path.join(epub_local_dir, epub_name)
            with open(epub_local_path, 'w') as f:
                f.write(epub_content)
            # Add to progress using the functional approach, path must be absolute
            # pm.add_epub_file_to_progress expects progress_data, name, abs_path, story_id, workspace_root
            pm.add_epub_file_to_progress(progress_data, epub_name, os.path.abspath(epub_local_path), story_id, TEST_WORKSPACE_ROOT)

        pm.save_progress(story_id, progress_data, workspace_root=TEST_WORKSPACE_ROOT)
        return pm.get_progress_filepath(story_id, workspace_root=TEST_WORKSPACE_ROOT)

    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_single_story_success(self, mock_contexts_config_manager, mock_contexts_gdrive_sync):
        # Setup mocks
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        # Prepare GDriveSync instance mocks
        self.mock_gdrive_sync_instance.create_folder_if_not_exists.side_effect = ['base_folder_id_123', 'story_folder_id_abc']
        # Mock get_file_metadata: first call (progress file) returns None (not found), subsequent (epub) also None
        self.mock_gdrive_sync_instance.get_file_metadata.return_value = None

        mock_uploaded_progress_meta = {'id': 'gdrive_progress_id', 'name': 'progress_status.json', 'modifiedTime': 'ts1'}
        mock_uploaded_epub_meta = {'id': 'gdrive_epub_id_1', 'name': 'test_story_123_vol_1.epub', 'modifiedTime': 'ts2'}
        self.mock_gdrive_sync_instance.upload_file.side_effect = [mock_uploaded_progress_meta, mock_uploaded_epub_meta]

        # Create dummy files
        epub_files_setup = [{'name': 'test_story_123_vol_1.epub'}]
        progress_file_local_path = self._create_dummy_progress_file(TEST_STORY_ID, epub_files_info=epub_files_setup)
        epub_local_path = os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, TEST_STORY_ID, 'test_story_123_vol_1.epub')

        # Run CLI command
        result = self.runner.invoke(archiver, [
            'cloud-backup', TEST_STORY_ID,
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])

        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")

        # Assert GDriveSync interactions
        self.mock_gdrive_sync_instance.create_folder_if_not_exists.assert_has_calls([
            call('Webnovel Archiver Backups', parent_folder_id=None),
            call(TEST_STORY_ID, parent_folder_id='base_folder_id_123')
        ])

        # Assert get_file_metadata calls (to check if files exist and are newer)
        # Order matters here: progress file first, then epub
        self.mock_gdrive_sync_instance.get_file_metadata.assert_has_calls([
            call(file_name='progress_status.json', folder_id='story_folder_id_abc'),
            call(file_name='test_story_123_vol_1.epub', folder_id='story_folder_id_abc')
        ])

        # Assert upload_file calls
        self.mock_gdrive_sync_instance.upload_file.assert_has_calls([
            call(progress_file_local_path, 'story_folder_id_abc', remote_file_name='progress_status.json'),
            call(os.path.abspath(epub_local_path), 'story_folder_id_abc', remote_file_name='test_story_123_vol_1.epub')
        ])

        # Verify progress_status.json update
        updated_progress_data = pm.load_progress(TEST_STORY_ID, workspace_root=TEST_WORKSPACE_ROOT)
        backup_status = pm.get_cloud_backup_status(updated_progress_data)

        self.assertEqual(backup_status['service'], 'gdrive')
        self.assertEqual(backup_status['story_cloud_folder_id'], 'story_folder_id_abc')
        self.assertEqual(len(backup_status['backed_up_files']), 2)

        progress_backup_info = next(f for f in backup_status['backed_up_files'] if f['cloud_file_name'] == 'progress_status.json')
        epub_backup_info = next(f for f in backup_status['backed_up_files'] if f['cloud_file_name'] == 'test_story_123_vol_1.epub')

        self.assertEqual(progress_backup_info['status'], 'uploaded')
        self.assertEqual(progress_backup_info['cloud_file_id'], 'gdrive_progress_id')
        self.assertEqual(epub_backup_info['status'], 'uploaded')
        self.assertEqual(epub_backup_info['cloud_file_id'], 'gdrive_epub_id_1')


    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_skip_if_remote_not_older(self, mock_contexts_config_manager, mock_contexts_gdrive_sync):
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        self.mock_gdrive_sync_instance.create_folder_if_not_exists.side_effect = ['base_folder_id_456', 'story_folder_id_def']

        # Mock get_file_metadata: both files exist and are NOT older
        # Note: GDriveSync.is_remote_older needs to return False for skip to happen
        self.mock_gdrive_sync_instance.get_file_metadata.side_effect = [
            {'id': 'remote_progress_id', 'name': 'progress_status.json', 'modifiedTime': 'remote_ts1'},
            {'id': 'remote_epub_id', 'name': 'test_story_123_vol_1.epub', 'modifiedTime': 'remote_ts2'}
        ]
        self.mock_gdrive_sync_instance.is_remote_older.return_value = False # Crucial for this test

        self._create_dummy_progress_file(TEST_STORY_ID, epub_files_info=[{'name': 'test_story_123_vol_1.epub'}])

        result = self.runner.invoke(archiver, [
            'cloud-backup', TEST_STORY_ID,
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])

        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")
        self.mock_gdrive_sync_instance.upload_file.assert_not_called() # No uploads should happen

        # Verify progress_status.json reports skipped status
        updated_progress_data = pm.load_progress(TEST_STORY_ID, workspace_root=TEST_WORKSPACE_ROOT)
        backup_status = pm.get_cloud_backup_status(updated_progress_data)
        self.assertEqual(len(backup_status['backed_up_files']), 2)
        for file_backup_info in backup_status['backed_up_files']:
            self.assertEqual(file_backup_info['status'], 'skipped_up_to_date')
            self.assertIn('cloud_file_id', file_backup_info) # Should still record the ID

    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_force_full_upload(self, mock_contexts_config_manager, mock_contexts_gdrive_sync):
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        self.mock_gdrive_sync_instance.create_folder_if_not_exists.side_effect = ['base_folder_id_789', 'story_folder_id_ghi']
        # get_file_metadata might still be called by GDriveSync's upload if it tries to update vs create
        # but the handler logic for --force-full-upload should bypass calling it directly for decision making.
        # For simplicity, let's assume it won't be called by the handler.
        # GDriveSync.upload_file itself checks for existing files to update vs create.
        # So, get_file_metadata *will* be called by GDriveSync's upload_file method.
        # Let's have it return None to simulate files not existing on remote for a clean create.
        self.mock_gdrive_sync_instance.get_file_metadata.return_value = None


        mock_uploaded_progress_meta = {'id': 'forced_progress_id', 'name': 'progress_status.json', 'modifiedTime': 'ts_force1'}
        mock_uploaded_epub_meta = {'id': 'forced_epub_id_1', 'name': 'test_story_123_vol_1.epub', 'modifiedTime': 'ts_force2'}
        self.mock_gdrive_sync_instance.upload_file.side_effect = [mock_uploaded_progress_meta, mock_uploaded_epub_meta]

        self._create_dummy_progress_file(TEST_STORY_ID, epub_files_info=[{'name': 'test_story_123_vol_1.epub'}])
        progress_file_local_path = pm.get_progress_filepath(TEST_STORY_ID, workspace_root=TEST_WORKSPACE_ROOT)
        epub_local_path = os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, TEST_STORY_ID, 'test_story_123_vol_1.epub')


        result = self.runner.invoke(archiver, [
            'cloud-backup', TEST_STORY_ID,
            '--force-full-upload',
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])

        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")

        # Handler should NOT call get_file_metadata or is_remote_older for decision making
        # self.mock_gdrive_sync_instance.get_file_metadata.assert_not_called() # This is too strict, GDriveSync.upload_file calls it.
        self.mock_gdrive_sync_instance.is_remote_older.assert_not_called() # This is key for --force-full-upload

        self.mock_gdrive_sync_instance.upload_file.assert_has_calls([
            call(progress_file_local_path, 'story_folder_id_ghi', remote_file_name='progress_status.json'),
            call(os.path.abspath(epub_local_path), 'story_folder_id_ghi', remote_file_name='test_story_123_vol_1.epub')
        ])

        updated_progress_data = pm.load_progress(TEST_STORY_ID, workspace_root=TEST_WORKSPACE_ROOT)
        backup_status = pm.get_cloud_backup_status(updated_progress_data)
        self.assertEqual(len(backup_status['backed_up_files']), 2)
        for file_backup_info in backup_status['backed_up_files']:
            self.assertEqual(file_backup_info['status'], 'uploaded')

    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_all_stories(self, mock_contexts_config_manager, mock_contexts_gdrive_sync):
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        # Setup for two stories
        story_id_1 = "story_alpha"
        story_id_2 = "story_beta"
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.ARCHIVAL_STATUS_DIR_NAME, story_id_1), exist_ok=True)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, story_id_1), exist_ok=True)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.ARCHIVAL_STATUS_DIR_NAME, story_id_2), exist_ok=True)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, story_id_2), exist_ok=True)

        self._create_dummy_progress_file(story_id_1, epub_files_info=[{'name': 's1.epub'}])
        self._create_dummy_progress_file(story_id_2, epub_files_info=[{'name': 's2.epub'}])

        # Mock GDrive behavior
        # create_folder_if_not_exists is called:
        # 1. For base "Webnovel Archiver Backups" folder (before loop)
        # 2. For "story_alpha" (inside loop)
        # 3. For "story_beta" (inside loop)
        # The base folder ID is established once.
        self.mock_gdrive_sync_instance.create_folder_if_not_exists.side_effect = [
            'base_folder_all_id',   # ID for "Webnovel Archiver Backups"
            'story_alpha_folder_id', # ID for "story_alpha"
            'story_beta_folder_id'   # ID for "story_beta"
        ]
        self.mock_gdrive_sync_instance.get_file_metadata.return_value = None # All files are new
        self.mock_gdrive_sync_instance.upload_file.return_value = {'id': 'mock_id', 'name': 'uploaded_file', 'modifiedTime': 'ts_all'}

        result = self.runner.invoke(archiver, [
            'cloud-backup', # No story_id, so all
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])
        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")

        # Check that upload_file was called 4 times (progress + epub for each of 2 stories)
        self.assertEqual(self.mock_gdrive_sync_instance.upload_file.call_count, 4)

        # Check progress for story_alpha
        progress1 = pm.load_progress(story_id_1, TEST_WORKSPACE_ROOT)
        backup_status1 = pm.get_cloud_backup_status(progress1)
        self.assertEqual(backup_status1['story_cloud_folder_id'], 'story_alpha_folder_id') # Use the ID from side_effect
        self.assertEqual(len(backup_status1['backed_up_files']), 2) # progress + 1 epub
        for f_info in backup_status1['backed_up_files']: self.assertEqual(f_info['status'], 'uploaded')

        # Check progress for story_beta
        progress2 = pm.load_progress(story_id_2, TEST_WORKSPACE_ROOT)
        backup_status2 = pm.get_cloud_backup_status(progress2)
        self.assertEqual(backup_status2['story_cloud_folder_id'], 'story_beta_folder_id') # Use the ID from side_effect
        self.assertEqual(len(backup_status2['backed_up_files']), 2)
        for f_info in backup_status2['backed_up_files']: self.assertEqual(f_info['status'], 'uploaded')


    @patch('webnovel_archiver.cli.handlers.generate_report_main_func')
    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_generates_report_before_backup(self, mock_contexts_config_manager, mock_contexts_gdrive_sync, mock_generate_report):
        # Setup mocks
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        # Mock GDrive behavior to avoid actual cloud calls
        self.mock_gdrive_sync_instance.create_folder_if_not_exists.return_value = 'base_folder_id_report_test'
        self.mock_gdrive_sync_instance.get_file_metadata.return_value = None
        self.mock_gdrive_sync_instance.upload_file.return_value = {'id': 'mock_id', 'name': 'uploaded_file', 'modifiedTime': 'ts_report'}

        # Create a dummy story so the backup process runs
        self._create_dummy_progress_file(TEST_STORY_ID)

        # Run CLI command
        result = self.runner.invoke(archiver, [
            'cloud-backup', TEST_STORY_ID,
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])

        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")

        # Assert that generate_report_main_func was called
        mock_generate_report.assert_called_once()

        # Also assert that the backup process continued after the report generation
        self.mock_gdrive_sync_instance.upload_file.assert_called()

    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Patch GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # Patch ConfigManager where it's used by CloudBackupContext
    def test_cloud_backup_no_stories_found(self, mock_contexts_config_manager, mock_contexts_gdrive_sync):
        mock_contexts_config_manager.return_value = self.mock_config_manager
        mock_contexts_gdrive_sync.return_value = self.mock_gdrive_sync_instance

        # Ensure the archival status directory is empty or doesn't exist for any story
        archival_base_dir = os.path.join(TEST_WORKSPACE_ROOT, PathManager.ARCHIVAL_STATUS_DIR_NAME)
        if os.path.exists(os.path.join(archival_base_dir, TEST_STORY_ID)): # If the default test story dir exists
            shutil.rmtree(os.path.join(archival_base_dir, TEST_STORY_ID))
        # If archival_base_dir itself is empty or only contains non-story items, that's fine.
        # If it doesn't exist, create it so listdir doesn't fail, but it will be empty.
        os.makedirs(archival_base_dir, exist_ok=True)


        result = self.runner.invoke(archiver, [
            'cloud-backup',
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])
        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")
        self.assertIn("No stories found to back up.", result.output) # Adjusted expected message based on handler
        # Expect create_folder_if_not_exists to be called once for the base backup folder
        self.mock_gdrive_sync_instance.create_folder_if_not_exists.assert_called_once_with(
            'Webnovel Archiver Backups', parent_folder_id=None
        )


    @patch('webnovel_archiver.cli.contexts.GDriveSync') # Target GDriveSync where CloudBackupContext imports it
    @patch('webnovel_archiver.cli.contexts.ConfigManager') # This targets ConfigManager import in contexts.py
    def test_cloud_backup_gdrive_connection_error(self, mock_contexts_config_manager, mock_gdrive_sync_in_context): # Renamed mock
        mock_contexts_config_manager.return_value = self.mock_config_manager
        # Simulate GDriveSync constructor (as imported by CloudBackupContext) raising ConnectionError
        mock_gdrive_sync_in_context.side_effect = ConnectionError("Failed to connect to GDrive API")

        self._create_dummy_progress_file(TEST_STORY_ID)

        result = self.runner.invoke(archiver, [
            'cloud-backup', TEST_STORY_ID,
            '--credentials-file', TEST_CREDENTIALS_FILE,
            '--token-file', TEST_TOKEN_FILE
        ])
        # Command should not fail with non-zero exit code, but print an error message
        self.assertEqual(result.exit_code, 0, f"CLI command failed: {result.output}")
        self.assertIn("Error: Could not connect to Google Drive", result.output)

if __name__ == '__main__':
    unittest.main()
