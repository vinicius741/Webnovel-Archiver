import os
import re # Added for migration handler
import shutil # Added for migration handler
import click # For feedback and potentially type hinting
import datetime # For timestamps
# import json # No longer needed directly for loading/saving progress in handler
from typing import Optional, List, Dict, Any, Union # Added Union

# Import existing components
from webnovel_archiver.core.orchestrator import archive_story as call_orchestrator_archive_story
from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
from webnovel_archiver.core.storage.progress_manager import EBOOKS_DIR as WORKSPACE_EBOOKS_DIR, ARCHIVAL_STATUS_DIR as WORKSPACE_ARCHIVAL_STATUS_DIR
# Using 'as' to keep the constant names the same as they were used throughout the handler code.
from webnovel_archiver.utils.logger import get_logger

# Import new cloud sync components
from webnovel_archiver.core.cloud_sync import GDriveSync, BaseSyncService # Assuming BaseSyncService is still relevant for type hinting
# Import progress_manager functionally
import webnovel_archiver.core.storage.progress_manager as pm


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
    chapters_per_volume: Optional[int]
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

        try:
            base_backup_folder_name = "Webnovel Archiver Backups"
            cloud_base_folder_id = sync_service.create_folder_if_not_exists(base_backup_folder_name, parent_folder_id=None)
            story_cloud_folder_id = sync_service.create_folder_if_not_exists(current_story_id, parent_folder_id=cloud_base_folder_id)
            click.echo(f"Ensured cloud folder structure: '{base_backup_folder_name}/{current_story_id}' (ID: {story_cloud_folder_id})")
        except ConnectionError as e:
            click.echo(f"Error creating/verifying cloud folder for story {current_story_id}: {e}", err=True)
            logger.error(f"Cloud folder creation error for {current_story_id}: {e}")
            continue

        files_to_upload_info: List[Dict[str, str]] = []
        # Add progress_status.json itself, using its specific path
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
                click.echo(f"Warning: EPUB file {epub_local_abs_path} not found for story {current_story_id}. Skipping.", err=True)
                logger.warning(f"EPUB file {epub_local_abs_path} not found, skipping upload.")
                continue
            files_to_upload_info.append({'local_path': epub_local_abs_path, 'name': epub_filename})

        backup_files_results: List[Dict[str, Any]] = []

        for file_info_to_upload in files_to_upload_info:
            local_path = file_info_to_upload['local_path']
            upload_name = file_info_to_upload['name']

            should_upload = True
            if not force_full_upload:
                try:
                    remote_metadata = sync_service.get_file_metadata(file_name=upload_name, folder_id=story_cloud_folder_id)
                    if remote_metadata and remote_metadata.get('modifiedTime'):
                        if not sync_service.is_remote_older(local_path, remote_metadata['modifiedTime']):
                            should_upload = False
                            click.echo(f"Skipping '{upload_name}': Remote file is not older than local.")
                            logger.info(f"Skipping upload of {upload_name} for story {current_story_id} as remote is not older.")
                            backup_files_results.append({
                                'local_path': local_path,
                                'cloud_file_name': upload_name,
                                'cloud_file_id': remote_metadata.get('id'),
                                'last_backed_up_timestamp': remote_metadata.get('modifiedTime'),
                                'status': 'skipped_up_to_date'
                            })
                        else:
                             click.echo(f"Local file '{upload_name}' is newer. Uploading...")
                    else:
                        click.echo(f"Remote file '{upload_name}' not found or no timestamp. Uploading...")
                except ConnectionError as e:
                    click.echo(f"Warning: Could not get remote metadata for '{upload_name}': {e}. Will attempt upload.", err=True)
                    logger.warning(f"Could not get remote metadata for {upload_name} (story {current_story_id}): {e}")
                except Exception as e:
                    click.echo(f"Warning: Error checking remote status for '{upload_name}': {e}. Will attempt upload.", err=True)
                    logger.warning(f"Error checking remote status for {upload_name} (story {current_story_id}): {e}", exc_info=True)

            if should_upload:
                try:
                    click.echo(f"Uploading '{upload_name}' for story {current_story_id}...")
                    uploaded_file_meta = sync_service.upload_file(local_path, story_cloud_folder_id, remote_file_name=upload_name)
                    click.echo(f"Successfully uploaded '{uploaded_file_meta.get('name')}' (ID: {uploaded_file_meta.get('id')}).")
                    backup_files_results.append({
                        'local_path': local_path,
                        'cloud_file_name': uploaded_file_meta.get('name'),
                        'cloud_file_id': uploaded_file_meta.get('id'),
                        'last_backed_up_timestamp': uploaded_file_meta.get('modifiedTime') or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        'status': 'uploaded'
                    })
                except FileNotFoundError:
                    click.echo(f"Error: Local file {local_path} vanished before upload. Skipping.", err=True)
                except ConnectionError as e:
                    click.echo(f"Error uploading '{upload_name}' for story {current_story_id}: {e}", err=True)
                    logger.error(f"Upload failed for {local_path} to story {current_story_id} folder: {e}")
                    backup_files_results.append({ 'local_path': local_path, 'cloud_file_name': upload_name, 'status': 'failed', 'error': str(e) })
                except Exception as e:
                    click.echo(f"An unexpected error occurred uploading '{upload_name}': {e}", err=True)
                    logger.error(f"Unexpected error uploading {local_path} for story {current_story_id}: {e}", exc_info=True)
                    backup_files_results.append({ 'local_path': local_path, 'cloud_file_name': upload_name, 'status': 'failed', 'error': str(e) })

        if backup_files_results:
            current_utc_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            all_ops_successful_or_skipped = all(f.get('status') in ['uploaded', 'skipped_up_to_date'] for f in backup_files_results)
            existing_backup_status = pm.get_cloud_backup_status(progress_data)

            latest_op_time = None
            if all_ops_successful_or_skipped and backup_files_results:
                valid_timestamps = [
                    f['last_backed_up_timestamp'] for f in backup_files_results
                    if f.get('last_backed_up_timestamp') and f.get('status') in ['uploaded', 'skipped_up_to_date']
                ]
                if valid_timestamps: latest_op_time = max(valid_timestamps)
                else: latest_op_time = current_utc_time_iso

            cloud_backup_update_data = {
                'last_backup_attempt_timestamp': current_utc_time_iso,
                'last_successful_backup_timestamp': latest_op_time if all_ops_successful_or_skipped else existing_backup_status.get('last_successful_backup_timestamp'),
                'service': cloud_service_name.lower(),
                'base_cloud_folder_name': base_backup_folder_name,
                'story_cloud_folder_name': current_story_id,
                'cloud_base_folder_id': cloud_base_folder_id,
                'story_cloud_folder_id': story_cloud_folder_id,
                'backed_up_files': backup_files_results
            }

            try:
                pm.update_cloud_backup_status(progress_data, cloud_backup_update_data)
                pm.save_progress(current_story_id, progress_data, workspace_root)
                click.echo(f"Updated local progress status for story {current_story_id} with backup information.")
            except Exception as e:
                click.echo(f"Error updating and saving progress file for story {current_story_id}: {e}", err=True)
                logger.error(f"Failed to update/save progress_status.json for {current_story_id}: {e}", exc_info=True)

        processed_stories_count +=1
        click.echo(f"Finished processing story: {current_story_id}\n")

    if processed_stories_count > 0:
        click.echo(f"Cloud backup process completed for {processed_stories_count} story/stories.")
    elif not story_ids_to_process:
        pass
    else:
        click.echo("Cloud backup process completed, but no stories were actually backed up.")

# --- Migration Handler ---

# Constants for directory names used in migration (consistent with progress_manager and workspace structure)
# ARCHIVAL_STATUS_DIR is already imported as WORKSPACE_ARCHIVAL_STATUS_DIR
# EBOOKS_DIR is already imported as WORKSPACE_EBOOKS_DIR
RAW_CONTENT_DIR = "raw_content"  # Typically where raw HTML/text might be stored
PROCESSED_CONTENT_DIR = "processed_content" # Typically where processed/parsed content might be stored

def migrate_royalroad_legacy_id_handler(legacy_story_id: Optional[str], migration_type: str):
    """
    Handles the migration of RoyalRoad stories from the legacy ID format
    (e.g., 12345-some-slug) to the new format (e.g., royalroad-12345).
    """
    if migration_type != "royalroad-legacy-id":
        click.echo(f"Error: Unknown migration type '{migration_type}'. Only 'royalroad-legacy-id' is supported.", err=True)
        logger.error(f"Attempted migration with unsupported type: {migration_type}")
        return

    click.echo("Starting RoyalRoad legacy ID migration...")
    logger.info("RoyalRoad legacy ID migration process started.")

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
    except Exception as e:
        logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
        click.echo(f"Error: Could not determine workspace path. {e}", err=True)
        # Fallback to default path as a last resort, though operations might still fail if this isn't the correct user workspace
        workspace_root = DEFAULT_WORKSPACE_PATH
        click.echo(f"Warning: Using default workspace path '{workspace_root}' due to error. Ensure this is correct.", err=True)


    archival_status_base_path = os.path.join(workspace_root, WORKSPACE_ARCHIVAL_STATUS_DIR)
    story_dirs_to_migrate = []

    if legacy_story_id:
        # Specific story ID provided
        if not os.path.isdir(os.path.join(archival_status_base_path, legacy_story_id)):
            click.echo(f"Error: Provided legacy story ID directory '{legacy_story_id}' not found in {archival_status_base_path}.", err=True)
            logger.error(f"Legacy story ID directory not found: {legacy_story_id} in {archival_status_base_path}")
            return
        story_dirs_to_migrate.append(legacy_story_id)
    else:
        # Scan all directories in archival_status
        if not os.path.isdir(archival_status_base_path):
            click.echo(f"Error: Archival status directory not found at {archival_status_base_path}. Cannot scan for stories.", err=True)
            logger.error(f"Archival status directory not found: {archival_status_base_path}")
            return
        try:
            story_dirs_to_migrate = [d for d in os.listdir(archival_status_base_path) if os.path.isdir(os.path.join(archival_status_base_path, d))]
        except OSError as e:
            click.echo(f"Error reading archival status directory {archival_status_base_path}: {e}", err=True)
            logger.error(f"Error listing directories in {archival_status_base_path}: {e}")
            return

        if not story_dirs_to_migrate:
            click.echo(f"No story directories found in {archival_status_base_path} to scan.")
            logger.info(f"No story directories found in {archival_status_base_path}.")
            return

    legacy_pattern = re.compile(r"^\d+-[a-zA-Z0-9_-]+$") # Allow underscores as well in slug
    migrated_count = 0
    processed_count = 0

    for dir_name in story_dirs_to_migrate:
        processed_count += 1
        if not legacy_pattern.match(dir_name):
            logger.debug(f"Directory '{dir_name}' does not match legacy RoyalRoad format. Skipping.")
            if legacy_story_id: # If a specific ID was given and it doesn't match
                click.echo(f"Warning: Story ID '{dir_name}' does not match the expected legacy RoyalRoad format (e.g., '12345-some-slug'). No migration performed.", err=True)
            continue

        numerical_id_match = re.match(r"^(\d+)-", dir_name)
        if not numerical_id_match:
            logger.warning(f"Could not extract numerical ID from '{dir_name}' despite matching pattern. Skipping.")
            continue

        numerical_id = numerical_id_match.group(1)
        new_story_id = f"royalroad-{numerical_id}"

        click.echo(f"INFO: Found legacy story '{dir_name}'. Attempting to migrate to '{new_story_id}'...")
        logger.info(f"Found legacy story '{dir_name}'. Migrating to '{new_story_id}'.")

        # Check if target directory already exists in archival_status (primary check)
        if os.path.exists(os.path.join(archival_status_base_path, new_story_id)):
            click.echo(f"Warning: Target directory '{new_story_id}' already exists in {WORKSPACE_ARCHIVAL_STATUS_DIR}. Skipping migration for '{dir_name}'.", err=True)
            logger.warning(f"Target directory '{new_story_id}' already exists in {WORKSPACE_ARCHIVAL_STATUS_DIR}. Skipping migration for '{dir_name}'.")
            continue

        migration_successful_for_story = True
        # Define paths relative to workspace_root for clarity
        paths_to_rename = {
            WORKSPACE_ARCHIVAL_STATUS_DIR: (os.path.join(workspace_root, WORKSPACE_ARCHIVAL_STATUS_DIR, dir_name), os.path.join(workspace_root, WORKSPACE_ARCHIVAL_STATUS_DIR, new_story_id)),
            WORKSPACE_EBOOKS_DIR: (os.path.join(workspace_root, WORKSPACE_EBOOKS_DIR, dir_name), os.path.join(workspace_root, WORKSPACE_EBOOKS_DIR, new_story_id)),
            RAW_CONTENT_DIR: (os.path.join(workspace_root, RAW_CONTENT_DIR, dir_name), os.path.join(workspace_root, RAW_CONTENT_DIR, new_story_id)),
            PROCESSED_CONTENT_DIR: (os.path.join(workspace_root, PROCESSED_CONTENT_DIR, dir_name), os.path.join(workspace_root, PROCESSED_CONTENT_DIR, new_story_id)),
        }

        for key, (old_path, new_path) in paths_to_rename.items():
            if os.path.exists(old_path):
                try:
                    # Ensure parent directory of new_path exists if we are renaming into a structure that might not be there
                    # For simple renaming of story_id folders, the parent (e.g. workspace/ebooks) should exist.
                    # If renaming story_id to new_story_id, os.makedirs(os.path.dirname(new_path), exist_ok=True) isn't strictly necessary
                    # unless the base directories (ebooks, raw_content etc.) themselves might not exist.
                    # Assuming base directories like 'ebooks', 'raw_content' exist at workspace_root.
                    shutil.move(old_path, new_path)
                    logger.info(f"Successfully renamed {key} directory: '{old_path}' to '{new_path}'.")
                except Exception as e:
                    click.echo(f"Error renaming {key} directory from '{old_path}' to '{new_path}': {e}", err=True)
                    logger.error(f"Error renaming {key} directory for story '{dir_name}' to '{new_story_id}': {e}", exc_info=True)
                    migration_successful_for_story = False
                    # Basic rollback attempt for the critical archival_status dir if it failed after others succeeded.
                    # This is complex; for now, log error and make user aware.
                    if key == WORKSPACE_ARCHIVAL_STATUS_DIR:
                        click.echo(f"CRITICAL: Failed to rename main archival status directory for '{dir_name}'. Story state might be inconsistent.", err=True)
                    break # Stop renaming for this story if one part fails
            else:
                logger.info(f"{key} directory not found at '{old_path}'. No action needed for this part.")

        if migration_successful_for_story:
            click.echo(click.style(f"SUCCESS: Migration for '{new_story_id}' (from '{dir_name}') completed.", fg="green"))
            logger.info(f"Successfully migrated story '{dir_name}' to '{new_story_id}'.")
            migrated_count += 1
        else:
            click.echo(click.style(f"ERROR: Migration for '{dir_name}' failed or was incomplete. Check logs. You may need to manually restore from backups or complete the rename.", fg="red"), err=True)
            logger.error(f"Migration for '{dir_name}' failed or was incomplete.")


    if legacy_story_id: # Reporting for single story migration
        if migrated_count == 1:
             click.echo(f"Migration for '{legacy_story_id}' to '{new_story_id}' successful.") # new_story_id will be set if migration happened
        elif processed_count == 1 : # Processed the one, but didn't migrate it (e.g. wrong format, target existed, or error)
             click.echo(f"Migration check for '{legacy_story_id}' complete. No migration was performed or it failed. See logs for details.")
        # else: # processed_count == 0, means the initial dir check failed, error already printed.
    else: # Reporting for full scan
        click.echo(f"Migration scan complete. Processed {processed_count} directories. Successfully migrated {migrated_count} stories.")
        logger.info(f"Migration scan complete. Processed {processed_count} directories. Migrated {migrated_count} stories.")

    if processed_count == 0 and not legacy_story_id: # Only if full scan and nothing found
        click.echo(f"No story directories found to process in {archival_status_base_path}.")
