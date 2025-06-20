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

        # The logger module creates the directory on import.
        # For test isolation, we only clean the log file before each test.
        # The directory is expected to exist from the initial module import.
        # Close any open file handlers on the target log file before removing it.
        logger_to_test = logging.getLogger("WebnovelArchiver") # Assuming this is the logger with the file handler
        for handler in logger_to_test.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == self.log_file:
                handler.close() # Close the handler before removing the file

        if os.path.exists(self.log_file):
            os.remove(self.log_file)

        # We will not call os.makedirs(self.log_dir, exist_ok=True) here.
        # test_log_directory_creation_by_logger_module will assert its existence from module load.
        # test_log_file_creation_and_content will rely on RotatingFileHandler creating the file in the existing dir.


    def tearDown(self):
        # Clean up the log file after each test
        if os.path.exists(self.log_file):
            try:
                os.remove(self.log_file)
            except OSError: # pragma: no cover
                pass # Ignore if it's already gone somehow
        # We don't remove the log_dir itself here, as it's created by module import
        # and might be expected by other test classes if they run in parallel or sequence.
        # If the test runner cleans the whole workspace, that's better.

    def test_log_file_creation_and_content(self):
        logger = get_logger() # Get the main "WebnovelArchiver" logger

        test_message = "This is a test log message from test_log_file_creation_and_content."
        logger.info(test_message)

        # Attempt to flush handlers
        for handler in logger.handlers:
            handler.flush()

        # Debug prints
        print(f"DEBUG: Workspace path (logger.py): {WORKSPACE_PATH}")
        print(f"DEBUG: Log dir path (logger.py): {os.path.dirname(LOG_FILE_PATH)}")
        print(f"DEBUG: Log file path (logger.py): {LOG_FILE_PATH}")
        print(f"DEBUG: Expected log_dir (test): {self.log_dir}")
        print(f"DEBUG: Expected log_file (test): {self.log_file}")
        print(f"DEBUG: Exists {self.log_dir}? {os.path.exists(self.log_dir)}")
        if os.path.exists(self.log_dir):
            print(f"DEBUG: Contents of {self.log_dir}: {os.listdir(self.log_dir)}")

        self.assertTrue(os.path.exists(self.log_file), f"Log file not found at {self.log_file}")

        with open(self.log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()

        self.assertIn(test_message, log_content, "Test message not found in log file.")
        self.assertIn("INFO", log_content, "Log level 'INFO' not found in log message.")
        # %(name)s for the default logger is "WebnovelArchiver"
        self.assertIn("WebnovelArchiver", log_content, "Logger name 'WebnovelArchiver' not found in log message.")
        # %(module)s is 'test_logger' (the module name of this test file)
        self.assertIn("test_logger", log_content, "Module name 'test_logger' not found in log content.")
        # %(funcName)s is 'test_log_file_creation_and_content'
        self.assertIn("test_log_file_creation_and_content", log_content, "Function name 'test_log_file_creation_and_content' not found in log content.")


    def test_log_directory_creation_by_logger_module(self):
        # This test verifies that the logger module, upon import,
        # created the log directory. setUp ensures the directory is present for the file test.
        self.assertTrue(os.path.exists(self.log_dir),
                        f"Log directory '{self.log_dir}' should have been created by logger module import.")

if __name__ == '__main__':
    unittest.main()
