import logging
import os
from logging.handlers import RotatingFileHandler

# Default log level - can be overridden by environment variable or config
LOG_LEVEL_STR = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# Basic log format - will be used by handlers added later
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Determine project root based on the location of logger.py
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORKSPACE_PATH = os.path.join(PROJECT_ROOT, 'workspace')
DEFAULT_LOGS_DIR_NAME = 'logs'
LOGS_DIR = os.path.join(WORKSPACE_PATH, DEFAULT_LOGS_DIR_NAME)

def setup_logger(logger_name, log_file, level=logging.INFO, add_console_handler=True):
    """Generic function to set up a logger."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    # Remove existing handlers to avoid duplication
    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler
    if add_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level) # Set level for console handler
        console_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger

# Setup main application logger
main_log_file = os.path.join(LOGS_DIR, 'archiver.log')
logger = setup_logger('WebnovelArchiver', main_log_file, LOG_LEVEL)

# Setup migration logger
migration_log_file = os.path.join(LOGS_DIR, 'migration.log')
migration_logger = setup_logger('MigrationLogger', migration_log_file, logging.INFO, add_console_handler=False) # Console output for migration is handled via click.echo

def get_logger(name: str = 'WebnovelArchiver') -> logging.Logger:
    """
    Returns the main application logger instance.
    """
    return logging.getLogger(name)

def get_migration_logger() -> logging.Logger:
    """
    Returns the migration logger instance.
    """
    return logging.getLogger('MigrationLogger')

if __name__ == '__main__':
    # Example usage:
    main_logger = get_logger()
    main_logger.debug("This is a debug message for the main logger.")
    main_logger.info("This is an info message for the main logger.")

    mig_logger = get_migration_logger()
    mig_logger.info("This is an info message for the migration logger.")
    
    print(f"Main log file: {main_log_file}")
    print(f"Migration log file: {migration_log_file}")

