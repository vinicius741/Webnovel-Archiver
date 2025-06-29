import os
import json
import click
from webnovel_archiver.core.path_manager import PathManager
from webnovel_archiver.core.fetchers.fetcher_factory import FetcherFactory

def trigger_migration_if_needed():
    """
    Checks if the story index exists and triggers the migration process if it doesn't.
    """
    path_manager = PathManager("workspace")
    index_path = path_manager.index_path
    
    if not os.path.exists(index_path):
        click.echo("Story index not found. Starting one-time migration process...")
        migrate_legacy_archive(path_manager)
        click.echo("Migration complete. Story index created at: {}".format(index_path))

def migrate_legacy_archive(path_manager: PathManager):
    """
    Scans the legacy archive and creates the new index.json file.
    """
    index = {}
    archival_status_dir = path_manager.get_base_directory(PathManager.ARCHIVAL_STATUS_DIR_NAME)

    if not os.path.isdir(archival_status_dir):
        click.echo(f"Warning: Archival status directory not found at '{archival_status_dir}'. No migration needed.")
        # Create an empty index file to prevent this from running again
        with open(path_manager.index_path, 'w') as f:
            json.dump({}, f)
        return

    for story_folder in os.listdir(archival_status_dir):
        progress_path = os.path.join(archival_status_dir, story_folder, PathManager.PROGRESS_FILENAME)

        if os.path.exists(progress_path):
            try:
                with open(progress_path, 'r') as f:
                    progress_data = json.load(f)
                
                url = progress_data.get('url')
                if not url:
                    click.echo(f"Warning: Could not find URL in {progress_path}. Skipping.")
                    continue

                fetcher = FetcherFactory.get_fetcher(url)
                permanent_id = fetcher.get_permanent_id()
                
                if permanent_id in index:
                    click.echo(f"Warning: Duplicate permanent ID '{permanent_id}' found for folder '{story_folder}'. The existing entry points to '{index[permanent_id]}'. Skipping this folder.")
                else:
                    index[permanent_id] = story_folder

            except json.JSONDecodeError:
                click.echo(f"Warning: Could not parse {progress_path}. Skipping.")
            except Exception as e:
                click.echo(f"An unexpected error occurred while processing {story_folder}: {e}. Skipping.")

    with open(path_manager.index_path, 'w') as f:
        json.dump(index, f, indent=4)
