import os
import json
import unittest
from unittest.mock import patch, MagicMock, call, mock_open
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
        self.patchers = {}
        # Ensure a clean test workspace
        if os.path.exists(TEST_WORKSPACE_ROOT):
            shutil.rmtree(TEST_WORKSPACE_ROOT)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.ARCHIVAL_STATUS_DIR_NAME, TEST_STORY_ID), exist_ok=True)
        os.makedirs(os.path.join(TEST_WORKSPACE_ROOT, PathManager.EBOOKS_DIR_NAME, TEST_STORY_ID), exist_ok=True)

        # Create a dummy index.json for tests that require it
        self.index_path = os.path.join(TEST_WORKSPACE_ROOT, "index.json")
        with open(self.index_path, 'w') as f:
            json.dump({TEST_STORY_ID: TEST_STORY_ID}, f)

        # Mock os.path.exists and open for index.json
        self.original_os_path_exists = os.path.exists
        self.original_open = open

        def mock_os_path_exists(path):
            if path == self.index_path:
                return True
            return self.original_os_path_exists(path)

        def mock_open_func(file, mode='r', *args, **kwargs):
            if file == self.index_path:
                if 'r' in mode:
                    return mock_open(read_data=json.dumps({TEST_STORY_ID: TEST_STORY_ID})).return_value
                elif 'w' in mode:
                    return mock_open() # For writing, just return a mock
            return self.original_open(file, mode, *args, **kwargs)

        # Patch os.path.exists and open globally for the duration of the test
        self.patchers['os_path_exists'] = patch('os.path.exists', side_effect=mock_os_path_exists)
        self.patchers['builtins_open'] = patch('builtins.open', side_effect=mock_open_func)

        for p in self.patchers.values():
            p.start()

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