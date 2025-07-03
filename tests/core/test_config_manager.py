import configparser
import os
import pytest
from unittest import mock

from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_CONFIG_PATH, DEFAULT_WORKSPACE_PATH

# Determine the project root based on the location of this test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TEST_DIR)) # Up two levels from tests/core to project root

# Define a temporary config file path for testing
TEST_CONFIG_FILE = os.path.join(PROJECT_ROOT, 'test_workspace', 'config', 'test_settings.ini')
TEST_WORKSPACE_PATH = os.path.join(PROJECT_ROOT, 'test_workspace', 'test_files')
TEST_SENTENCE_REMOVAL_FILE = os.path.join(TEST_WORKSPACE_PATH, 'config', 'test_sentence_removal.json')

@pytest.fixture
def temp_config_file(request, isolated_workspace):
    """
    Creates a temporary config file for testing.
    The content of the config file can be customized by passing a dictionary
    to `request.param`.
    """
    config_content = getattr(request, "param", {})
    config = configparser.ConfigParser()

    for section, options in config_content.items():
        config[section] = options

    config_path = os.path.join(isolated_workspace, "test_settings.ini")
    with open(config_path, 'w') as configfile:
        config.write(configfile)
    return config_path

@pytest.fixture
def mock_default_config_path(isolated_workspace):
    with mock.patch('webnovel_archiver.core.config_manager.DEFAULT_CONFIG_PATH', os.path.join(isolated_workspace, "settings.ini")):
        yield

@pytest.fixture
def mock_default_workspace_path(isolated_workspace):
     with mock.patch('webnovel_archiver.core.config_manager.DEFAULT_WORKSPACE_PATH', isolated_workspace):
        yield


def test_load_config_file_not_found_creates_default(mock_default_config_path, mock_default_workspace_path, isolated_workspace):
    """Test that a default config is created if the config file is not found."""
    config_path = os.path.join(isolated_workspace, "settings.ini")
    if os.path.exists(config_path):
        os.remove(config_path) # Ensure it doesn't exist

    cm = ConfigManager(config_file_path=config_path)
    assert os.path.exists(config_path)
    assert cm.config.get('General', 'workspace_path') == isolated_workspace

    # Check if the default sentence removal file path is correctly set relative to the (mocked) default workspace
    expected_sentence_removal_path = os.path.join(isolated_workspace, 'config', 'default_sentence_removal.json')
    assert cm.config.get('SentenceRemoval', 'default_sentence_removal_file') == expected_sentence_removal_path


@pytest.mark.parametrize("temp_config_file", [{
    'General': {'workspace_path': TEST_WORKSPACE_PATH},
    'SentenceRemoval': {'default_sentence_removal_file': TEST_SENTENCE_REMOVAL_FILE}
}], indirect=True)
def test_load_existing_config(temp_config_file, isolated_workspace):
    """Test loading an existing config file."""
    cm = ConfigManager(config_file_path=temp_config_file)
    assert cm.get_workspace_path() == os.path.abspath(isolated_workspace)
    assert cm.get_default_sentence_removal_file() == TEST_SENTENCE_REMOVAL_FILE

def test_get_workspace_path_from_env_var(monkeypatch, isolated_workspace):
    """Test that workspace path is taken from environment variable if set."""
    env_path = isolated_workspace
    monkeypatch.setenv('WNA_WORKSPACE_ROOT', env_path)
    cm = ConfigManager(config_file_path=TEST_CONFIG_FILE) # Config file doesn't need to exist for this test
    assert cm.get_workspace_path() == os.path.abspath(env_path)

@pytest.mark.parametrize("temp_config_file", [{
    'General': {'workspace_path': 'relative/path/to/workspace'},
}], indirect=True)
def test_get_workspace_path_relative_from_config(temp_config_file, isolated_workspace):
    """Test resolving a relative workspace path from config."""
    cm = ConfigManager(config_file_path=temp_config_file)
    expected_path = os.path.abspath(os.path.join(PROJECT_ROOT, 'relative/path/to/workspace'))
    assert cm.get_workspace_path() == os.path.abspath(isolated_workspace)


def test_get_workspace_path_default_fallback(mock_default_config_path, mock_default_workspace_path, isolated_workspace):
    """Test fallback to default workspace path if not in env or config."""
    # Ensure no env var is set
    with mock.patch.dict(os.environ, {}, clear=True):
        # Ensure config file does not exist to force default
        config_path = os.path.join(isolated_workspace, "settings.ini")
        if os.path.exists(config_path):
            os.remove(config_path)

        cm = ConfigManager(config_file_path=config_path)
        # Since the config file is removed, it will be recreated with defaults during __init__
        # The default workspace path used will be the mocked DEFAULT_WORKSPACE_PATH
        assert cm.get_workspace_path() == os.path.abspath(isolated_workspace)


@pytest.mark.parametrize("temp_config_file", [{
    'Logging': {'level': 'DEBUG'}
}], indirect=True)
def test_get_setting(temp_config_file):
    """Test getting a specific setting."""
    cm = ConfigManager(config_file_path=temp_config_file)
    assert cm.get_setting('Logging', 'level') == 'DEBUG'

def test_get_setting_fallback(temp_config_file): # temp_config_file is not strictly needed if we test missing option
    """Test fallback for get_setting."""
    cm = ConfigManager(config_file_path=temp_config_file) # An empty or non-existent config file
    assert cm.get_setting('NonExistentSection', 'non_existent_option', fallback='default_value') == 'default_value'

@pytest.mark.parametrize("temp_config_file", [{
    'SentenceRemoval': {'default_sentence_removal_file': TEST_SENTENCE_REMOVAL_FILE}
}], indirect=True)
def test_get_default_sentence_removal_file(temp_config_file):
    """Test getting the default sentence removal file path."""
    cm = ConfigManager(config_file_path=temp_config_file)
    assert cm.get_default_sentence_removal_file() == TEST_SENTENCE_REMOVAL_FILE

@pytest.mark.parametrize("temp_config_file", [{
    'General': {'workspace_path': TEST_WORKSPACE_PATH} # Missing SentenceRemoval section
}], indirect=True)
def test_get_default_sentence_removal_file_missing_section_adds_defaults(temp_config_file, mock_default_workspace_path, isolated_workspace): # Add fixture
    """Test that default sentence removal settings are added if section is missing."""
    # mock_default_workspace_path is now active here via fixture injection

    # This ConfigManager will be created with the mocked DEFAULT_WORKSPACE_PATH
    cm = ConfigManager(config_file_path=temp_config_file)

    assert cm.config.has_section('SentenceRemoval')
    assert cm.config.has_option('SentenceRemoval', 'default_sentence_removal_file')

    # The path in the config should now be based on the mocked TEST_WORKSPACE_PATH
    expected_default_path = os.path.join(isolated_workspace, 'config', 'default_sentence_removal.json')

    assert cm.get_default_sentence_removal_file() == expected_default_path

    # Also check if the file was updated correctly
    reloaded_config = configparser.ConfigParser()
    reloaded_config.read(temp_config_file)
    assert reloaded_config.get('SentenceRemoval', 'default_sentence_removal_file') == expected_default_path


@pytest.mark.parametrize("temp_config_file", [{
    'SentenceRemoval': {'default_sentence_removal_file': '   '} # Empty path
}], indirect=True)
def test_get_default_sentence_removal_file_empty_path(temp_config_file):
    """Test that None is returned if the path is empty or whitespace."""
    cm = ConfigManager(config_file_path=temp_config_file)
    assert cm.get_default_sentence_removal_file() is None

def test_config_manager_handles_ioerror_on_default_creation(mock_default_config_path, mock_default_workspace_path, caplog, isolated_workspace):
    """Test that ConfigManager handles IOError when creating a default config file and uses hardcoded defaults."""
    config_path = os.path.join(isolated_workspace, "settings.ini")
    if os.path.exists(config_path):
        os.remove(config_path)

    with mock.patch('builtins.open', mock.mock_open()) as mocked_open:
        mocked_open.side_effect = IOError("Permission denied")
        cm = ConfigManager(config_file_path=config_path)

        assert "Error creating default config file: Permission denied" in caplog.text
        # Check if hardcoded defaults are used
        assert cm.config.get('General', 'workspace_path') == isolated_workspace
        expected_sentence_removal_path = os.path.join(isolated_workspace, 'config', 'default_sentence_removal.json')
        assert cm.config.get('SentenceRemoval', 'default_sentence_removal_file') == expected_sentence_removal_path

def test_config_manager_handles_ioerror_on_update_with_sentence_removal(caplog, isolated_workspace):
    """Test that ConfigManager handles IOError when updating config file with SentenceRemoval settings."""
    # Create a config file without SentenceRemoval section
    config_data = {'General': {'workspace_path': TEST_WORKSPACE_PATH}}
    config = configparser.ConfigParser()
    config['General'] = config_data['General']

    config_path = os.path.join(isolated_workspace, "settings.ini")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as cf:
        config.write(cf)

    with mock.patch('builtins.open', mock.mock_open(read_data=open(config_path).read())) as mocked_open_logic:
        # The first open for reading should succeed. The second for writing should fail.
        mocked_open_logic.side_effect = [
            mock.DEFAULT, # For the initial read
            IOError("Permission denied for update") # For the write operation
        ]

        cm = ConfigManager(config_file_path=config_path)

        assert f"Error updating config file with SentenceRemoval settings: Permission denied for update" in caplog.text
        # Ensure that the config in memory still has the added SentenceRemoval settings
        assert cm.config.has_section('SentenceRemoval')
        assert cm.config.has_option('SentenceRemoval', 'default_sentence_removal_file')

        # Since the write failed, the actual file should not have been updated.
        # The in-memory config should reflect the defaults it tried to set.
        # The default path for sentence removal is based on DEFAULT_WORKSPACE_PATH.
        expected_default_sentence_path = os.path.join(DEFAULT_WORKSPACE_PATH, 'config', 'default_sentence_removal.json')
        assert cm.get_default_sentence_removal_file() == expected_default_sentence_path

    if os.path.exists(config_path):
        os.remove(config_path)
