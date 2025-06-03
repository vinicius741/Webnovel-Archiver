import os
import datetime
from typing import Dict, Any
import requests # For specific exception types like requests.exceptions.RequestException

from webnovel_archiver.utils.logger import get_logger # Import logger
from .fetchers.royalroad_fetcher import RoyalRoadFetcher
# Assuming StoryMetadata and ChapterInfo will be used from base_fetcher if needed directly
# from .fetchers.base_fetcher import StoryMetadata, ChapterInfo
from .storage.progress_manager import (
    generate_story_id,
    load_progress,
    save_progress,
    DEFAULT_WORKSPACE_ROOT, # For constructing paths if needed for simulation
    ARCHIVAL_STATUS_DIR
)
from .parsers.html_cleaner import HTMLCleaner

# Define directories for simulated content saving (relative to workspace_root)
RAW_CONTENT_DIR = "raw_content"
PROCESSED_CONTENT_DIR = "processed_content"

# Initialize logger for this module
logger = get_logger(__name__)

def archive_story(story_url: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> None:
    """
    Orchestrates the archiving process for a given story URL.
    Handles fetching, cleaning, saving, and progress management.
    """
    logger.info(f"Starting archiving process for: {story_url}")

    # 1. Fetcher Initialization
    fetcher = RoyalRoadFetcher() # Later, select based on URL or config.

    # 2. Metadata Fetching
    logger.info(f"Fetching story metadata for URL: {story_url}")
    try:
        metadata = fetcher.get_story_metadata(story_url)
        logger.info(f"Successfully fetched metadata. Title: {metadata.original_title}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch story metadata for URL: {story_url}. Network error: {e}")
        return
    except Exception as e: # Catch other potential errors from fetcher
        logger.error(f"An unexpected error occurred while fetching story metadata for URL: {story_url}. Error: {e}")
        return

    # 3. Chapter List Fetching
    logger.info(f"Fetching chapter list for: {metadata.original_title}")
    try:
        chapters_info_list = fetcher.get_chapter_urls(story_url)
        logger.info(f"Found {len(chapters_info_list)} chapters.")
        if not chapters_info_list:
            logger.warning("No chapters found. Aborting archival for this story.")
            return
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch chapter list for: {metadata.original_title}. Network error: {e}")
        return
    except Exception as e: # Catch other potential errors
        logger.error(f"An unexpected error occurred while fetching chapter list for: {metadata.original_title}. Error: {e}")
        return

    # 4. Progress Management (Initial Setup)
    s_id = generate_story_id(url=story_url, title=metadata.original_title)
    metadata.story_id = s_id
    logger.info(f"Generated story ID: {s_id}")

    progress_data = load_progress(s_id, workspace_root)

    # Update progress_data with fetched metadata (if not already there or to refresh)
    progress_data["story_id"] = s_id
    progress_data["story_url"] = story_url # or metadata.story_url if it was set by fetcher
    progress_data["original_title"] = metadata.original_title
    progress_data["original_author"] = metadata.original_author
    progress_data["cover_image_url"] = metadata.cover_image_url
    progress_data["synopsis"] = metadata.synopsis
    progress_data["estimated_total_chapters_source"] = metadata.estimated_total_chapters_source

    # 4. Chapter Iteration: Download, Save (Simulated), Update Progress
    html_cleaner = HTMLCleaner()

    # Keep track of existing downloaded chapters to avoid reprocessing if not forced
    # For phase 1, we'll assume we process all chapters found by get_chapter_urls
    # and update/add them to progress_data["downloaded_chapters"].
    # A more sophisticated check for existing chapters would be needed for incremental downloads.

    # Clear existing chapters in progress if we are reprocessing all.
    # For incremental downloads, this logic would need to be more sophisticated,
    # merging new chapters with existing ones in progress_data["downloaded_chapters"].
    # For now, if progress_data["downloaded_chapters"] exists, we assume previous run.
    # This simple example will re-process all chapters every time.
    # A proper implementation would check `chapter_info.chapter_url` against existing entries.

    # We will build a new list of chapter details for this run.
    # If a chapter fails, it won't be added to this list for this run.
    current_run_processed_chapters = []


    for chapter_info in chapters_info_list:
        logger.info(f"Processing chapter: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")

        raw_html_content = None
        try:
            raw_html_content = fetcher.download_chapter_content(chapter_info.chapter_url)
            # RoyalRoadFetcher's download_chapter_content now raises HTTPError for network/HTTP issues
            # or returns "Chapter content not found." if the div is missing.
            if raw_html_content == "Chapter content not found.":
                logger.warning(f"Content div not found for chapter: {chapter_info.chapter_title}. Skipping.")
                continue # Skip this chapter, don't add to progress for this run
        except requests.exceptions.HTTPError as e: # Catch HTTP errors from _fetch_html_content via download_chapter_content
            logger.error(f"Failed to download chapter: {chapter_info.chapter_title}. HTTP Error: {e}")
            continue # Skip to the next chapter
        except Exception as e: # Catch any other unexpected errors during download
            logger.error(f"An unexpected error occurred while downloading chapter: {chapter_info.chapter_title}. Error: {e}")
            continue # Skip to the next chapter

        # At this point, raw_html_content should be valid HTML string if no exception/skip
        raw_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}.html"
        raw_file_directory = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id)
        os.makedirs(raw_file_directory, exist_ok=True)
        raw_filepath = os.path.join(raw_file_directory, raw_filename)

        try:
            with open(raw_filepath, 'w', encoding='utf-8') as f:
                f.write(raw_html_content)
            logger.info(f"Successfully saved raw content to: {raw_filepath}")
        except IOError as e:
            logger.error(f"Error saving raw content for {chapter_info.chapter_title} to {raw_filepath}: {e}")
            continue # If saving raw content fails, skip this chapter for progress

        # Clean HTML
        logger.info(f"Cleaning HTML for: {chapter_info.chapter_title}")
        cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad") # Assuming RoyalRoad for now

        processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
        processed_file_directory = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id)
        os.makedirs(processed_file_directory, exist_ok=True)
        processed_filepath = os.path.join(processed_file_directory, processed_filename)

        try:
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_html_content)
            logger.info(f"Successfully saved processed content to: {processed_filepath}")
        except IOError as e:
            logger.error(f"Error saving processed content for {chapter_info.chapter_title} to {processed_filepath}: {e}")
            # If processed saving fails, we might still want to record the raw download.
            # For this iteration, let's make processed_filename None if saving it failed.
            processed_filename = None

        # Add details of successfully processed chapter to current run's list
        # Only add chapter to progress if raw content was successfully saved
        # and processed content saving was attempted (even if it failed, processed_filename would be None)
        chapter_detail_entry = {
            "source_chapter_id": chapter_info.source_chapter_id,
            "download_order": chapter_info.download_order,
            "chapter_url": chapter_info.chapter_url,
            "chapter_title": chapter_info.chapter_title,
            "local_raw_filename": raw_filename,
            "local_processed_filename": processed_filename,
            "download_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }
        current_run_processed_chapters.append(chapter_detail_entry)

        # Update last downloaded and next to download (simplified for linear processing)
        # These are updated per successfully processed chapter in this run.
        if current_run_processed_chapters: # If list is not empty
            progress_data["last_downloaded_chapter_url"] = current_run_processed_chapters[-1]["chapter_url"]

        # Determine next chapter URL based on the original full list
        current_chapter_index_in_full_list = chapters_info_list.index(chapter_info)
        if current_chapter_index_in_full_list < len(chapters_info_list) - 1:
            progress_data["next_chapter_to_download_url"] = chapters_info_list[current_chapter_index_in_full_list + 1].chapter_url
        else:
            progress_data["next_chapter_to_download_url"] = None

    # Update the main downloaded_chapters list in progress_data.
    # This simple replacement means if a chapter was downloaded previously but fails in this run,
    # it will be removed from the list. More sophisticated merging would be needed for true incrementals
    # where you only add new or update existing.
    progress_data["downloaded_chapters"] = current_run_processed_chapters

    # 6. Save Final Progress
    logger.info("Saving final progress status...")
    try:
        save_progress(s_id, progress_data, workspace_root)
        logger.info(f"Progress saved to {os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, s_id, 'progress_status.json')}")
    except Exception as e:
        logger.error(f"Error saving progress for story ID {s_id}: {e}")

    logger.info(f"Archiving process completed for story ID: {s_id}")

if __name__ == '__main__':
    import shutil
    # Setup basic logging for the __main__ block if you want to see Orchestrator logs
    # This is separate from the logger used within the Orchestrator module itself if it's configured.
    # from webnovel_archiver.utils.logger import setup_basic_logging
    # setup_basic_logging() # Call this if you want to see logs from the example run below

    test_story_url = "https://www.royalroad.com/fiction/117255/rend"
    test_workspace = "temp_workspace_orchestrator_tests"

    story_id_for_run = generate_story_id(url=test_story_url) # For verification path

    logger.info(f"--- Preparing Test Environment: Cleaning workspace '{test_workspace}' ---")
    if os.path.exists(test_workspace):
        shutil.rmtree(test_workspace)
    os.makedirs(test_workspace, exist_ok=True)

    logger.info(f"--- Running Orchestrator Test for: {test_story_url} ---")
    logger.info(f"--- Workspace: {test_workspace} ---")

    archive_story(test_story_url, workspace_root=test_workspace)

    logger.info(f"--- Orchestrator Test Run Finished ---")

    logger.info("--- Verifying Created Files (Basic Checks) ---")
    progress_file_path = os.path.join(test_workspace, ARCHIVAL_STATUS_DIR, story_id_for_run, "progress_status.json")
    raw_dir_path = os.path.join(test_workspace, RAW_CONTENT_DIR, story_id_for_run)
    processed_dir_path = os.path.join(test_workspace, PROCESSED_CONTENT_DIR, story_id_for_run)

    if os.path.exists(progress_file_path):
        logger.info(f"SUCCESS: Progress file found at {progress_file_path}")
        loaded_p_data = load_progress(story_id_for_run, workspace_root=test_workspace)
        if loaded_p_data.get("downloaded_chapters"):
            logger.info(f"SUCCESS: Progress data contains {len(loaded_p_data['downloaded_chapters'])} chapter entries.")
            if loaded_p_data['downloaded_chapters']: # Check if not empty
                first_chapter_entry = loaded_p_data['downloaded_chapters'][0]
                raw_file_expected = os.path.join(raw_dir_path, first_chapter_entry['local_raw_filename'])
                processed_file_expected = os.path.join(processed_dir_path, first_chapter_entry['local_processed_filename'])
                if os.path.exists(raw_file_expected): logger.info(f"SUCCESS: Raw file for first chapter found: {raw_file_expected}")
                else: logger.error(f"FAILURE: Raw file for first chapter NOT found: {raw_file_expected}")
                if processed_file_expected and os.path.exists(processed_file_expected): logger.info(f"SUCCESS: Processed file for first chapter found: {processed_file_expected}")
                elif processed_file_expected: logger.error(f"FAILURE: Processed file for first chapter NOT found: {processed_file_expected}")
                # If processed_file_expected is None (due to saving error), it's an expected state for this test if that error occurs.
        else:
            logger.warning("WARNING: Progress data does not contain any downloaded chapters.")
    else:
        logger.error(f"FAILURE: Progress file NOT found at {progress_file_path}")

    if os.path.exists(raw_dir_path) and os.listdir(raw_dir_path): logger.info(f"SUCCESS: Raw content directory found and is not empty: {raw_dir_path}")
    else: logger.error(f"FAILURE: Raw content directory NOT found or is empty: {raw_dir_path}")
    if os.path.exists(processed_dir_path) and os.listdir(processed_dir_path): logger.info(f"SUCCESS: Processed content directory found and is not empty: {processed_dir_path}")
    else: logger.error(f"FAILURE: Processed content directory NOT found or is empty: {processed_dir_path}")

    logger.info(f"--- Cleaning up Test Environment: Removing workspace '{test_workspace}' ---")
    if os.path.exists(test_workspace):
        try:
            shutil.rmtree(test_workspace)
            logger.info(f"Successfully removed test workspace: {test_workspace}")
        except Exception as e:
            logger.error(f"Error removing test workspace {test_workspace}: {e}")
    else:
        logger.info(f"Test workspace {test_workspace} not found, no cleanup needed or it failed to create.")

    logger.info("--- Test Script Complete ---")
