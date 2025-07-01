import json
import os
import sys # Import sys for command-line arguments
from webnovel_archiver.core.builders.epub_generator import EPUBGenerator
from webnovel_archiver.core.path_manager import PathManager
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    if len(sys.argv) < 2:
        logger.error("Usage: python run_epub_generation_script.py <permanent_story_id>")
        logger.error("Example: python run_epub_generation_script.py royalroad-12345")
        return

    selected_perm_id = sys.argv[1]

    workspace_root = "workspace"
    index_file_path = os.path.join(workspace_root, "index.json")
    
    index_data = {}
    if os.path.exists(index_file_path):
        try:
            with open(index_file_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading or parsing index.json: {e}")
            return
    else:
        logger.warning(f"index.json not found at {index_file_path}. Please ensure you have run the migration process to create it.")
        logger.info("You can typically trigger the migration by running the main CLI application.")
        return

    if not index_data:
        logger.warning("index.json is empty. No stories to generate EPUBs for.")
        return

    logger.info("Available stories (Permanent ID: Folder Name):")
    for perm_id, folder_name in index_data.items():
        logger.info(f"- {perm_id}: {folder_name}")

    if selected_perm_id not in index_data:
        logger.error(f"Permanent ID '{selected_perm_id}' not found in index.json.")
        return

    story_folder_name = index_data[selected_perm_id]
    logger.info(f"Selected story '{selected_perm_id}' maps to folder: '{story_folder_name}'")

    # Initialize PathManager with the actual story folder name
    pm = PathManager(workspace_root, story_folder_name)

    progress_file_path = pm.get_progress_filepath()

    if not os.path.exists(progress_file_path):
        logger.error(f"Progress file not found for story '{story_folder_name}': {progress_file_path}")
        return

    try:
        with open(progress_file_path, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading or parsing progress file {progress_file_path}: {e}")
        return

    # Ensure ebooks directory exists for the story (using PathManager)
    os.makedirs(pm.get_ebooks_story_dir(), exist_ok=True)

    # Ensure processed_content directory exists for the story (using PathManager)
    os.makedirs(pm.get_processed_content_story_dir(), exist_ok=True)

    logger.info(f"Preparing to generate EPUB for story ID: {selected_perm_id} (Folder: {story_folder_name}) using data from {progress_file_path}")
    logger.info(f"Effective title: {progress_data.get('effective_title')}")
    logger.info(f"Synopsis: {progress_data.get('synopsis')}")
    logger.info(f"Cover URL: {progress_data.get('cover_image_url')}")
    logger.info(f"Number of chapters in progress data: {len(progress_data.get('downloaded_chapters', []))}")

    epub_generator = EPUBGenerator(pm)

    chapters_per_volume = None # Set to None for single volume, or a number for multi-volume

    logger.info(f"Calling EPUBGenerator with chapters_per_volume={chapters_per_volume}")
    generated_files = epub_generator.generate_epub(progress_data, chapters_per_volume=chapters_per_volume)

    if generated_files:
        logger.info("EPUB generation successful. Generated files:")
        for file_path in generated_files:
            logger.info(f"- {file_path}")
            # Additional check: verify file existence and size
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(f"  File exists and is not empty (Size: {os.path.getsize(file_path)} bytes).")
            else:
                logger.error(f"  File {file_path} was reported as generated but is missing or empty.")
    else:
        logger.error("EPUB generation failed or produced no files.")

if __name__ == "__main__":
    main()
