import unittest
import os
import shutil
import json
from unittest.mock import patch, MagicMock

from webnovel_archiver.generate_report import main as generate_report_main

class TestGenerateReport(unittest.TestCase):

    def setUp(self):
        self.test_dir = "workspace"
        os.makedirs(self.test_dir, exist_ok=True)
        self.index_path = os.path.join(self.test_dir, "index.json")
        self.archival_status_path = os.path.join(self.test_dir, "archival_status")
        os.makedirs(self.archival_status_path, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('webnovel_archiver.generate_report.webbrowser')
    def test_generate_report_with_index(self, mock_webbrowser):
        # Create a dummy index file
        index_data = {
            "royalroad-12345": "test-story"
        }
        with open(self.index_path, 'w') as f:
            json.dump(index_data, f)

        # Create a dummy progress file
        story_folder = os.path.join(self.archival_status_path, "test-story")
        os.makedirs(story_folder)
        progress_file = os.path.join(story_folder, "progress_status.json")
        with open(progress_file, 'w') as f:
            json.dump({"story_id": "royalroad-12345", "original_title": "Test Story"}, f)

        # Run the report generator
        with patch('webnovel_archiver.generate_report.ConfigManager') as mock_config_manager:
            mock_config_manager.return_value.get_workspace_path.return_value = self.test_dir
            generate_report_main()

        # Check if the report was generated
        report_path = os.path.join(self.test_dir, "reports", "archive_report_new.html")
        self.assertTrue(os.path.exists(report_path))

        # Check the content of the report
        with open(report_path, 'r') as f:
            report_content = f.read()
            self.assertIn("Test Story", report_content)
            self.assertIn("royalroad-12345", report_content)

if __name__ == '__main__':
    unittest.main()
