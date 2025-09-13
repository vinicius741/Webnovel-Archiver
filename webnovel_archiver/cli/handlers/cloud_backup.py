import os
import click
import datetime
from typing import Optional, List, Dict, Any

from webnovel_archiver.generate_report import main as generate_report_main_func
import webnovel_archiver.core.storage.progress_manager as pm
from webnovel_archiver.core.storage.progress_epub import get_epub_file_details
from webnovel_archiver.core.storage.progress_cloud import get_cloud_backup_status, update_cloud_backup_status
from ..contexts import CloudBackupContext
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

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
        cloud_backup_status = get_cloud_backup_status(progress_data)
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
        epub_file_entries = get_epub_file_details(progress_data, story_folder_name, workspace_root)

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
            update_cloud_backup_status(progress_data, {
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

    report_path = os.path.join(workspace_root, "reports", "archive_report_new.html")
    if os.path.exists(report_path):
        click.echo("HTML report found. Attempting to upload...")
        if cloud_base_folder_id and sync_service:
            try:
                sync_service.upload_file(report_path, cloud_base_folder_id, "archive_report_new.html")
                click.echo(click.style("✓ Successfully uploaded HTML report", fg="green"))
            except Exception as e:
                click.echo(click.style(f"Error uploading HTML report: {e}", fg="red"), err=True)
