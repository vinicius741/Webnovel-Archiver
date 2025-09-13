import os
import shutil
import click
from typing import Optional

import webnovel_archiver.core.storage.progress_manager as pm
from ..contexts import MigrationContext
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

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
