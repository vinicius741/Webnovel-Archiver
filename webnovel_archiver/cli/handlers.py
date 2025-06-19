import os
import click # For feedback and potentially type hinting
import datetime # For timestamps
# import json # No longer needed directly for loading/saving progress in handler
import shutil # Added for migration_handler
import re # Added for migration_handler
from typing import Optional, List, Dict, Any, Union # Added Union

# Import existing components
from webnovel_archiver.core.orchestrator import archive_story as call_orchestrator_archive_story, PROCESSED_CONTENT_DIR
from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
from webnovel_archiver.core.storage.progress_manager import EBOOKS_DIR as WORKSPACE_EBOOKS_DIR, ARCHIVAL_STATUS_DIR as WORKSPACE_ARCHIVAL_STATUS_DIR
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
    ARCHIVAL_STATUS_DIR, # Already aliased as WORKSPACE_ARCHIVAL_STATUS_DIR, consider removing direct import if not used elsewhere
    EBOOKS_DIR, # Already aliased as WORKSPACE_EBOOKS_DIR, consider removing direct import if not used elsewhere
    load_progress, # Already available via pm alias, but explicit import can be clear
    get_progress_filepath # Already available via pm alias
)
# ConfigManager and DEFAULT_WORKSPACE_PATH are already imported
# click and get_logger are already imported above.


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
    def display_progress(message: Union[str, Dict[str, Any]]) -> None:
        if isinstance(message, str):
            click.echo(message)
        elif isinstance(message, dict):
            # Customizable formatting based on expected dictionary structure
            status = message.get("status", "info")
            msg = message.get("message", "No message content.")

            # More detailed formatting for specific messages if needed
            if "Processing chapter" in msg and "current_chapter_num" in message and "total_chapters" in message:
                # Example: "Processing chapter: Chapter Title (1/10)" is already part of msg from orchestrator
                formatted_message = f"[{status.upper()}] {msg}"
            elif "Successfully fetched metadata" in msg:
                formatted_message = f"[{status.upper()}] {msg}" # msg already contains title
            elif "Found" in msg and "chapters" in msg:
                formatted_message = f"[{status.upper()}] {msg}" # msg already contains count
            else:
                # Generic formatting for other dict messages
                formatted_message = f"[{status.upper()}] {msg}"

            # Add more specific formatting based on other keys if necessary
            # For example, if there's a progress percentage or specific data points:
            # if "progress_percent" in message:
            #    formatted_message += f" ({message['progress_percent']}%)"

            click.echo(formatted_message)
        else:
            click.echo(str(message))

    click.echo(f"Received story URL: {story_url}")
    if output_dir:
        workspace_root = output_dir
        click.echo(f"Using provided output directory: {workspace_root}")
    else:
        try:
            config_manager = ConfigManager()
            workspace_root = config_manager.get_workspace_path()
            click.echo(f"Using workspace directory from config: {workspace_root}")
        except Exception as e:
            logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
            workspace_root = DEFAULT_WORKSPACE_PATH
            click.echo(f"Warning: Using default workspace path due to error: {workspace_root}", err=True)

    # click.echo("Starting archival process...") # Removed, orchestrator callback will handle this
    logger.info(f"CLI handler initiated archival for {story_url} to workspace {workspace_root}")

    # Determine the final sentence removal file
    final_sentence_removal_file: Optional[str] = None
    config_manager_for_sr = ConfigManager() # Initialize once if needed for defaults

    if no_sentence_removal:
        logger.info("Sentence removal explicitly disabled via --no-sentence-removal flag.")
        final_sentence_removal_file = None
    elif cli_sentence_removal_file:
        if os.path.exists(cli_sentence_removal_file):
            logger.info(f"Using sentence removal file provided via CLI: {cli_sentence_removal_file}")
            final_sentence_removal_file = cli_sentence_removal_file
        else:
            logger.warning(f"Sentence removal file provided via CLI not found: {cli_sentence_removal_file}. Proceeding without sentence removal.")
            final_sentence_removal_file = None
    else:
        default_sr_file_path = config_manager_for_sr.get_default_sentence_removal_file()
        if default_sr_file_path:
            if os.path.exists(default_sr_file_path):
                logger.info(f"Using default sentence removal file from config: {default_sr_file_path}")
                final_sentence_removal_file = default_sr_file_path
            else:
                logger.warning(f"Default sentence removal file configured at '{default_sr_file_path}' not found. Proceeding without sentence removal.")
                final_sentence_removal_file = None
        else:
            logger.info("No sentence removal file provided via CLI and no default configured. Proceeding without sentence removal.")
            final_sentence_removal_file = None

    try:
        summary = call_orchestrator_archive_story(
            story_url=story_url,
            workspace_root=workspace_root,
            ebook_title_override=ebook_title_override,
            keep_temp_files=keep_temp_files,
            force_reprocessing=force_reprocessing,
            sentence_removal_file=final_sentence_removal_file, # Pass the determined file
            no_sentence_removal=no_sentence_removal, # Pass through the direct flag
            chapters_per_volume=chapters_per_volume,
            epub_contents=epub_contents, # Pass new parameter
            progress_callback=display_progress
        )

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

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
    except Exception as e:
        logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
        click.echo(f"Error: Could not determine workspace path. {e}", err=True)
        return

    archival_status_dir = os.path.join(workspace_root, WORKSPACE_ARCHIVAL_STATUS_DIR)
    ebooks_base_dir = os.path.join(workspace_root, WORKSPACE_EBOOKS_DIR) # Renamed for clarity

    if not os.path.isdir(archival_status_dir):
        click.echo(f"Error: Archival status directory not found: {archival_status_dir}", err=True)
        return
    if not os.path.isdir(ebooks_base_dir): # Check base ebooks dir
        click.echo(f"Error: Ebooks directory not found: {ebooks_base_dir}", err=True)
        return

    sync_service: Optional[BaseSyncService] = None
    if cloud_service_name.lower() == 'gdrive':
        try:
            if not os.path.exists(gdrive_credentials_path) and not os.path.exists(gdrive_token_path) :
                 click.echo(f"Warning: Google Drive credentials ('{gdrive_credentials_path}') or token ('{gdrive_token_path}') not found. Authentication may fail or require interaction.", err=True)
            sync_service = GDriveSync(credentials_path=gdrive_credentials_path, token_path=gdrive_token_path)
            click.echo("Google Drive sync service initialized.")
        except FileNotFoundError as e:
            click.echo(f"Error: GDrive credentials file '{gdrive_credentials_path}' not found. Please provide it using --credentials-file or ensure it's in the default location.", err=True)
            logger.error(f"GDrive credentials file not found: {gdrive_credentials_path}")
            return
        except ConnectionError as e:
            click.echo(f"Error: Could not connect to Google Drive: {e}", err=True)
            logger.error(f"GDrive connection error: {e}")
            return
        except Exception as e:
            click.echo(f"Error initializing Google Drive service: {e}", err=True)
            logger.error(f"GDrive initialization error: {e}", exc_info=True)
            return
    else:
        click.echo(f"Error: Cloud service '{cloud_service_name}' is not supported.", err=True)
        return

    if not sync_service:
        click.echo("Error: Sync service could not be initialized.", err=True)
        return

    story_ids_to_process: List[str] = []
    # This will store the ID of the main "Webnovel Archiver Backups" folder in the cloud.
    cloud_base_folder_id: Optional[str] = None
    base_backup_folder_name = "Webnovel Archiver Backups" # Define folder name once

    # Attempt to create the base backup folder before processing any stories.
    try:
        click.echo(f"Ensuring base cloud backup folder '{base_backup_folder_name}' exists...")
        cloud_base_folder_id = sync_service.create_folder_if_not_exists(base_backup_folder_name, parent_folder_id=None)
        if not cloud_base_folder_id:
            click.echo(click.style(f"Error: Failed to create or retrieve base cloud folder '{base_backup_folder_name}'. Cannot proceed with backup.", fg="red"), err=True)
            logger.error(f"Failed to create/retrieve base cloud folder '{base_backup_folder_name}'. Aborting cloud backup.")
            return
        click.echo(f"Base cloud folder '{base_backup_folder_name}' ensured (ID: {cloud_base_folder_id}).")
    except ConnectionError as e:
        click.echo(click.style(f"Error: Connection error while creating base cloud folder '{base_backup_folder_name}': {e}. Cannot proceed.", fg="red"), err=True)
        logger.error(f"Connection error creating base cloud folder '{base_backup_folder_name}': {e}")
        return
    except Exception as e: # Catch any other unexpected errors during base folder creation
        click.echo(click.style(f"Error: Unexpected error while creating base cloud folder '{base_backup_folder_name}': {e}. Cannot proceed.", fg="red"), err=True)
        logger.error(f"Unexpected error creating base cloud folder '{base_backup_folder_name}': {e}", exc_info=True)
        return

    if story_id:
        # Verify this story_id exists
        if not os.path.isdir(os.path.join(archival_status_dir, story_id)):
            click.echo(f"Error: No archival status found for story ID '{story_id}' in {archival_status_dir}.", err=True)
            return
        story_ids_to_process.append(story_id)
    else:
        try:
            story_ids_to_process = [d for d in os.listdir(archival_status_dir) if os.path.isdir(os.path.join(archival_status_dir, d))]
            if not story_ids_to_process:
                click.echo("No stories found in the archival status directory to back up.")
                return
            click.echo(f"Found {len(story_ids_to_process)} stories to potentially back up: {', '.join(story_ids_to_process)}")
        except OSError as e:
            click.echo(f"Error listing stories in {archival_status_dir}: {e}", err=True)
            return

    processed_stories_count = 0
    for current_story_id in story_ids_to_process:
        any_epub_uploaded_for_this_story = False # Initialize EPUB upload flag
        an_upload_occurred = False # Initialize flag for each story
        click.echo(f"Processing story: {current_story_id}")

        progress_file_path = pm.get_progress_filepath(current_story_id, workspace_root)

        if not os.path.exists(progress_file_path):
            click.echo(f"Warning: Progress file not found for story {current_story_id} at {progress_file_path}. Skipping.", err=True)
            logger.warning(f"Progress file not found for story {current_story_id}, skipping backup.")
            continue

        progress_data = pm.load_progress(current_story_id, workspace_root)
        if not progress_data:
            click.echo(f"Error: Failed to load progress data for story {current_story_id}. Skipping.", err=True)
            continue

        # Determine if this story needs backup
        story_requires_backup = False
        last_archived_ts_str = progress_data.get("last_archived_timestamp")
        cloud_backup_status = pm.get_cloud_backup_status(progress_data) # Use getter to ensure structure
        last_successful_backup_ts_str = cloud_backup_status.get("last_successful_backup_timestamp")

        if force_full_upload:
            story_requires_backup = True
            click.echo(f"Story {current_story_id}: Forced full upload.")
            logger.info(f"Story {current_story_id}: Forced full upload.")
        elif not last_successful_backup_ts_str:
            story_requires_backup = True
            click.echo(f"Story {current_story_id}: No previous successful backup found. Requires backup.")
            logger.info(f"Story {current_story_id}: No previous successful backup. Queued for backup.")
        elif last_archived_ts_str:
            try:
                # Ensure timestamps are comparable (e.g., datetime objects)
                # ISO format strings can be compared directly if they are consistently formatted (which they should be)
                if last_archived_ts_str > last_successful_backup_ts_str:
                    story_requires_backup = True
                    click.echo(f"Story {current_story_id}: Archived more recently ({last_archived_ts_str}) than last backup ({last_successful_backup_ts_str}). Requires backup.")
                    logger.info(f"Story {current_story_id}: Archived ({last_archived_ts_str}) after last backup ({last_successful_backup_ts_str}). Queued for backup.")
                else:
                    click.echo(f"Story {current_story_id}: Last archive ({last_archived_ts_str}) is not newer than last backup ({last_successful_backup_ts_str}). Skipping backup.")
                    logger.info(f"Story {current_story_id}: Last archive ({last_archived_ts_str}) not newer than last backup ({last_successful_backup_ts_str}). Skipping.")
            except TypeError as te: # Handles cases where one might be None or not string, though checks above should prevent
                logger.error(f"Story {current_story_id}: Timestamp comparison error - last_archived: {last_archived_ts_str}, last_backup: {last_successful_backup_ts_str}. Error: {te}. Assuming backup is needed.", exc_info=True)
                click.echo(f"Warning: Timestamp comparison error for story {current_story_id}. Proceeding with backup as a precaution.", err=True)
                story_requires_backup = True # Err on the side of caution
        else:
            # No last_archived_timestamp, but there was a last_successful_backup.
            # This implies it was backed up but never "archived" with the new timestamp system.
            # Or it's an old record. To be safe, or by policy, we might decide to back it up.
            # For now, let's assume if last_archived_timestamp is missing, it doesn't trigger a new backup
            # unless force_full_upload or no last_successful_backup_ts_str.
            click.echo(f"Story {current_story_id}: Has a last backup timestamp ({last_successful_backup_ts_str}) but no last_archived_timestamp. Skipping unless forced.")
            logger.info(f"Story {current_story_id}: Has last backup ({last_successful_backup_ts_str}) but no last_archived_timestamp. Skipping.")


        if not story_requires_backup:
            # We still count it as "processed" in terms of the loop, but no backup actions are taken.
            # No need to update progress file if no backup actions taken.
            processed_stories_count +=1 # Count it as looked at
            click.echo(f"Finished processing story (skipped backup): {current_story_id}\n")
            continue


        # --- Proceed with backup for the story if story_requires_backup is True ---
        click.echo(f"Story {current_story_id}: Preparing for cloud backup.")

        # cloud_base_folder_id is now created before the loop.
        if not cloud_base_folder_id:
            click.echo(click.style(f"Critical Error: Base cloud folder ID not available for story {current_story_id}. Skipping.", fg="red"), err=True)
            logger.error(f"Critical: cloud_base_folder_id is None when processing story {current_story_id}.")
            continue

        story_cloud_folder_id: Optional[str] = None
        try:
            story_cloud_folder_id = sync_service.create_folder_if_not_exists(current_story_id, parent_folder_id=cloud_base_folder_id)
            if not story_cloud_folder_id:
                click.echo(click.style(f"Error: Failed to create or retrieve cloud folder for story '{current_story_id}'. Skipping story.", fg="red"), err=True)
                logger.error(f"Failed to create/retrieve story folder for {current_story_id} under parent {cloud_base_folder_id}.")
                continue
            click.echo(f"Ensured cloud folder structure: '{base_backup_folder_name}/{current_story_id}' (Story Folder ID: {story_cloud_folder_id})")
        except ConnectionError as e:
            click.echo(f"Error creating/verifying cloud folder for story {current_story_id}: {e}. Skipping story.", err=True)
            logger.error(f"Cloud folder creation error for {current_story_id}: {e}")
            continue

        files_to_upload_info: List[Dict[str, str]] = []
        files_to_upload_info.append({'local_path': progress_file_path, 'name': "progress_status.json"})
        epub_file_entries = pm.get_epub_file_details(progress_data, current_story_id, workspace_root)

        if not epub_file_entries:
             click.echo(f"No EPUB files listed in progress status for story {current_story_id}.")

        for epub_entry in epub_file_entries:
            epub_filename = epub_entry.get('name')
            epub_local_abs_path = epub_entry.get('path')
            if not epub_filename or not epub_local_abs_path:
                logger.warning(f"Skipping EPUB entry with missing name or path in {current_story_id}: {epub_entry}")
                continue
            if not os.path.exists(epub_local_abs_path):
                click.echo(f"Warning: EPUB file {epub_local_abs_path} not found for story {current_story_id}. Skipping this EPUB.", err=True)
                logger.warning(f"EPUB file {epub_local_abs_path} not found, skipping upload for this EPUB.")
                continue
            files_to_upload_info.append({'local_path': epub_local_abs_path, 'name': epub_filename})

        backup_files_results: List[Dict[str, Any]] = []
        actual_files_uploaded_this_story = False # Track if any file (EPUB or progress.json) is actually uploaded

        for file_info_to_upload in files_to_upload_info:
            local_path = file_info_to_upload['local_path']
            upload_name = file_info_to_upload['name']
            file_should_be_uploaded_due_to_overwrite_or_missing_remote = True # Default to true

            if not force_full_upload: # If not forcing, check remote state
                try:
                    remote_metadata = sync_service.get_file_metadata(file_name=upload_name, folder_id=story_cloud_folder_id)
                    if remote_metadata and remote_metadata.get('modifiedTime'):
                        if not sync_service.is_remote_older(local_path, remote_metadata['modifiedTime']):
                            file_should_be_uploaded_due_to_overwrite_or_missing_remote = False
                            click.echo(f"Skipping '{upload_name}': Remote file is not older than local.")
                            logger.info(f"Skipping upload of {upload_name} for story {current_story_id} as remote is not older.")
                            backup_files_results.append({
                                'local_path': local_path,
                                'cloud_file_name': upload_name,
                                'cloud_file_id': remote_metadata.get('id'),
                                'last_backed_up_timestamp': remote_metadata.get('modifiedTime'), # Use remote's mod time as "last backed up"
                                'status': 'skipped_up_to_date'
                            })
                        else:
                             click.echo(f"Local file '{upload_name}' is newer. Uploading...")
                    else: # Remote file not found or no timestamp
                        click.echo(f"Remote file '{upload_name}' not found or no timestamp. Uploading...")
                except ConnectionError as e:
                    click.echo(f"Warning: Could not get remote metadata for '{upload_name}': {e}. Will attempt upload.", err=True)
                    logger.warning(f"Could not get remote metadata for {upload_name} (story {current_story_id}): {e}")
                except Exception as e: # Other errors during metadata check
                    click.echo(f"Warning: Error checking remote status for '{upload_name}': {e}. Will attempt upload.", err=True)
                    logger.warning(f"Error checking remote status for {upload_name} (story {current_story_id}): {e}", exc_info=True)

            if file_should_be_uploaded_due_to_overwrite_or_missing_remote:
                try:
                    click.echo(f"Uploading '{upload_name}' for story {current_story_id}...")
                    uploaded_file_meta = sync_service.upload_file(local_path, story_cloud_folder_id, remote_file_name=upload_name)
                    click.echo(f"Successfully uploaded '{uploaded_file_meta.get('name')}' (ID: {uploaded_file_meta.get('id')}).")
                    actual_files_uploaded_this_story = True # Mark that an upload occurred
                    backup_files_results.append({
                        'local_path': local_path,
                        'cloud_file_name': uploaded_file_meta.get('name'),
                        'cloud_file_id': uploaded_file_meta.get('id'),
                        'last_backed_up_timestamp': uploaded_file_meta.get('modifiedTime') or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'status': 'uploaded'
                    })
                    if upload_name.endswith('.epub'): # This flag was used for deciding to save progress.json
                        any_epub_uploaded_for_this_story = True # Still useful for specific logging/conditions if needed
                except FileNotFoundError:
                    click.echo(f"Error: Local file {local_path} vanished before upload. Skipping this file.", err=True)
                    logger.error(f"Local file {local_path} not found for upload (story {current_story_id}).")
                    backup_files_results.append({ 'local_path': local_path, 'cloud_file_name': upload_name, 'status': 'failed', 'error': 'Local file not found' })
                except ConnectionError as e:
                    click.echo(f"Error uploading '{upload_name}' for story {current_story_id}: {e}", err=True)
                    logger.error(f"Upload failed for {local_path} to story {current_story_id} folder: {e}")
                    backup_files_results.append({ 'local_path': local_path, 'cloud_file_name': upload_name, 'status': 'failed', 'error': str(e) })
                except Exception as e:
                    click.echo(f"An unexpected error occurred uploading '{upload_name}': {e}", err=True)
                    logger.error(f"Unexpected error uploading {local_path} for story {current_story_id}: {e}", exc_info=True)
                    backup_files_results.append({ 'local_path': local_path, 'cloud_file_name': upload_name, 'status': 'failed', 'error': str(e) })

        # Update progress_status.json for this story if any file operation (upload/skip/fail) occurred.
        # The decision to backup the story overall was made earlier. Now we record the outcome.
        if backup_files_results: # If there were any file operations attempted
            click.echo(f"Updating progress file for story {current_story_id} with backup operation results.")
            current_utc_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Determine if this specific backup attempt for the story was "successful" overall
            # Successful means all attempted files were either uploaded or skipped (already up-to-date)
            all_attempted_ops_successful_or_skipped = all(
                f.get('status') in ['uploaded', 'skipped_up_to_date'] for f in backup_files_results
            )

            # Update last_successful_backup_timestamp only if this attempt was successful overall
            # and at least one file was actually uploaded (not just skipped or all failed)
            new_last_successful_ts = last_successful_backup_ts_str # Default to existing
            if all_attempted_ops_successful_or_skipped and actual_files_uploaded_this_story :
                # If multiple files uploaded, use the latest modifiedTime from the successful uploads.
                # If only skips, or if uploaded files don't have modifiedTime, use current time.
                successful_upload_timestamps = [
                    f['last_backed_up_timestamp'] for f in backup_files_results
                    if f.get('status') == 'uploaded' and f.get('last_backed_up_timestamp')
                ]
                if successful_upload_timestamps:
                    new_last_successful_ts = max(successful_upload_timestamps)
                else: # No successful uploads with timestamps (e.g. only skips, or API error giving timestamp)
                    new_last_successful_ts = current_utc_time_iso # Fallback to current time for this successful backup operation
                click.echo(f"Story {current_story_id}: Backup attempt successful. Updating last_successful_backup_timestamp to {new_last_successful_ts}.")
                logger.info(f"Story {current_story_id}: Backup successful. New last_successful_backup_timestamp: {new_last_successful_ts}.")


            cloud_backup_update_data = {
                'last_backup_attempt_timestamp': current_utc_time_iso,
                'last_successful_backup_timestamp': new_last_successful_ts,
                'service': cloud_service_name.lower(),
                'base_cloud_folder_name': base_backup_folder_name,
                'story_cloud_folder_name': current_story_id,
                'cloud_base_folder_id': cloud_base_folder_id,
                'story_cloud_folder_id': story_cloud_folder_id,
                'backed_up_files': backup_files_results # Store results of all attempted files
            }

            try:
                pm.update_cloud_backup_status(progress_data, cloud_backup_update_data)
                pm.save_progress(current_story_id, progress_data, workspace_root)
                click.echo(f"Successfully updated and saved local progress status for story {current_story_id}.")
            except Exception as e:
                click.echo(f"Error updating/saving progress file for story {current_story_id}: {e}", err=True)
                logger.error(f"Failed to update/save progress_status.json for {current_story_id} after backup ops: {e}", exc_info=True)
        else: # No files were even attempted (e.g. no EPUBs and progress.json somehow skipped)
             click.echo(f"No file operations (upload/skip/fail) were performed for story {current_story_id}. Progress file not updated for backup status.")
             logger.info(f"No file operations for story {current_story_id}. Progress file not updated with backup status.")


        processed_stories_count +=1
        click.echo(f"Finished processing story: {current_story_id}\n")

    if processed_stories_count > 0:
        click.echo(f"Cloud backup process completed for {processed_stories_count} story/stories.")
    elif not story_ids_to_process:
        pass # No stories were found to process initially
    else:
        # This case means stories were found, but none were actually processed (e.g. all skipped due to errors or missing files)
        click.echo("Cloud backup process completed, but no stories were actually backed up.")

    # --- HTML Report Upload Logic ---
    report_path = os.path.join(workspace_root, "reports", "archive_report.html")
    logger.info(f"Checking for HTML report at: {report_path}")

    if os.path.exists(report_path):
        click.echo("HTML report found. Attempting to upload...")
        logger.info("Attempting to upload HTML report...")

        # cloud_base_folder_id should have been created at the beginning.
        # If it wasn't (e.g., initial connection error), then we can't upload the report to the specific base folder.
        if not cloud_base_folder_id:
            click.echo(click.style(f"Warning: Base cloud folder ID ('{base_backup_folder_name}') not available. Cannot upload HTML report to it. This might be due to earlier errors.", fg="yellow"), err=True)
            logger.warning(f"HTML report upload skipped: cloud_base_folder_id is not set (base folder: '{base_backup_folder_name}').")
        elif sync_service: # cloud_base_folder_id exists and sync_service is available
            try:
                logger.info(f"Uploading report '{report_path}' to cloud folder ID '{cloud_base_folder_id}'.")
                uploaded_report_meta = sync_service.upload_file(
                    local_file_path=report_path,
                    remote_folder_id=cloud_base_folder_id,
                    remote_file_name="archive_report.html"
                )
                click.echo(click.style(f"✓ Successfully uploaded HTML report: {uploaded_report_meta.get('name')}", fg="green"))
                logger.info(f"HTML report uploaded successfully: {uploaded_report_meta.get('name')} (ID: {uploaded_report_meta.get('id')})")
            except FileNotFoundError:
                # This specific check might be redundant if os.path.exists passed, but good for robustness
                click.echo(click.style(f"Error: Report file {report_path} not found at time of upload. Skipping.", fg="red"), err=True)
                logger.error(f"Report file {report_path} not found during upload attempt.")
            except ConnectionError as e:
                click.echo(click.style(f"Error uploading HTML report: {e}", fg="red"), err=True)
                logger.error(f"Connection error during HTML report upload: {e}", exc_info=True)
            except Exception as e:
                click.echo(click.style(f"An unexpected error occurred during HTML report upload: {e}", fg="red"), err=True)
                logger.error(f"Unexpected error during HTML report upload: {e}", exc_info=True)
        # Removed 'elif sync_service:' as the logic is now: if cloud_base_folder_id is None, it's skipped.
        # If it exists, the 'try' block above is attempted.

    else:
        click.echo(f"HTML report not found at {report_path}, skipping upload.")
        logger.info(f"HTML report not found at {report_path}, skipping upload.")
    # --- End of HTML Report Upload Logic ---

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

    if migration_type.lower() != 'royalroad-legacy-id':
        click.echo(f"Error: Migration type '{migration_type}' is not supported. Currently, only 'royalroad-legacy-id' is available.", err=True)
        logger.error(f"Unsupported migration type requested: {migration_type}")
        return

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
    except Exception as e:
        logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
        click.echo(f"Error: Could not determine workspace path. {e}", err=True)
        return

    archival_status_base_dir = os.path.join(workspace_root, WORKSPACE_ARCHIVAL_STATUS_DIR)
    ebooks_base_dir = os.path.join(workspace_root, WORKSPACE_EBOOKS_DIR)
    # Define other potential directories if they are standard and need migration
    # For example:
    # raw_content_base_dir = os.path.join(workspace_root, "raw_content")
    # processed_content_base_dir = os.path.join(workspace_root, "processed_content")

    if not os.path.isdir(archival_status_base_dir):
        click.echo(f"Error: Archival status directory not found: {archival_status_base_dir}. Nothing to migrate.", err=True)
        logger.error(f"Archival status directory {archival_status_base_dir} not found.")
        return

    legacy_story_ids_to_process: List[str] = []
    if story_id:
        # Check if the provided story_id looks like a legacy one before proceeding
        if not re.match(r"^\d+-[\w-]+$", story_id): # Simple regex: starts with digits, hyphen, then chars/hyphens
            click.echo(f"Provided story ID '{story_id}' does not match the expected legacy RoyalRoad format (e.g., '12345-some-title'). Skipping.", err=True)
            logger.warning(f"Skipping migration for explicitly provided ID '{story_id}' as it doesn't match legacy format.")
            return
        legacy_story_ids_to_process.append(story_id)
    else:
        try:
            # Scan all directories in archival_status_base_dir
            for item_name in os.listdir(archival_status_base_dir):
                item_path = os.path.join(archival_status_base_dir, item_name)
                if os.path.isdir(item_path):
                    # Check if item_name matches the legacy RoyalRoad format
                    # Regex: starts with one or more digits, followed by a hyphen,
                    # followed by one or more word characters (alphanumeric/underscore) or hyphens.
                    if re.match(r"^\d+-[\w-]+$", item_name):
                        legacy_story_ids_to_process.append(item_name)

            if not legacy_story_ids_to_process:
                click.echo("No legacy RoyalRoad stories found to migrate in the scan.")
                logger.info("No legacy RoyalRoad story IDs found matching pattern during scan.")
                return
            click.echo(f"Found {len(legacy_story_ids_to_process)} potential legacy RoyalRoad stories to process: {', '.join(legacy_story_ids_to_process)}")
        except OSError as e:
            click.echo(f"Error listing stories in {archival_status_base_dir}: {e}", err=True)
            logger.error(f"OSError while listing legacy stories in {archival_status_base_dir}: {e}")
            return

    migrated_count = 0
    for legacy_id in legacy_story_ids_to_process:
        click.echo(f"Processing legacy story ID: {legacy_id}")

        # Double check it's not already in the new format (e.g. "royalroad-12345")
        if legacy_id.startswith("royalroad-"):
            click.echo(f"Skipping '{legacy_id}': Already appears to be in the new format.")
            logger.info(f"Skipping migration for '{legacy_id}' as it seems to be in the new format.")
            continue

        numerical_id_match = re.match(r"^(\d+)-", legacy_id)
        if not numerical_id_match:
            click.echo(f"Warning: Could not extract numerical ID from '{legacy_id}'. Skipping.", err=True)
            logger.warning(f"Could not extract numerical ID from legacy ID '{legacy_id}'.")
            continue

        numerical_id = numerical_id_match.group(1)
        new_story_id = f"royalroad-{numerical_id}"

        click.echo(f"  Attempting to migrate '{legacy_id}' to '{new_story_id}'...")

        # Define paths for various directories
        # Store them as (old_path, new_path) tuples
        dirs_to_migrate = [
            (os.path.join(archival_status_base_dir, legacy_id), os.path.join(archival_status_base_dir, new_story_id)),
            (os.path.join(ebooks_base_dir, legacy_id), os.path.join(ebooks_base_dir, new_story_id)),
            # Add other dirs here if they follow the same <base_dir>/<story_id> pattern
            # (os.path.join(workspace_root, "raw_content", legacy_id), os.path.join(workspace_root, "raw_content", new_story_id)),
            # (os.path.join(workspace_root, "processed_content", legacy_id), os.path.join(workspace_root, "processed_content", new_story_id)),
        ]

        all_renames_successful_for_story = True
        for old_dir_path, new_dir_path in dirs_to_migrate:
            if os.path.isdir(old_dir_path):
                if os.path.exists(new_dir_path):
                    click.echo(f"  Warning: Target directory '{new_dir_path}' already exists. Skipping rename for this path. Manual check may be required.", err=True)
                    logger.warning(f"Target directory '{new_dir_path}' already exists for legacy ID '{legacy_id}'. Skipping rename of '{old_dir_path}'.")
                    # This specific path rename failed/skipped, but we might continue with others for the story.
                    # Depending on desired atomicity, could set all_renames_successful_for_story = False
                    continue
                try:
                    shutil.move(old_dir_path, new_dir_path)
                    click.echo(f"  Successfully renamed '{old_dir_path}' to '{new_dir_path}'.")
                    logger.info(f"Successfully renamed directory from '{old_dir_path}' to '{new_dir_path}' for story '{legacy_id}'.")
                except Exception as e:
                    click.echo(f"  Error renaming directory '{old_dir_path}' to '{new_dir_path}': {e}", err=True)
                    logger.error(f"Error renaming directory '{old_dir_path}' to '{new_dir_path}': {e}", exc_info=True)
                    all_renames_successful_for_story = False
                    # If one rename fails, we might want to stop or attempt to revert,
                    # but simple approach is to report and continue.
            elif os.path.exists(old_dir_path): # It's a file, not a directory, something is wrong.
                click.echo(f"  Warning: Expected a directory but found a file at '{old_dir_path}'. Skipping.", err=True)
                logger.warning(f"Expected directory, found file at '{old_dir_path}' for story '{legacy_id}'.")
            # else:
                # click.echo(f"  Directory '{old_dir_path}' not found, no action needed for this path.")
                # logger.debug(f"Directory '{old_dir_path}' not found for story '{legacy_id}', skipping rename for this path.")

        json_update_ok = False
        if all_renames_successful_for_story:
            progress_json_path_in_new_dir = pm.get_progress_filepath(new_story_id, workspace_root)

            if os.path.exists(progress_json_path_in_new_dir):
                try:
                    progress_data = pm.load_progress(new_story_id, workspace_root)

                    if progress_data.get('story_id') == new_story_id:
                        click.echo(f"  INFO: Story ID in '{progress_json_path_in_new_dir}' is already '{new_story_id}'. No update needed.")
                        logger.info(f"Story ID in progress file {progress_json_path_in_new_dir} is already correct.")
                        json_update_ok = True
                    else:
                        old_json_story_id = progress_data.get('story_id')
                        progress_data['story_id'] = new_story_id
                        # Future: Consider updating story_url if it contains the old ID/slug.
                        # This is complex due to various URL structures and potential for unintended changes.
                        # For now, only story_id field is updated.

                        pm.save_progress(new_story_id, progress_data, workspace_root)
                        click.echo(f"  Successfully updated story_id from '{old_json_story_id}' to '{new_story_id}' in '{progress_json_path_in_new_dir}'.")
                        logger.info(f"Updated story_id in {progress_json_path_in_new_dir} from '{old_json_story_id}' to '{new_story_id}'.")
                        json_update_ok = True
                except Exception as e:
                    click.echo(f"  Error updating story_id in '{progress_json_path_in_new_dir}': {e}", err=True)
                    logger.error(f"Failed to update story_id in {progress_json_path_in_new_dir} for new ID {new_story_id}: {e}", exc_info=True)
                    click.echo(f"  WARNING: Directories for {legacy_id} renamed to {new_story_id}, but failed to update internal story_id in progress file. Manual correction needed.", err=True)
                    json_update_ok = False # Explicitly set
            else:
                click.echo(f"  Warning: Progress file '{progress_json_path_in_new_dir}' not found after directory rename. Cannot update story_id.", err=True)
                logger.warning(f"Progress file {progress_json_path_in_new_dir} not found for new story ID {new_story_id} after rename. Cannot update internal story_id.")
                json_update_ok = False # Cannot update JSON if not found

        if all_renames_successful_for_story and json_update_ok:
            migrated_count += 1
            logger.info(f"Successfully migrated '{legacy_id}' to '{new_story_id}' (directories and JSON).")
        else:
            click.echo(f"  Migration for '{legacy_id}' completed with issues or was skipped. Directory rename status: {all_renames_successful_for_story}, JSON update status: {json_update_ok}. Manual review may be recommended.", err=True)
            logger.error(f"Migration for '{legacy_id}' to '{new_story_id}' failed or was incomplete. Dirs renamed: {all_renames_successful_for_story}, JSON updated: {json_update_ok}.")

    if migrated_count > 0:
        click.echo(f"\nSuccessfully completed full migration for {migrated_count} story/stories.")
    elif not legacy_story_ids_to_process and not story_id:
        click.echo("No legacy RoyalRoad stories requiring migration were found.")
    elif story_id and not migrated_count:
         click.echo(f"Migration for story ID '{story_id}' was not completed or it was not a legacy RoyalRoad ID. Check previous messages.")
    else:
        click.echo("Migration process finished. No stories were fully migrated.")

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

    archival_status_base_dir = os.path.join(workspace_root, ARCHIVAL_STATUS_DIR)
    ebooks_base_dir = os.path.join(workspace_root, EBOOKS_DIR)
    processed_content_base_dir = os.path.join(workspace_root, PROCESSED_CONTENT_DIR)

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
