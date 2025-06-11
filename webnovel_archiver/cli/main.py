import click
from typing import Optional
from webnovel_archiver.cli.handlers import archive_story_handler, generate_report_handler
from webnovel_archiver.generate_report import main as generate_report_main

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
@click.option('--epub-contents', default='all', type=click.Choice(['all', 'active-only'], case_sensitive=False), help='Determines what to include in the EPUB: "all" (default) includes active and archived chapters; "active-only" mirrors the source website.')
@click.option('--resume-from-url', default=None, type=str, help='URL of the chapter to resume processing from.')
@click.option('--chapter-limit-for-run', default=None, type=int, help='Maximum number of chapters to download/process in this run.')
def archive_story(
    story_url: str,
    output_dir: Optional[str],
    ebook_title_override: Optional[str],
    keep_temp_files: bool,
    force_reprocessing: bool,
    sentence_removal_file: Optional[str],
    no_sentence_removal: bool,
    chapters_per_volume: Optional[int],
    epub_contents: str,
    resume_from_url: Optional[str],
    chapter_limit_for_run: Optional[int]
):
    """Archives a webnovel from a given URL with specified options."""
    archive_story_handler(
        story_url=story_url,
        output_dir=output_dir,
        ebook_title_override=ebook_title_override,
        keep_temp_files=keep_temp_files,
        force_reprocessing=force_reprocessing,
        cli_sentence_removal_file=sentence_removal_file, # Changed to cli_sentence_removal_file
        no_sentence_removal=no_sentence_removal,
        chapters_per_volume=chapters_per_volume,
        epub_contents=epub_contents,
        resume_from_url=resume_from_url,
        chapter_limit_for_run=chapter_limit_for_run
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

@archiver.command(name='migrate')
@click.argument('story_id', required=False, default=None)
@click.option(
    '--type', 'migration_type', # Use 'migration_type' as the Python variable name
    required=True,
    type=click.Choice(['royalroad-legacy-id'], case_sensitive=False),
    help='The type of migration to perform. Currently only supports "royalroad-legacy-id".'
)
def migrate(story_id: Optional[str], migration_type: str):
    """
    Migrates existing story archives to new formats or structures.

    If STORY_ID is provided, only that specific story archive will be considered for migration.
    Otherwise, all relevant story archives will be scanned.
    The --type option specifies the migration logic to apply.
    """
    # Dynamically import the handler to avoid potential circular imports
    # and to keep imports minimal at the top level if handlers.py grows.
    from webnovel_archiver.cli.handlers import migration_handler # Assuming this will be the handler's name

    migration_handler(
        story_id=story_id,
        migration_type=migration_type
    )

@archiver.command(name='generate-report')
def generate_report_command():
    """Generates an HTML report of the archived webnovels."""
    # Handler will be called here in a later step
    # For now, we can import and call the handler directly if it's simple,
    # or call a placeholder / the actual function.
    # Let's call generate_report_main directly for now, and refine if a separate handler is strictly needed.
    # This simplifies the plan slightly by merging handler creation if direct call is sufficient.
    # However, the plan was to create a separate handler.
    # For now, let's stick to the plan and assume a handler will be created.
    # So, this function body will be updated later to call the handler.
    # For this step, just defining the command and its docstring is enough.
    # The actual call to generate_report_main or a handler will be done in step 4.
    # To make the file runnable, we can add a pass or a click.echo temporary message.
    generate_report_handler()

if __name__ == '__main__':
    archiver()
