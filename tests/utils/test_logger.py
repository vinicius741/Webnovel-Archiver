import unittest
import os
import logging
import shutil # For cleaning up created directories/files

from webnovel_archiver.utils.logger import get_logger, LOG_FILE_PATH, WORKSPACE_PATH, DEFAULT_LOGS_DIR_NAME, DEFAULT_LOG_FILE_NAME
# from webnovel_archiver.core.config_manager import PROJECT_ROOT # WORKSPACE_PATH from logger.py is effectively PROJECT_ROOT/workspace

# Expected log directory and file path based on logger's own constants
EXPECTED_LOG_DIR = os.path.join(WORKSPACE_PATH, DEFAULT_LOGS_DIR_NAME)
EXPECTED_LOG_FILE = os.path.join(EXPECTED_LOG_DIR, DEFAULT_LOG_FILE_NAME)

class TestLogger(unittest.TestCase):

    def setUp(self):
        self.log_dir = EXPECTED_LOG_DIR
        self.log_file = EXPECTED_LOG_FILE

        if os.path.exists(self.log_dir):
            shutil.rmtree(self.log_dir)

        # Ensure logger's initialization code (including directory creation) runs.
        get_logger("SetupLoggerInit")


    def tearDown(self):
        if os.path.exists(self.log_dir):
            shutil.rmtree(self.log_dir)

    def test_log_file_creation_and_content(self):
        logger = get_logger('TestLogger')

        test_message = "This is a test log message from test_log_file_creation_and_content."
        logger.info(test_message)

        self.assertTrue(os.path.exists(self.log_file), f"Log file not found at {self.log_file}")

        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()

        self.assertIn(test_message, log_content, "Test message not found in log file.")
        self.assertIn("INFO", log_content, "Log level 'INFO' not found in log message.")
        # LOG_FORMAT is '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
        # %(name)s should be 'TestLogger'
        self.assertIn("TestLogger", log_content, "Logger name 'TestLogger' not found in log message.")
        # %(module)s should be 'test_logger' (the module name of this test file)
        # The prompt expected "test_logger.py", let's stick to that for now.
        self.assertIn("test_logger.py", log_content, "Module name 'test_logger.py' not found in log content")
        # %(funcName)s is 'test_log_file_creation_and_content'
        self.assertIn("test_log_file_creation_and_content", log_content, "Function name 'test_log_file_creation_and_content' not found in log content")


    def test_log_directory_creation_by_logger_module(self):
        # setUp already calls get_logger, which should trigger directory creation.
        # To be absolutely sure for this specific test, we can clean and re-trigger.
        if os.path.exists(self.log_dir):
            shutil.rmtree(self.log_dir)

        get_logger("DirCreateTestEnsureInit") # Ensures logger module code has run.

        self.assertTrue(os.path.exists(self.log_dir),
                        f"Log directory '{self.log_dir}' was not created by the logger module.")

if __name__ == '__main__':
    unittest.main()
