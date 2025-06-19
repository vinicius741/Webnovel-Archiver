import json
import os
from webnovel_archiver.core.builders.epub_generator import EPUBGenerator
# from webnovel_archiver.utils.logger import get_logger # Assuming EPUBGenerator handles its own logging
import logging # Keep for basic script logging if needed, or remove if relying on module's logger

# logger = get_logger(__name__) # Or use basicConfig if you want script-level logging configuration.
# For simplicity, let's use print for this script's direct feedback,
# relying on EPUBGenerator's logger for its internal messages.
# If EPUBGenerator's logger is not configured by default to show INFO, we might not see its logs.
# A more robust approach for a utility script would be:
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    story_id = "story123"
    workspace_root = "test_workspace" # Assuming script is run from repo root

    progress_file_path = os.path.join(workspace_root, "archival_status", story_id, "progress.json")

    if not os.path.exists(progress_file_path):
        logger.error(f"Progress file not found: {progress_file_path}")
        return

    try:
        with open(progress_file_path, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading or parsing progress file {progress_file_path}: {e}")
        return

    # Ensure ebooks directory exists for the story
    ebooks_story_dir = os.path.join(workspace_root, "ebooks", story_id)
    os.makedirs(ebooks_story_dir, exist_ok=True)

    # Ensure processed_content directory exists for the story (already done by creating files, but good check)
    processed_content_story_dir = os.path.join(workspace_root, "processed_content", story_id)
    if not os.path.isdir(processed_content_story_dir):
        logger.error(f"Processed content directory not found: {processed_content_story_dir}. Make sure dummy HTML files are in place.")
        # Create it if it somehow wasn't, though individual file creation should have done this.
        os.makedirs(processed_content_story_dir, exist_ok=True)


    logger.info(f"Preparing to generate EPUB for story ID: {story_id} using data from {progress_file_path}")
    logger.info(f"Effective title: {progress_data.get('effective_title')}")
    logger.info(f"Synopsis: {progress_data.get('synopsis')}")
    logger.info(f"Cover URL: {progress_data.get('cover_image_url')}")
    logger.info(f"Number of chapters in progress data: {len(progress_data.get('downloaded_chapters', []))}")


    epub_generator = EPUBGenerator(workspace_root=workspace_root)

    # For this test, let's generate a single volume EPUB
    # chapters_per_volume = None  # Single volume
    # To test multi-volume, you could set e.g. chapters_per_volume = 2
    chapters_per_volume = 2


    logger.info(f"Calling EPUBGenerator with chapters_per_volume={chapters_per_volume}")
    generated_files = epub_generator.generate_epub(story_id, progress_data, chapters_per_volume=chapters_per_volume)

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
