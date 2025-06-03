import os
import click # For feedback and potentially type hinting
from typing import Optional

# Import necessary core components
from webnovel_archiver.core.orchestrator import archive_story as call_orchestrator_archive_story
from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
from webnovel_archiver.utils.logger import get_logger

# It's good practice to set up logging if the CLI is the entry point
logger = get_logger(__name__)

def archive_story_handler(
    story_url: str,
    output_dir: Optional[str],
    ebook_title_override: Optional[str],
    keep_temp_files: bool,
    force_reprocessing: bool,
    sentence_removal_file: Optional[str],
    no_sentence_removal: bool,
    chapters_per_volume: Optional[int]
):
    """
    Handles the logic for the 'archive-story' CLI command.
    It determines workspace, instantiates Orchestrator, and calls the archiving process.
    """
    click.echo(f"Received story URL: {story_url}")
    # For debugging, echo received options
    # click.echo(f"Output Dir: {output_dir}")
    # click.echo(f"Ebook Title Override: {ebook_title_override}")
    # click.echo(f"Keep Temp Files: {keep_temp_files}")
    # click.echo(f"Force Reprocessing: {force_reprocessing}")
    # click.echo(f"Sentence Removal File: {sentence_removal_file}")
    # click.echo(f"No Sentence Removal: {no_sentence_removal}")
    # click.echo(f"Chapters per Volume: {chapters_per_volume}")

    # 1. Determine workspace_root
    if output_dir:
        workspace_root = output_dir
        click.echo(f"Using provided output directory: {workspace_root}")
    else:
        try:
            # Note: ConfigManager might print warnings if config file is missing.
            # Consider if this is desired CLI behavior or if it should be quieter.
            config_manager = ConfigManager()
            workspace_root = config_manager.get_workspace_path()
            click.echo(f"Using workspace directory from config: {workspace_root}")
        except Exception as e:
            logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
            # Fallback to a default path if ConfigManager fails catastrophically
            workspace_root = DEFAULT_WORKSPACE_PATH
            click.echo(f"Warning: Using default workspace path due to error: {workspace_root}", err=True)

    # Ensure workspace_root exists or can be created by orchestrator/downloader
    # os.makedirs(workspace_root, exist_ok=True) # Orchestrator might handle this

    click.echo("Starting archival process...")
    logger.info(f"CLI handler initiated archival for {story_url} to workspace {workspace_root}")

    try:
        # 2. Call core.Orchestrator.archive_story()
        # Note: The orchestrator.py's archive_story function needs to be updated
        # to accept these new parameters. This subtask assumes it will be.
        call_orchestrator_archive_story(
            story_url=story_url,
            workspace_root=workspace_root,
            # These parameters need to be added to the orchestrator's archive_story function
            ebook_title_override=ebook_title_override,
            keep_temp_files=keep_temp_files,
            force_reprocessing=force_reprocessing,
            sentence_removal_file=sentence_removal_file,
            no_sentence_removal=no_sentence_removal,
            chapters_per_volume=chapters_per_volume
        )
        click.echo(f"Archival process completed for: {story_url}")
        logger.info(f"Successfully completed archival for {story_url}")

    except Exception as e:
        # Catching a broad exception here to provide some feedback to the CLI user.
        # Specific exceptions should be handled within the orchestrator or its components.
        click.echo(f"An error occurred during the archival process: {e}", err=True)
        logger.error(f"CLI handler caught an error during archival for {story_url}: {e}", exc_info=True)
        # Consider exiting with a non-zero status code for errors
        # import sys
        # sys.exit(1)
