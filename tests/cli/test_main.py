import pytest
from click.testing import CliRunner
from unittest import mock

from webnovel_archiver.cli.main import archiver

# Path to the handler to mock within main.py's context
MOCK_HANDLER_PATH_IN_MAIN = "webnovel_archiver.cli.main.archive_story_handler"

@pytest.fixture
def runner():
    return CliRunner()

import os

def test_archive_story_cli_passes_params_to_handler(runner, tmp_path):
    """
    Tests that the 'archive-story' CLI command correctly passes all its options
    as arguments to the archive_story_handler function.
    """
    story_url_in = "http://example.com/story-to-archive"
    # For type=click.Path(exists=True), Click would normally check this.
    # However, for this unit test of main.py -> handler call, we don't need the file to actually exist.
    # Click's processing of exists=True happens before our mock_handler is called.
    # If the path was invalid and exists=True was active without `resolve_path=False`,
    # Click would error out before calling the command's Python function.
    # Here, we just need a string path.
    rules_file_in = tmp_path / "dummy_rules.json"
    rules_file_in.touch() # Create the dummy file
    rules_file_in = str(rules_file_in.resolve())

    output_dir_in = "/custom/output/dir"
    ebook_title_override_in = "My Custom Test Title"
    chapters_per_volume_in = 30

    with mock.patch(MOCK_HANDLER_PATH_IN_MAIN) as mock_handler:
        result = runner.invoke(archiver, [
            'archive-story',
            story_url_in,
            '--output-dir', output_dir_in,
            '--ebook-title-override', ebook_title_override_in,
            '--sentence-removal-file', rules_file_in,
            '--no-sentence-removal',        # Flag, so it's True
            '--keep-temp-files',            # Flag, so it's True
            '--force-reprocessing',         # Flag, so it's True
            '--chapters-per-volume', str(chapters_per_volume_in)
        ])

        assert result.exit_code == 0, f"CLI command failed: {result.output}"
        mock_handler.assert_called_once()

        # Get the keyword arguments from the mock call
        # The first element of call_args is a tuple of positional args,
        # the second is a dictionary of keyword args.
        # handler is called with all keyword args.
        called_kwargs = mock_handler.call_args[1]

        assert called_kwargs['story_url'] == story_url_in
        assert called_kwargs['output_dir'] == output_dir_in
        assert called_kwargs['ebook_title_override'] == ebook_title_override_in
        assert called_kwargs['keep_temp_files'] is True
        assert called_kwargs['force_reprocessing'] is True
        assert called_kwargs['cli_sentence_removal_file'] == rules_file_in
        assert called_kwargs['no_sentence_removal'] is True
        assert called_kwargs['chapters_per_volume'] == chapters_per_volume_in

def test_archive_story_cli_default_params(runner):
    """
    Tests that the 'archive-story' CLI command passes default values
    to the archive_story_handler when options are not provided.
    """
    story_url_in = "http://example.com/default-param-story"

    with mock.patch(MOCK_HANDLER_PATH_IN_MAIN) as mock_handler:
        result = runner.invoke(archiver, [
            'archive-story',
            story_url_in
            # No other options provided, so defaults should be used
        ])

        assert result.exit_code == 0, f"CLI command failed: {result.output}"
        mock_handler.assert_called_once()

        called_kwargs = mock_handler.call_args[1]

        assert called_kwargs['story_url'] == story_url_in
        # Check default values as defined in main.py's @click.option decorators
        assert called_kwargs['output_dir'] is None
        assert called_kwargs['ebook_title_override'] is None
        assert called_kwargs['keep_temp_files'] is False
        assert called_kwargs['force_reprocessing'] is False
        assert called_kwargs['cli_sentence_removal_file'] is None # Default for the option
        assert called_kwargs['no_sentence_removal'] is False
        assert called_kwargs['chapters_per_volume'] is None # Default for the option
