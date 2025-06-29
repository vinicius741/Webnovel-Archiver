import os
import click # For feedback and potentially type hinting
import datetime # For timestamps
# import json # No longer needed directly for loading/saving progress in handler
import shutil # Added for migration_handler
import re # Added for migration_handler
from typing import Optional, List, Dict, Any, Union # Added Union

# Import existing components
from webnovel_archiver.core.orchestrator import archive_story as call_orchestrator_archive_story
from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
# EBOOKS_DIR and ARCHIVAL_STATUS_DIR are now in PathManager
# from webnovel_archiver.core.storage.progress_manager import EBOOKS_DIR as WORKSPACE_EBOOKS_DIR, ARCHIVAL_STATUS_DIR as WORKSPACE_ARCHIVAL_STATUS_DIR
# Using 'as' to keep the constant names the same as they were used throughout the handler code.
from webnovel_archiver.utils.logger import get_logger

# Import new cloud sync components
from webnovel_archiver.core.cloud_sync import GDriveSync, BaseSyncService # Assuming BaseSyncService is still relevant for type hinting
# Import progress_manager functionally
import webnovel_archiver.core.storage.progress_manager as pm

# Import for generate_report_handler
from webnovel_archiver.generate_report import main as generate_report_main_func
import zipfile # For EPUB extraction
import json # For loading progress.json (though pm.load_progress might abstract this)

# Import necessary constants and functions from progress_manager
from webnovel_archiver.core.storage.progress_manager import (
    # ARCHIVAL_STATUS_DIR, # Moved to PathManager
    # EBOOKS_DIR, # Moved to PathManager
    load_progress, # Already available via pm alias, but explicit import can be clear
    get_progress_filepath # Already available via pm alias
)
# ConfigManager and DEFAULT_WORKSPACE_PATH are already imported
# click and get_logger are already imported above.

# Import PathManager
from webnovel_archiver.core.path_manager import PathManager

# Import the new context classes
from .contexts import ArchiveStoryContext, CloudBackupContext, MigrationContext

logger = get_logger(__name__)

# Existing archive_story_handler (ensure it's here or imported if in a different structure)
# This handler does not use ProgressManager directly in the provided snippet, so it might not need changes
# unless it also starts using the functional progress_manager. For now, keeping it as is.
def archive_story_handler(
    story_url: str,
    output_dir: Optional[str],
    ebook_title_override: Optional[str],
    keep_temp_files: bool,
    force_reprocessing: bool,
    cli_sentence_removal_file: Optional[str], # Renamed from sentence_removal_file
    no_sentence_removal: bool,
    chapters_per_volume: Optional[int],
    epub_contents: Optional[str] # Added new parameter
):
    # display_progress callback remains in the handler as it's UI related
    def display_progress(message: Union[str, Dict[str, Any]]) -> None:
        if isinstance(message, str):
            click.echo(message)
        elif isinstance(message, dict):
            status = message.get("status", "info")
            msg = message.get("message", "No message content.")
            if "Processing chapter" in msg and "current_chapter_num" in message and "total_chapters" in message:
                formatted_message = f"[{status.upper()}] {msg}"
            elif "Successfully fetched metadata" in msg:
                formatted_message = f"[{status.upper()}] {msg}"
            elif "Found" in msg and "chapters" in msg:
                formatted_message = f"[{status.upper()}] {msg}"
            else:
                formatted_message = f"[{status.upper()}] {msg}"
            click.echo(formatted_message)
        else:
            click.echo(str(message))

    # 1. Instantiate Context
    context = ArchiveStoryContext(
        story_url=story_url,
        output_dir=output_dir,
        ebook_title_override=ebook_title_override,
        keep_temp_files=keep_temp_files,
        force_reprocessing=force_reprocessing,
        cli_sentence_removal_file=cli_sentence_removal_file,
        no_sentence_removal=no_sentence_removal,
        chapters_per_volume=chapters_per_volume,
        epub_contents=epub_contents
    )

    # Report any initial context setup warnings (e.g., file not found, using defaults)
    for msg in context.error_messages: # error_messages now also includes warnings
        click.echo(click.style(msg, fg="yellow"), err=True) # Print warnings to stderr

    if not context.is_valid():
        # is_valid() should populate error_messages for critical errors
        for msg in context.error_messages: # Re-iterate if new messages were added by is_valid
            if "Error:" in msg: # Only print critical errors here
                 click.echo(click.style(msg, fg="red"), err=True)
        logger.error(f"ArchiveStoryContext validation failed. Errors: {context.error_messages}")
        return # Exit if context is not valid

    click.echo(f"Received story URL: {context.story_url}")
    click.echo(f"Workspace directory: {context.workspace_root}")
    if context.sentence_removal_file:
        click.echo(f"Using sentence removal file: {context.sentence_removal_file}")
    elif context.no_sentence_removal:
        click.echo("Sentence removal explicitly disabled.")
    else:
        click.echo("No sentence removal file specified or found; proceeding without it.")

    logger.info(f"CLI handler initiated archival for {context.story_url} to workspace {context.workspace_root}")

    try:
        # 2. Call Orchestrator with prepared context
        orchestrator_kwargs = context.get_orchestrator_kwargs()
        summary = call_orchestrator_archive_story(
            **orchestrator_kwargs,
            progress_callback=display_progress # Add callback separately
        )

        # 3. Report results
        if summary:
            click.echo(click.style("✓ Archival process completed successfully!", fg="green"))
            click.echo(f"  Title: {summary['title']}")
            click.echo(f"  Story ID: {summary['story_id']}")
            click.echo(f"  Chapters processed in this run: {summary['chapters_processed']}")
            if summary['epub_files']:
                click.echo("  Generated EPUB file(s):")
                for epub_file_path in summary['epub_files']:
                    click.echo(f"    - {epub_file_path}")
            else:
                click.echo("  No EPUB files were generated in this run.")
            click.echo(f"  Workspace: {summary['workspace_root']}")
            logger.info(
                f"Successfully completed archival for '{summary['title']}' (ID: {summary['story_id']}). "
                f"Processed {summary['chapters_processed']} chapters. "
                f"EPUBs: {', '.join(summary['epub_files']) if summary['epub_files'] else 'None'}. "
                f"Workspace: {summary['workspace_root']}"
            )
        else:
            # Orchestrator returned None, indicating an issue was already handled by callback and logged.
            # We can choose to print a more generic failure message here or rely on callbacks.
            # For now, let's assume callbacks were sufficient.
            logger.warning(f"Archival process for {story_url} concluded without a summary. Check logs for errors reported by callbacks.")
            # Optionally, uncomment below if a generic CLI message is desired when orchestrator returns None
            # click.echo(click.style("Archival process for {story_url} finished, but may not have been fully successful. Please check logs.", fg="yellow"), err=True)


    except Exception as e:
        click.echo(f"An unexpected error occurred in the CLI handler: {e}", err=True)
        logger.error(f"CLI handler caught an unexpected error during archival for {story_url}: {e}", exc_info=True)


# New cloud_backup_handler function - REFACTORED
def cloud_backup_handler(
    story_id: Optional[str],
    cloud_service_name: str,
    force_full_upload: bool,
    gdrive_credentials_path: str,
    gdrive_token_path: str
):
    """Handles the logic for the 'cloud-backup' CLI command."""
    click.echo(f"Cloud backup initiated. Story ID: {story_id if story_id else 'All stories'}. Service: {cloud_service_name}.")

    context = CloudBackupContext(
        story_id_option=story_id,
        cloud_service_name=cloud_service_name,
        force_full_upload=force_full_upload,
        gdrive_credentials_path=gdrive_credentials_path,
        gdrive_token_path=gdrive_token_path
    )

    for msg in context.warning_messages:
        click.echo(click.style(msg, fg="yellow"), err=True)

    if not context.is_valid():
        for msg in context.error_messages:
            click.echo(click.style(msg, fg="red"), err=True)
        logger.error(f"CloudBackupContext validation failed. Errors: {context.error_messages}")
        return

    sync_service = context.sync_service
    workspace_root = context.workspace_root
    story_index = context.story_index
    cloud_base_folder_id = context.cloud_base_folder_id
    base_backup_folder_name = context.base_backup_folder_name

    # Automatically generate the report before backup
    click.echo("Generating latest report before backup...")
    try:
        generate_report_main_func()
        click.echo("Report generation complete.")
    except Exception as e:
        click.echo(click.style(f"Warning: Report generation failed: {e}. Continuing with backup.", fg="yellow"), err=True)
        logger.warning(f"Report generation failed before backup: {e}", exc_info=True)

    stories_to_process = story_index.items()
    if story_id:
        if story_id not in story_index:
            click.echo(click.style(f"Error: Story ID '{story_id}' not found in the index.", fg="red"), err=True)
            return
        stories_to_process = [(story_id, story_index[story_id])]

    if not stories_to_process:
        click.echo("No stories found to back up.")
    else:
        click.echo(f"Found {len(stories_to_process)} stories to potentially back up.")

    processed_stories_count = 0
    for permanent_id, story_folder_name in stories_to_process:
        click.echo(f"Processing story: {story_folder_name} (ID: {permanent_id})")

        progress_file_path = pm.get_progress_filepath(story_folder_name, workspace_root)

        if not os.path.exists(progress_file_path):
            click.echo(f"Warning: Progress file not found for story {story_folder_name} at {progress_file_path}. Skipping.", err=True)
            logger.warning(f"Progress file not found for story {story_folder_name}, skipping backup.")
            continue

        progress_data = pm.load_progress(story_folder_name, workspace_root)
        if not progress_data:
            click.echo(f"Error: Failed to load progress data for story {story_folder_name}. Skipping.", err=True)
            continue

        story_requires_backup = False
        last_archived_ts_str = progress_data.get("last_archived_timestamp")
        cloud_backup_status = pm.get_cloud_backup_status(progress_data)
        last_successful_backup_ts_str = cloud_backup_status.get("last_successful_backup_timestamp")

        if context.force_full_upload:
            story_requires_backup = True
        elif not last_successful_backup_ts_str:
            story_requires_backup = True
        elif last_archived_ts_str and last_archived_ts_str > last_successful_backup_ts_str:
            story_requires_backup = True

        if not story_requires_backup:
            click.echo(f"Skipping story {story_folder_name}: No new changes to back up.")
            continue

        story_cloud_folder_id: Optional[str] = None
        try:
            story_cloud_folder_id = sync_service.create_folder_if_not_exists(permanent_id, parent_folder_id=cloud_base_folder_id)
            if not story_cloud_folder_id:
                click.echo(click.style(f"Error: Failed to create or retrieve cloud folder for story '{permanent_id}'. Skipping story.", fg="red"), err=True)
                continue
            click.echo(f"Ensured cloud folder structure: '{base_backup_folder_name}/{permanent_id}'")
        except ConnectionError as e:
            click.echo(f"Error creating/verifying cloud folder for story {permanent_id}: {e}. Skipping story.", err=True)
            continue

        files_to_upload_info: List[Dict[str, str]] = []
        files_to_upload_info.append({'local_path': progress_file_path, 'name': "progress_status.json"})
        epub_file_entries = pm.get_epub_file_details(progress_data, story_folder_name, workspace_root)

        for epub_entry in epub_file_entries:
            files_to_upload_info.append({'local_path': epub_entry['path'], 'name': epub_entry['name']})

        backup_files_results: List[Dict[str, Any]] = []
        for file_info in files_to_upload_info:
            try:
                uploaded_file_meta = sync_service.upload_file(file_info['local_path'], story_cloud_folder_id, remote_file_name=file_info['name'])
                backup_files_results.append({
                    'local_path': file_info['local_path'],
                    'cloud_file_name': uploaded_file_meta.get('name'),
                    'cloud_file_id': uploaded_file_meta.get('id'),
                    'last_backed_up_timestamp': uploaded_file_meta.get('modifiedTime'),
                    'status': 'uploaded'
                })
            except Exception as e:
                backup_files_results.append({ 'local_path': file_info['local_path'], 'cloud_file_name': file_info['name'], 'status': 'failed', 'error': str(e) })

        if backup_files_results:
            pm.update_cloud_backup_status(progress_data, {
                'last_backup_attempt_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'last_successful_backup_timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'service': context.cloud_service_name.lower(),
                'base_cloud_folder_name': base_backup_folder_name,
                'story_cloud_folder_name': permanent_id,
                'cloud_base_folder_id': cloud_base_folder_id,
                'story_cloud_folder_id': story_cloud_folder_id,
                'backed_up_files': backup_files_results
            })
            pm.save_progress(story_folder_name, progress_data, workspace_root)

        processed_stories_count += 1

    if processed_stories_count > 0:
        click.echo(f"Cloud backup process completed for {processed_stories_count} story/stories.")

    report_path = os.path.join(workspace_root, "reports", "archive_report.html")
    if os.path.exists(report_path):
        click.echo("HTML report found. Attempting to upload...")
        if cloud_base_folder_id and sync_service:
            try:
                sync_service.upload_file(report_path, cloud_base_folder_id, "archive_report.html")
                click.echo(click.style("✓ Successfully uploaded HTML report", fg="green"))
            except Exception as e:
                click.echo(click.style(f"Error uploading HTML report: {e}", fg="red"), err=True)


# Migration Handler
# Note: logger is already defined at the top of this file.
# from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH # Already imported
# from webnovel_archiver.core.storage.progress_manager import ARCHIVAL_STATUS_DIR, EBOOKS_DIR # Already imported as WORKSPACE_ARCHIVAL_STATUS_DIR etc.
# from webnovel_archiver.utils.logger import get_logger # Already imported and logger instance created
# import click # Already imported
# from typing import Optional, List # Already imported

def migration_handler(
    story_id: Optional[str],
    migration_type: str
):
    """Handles the logic for the 'migrate' CLI command."""
    click.echo(f"Migration process initiated. Type: {migration_type}, Story ID: {story_id if story_id else 'All stories'}")

    context = MigrationContext(
        story_id_option=story_id,
        migration_type=migration_type
    )

    # Display warnings from context setup (e.g., specific story ID format mismatch if not critical error)
    for msg in context.warning_messages:
        click.echo(click.style(msg, fg="yellow"), err=True)

    if not context.is_valid():
        for msg in context.error_messages: # These are critical errors
            click.echo(click.style(msg, fg="red"), err=True)
        logger.error(f"MigrationContext validation failed. Errors: {context.error_messages}")
        return

    legacy_story_ids_to_process = context.legacy_story_ids_to_process
    workspace_root = context.workspace_root # For progress_manager calls

    if not legacy_story_ids_to_process:
        # Context would have added a warning if no stories found via scan.
        # If a specific story_id was given and it was invalid (leading to empty list),
        # context.is_valid() or warning_messages should have covered it.
        if not context.story_id_option : # General scan found nothing
             click.echo("No legacy stories found matching the criteria for migration.")
        # If context.story_id_option was set, messages about it not being found or invalid format were already shown.
        return

    if context.story_id_option: # Specific story ID was provided and found
        click.echo(f"Preparing to migrate specified story ID: {context.story_id_option}")
    else: # Scan mode
        click.echo(f"Found {len(legacy_story_ids_to_process)} potential legacy stories to process: {', '.join(legacy_story_ids_to_process)}")


    migrated_count = 0
    for legacy_id in legacy_story_ids_to_process:
        click.echo(f"Processing legacy story ID: {legacy_id}")

        # Double check it's not already in the new format (e.g. "royalroad-12345")
        # This check is simple and can remain, or be part of context's _prepare if desired.
        if legacy_id.startswith(f"{context.migration_type.split('-')[0]}-"): # e.g. "royalroad-"
            click.echo(f"Skipping '{legacy_id}': Already appears to be in the new format for this migration type.")
            logger.info(f"Skipping migration for '{legacy_id}' as it seems to be in the new format.")
            continue

        new_story_id = context.get_new_story_id(legacy_id)
        if not new_story_id:
            # context.get_new_story_id would log and add warning if extraction failed
            click.echo(f"Warning: Could not determine new story ID for '{legacy_id}'. Skipping.", err=True)
            continue # Skip this legacy_id

        click.echo(f"  Attempting to migrate '{legacy_id}' to '{new_story_id}'...")

        dirs_to_migrate = context.get_paths_to_migrate(legacy_id, new_story_id)
        all_renames_successful_for_story = True

        for old_dir_path, new_dir_path in dirs_to_migrate:
            if os.path.isdir(old_dir_path):
                if os.path.exists(new_dir_path):
                    click.echo(f"  Warning: Target directory '{new_dir_path}' already exists. Skipping rename for this path. Manual check may be required.", err=True)
                    logger.warning(f"Target directory '{new_dir_path}' already exists for legacy ID '{legacy_id}'. Skipping rename of '{old_dir_path}'.")
                    continue
                try:
                    shutil.move(old_dir_path, new_dir_path)
                    click.echo(f"  Successfully renamed '{old_dir_path}' to '{new_dir_path}'.")
                    logger.info(f"Successfully renamed directory from '{old_dir_path}' to '{new_dir_path}' for story '{legacy_id}'.")
                except Exception as e:
                    click.echo(f"  Error renaming directory '{old_dir_path}' to '{new_dir_path}': {e}", err=True)
                    logger.error(f"Error renaming directory '{old_dir_path}' to '{new_dir_path}': {e}", exc_info=True)
                    all_renames_successful_for_story = False
            elif os.path.exists(old_dir_path):
                click.echo(f"  Warning: Expected a directory but found a file at '{old_dir_path}'. Skipping.", err=True)
                logger.warning(f"Expected directory, found file at '{old_dir_path}' for story '{legacy_id}'.")

        json_update_ok = False
        if all_renames_successful_for_story:
            # workspace_root from context
            progress_json_path_in_new_dir = pm.get_progress_filepath(new_story_id, workspace_root)

            if os.path.exists(progress_json_path_in_new_dir):
                try:
                    # workspace_root from context
                    progress_data = pm.load_progress(new_story_id, workspace_root)
                    if not progress_data: # Defensive check
                        click.echo(f"  Error: Failed to load progress data from '{progress_json_path_in_new_dir}'. Cannot update story_id.", err=True)
                        logger.error(f"Failed to load progress data from {progress_json_path_in_new_dir} for new ID {new_story_id}.")
                    elif progress_data.get('story_id') == new_story_id:
                        click.echo(f"  INFO: Story ID in '{progress_json_path_in_new_dir}' is already '{new_story_id}'. No update needed.")
                        logger.info(f"Story ID in progress file {progress_json_path_in_new_dir} is already correct.")
                        json_update_ok = True
                    else:
                        old_json_story_id = progress_data.get('story_id')
                        progress_data['story_id'] = new_story_id

                        # workspace_root from context
                        pm.save_progress(new_story_id, progress_data, workspace_root)
                        click.echo(f"  Successfully updated story_id from '{old_json_story_id}' to '{new_story_id}' in '{progress_json_path_in_new_dir}'.")
                        logger.info(f"Updated story_id in {progress_json_path_in_new_dir} from '{old_json_story_id}' to '{new_story_id}'.")
                        json_update_ok = True
                except Exception as e:
                    click.echo(f"  Error updating story_id in '{progress_json_path_in_new_dir}': {e}", err=True)
                    logger.error(f"Failed to update story_id in {progress_json_path_in_new_dir} for new ID {new_story_id}: {e}", exc_info=True)
                    click.echo(f"  WARNING: Directories for {legacy_id} renamed to {new_story_id}, but failed to update internal story_id in progress file. Manual correction needed.", err=True)
            else:
                click.echo(f"  Warning: Progress file '{progress_json_path_in_new_dir}' not found after directory rename. Cannot update story_id.", err=True)
                logger.warning(f"Progress file {progress_json_path_in_new_dir} not found for new story ID {new_story_id} after rename. Cannot update internal story_id.")

        if all_renames_successful_for_story and json_update_ok:
            migrated_count += 1
            logger.info(f"Successfully migrated '{legacy_id}' to '{new_story_id}' (directories and JSON).")
        else:
            click.echo(f"  Migration for '{legacy_id}' completed with issues or was skipped. Directory rename status: {all_renames_successful_for_story}, JSON update status: {json_update_ok}. Manual review may be recommended.", err=True)
            logger.error(f"Migration for '{legacy_id}' to '{new_story_id}' failed or was incomplete. Dirs renamed: {all_renames_successful_for_story}, JSON updated: {json_update_ok}.")

    if migrated_count > 0:
        click.echo(f"\nSuccessfully completed full migration for {migrated_count} story/stories.")
    elif not legacy_story_ids_to_process and not context.story_id_option : # Scan found nothing
        # Message already printed by "No legacy stories found..."
        pass
    elif context.story_id_option and not migrated_count: # Specific story ID given, but it wasn't migrated (e.g. invalid format, not found, or failed)
         click.echo(f"Migration for story ID '{context.story_id_option}' was not completed. Check previous messages for details (e.g., if it was invalid, not found, or failed during processing).")
    elif not migrated_count and legacy_story_ids_to_process : # Scan found stories, but none were successfully migrated
        click.echo("Migration process finished. No stories were fully migrated in this run (check logs for individual story issues).")
    # Implicit: if legacy_story_ids_to_process was empty AND story_id_option was None, initial message handles it.

def generate_report_handler():
    """Handles the logic for the 'generate-report' CLI command."""
    logger.info("generate_report_handler invoked.")
    click.echo("Starting HTML report generation...")
    try:
        # Call the main function from the generate_report script
        generate_report_main_func()
        # generate_report_main_func is expected to print the success message and path to the report.
        # If it doesn't, we might need to adjust it or capture output.
        # For now, assume it prints "HTML report generated: <path>" on success.
        logger.info("generate_report_main_func completed successfully.")
        # click.echo(click.style("✓ HTML report generation complete!", fg="green"))
        # The line above is commented out because generate_report_main_func already prints the final path.
    except Exception as e:
        logger.error(f"Error during report generation: {e}", exc_info=True)
        click.echo(click.style(f"Error generating report: {e}", fg="red"), err=True)
        click.echo("Check logs for more details.")

def handle_restore_from_epubs():
    """
    Restores processed chapter content from existing EPUB files into the
    workspace/processed_content/<story_id>/ directory.
    It uses progress.json to map EPUB chapters to their correct filenames.
    """
    logger_restore = get_logger(__name__ + ".restore_from_epubs") # More specific logger
    logger_restore.info("Starting restore from EPUBs process...")
    click.echo("Starting restore from EPUBs process...")

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
        logger_restore.info(f"Using workspace: {workspace_root}")
    except Exception as e:
        logger_restore.error(f"Failed to initialize ConfigManager or get workspace path: {e}", exc_info=True)
        click.echo(click.style(f"Error: Could not determine workspace path. {e}", fg="red"), err=True)
        workspace_root = DEFAULT_WORKSPACE_PATH
        logger_restore.warning(f"Falling back to default workspace path: {workspace_root}")
        click.echo(click.style(f"Warning: Using default workspace path: {workspace_root}", fg="yellow"), err=True)

    archival_status_base_dir = os.path.join(workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME)
    ebooks_base_dir = os.path.join(workspace_root, PathManager.EBOOKS_DIR_NAME)
    processed_content_base_dir = os.path.join(workspace_root, PathManager.PROCESSED_CONTENT_DIR_NAME)

    logger_restore.info(f"Archival status directory: {archival_status_base_dir}")
    logger_restore.info(f"Ebooks directory: {ebooks_base_dir}")
    logger_restore.info(f"Processed content directory: {processed_content_base_dir}")

    if not os.path.isdir(archival_status_base_dir):
        logger_restore.error(f"Archival status directory not found: {archival_status_base_dir}. Cannot proceed.")
        click.echo(click.style(f"Error: Archival status directory not found: {archival_status_base_dir}", fg="red"), err=True)
        return

    story_ids_found = [
        item for item in os.listdir(archival_status_base_dir)
        if os.path.isdir(os.path.join(archival_status_base_dir, item))
    ]

    if not story_ids_found:
        logger_restore.info("No story IDs found in the archival status directory.")
        click.echo("No stories found to process.")
        return

    logger_restore.info(f"Found {len(story_ids_found)} potential story IDs: {story_ids_found}")
    click.echo(f"Found {len(story_ids_found)} potential stories. Scanning for EPUBs and progress files...")

    overall_stories_processed = 0
    overall_stories_restored_successfully = 0

    for story_id in story_ids_found:
        logger_restore.info(f"Processing story ID: {story_id}")
        click.echo(f"\nProcessing story: {story_id}")

        progress_json_path = get_progress_filepath(story_id, workspace_root)
        if not os.path.exists(progress_json_path):
            logger_restore.warning(f"Progress.json not found for story ID '{story_id}' at {progress_json_path}. Skipping.")
            click.echo(click.style(f"  Warning: Progress file not found for '{story_id}'. Skipping.", fg="yellow"))
            continue

        try:
            progress_data = load_progress(story_id, workspace_root)
            if not progress_data: # load_progress might return None on error
                logger_restore.warning(f"Failed to load progress data for story ID '{story_id}'. Skipping.")
                click.echo(click.style(f"  Warning: Could not load progress data for '{story_id}'. Skipping.", fg="yellow"))
                continue
        except Exception as e:
            logger_restore.error(f"Error loading progress.json for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  Error loading progress data for '{story_id}': {e}. Skipping.", fg="red"))
            continue

        story_title = progress_data.get('effective_title') or progress_data.get('original_title', 'Unknown Title')
        downloaded_chapters = progress_data.get('downloaded_chapters')

        if not isinstance(downloaded_chapters, list) or not downloaded_chapters:
            logger_restore.warning(f"No 'downloaded_chapters' list found or it's empty in progress.json for story ID '{story_id}'. Skipping.")
            click.echo(click.style(f"  Warning: No chapter information found in progress file for '{story_id}'. Skipping.", fg="yellow"))
            continue

        # Determine EPUB Path
        epub_path = None
        # Strategy 1: Look in story-specific ebook directory: workspace/ebooks/<story_id>/
        story_specific_ebook_dir = os.path.join(ebooks_base_dir, story_id)
        logger_restore.debug(f"Checking story-specific EPUB directory: {story_specific_ebook_dir}")
        if os.path.isdir(story_specific_ebook_dir):
            for item in os.listdir(story_specific_ebook_dir):
                if item.lower().endswith('.epub'):
                    epub_path = os.path.join(story_specific_ebook_dir, item)
                    logger_restore.info(f"Found EPUB in story-specific directory: {epub_path}")
                    click.echo(f"  Found EPUB: {epub_path}")
                    break # Use the first one found

        # Strategy 2: Look for EPUB named after story title (if Strategy 1 fails)
        if not epub_path and story_title != 'Unknown Title':
            potential_epub_name = f"{story_title}.epub"
            # Sanitize story_title for use as a filename if necessary (not done here, assuming titles are safe)
            path_strat2 = os.path.join(ebooks_base_dir, potential_epub_name)
            logger_restore.debug(f"Checking for EPUB by title: {path_strat2}")
            if os.path.isfile(path_strat2):
                epub_path = path_strat2
                logger_restore.info(f"Found EPUB by title: {epub_path}")
                click.echo(f"  Found EPUB: {epub_path}")

        if not epub_path:
            logger_restore.warning(f"EPUB file not found for story ID '{story_id}' (Title: '{story_title}'). Searched in '{story_specific_ebook_dir}' and as '{os.path.join(ebooks_base_dir, story_title + '.epub')}'. Skipping.")
            click.echo(click.style(f"  Warning: EPUB not found for '{story_id}'. Skipping.", fg="yellow"))
            continue

        # Create Destination Directory
        processed_story_dir = os.path.join(processed_content_base_dir, story_id)
        try:
            os.makedirs(processed_story_dir, exist_ok=True)
            logger_restore.info(f"Ensured processed content directory exists: {processed_story_dir}")
        except OSError as e:
            logger_restore.error(f"Failed to create destination directory '{processed_story_dir}' for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  Error: Could not create destination directory for '{story_id}': {e}. Skipping.", fg="red"))
            continue

        # Extract from EPUB
        try:
            with zipfile.ZipFile(epub_path, 'r') as epub_archive:
                all_files_in_epub = epub_archive.namelist()

                excluded_structural_files = ['nav.xhtml', 'toc.xhtml', 'cover.xhtml', 'titlepage.xhtml', 'copyright.xhtml', 'landmarks.xhtml', 'loitoc.xhtml']

                chapter_patterns = [
                    # More specific patterns first
                    (lambda f: f.lower().startswith('oebps/chapter') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/chapter*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/chapter') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/chapter*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('oebps/item') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/item*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/item') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/item*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('oebps/page') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/page*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/page') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/page*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('xhtml/') and f.lower().endswith('.xhtml') and os.path.basename(f.lower()) not in excluded_structural_files, "xhtml/*.xhtml (excluding structural)"),
                    (lambda f: f.lower().startswith('html/') and f.lower().endswith('.html') and os.path.basename(f.lower()) not in excluded_structural_files, "html/*.html (excluding structural)"),

                    # Broader patterns that are more likely to catch structural files, so exclusion is important
                    (lambda f: (f.lower().startswith('oebps/') or f.lower().startswith('ops/')) and f.lower().endswith('.xhtml') and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/*.xhtml or OPS/*.xhtml (excluding structural)"),
                    (lambda f: (f.lower().startswith('oebps/') or f.lower().startswith('ops/')) and f.lower().endswith('.html') and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/*.html or OPS/*.html (excluding structural)"),

                    # Last resort pattern with robust exclusion
                    (lambda f: not f.lower().startswith('meta-inf/') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "Non-META-INF *.xhtml/html (excluding structural, last resort)"),
                ]

                chapter_files_in_epub = []
                used_pattern_description = "None"

                for pattern_fn, pattern_desc in chapter_patterns:
                    potential_chapters = sorted([f for f in all_files_in_epub if pattern_fn(f)])
                    if potential_chapters:
                        logger_restore.info(f"Pattern '{pattern_desc}' found {len(potential_chapters)} potential chapter files for story '{story_id}'.")
                        # Basic check: if a pattern yields an unusually high number of files (e.g. more than total chapters + reasonable overhead)
                        # it might be too broad. For now, we accept the first match.
                        # A more sophisticated check could compare against num_chapters_in_progress here if desired,
                        # but that might prematurely discard a valid pattern if progress.json is off.
                        chapter_files_in_epub = potential_chapters
                        used_pattern_description = pattern_desc
                        click.echo(f"  Discovered {len(chapter_files_in_epub)} chapter files using pattern: {pattern_desc}.")
                        break

                if not chapter_files_in_epub:
                    logger_restore.warning(f"No chapter files found within EPUB '{epub_path}' after trying all patterns. Skipping story '{story_id}'.")
                    click.echo(click.style(f"  Warning: No chapter files found in '{os.path.basename(epub_path)}' after trying all patterns. Skipping.", fg="yellow"))
                    continue

                # Chapter Count Validation
                num_chapters_in_progress = len(downloaded_chapters)
                num_chapters_in_epub = len(chapter_files_in_epub)

                if num_chapters_in_progress == 0: # Already checked 'not downloaded_chapters' but defensive.
                    logger_restore.warning(f"No chapters listed in progress.json for story '{story_id}', nothing to restore.")
                    click.echo(click.style(f"  Warning: No chapters in progress file for '{story_id}'. Skipping.", fg="yellow"))
                    continue

                if num_chapters_in_progress != num_chapters_in_epub:
                    logger_restore.critical(f"Chapter count mismatch for story ID '{story_id}' (Title: '{story_title}'). Progress.json has {num_chapters_in_progress}, EPUB ('{os.path.basename(epub_path)}') has {num_chapters_in_epub} (found with pattern '{used_pattern_description}'). Skipping restoration for this story.")
                    click.echo(click.style(f"  CRITICAL: Chapter count mismatch for '{story_id}'. Progress: {num_chapters_in_progress}, EPUB: {num_chapters_in_epub} (Pattern: '{used_pattern_description}'). Skipping.", fg="red"))
                    # Log more details if count mismatches, this can help diagnose pattern issues
                    if num_chapters_in_epub > 0 : # Only log if files were actually found
                        logger_restore.debug(f"Files found by pattern '{used_pattern_description}' for '{story_id}': {chapter_files_in_epub[:10]}") # Log first 10
                    if abs(num_chapters_in_progress - num_chapters_in_epub) > 5 and num_chapters_in_epub > num_chapters_in_progress : # Arbitrary threshold for "too many files"
                        logger_restore.warning(f"Pattern '{used_pattern_description}' yielded significantly more files ({num_chapters_in_epub}) than expected ({num_chapters_in_progress}) for story '{story_id}'. This pattern might be too broad for this EPUB structure.")

                    continue

                # Restore Chapter Files
                restored_files_count = 0
                for i, chapter_info in enumerate(downloaded_chapters):
                    if not isinstance(chapter_info, dict):
                        logger_restore.warning(f"Malformed chapter_info entry at index {i} for story '{story_id}'. Skipping this chapter entry.")
                        click.echo(click.style(f"  Warning: Malformed chapter data at index {i} for '{story_id}'. Skipping entry.", fg="yellow"))
                        continue

                    target_filename = chapter_info.get('local_processed_filename')
                    if not target_filename:
                        logger_restore.warning(f"Missing 'local_processed_filename' for chapter {chapter_info.get('chapter_title', 'Unknown Title')} (index {i}) in story '{story_id}'. Skipping this chapter.")
                        click.echo(click.style(f"  Warning: Missing target filename for chapter index {i} ('{chapter_info.get('chapter_title', 'N/A')}') in '{story_id}'. Skipping.", fg="yellow"))
                        continue

                    # This assumes a direct 1-to-1 mapping by order.
                    epub_chapter_source_path = chapter_files_in_epub[i]
                    target_path = os.path.join(processed_story_dir, target_filename)

                    try:
                        chapter_content_bytes = epub_archive.read(epub_chapter_source_path)
                        with open(target_path, 'wb') as f_out:
                            f_out.write(chapter_content_bytes)
                        # logger_restore.debug(f"Restored '{target_filename}' from '{epub_chapter_source_path}'")
                        restored_files_count += 1
                    except KeyError:
                        logger_restore.error(f"File '{epub_chapter_source_path}' not found in EPUB archive for story '{story_id}', though it was listed. Skipping this chapter.", exc_info=True)
                        click.echo(click.style(f"  Error: EPUB chapter file '{epub_chapter_source_path}' gone missing for '{story_id}'. Skipping.", fg="red"))
                        # This might indicate a flaw in chapter_files_in_epub logic or a very strange EPUB.
                        # Consider if this should halt the story's restoration. For now, skip chapter.
                    except IOError as e:
                        logger_restore.error(f"IOError writing file '{target_path}' for story '{story_id}': {e}", exc_info=True)
                        click.echo(click.style(f"  Error writing file '{target_filename}' for '{story_id}': {e}. Skipping chapter.", fg="red"))
                        # If one file fails to write, we might skip the whole story or just this chapter.
                        # For now, skip chapter.

                if restored_files_count == num_chapters_in_progress and num_chapters_in_progress > 0:
                    logger_restore.info(f"Successfully restored {restored_files_count} chapter files for story ID '{story_id}' (Title: '{story_title}') to '{processed_story_dir}'.")
                    click.echo(click.style(f"  ✓ Successfully restored {restored_files_count} files for '{story_id}' ('{story_title}').", fg="green"))
                    overall_stories_restored_successfully += 1
                elif restored_files_count > 0: # Partial success
                    logger_restore.warning(f"Partially restored story ID '{story_id}': {restored_files_count}/{num_chapters_in_progress} files restored to '{processed_story_dir}'.")
                    click.echo(click.style(f"  Warning: Partially restored '{story_id}': {restored_files_count}/{num_chapters_in_progress} files.", fg="yellow"))
                else: # No files restored, even if counts matched initially but individual steps failed
                    logger_restore.error(f"No files were restored for story ID '{story_id}' despite initial checks passing. Check warnings/errors for individual chapters.")
                    click.echo(click.style(f"  Error: No files restored for '{story_id}'. Check logs.", fg="red"))


        except zipfile.BadZipFile:
            logger_restore.error(f"'{epub_path}' is not a valid EPUB (zip) file for story ID '{story_id}'. Skipping.", exc_info=True)
            click.echo(click.style(f"  Error: '{os.path.basename(epub_path)}' is not a valid EPUB file for '{story_id}'. Skipping.", fg="red"))
            continue
        except FileNotFoundError: # Should be caught by epub_path check, but defensive.
            logger_restore.error(f"EPUB file '{epub_path}' not found when trying to open for story ID '{story_id}'. Skipping.", exc_info=True)
            click.echo(click.style(f"  Error: EPUB file '{os.path.basename(epub_path)}' not found for '{story_id}'. Skipping.", fg="red"))
            continue
        except Exception as e: # Catch-all for other issues during EPUB processing for a story
            logger_restore.error(f"An unexpected error occurred processing EPUB '{epub_path}' for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  An unexpected error occurred with EPUB for '{story_id}': {e}. Skipping.", fg="red"))
            continue
        finally:
            overall_stories_processed +=1


    logger_restore.info(f"Restore from EPUBs process completed. Processed {overall_stories_processed} stories. Successfully restored {overall_stories_restored_successfully} stories fully.")
    click.echo(f"\nRestore from EPUBs process finished.")
    click.echo(f"Summary: Processed {overall_stories_processed} stories. Successfully restored content for {overall_stories_restored_successfully} stories.")
    if overall_stories_processed > 0 and overall_stories_restored_successfully < overall_stories_processed:
        click.echo(click.style("  Some stories may have been skipped or had issues. Please check logs for details.", fg="yellow"))
