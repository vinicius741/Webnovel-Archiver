import configparser
import os
from typing import Optional

# Determine the absolute path to the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Construct the path to settings.ini relative to the project root (assuming script is in webnovel_archiver/core)
# Adjust '..' as necessary if the script moves or if your project structure is different.
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR)) # This goes up two levels from core/ to the project root
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'workspace', 'config', 'settings.ini')
DEFAULT_WORKSPACE_PATH = os.path.join(PROJECT_ROOT, 'workspace/')


class ConfigManager:
    def __init__(self, config_file_path=None):
        self.config_file_path = config_file_path or DEFAULT_CONFIG_PATH
        self.config = configparser.ConfigParser()
        self._load_config()

    def _load_config(self):
        """Loads the configuration from the INI file."""
        if not os.path.exists(self.config_file_path):
            # Fallback to default if config file doesn't exist
            print(f"Warning: Config file not found at {self.config_file_path}. Attempting to create a default config or using hardcoded defaults.")
            # Ensure the directory for the config file exists
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            # Create a default config
            default_config = configparser.ConfigParser()
            default_config['General'] = {'workspace_path': DEFAULT_WORKSPACE_PATH}
            try:
                with open(self.config_file_path, 'w') as configfile:
                    default_config.write(configfile)
                print(f"Created a default config file at: {self.config_file_path}")
                self.config = default_config
            except IOError as e:
                print(f"Error creating default config file: {e}. Using hardcoded defaults.")
                # Use hardcoded defaults if file creation fails
                self.config['General'] = {'workspace_path': DEFAULT_WORKSPACE_PATH}
            return

        self.config.read(self.config_file_path)

    def get_workspace_path(self) -> str:
        """Returns the workspace path from the config or a default value."""
        # Ensure that returned path is absolute or resolved correctly if relative
        path = self.config.get('General', 'workspace_path', fallback=DEFAULT_WORKSPACE_PATH)
        if not os.path.isabs(path):
            # Assuming workspace_path in config is relative to project root
            return os.path.join(PROJECT_ROOT, path)
        return path

    def get_setting(self, section: str, option: str, fallback=None) -> Optional[str]:
        """Gets a specific setting from the configuration."""
        try:
            return self.config.get(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

if __name__ == '__main__':
    # Example usage:
    config_manager = ConfigManager()
    workspace_path = config_manager.get_workspace_path()
    print(f"Workspace Path: {workspace_path}")

    # Example of getting another setting, or a default if not found
    log_level = config_manager.get_setting('Logging', 'level', fallback='INFO')
    print(f"Log Level: {log_level}")

    # To test with a non-existent config file to see the fallback mechanism:
    # test_config_manager = ConfigManager(config_file_path=os.path.join(PROJECT_ROOT, 'workspace', 'config', 'non_existent_settings.ini'))
    # test_workspace_path = test_config_manager.get_workspace_path()
    # print(f"Test Workspace Path (with non_existent_settings.ini): {test_workspace_path}")
    # log_level_test = test_config_manager.get_setting('Logging', 'level', fallback='DEBUG')
    # print(f"Test Log Level (with non_existent_settings.ini): {log_level_test}")
