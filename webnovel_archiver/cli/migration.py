import os
import json
import click
from webnovel_archiver.core.path_manager import PathManager
from webnovel_archiver.core.fetchers.fetcher_factory import FetcherFactory
from webnovel_archiver.utils.logger import get_migration_logger

migration_logger = get_migration_logger()

def trigger_migration_if_needed():
    """
    Checks if the story index exists and triggers the migration process if it doesn't.
    """
    path_manager = PathManager("workspace")
    index_path = path_manager.index_path
    
    if not os.path.exists(index_path):
        click.echo("Story index not found. Starting one-time migration process...")
        migration_logger.info("Story index not found. Starting one-time migration process...")
        migrate_legacy_archive(path_manager)
        click.echo(f"Migration complete. Story index created at: {index_path}")
        migration_logger.info(f"Migration complete. Story index created at: {index_path}")

def migrate_legacy_archive(path_manager: PathManager):
    """
    Scans the legacy archive and creates the new index.json file.
    """
    index = {}
    archival_status_dir = path_manager.get_base_directory(PathManager.ARCHIVAL_STATUS_DIR_NAME)

    if not os.path.isdir(archival_status_dir):
        message = f"Archival status directory not found at '{archival_status_dir}'. No migration needed."
        click.echo(f"Warning: {message}")
        migration_logger.warning(message)
        # Create an empty index file to prevent this from running again
        with open(path_manager.index_path, 'w') as f:
            json.dump({}, f)
        return

    for story_folder in os.listdir(archival_status_dir):
        progress_path = os.path.join(archival_status_dir, story_folder, PathManager.PROGRESS_FILENAME)

        if not os.path.exists(progress_path):
            migration_logger.warning(f"No progress file found for folder '{story_folder}'. Skipping.")
            continue

        try:
            with open(progress_path, 'r') as f:
                progress_data = json.load(f)
            
            url = progress_data.get('url')
            if not url:
                message = f"Could not find URL in {progress_path}. Skipping."
                click.echo(f"Warning: {message}")
                migration_logger.warning(message)
                continue

            fetcher = FetcherFactory.get_fetcher(url)
            permanent_id = fetcher.get_permanent_id()
            
            if permanent_id in index:
                message = f"Duplicate permanent ID '{permanent_id}' found for folder '{story_folder}'. The existing entry points to '{index[permanent_id]}'. Skipping this folder."
                click.echo(f"Warning: {message}")
                migration_logger.warning(message)
            else:
                index[permanent_id] = story_folder
                migration_logger.info(f"Mapped permanent ID '{permanent_id}' to folder '{story_folder}'.")

        except json.JSONDecodeError:
            message = f"Could not parse {progress_path}. Skipping."
            click.echo(f"Warning: {message}")
            migration_logger.warning(message)
        except Exception as e:
            message = f"An unexpected error occurred while processing {story_folder}: {e}. Skipping."
            click.echo(f"Warning: {message}")
            migration_logger.error(message, exc_info=True)

    with open(path_manager.index_path, 'w') as f:
        json.dump(index, f, indent=4)
