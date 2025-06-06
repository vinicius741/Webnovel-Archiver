import click
from typing import Optional
from webnovel_archiver.cli.handlers import archive_story_handler, migrate_royalroad_legacy_id_handler # Import handler

@click.group()
def archiver():
    """A CLI tool for archiving webnovels."""
    pass

@archiver.command()
@click.argument('story_url')
@click.option('--output-dir', default=None, type=click.Path(), help='Directory to save the archive. Overrides workspace default.')
@click.option('--ebook-title-override', default=None, help='Override the ebook title.')
@click.option('--keep-temp-files', is_flag=True, default=False, help='Keep temporary files after archiving.')
@click.option('--force-reprocessing', is_flag=True, default=False, help='Force reprocessing of already downloaded content.')
@click.option('--sentence-removal-file', default=None, type=click.Path(exists=True), help='Path to a JSON file for sentence removal rules.')
@click.option('--no-sentence-removal', is_flag=True, default=False, help='Disable sentence removal even if a file is provided.')
@click.option('--chapters-per-volume', default=None, type=int, help='Number of chapters per EPUB volume. Default is all in one volume.')
def archive_story(story_url: str, output_dir: Optional[str], ebook_title_override: Optional[str], keep_temp_files: bool, force_reprocessing: bool, sentence_removal_file: Optional[str], no_sentence_removal: bool, chapters_per_volume: Optional[int]):
    """Archives a webnovel from a given URL with specified options."""
    archive_story_handler(
        story_url=story_url,
        output_dir=output_dir,
        ebook_title_override=ebook_title_override,
        keep_temp_files=keep_temp_files,
        force_reprocessing=force_reprocessing,
        cli_sentence_removal_file=sentence_removal_file, # Changed to cli_sentence_removal_file
        no_sentence_removal=no_sentence_removal,
        chapters_per_volume=chapters_per_volume
    )

# New cloud-backup command
@archiver.command(name='cloud-backup') # Explicitly naming command
@click.argument('story_id', required=False, default=None)
@click.option(
    '--cloud-service',
    default='gdrive',
    type=click.Choice(['gdrive'], case_sensitive=False), # Initially only gdrive, extensible later
    help='The cloud service to use for backup. Default: gdrive'
)
@click.option(
    '--force-full-upload',
    is_flag=True,
    default=False,
    help='Force upload of all files, even if they appear up-to-date.'
)
# Placeholder for credentials file path for GDrive, can be expanded or moved to config
@click.option(
    '--credentials-file',
    default='credentials.json',
    type=click.Path(), # Not exists=True, as it might be created or user prompted
    help='Path to the Google Drive API credentials file (credentials.json).'
)
@click.option(
    '--token-file',
    default='token.json',
    type=click.Path(),
    help='Path to the Google Drive API token file (token.json).'
)
def cloud_backup(
    story_id: Optional[str],
    cloud_service: str,
    force_full_upload: bool,
    credentials_file: str,
    token_file: str
):
    """
    Backs up archived webnovels to a cloud storage service.

    If STORY_ID is provided, only that story will be backed up.
    Otherwise, all stories with existing progress status will be processed.
    """
    # click.echo(f"Cloud backup initiated for story ID: {story_id if story_id else 'All stories'}")
    # click.echo(f"Cloud service: {cloud_service}")
    # click.echo(f"Force full upload: {force_full_upload}")
    # click.echo(f"Credentials file: {credentials_file}")
    # click.echo(f"Token file: {token_file}")

    # Dynamically import the handler to avoid circular imports if handlers grow complex
    from webnovel_archiver.cli.handlers import cloud_backup_handler

    cloud_backup_handler(
        story_id=story_id,
        cloud_service_name=cloud_service,
        force_full_upload=force_full_upload,
        gdrive_credentials_path=credentials_file,
        gdrive_token_path=token_file
    )

@archiver.group()
def migrate():
    """Migrates story archives from old formats to new formats."""
    pass

@migrate.command(name="royalroad-legacy-id") # Keep name consistent with --type
@click.argument('story_id', required=False, default=None)
@click.option(
    '--type', # This option might seem redundant now but is for future extensibility
    "migration_type", # Use a distinct name for the parameter to avoid conflict with command name
    required=True,
    default="royalroad-legacy-id", # Default to current type
    show_default=True, # Show this default in help
    type=click.Choice(['royalroad-legacy-id'], case_sensitive=False), # Initially only this type
    help='The type of migration to perform.'
)
def migrate_royalroad_legacy_id(story_id: Optional[str], migration_type: str):
    """Migrates RoyalRoad stories from the legacy ID format (e.g., 12345-some-slug)
    to the new format (e.g., royalroad-12345).

    If STORY_ID is provided, only that specific story will be migrated.
    Otherwise, all stories matching the legacy RoyalRoad format will be scanned and migrated.
    """
    migrate_royalroad_legacy_id_handler(legacy_story_id=story_id, migration_type=migration_type) # Pass story_id as legacy_story_id

if __name__ == '__main__':
    archiver()
