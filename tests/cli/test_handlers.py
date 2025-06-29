import pytest
from unittest import mock
import click # Required for mock.patch('click.echo') etc.

from webnovel_archiver.cli.handlers import archive_story_handler, cloud_backup_handler, migration_handler, generate_report_handler, handle_restore_from_epubs
from webnovel_archiver.cli.contexts import ArchiveStoryContext # For mocking its instance

# Mock path for the orchestrator function called by the handler
ORCHESTRATOR_PATH = "webnovel_archiver.cli.handlers.call_orchestrator_archive_story"
# Mock path for the ArchiveStoryContext class
ARCHIVE_STORY_CONTEXT_PATH = "webnovel_archiver.cli.handlers.ArchiveStoryContext"
# Mock paths for click functions
CLICK_ECHO_PATH = "webnovel_archiver.cli.handlers.click.echo"
CLICK_STYLE_PATH = "webnovel_archiver.cli.handlers.click.style"
# Mock path for logger
LOGGER_ERROR_PATH = "webnovel_archiver.cli.handlers.logger.error"
LOGGER_INFO_PATH = "webnovel_archiver.cli.handlers.logger.info"
LOGGER_WARNING_PATH = "webnovel_archiver.cli.handlers.logger.warning"

@pytest.fixture
def mock_archive_story_context_valid():
    """Mocks a valid ArchiveStoryContext instance."""
    mock_context = mock.Mock(spec=ArchiveStoryContext)
    mock_context.is_valid.return_value = True
    mock_context.error_messages = []
    mock_context.warning_messages = [] # Added for consistency, though not directly used by archive_story_handler for initial reporting
    mock_context.story_url = "http://example.com/story"
    mock_context.workspace_root = "/mock/workspace"
    mock_context.sentence_removal_file = "/mock/sentence_removal.json"
    mock_context.no_sentence_removal = False
    mock_context.get_orchestrator_kwargs.return_value = {
        "story_url": "http://example.com/story",
        "output_dir": "/mock/workspace",
        # ... other kwargs the orchestrator expects
    }
    return mock_context

@pytest.fixture
def mock_archive_story_context_invalid():
    """Mocks an invalid ArchiveStoryContext instance."""
    mock_context = mock.Mock(spec=ArchiveStoryContext)
    mock_context.is_valid.return_value = False
    mock_context.error_messages = ["Error: Critical validation failed.", "Warning: A minor issue."]
    # Ensure warning_messages is also available if the handler iterates it (though it shouldn't for critical errors)
    mock_context.warning_messages = ["Warning: A minor issue."]
    return mock_context


class TestArchiveStoryHandler:

    @mock.patch(CLICK_STYLE_PATH, side_effect=lambda text, **kwargs: text) # Pass through style
    @mock.patch(CLICK_ECHO_PATH)
    @mock.patch(ORCHESTRATOR_PATH)
    @mock.patch(ARCHIVE_STORY_CONTEXT_PATH)
    @mock.patch(LOGGER_INFO_PATH)
    def test_archive_story_handler_success(
        self, mock_logger_info, mock_Context, mock_orchestrator, mock_echo, mock_style, mock_archive_story_context_valid
    ):
        mock_Context.return_value = mock_archive_story_context_valid
        mock_orchestrator.return_value = {
            "title": "Test Story",
            "story_id": "test001",
            "chapters_processed": 5,
            "epub_files": ["/mock/workspace/ebooks/test001/Test_Story.epub"],
            "workspace_root": "/mock/workspace",
        }

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None, # Will be handled by context
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None,
            epub_contents=None
        )

        mock_Context.assert_called_once()
        mock_archive_story_context_valid.is_valid.assert_called_once()
        mock_archive_story_context_valid.get_orchestrator_kwargs.assert_called_once()
        mock_orchestrator.assert_called_once()

        # Check some key echo calls
        # Need to be careful with how many times echo is called due to progress display
        # For now, check for the success message and some summary lines
        echo_calls = [call_args[0][0] for call_args in mock_echo.call_args_list]
        assert "Received story URL: http://example.com/story" in echo_calls
        assert "Workspace directory: /mock/workspace" in echo_calls
        assert "Using sentence removal file: /mock/sentence_removal.json" in echo_calls
        assert "✓ Archival process completed successfully!" in echo_calls
        assert "  Title: Test Story" in echo_calls
        assert "  Story ID: test001" in echo_calls
        assert "  Generated EPUB file(s):" in echo_calls
        assert "    - /mock/workspace/ebooks/test001/Test_Story.epub" in echo_calls

        # Check logger calls
        mock_logger_info.assert_any_call("CLI handler initiated archival for http://example.com/story to workspace /mock/workspace")
        mock_logger_info.assert_any_call(
            "Successfully completed archival for 'Test Story' (ID: test001). "
            "Processed 5 chapters. EPUBs: /mock/workspace/ebooks/test001/Test_Story.epub. "
            "Workspace: /mock/workspace"
        )


    @mock.patch(CLICK_STYLE_PATH, side_effect=lambda text, **kwargs: text)
    @mock.patch(CLICK_ECHO_PATH)
    @mock.patch(ORCHESTRATOR_PATH)
    @mock.patch(ARCHIVE_STORY_CONTEXT_PATH)
    @mock.patch(LOGGER_ERROR_PATH) # For context validation failure
    def test_archive_story_handler_context_invalid(
        self, mock_logger_error, mock_Context, mock_orchestrator, mock_echo, mock_style, mock_archive_story_context_invalid
    ):
        mock_Context.return_value = mock_archive_story_context_invalid

        archive_story_handler(
            story_url="http://invalid.url",
            output_dir=None,
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None,
            epub_contents=None
        )

        mock_Context.assert_called_once()
        mock_archive_story_context_invalid.is_valid.assert_called_once()
        # Orchestrator should not be called if context is invalid
        mock_orchestrator.assert_not_called()

        # Check that error messages from context are echoed
        echo_calls = [call_args[0][0] for call_args in mock_echo.call_args_list]
        # The handler logic prints all messages from context.error_messages (which includes warnings) first,
        # then re-prints critical "Error:" messages if context.is_valid() is false.
        assert "Error: Critical validation failed." in echo_calls
        assert "Warning: A minor issue." in echo_calls # This IS expected due to the first loop in the handler

        mock_logger_error.assert_called_once_with(
            "ArchiveStoryContext validation failed. Errors: ['Error: Critical validation failed.', 'Warning: A minor issue.']"
        )

    @mock.patch(CLICK_STYLE_PATH, side_effect=lambda text, **kwargs: text)
    @mock.patch(CLICK_ECHO_PATH)
    @mock.patch(ORCHESTRATOR_PATH)
    @mock.patch(ARCHIVE_STORY_CONTEXT_PATH)
    @mock.patch(LOGGER_WARNING_PATH) # For orchestrator returning None
    def test_archive_story_handler_orchestrator_returns_none(
        self, mock_logger_warning, mock_Context, mock_orchestrator, mock_echo, mock_style, mock_archive_story_context_valid
    ):
        mock_Context.return_value = mock_archive_story_context_valid
        mock_orchestrator.return_value = None # Simulate orchestrator handling error and returning None

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None,
            epub_contents=None
        )

        mock_orchestrator.assert_called_once()
        # Ensure no success message is printed
        echo_calls = [call_args[0][0] for call_args in mock_echo.call_args_list]
        assert "✓ Archival process completed successfully!" not in echo_calls

        mock_logger_warning.assert_called_once_with(
            "Archival process for http://example.com/story concluded without a summary. Check logs for errors reported by callbacks."
        )


    @mock.patch(CLICK_ECHO_PATH)
    @mock.patch(ORCHESTRATOR_PATH)
    @mock.patch(ARCHIVE_STORY_CONTEXT_PATH)
    @mock.patch(LOGGER_ERROR_PATH) # For unexpected error
    def test_archive_story_handler_unexpected_exception(
        self, mock_logger_error, mock_Context, mock_orchestrator, mock_echo, mock_archive_story_context_valid
    ):
        mock_Context.return_value = mock_archive_story_context_valid
        mock_orchestrator.side_effect = Exception("Unexpected boom!")

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None,
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            cli_sentence_removal_file=None,
            no_sentence_removal=False,
            chapters_per_volume=None,
            epub_contents=None
        )

        mock_orchestrator.assert_called_once()

        # Check for error message in echo
        echo_calls = [call_args[0][0] for call_args in mock_echo.call_args_list]
        # The exact message might depend on click.style, but the core error should be there
        assert any("An unexpected error occurred in the CLI handler: Unexpected boom!" in call for call in echo_calls)

        mock_logger_error.assert_called_once_with(
            "CLI handler caught an unexpected error during archival for http://example.com/story: Unexpected boom!",
            exc_info=True
        )

    # Test for display_progress callback
    @mock.patch(CLICK_ECHO_PATH)
    @mock.patch(ORCHESTRATOR_PATH, new_callable=mock.MagicMock) # Use MagicMock to capture callback
    @mock.patch(ARCHIVE_STORY_CONTEXT_PATH)
    def test_archive_story_handler_display_progress_callback(
        self, mock_Context, mock_orchestrator_magic, mock_echo, mock_archive_story_context_valid
    ):
        mock_Context.return_value = mock_archive_story_context_valid
        mock_orchestrator_magic.return_value = {"title": "Test", "story_id": "t1", "chapters_processed": 1, "epub_files": [], "workspace_root": "/"}

        archive_story_handler(
            story_url="http://example.com/story",
            output_dir=None, ebook_title_override=None, keep_temp_files=False, force_reprocessing=False,
            cli_sentence_removal_file=None, no_sentence_removal=False, chapters_per_volume=None, epub_contents=None
        )

        # Get the display_progress callback passed to the orchestrator
        # The callback is the 'progress_callback' keyword argument
        passed_kwargs = mock_orchestrator_magic.call_args.kwargs
        assert 'progress_callback' in passed_kwargs
        display_progress_callback = passed_kwargs['progress_callback']

        # Test the callback with a string message
        display_progress_callback("Simple string message")
        mock_echo.assert_any_call("Simple string message")

        # Test with a dictionary message (processing chapter)
        display_progress_callback({
            "status": "info",
            "message": "Processing chapter Test Chapter",
            "current_chapter_num": 1,
            "total_chapters": 10
        })
        mock_echo.assert_any_call("[INFO] Processing chapter Test Chapter")

        # Test with a dictionary message (metadata)
        display_progress_callback({"status": "success", "message": "Successfully fetched metadata for Story X"})
        mock_echo.assert_any_call("[SUCCESS] Successfully fetched metadata for Story X")

        # Test with a generic dictionary message
        display_progress_callback({"status": "debug", "message": "Some other update."})
        mock_echo.assert_any_call("[DEBUG] Some other update.")

        # Test with unknown message type (should convert to string)
        display_progress_callback(12345)
        mock_echo.assert_any_call("12345")

# TODO: Add test classes for cloud_backup_handler, migration_handler, generate_report_handler, handle_restore_from_epubs
# For cloud_backup_handler:
# - Mock CloudBackupContext
# - Mock sync_service methods (e.g., create_folder_if_not_exists, upload_file, get_file_metadata, is_remote_older)
# - Mock progress_manager functions (load_progress, get_progress_filepath, update_cloud_backup_status, save_progress, get_epub_file_details)
# - Mock os.path.exists
# - Mock generate_report_main_func

# For migration_handler:
# - Mock MigrationContext
# - Mock os.path.isdir, os.path.exists, shutil.move
# - Mock progress_manager functions (load_progress, save_progress, get_progress_filepath)

# For generate_report_handler:
# - Mock generate_report_main_func from webnovel_archiver.generate_report

# For handle_restore_from_epubs:
# - Mock ConfigManager, PathManager (or their outputs)
# - Mock os.listdir, os.path.isdir, os.path.isfile, os.makedirs
# - Mock progress_manager (load_progress, get_progress_filepath)
# - Mock zipfile.ZipFile
