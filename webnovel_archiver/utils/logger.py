import logging
import os
from logging.handlers import RotatingFileHandler

# Attempt to use ConfigManager to get workspace_path
# This creates a soft dependency; if ConfigManager is not yet available or fails,
# it falls back to a default log path.
try:
    from webnovel_archiver.core.config_manager import ConfigManager
    config_manager = ConfigManager()
    WORKSPACE_PATH = config_manager.get_workspace_path()
except ImportError:
    # Fallback if ConfigManager is not found (e.g., during early init or testing)
    # This assumes the script is run from the project root or WORKSPACE_PATH needs to be defined differently.
    # For robustness, especially if this logger is used by ConfigManager itself,
    # we might need a more independent way to determine WORKSPACE_PATH or use a relative path from this script.
    # For now, let's assume a 'workspace' directory in the current working directory or project root.
    # This path will be used if ConfigManager cannot be imported or used.
    PROJECT_ROOT_FALLBACK = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    WORKSPACE_PATH = os.path.join(PROJECT_ROOT_FALLBACK, 'workspace')


DEFAULT_LOG_FILE_NAME = 'archiver.log'
DEFAULT_LOGS_DIR_NAME = 'logs'
LOG_FILE_PATH = os.path.join(WORKSPACE_PATH, DEFAULT_LOGS_DIR_NAME, DEFAULT_LOG_FILE_NAME)

# Ensure the log directory exists
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

# Default log level - can be overridden by environment variable or config
LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Basic log format
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Configure the root logger - basicConfig can be used if you want to set it for the whole application easily
# However, creating a specific logger is often better for libraries or larger applications.
# logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt=DATE_FORMAT)

# Create a specific logger
logger = logging.getLogger('WebnovelArchiver')
logger.setLevel(LOG_LEVEL) # Set the threshold for this logger

# Prevent propagation to the root logger if it has default handlers, to avoid duplicate messages.
# This is important if other parts of the application or libraries also configure the root logger.
logger.propagate = False

# Create handlers if not already present (to avoid duplicate handlers on re-import)
if not logger.handlers:
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
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
