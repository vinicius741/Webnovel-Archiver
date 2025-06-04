import logging
import os
from logging.handlers import RotatingFileHandler

# Default log level - can be overridden by environment variable or config
LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Create a specific logger
logger = logging.getLogger('WebnovelArchiver')
logger.setLevel(LOG_LEVEL) # Set the threshold for this logger

# Initial minimal console handler for early messages
_early_console_handler = logging.StreamHandler()
# Using a simpler format for early logs, full format applied later
_early_console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
_early_console_handler.setFormatter(_early_console_formatter)
logger.addHandler(_early_console_handler)

# Determine project root based on the location of logger.py
# Assumes logger.py is in webnovel_archiver/utils/logger.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORKSPACE_PATH = os.path.join(PROJECT_ROOT, 'workspace')

DEFAULT_LOG_FILE_NAME = 'archiver.log'
DEFAULT_LOGS_DIR_NAME = 'logs'
LOG_FILE_PATH = os.path.join(WORKSPACE_PATH, DEFAULT_LOGS_DIR_NAME, DEFAULT_LOG_FILE_NAME)

logger.info(f"Log file path set to: {LOG_FILE_PATH}")

# Ensure the log directory exists
# The directory for the log file is created using the path derived from WORKSPACE_PATH.
log_dir = os.path.dirname(LOG_FILE_PATH)
logger.info(f"Ensuring log directory exists at: {log_dir}")
try:
    os.makedirs(log_dir, exist_ok=True)
    logger.info(f"Log directory '{log_dir}' ensured successfully.")
except OSError as e:
    logger.error(f"Failed to create log directory '{log_dir}': {e}", exc_info=True)
    # Depending on the application's needs, one might re-raise the exception or exit here
    # For now, we log the error and continue, the file handler might fail later if dir doesn't exist

# Basic log format - will be used by handlers added later
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Configure the root logger - basicConfig can be used if you want to set it for the whole application easily
# However, creating a specific logger is often better for libraries or larger applications.
# logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt=DATE_FORMAT)

# Prevent propagation to the root logger if it has default handlers, to avoid duplicate messages.
# This is important if other parts of the application or libraries also configure the root logger.
logger.propagate = False

# Create handlers if not already present (to avoid duplicate handlers on re-import)
# Note: _early_console_handler was already added. The check `if not logger.handlers:`
# might be too simple if this module can be reloaded in a way that handlers persist.
# However, standard import behavior usually creates a new logger object or re-initializes.
# For robustness, one might check handler types if adding identically configured handlers is an issue.
if len(logger.handlers) <= 1: # Check if only early_console_handler or no handlers exist
    # Remove early console handler if we are about to add the proper one
    # or if it's the only one and we want to replace it with a more configured one.
    # This logic depends on whether the early handler should persist alongside the new one.
    # For now, let's assume the new console handler is more complete and replace the early one.
    if _early_console_handler in logger.handlers:
        logger.removeHandler(_early_console_handler)

    # Console Handler (more sophisticated)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT) # Use detailed format
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler (Rotating)
    # Using RotatingFileHandler to prevent log files from growing indefinitely
    # Max 5MB per file, keeping up to 5 backup files.
    file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(LOG_LEVEL)
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

def get_logger(name: str = 'WebnovelArchiver') -> logging.Logger:
    """
    Returns a logger instance.
    You can pass a specific name to get a child logger of 'WebnovelArchiver'
    which can be useful for more granular logging in different parts of the application.
    e.g., logger = get_logger(__name__)
    """
    return logging.getLogger(name)

if __name__ == '__main__':
    # Example usage:
    # This demonstrates how the logger can be obtained and used.
    # In other modules, you would typically do:
    # from webnovel_archiver.utils.logger import get_logger
    # logger = get_logger(__name__) # or a specific name for that module

    # Using the main 'WebnovelArchiver' logger directly for this example
    main_logger = get_logger() # Gets the 'WebnovelArchiver' logger configured above

    main_logger.debug("This is a debug message.")
    main_logger.info("This is an info message. Application started.")
    main_logger.warning("This is a warning message. Something to be aware of.")
    main_logger.error("This is an error message. An error occurred.")
    main_logger.critical("This is a critical message. A critical failure.")

    # Example of a child logger
    child_logger = get_logger('WebnovelArchiver.module_x') # or simply get_logger(__name__) in another file
    child_logger.info("Info message from a child logger for specific module.")

    print(f"Logging configured. Log level: {LOG_LEVEL_STR}")
    print(f"Log messages are being output to console and to: {LOG_FILE_PATH}")
    print("Check the console output and the log file for messages.")
