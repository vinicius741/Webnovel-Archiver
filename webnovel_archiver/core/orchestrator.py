import os
import datetime
from typing import Dict, Any

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


def archive_story(story_url: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> None:
    """
    Orchestrates the archiving process for a given story URL.
    Phase 1: Fetches metadata, chapter list, simulates downloads, cleans HTML,
             and manages progress_status.json.
    """
    print(f"Starting archiving process for: {story_url}")

    # 1. Fetcher Initialization
    # For Phase 1, RoyalRoadFetcher is hardcoded.
    # Later, this could be selected based on URL or config.
    fetcher = RoyalRoadFetcher()

    # 2. Metadata and Chapter List Fetching
    # The fetcher methods currently use embedded example HTML for the given URL.
    print("Fetching story metadata...")
    try:
        metadata = fetcher.get_story_metadata(story_url)
        print(f"Successfully fetched metadata for title: {metadata.original_title}")
    except Exception as e:
        print(f"Error fetching story metadata: {e}")
        return

    print("Fetching chapter list...")
    try:
        chapters_info_list = fetcher.get_chapter_urls(story_url)
        print(f"Found {len(chapters_info_list)} chapters.")
        if not chapters_info_list:
            print("No chapters found. Aborting.")
            return
    except Exception as e:
        print(f"Error fetching chapter list: {e}")
        return

    # 3. Progress Management (Initial Setup)
    # Generate story_id (this might use metadata.original_title if URL parsing fails)
    s_id = generate_story_id(url=story_url, title=metadata.original_title)
    metadata.story_id = s_id # Store generated ID in metadata object as well for consistency

    print(f"Generated story ID: {s_id}")

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

    # Clear existing chapters in progress if we are reprocessing all,
    # or implement merging logic later. For now, let's rebuild it.
    processed_chapter_details = []

    for chapter_info in chapters_info_list:
        print(f"Processing chapter: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")

        # Simulate download
        raw_html_content = fetcher.download_chapter_content(chapter_info.chapter_url)

        # Define simulated filenames/paths
        # Filenames could be chapter_info.source_chapter_id or zero-padded download_order
        raw_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}.html"
        # raw_filepath = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id, raw_filename)
        # print(f"Simulating save of raw content to: {raw_filepath}") # Actual file write deferred

        processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
        # processed_filepath = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id, processed_filename)

        # Clean HTML
        print(f"Cleaning HTML for: {chapter_info.chapter_title}")
        cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad")
        # print(f"Simulating save of processed content to: {processed_filepath}") # Actual file write deferred

        # Update progress_status.json with downloaded chapter details
        chapter_detail_entry = {
            "source_chapter_id": chapter_info.source_chapter_id,
            "download_order": chapter_info.download_order,
            "chapter_url": chapter_info.chapter_url,
            "chapter_title": chapter_info.chapter_title,
            "local_raw_filename": raw_filename, # Store relative path or just filename
            "local_processed_filename": processed_filename, # Store relative path or just filename
            "download_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            # "next_chapter_url_from_page": chapter_info.next_chapter_url_from_page # If available from ChapterInfo
        }
        processed_chapter_details.append(chapter_detail_entry)

        # Update last downloaded and next to download (simplified for linear processing)
        progress_data["last_downloaded_chapter_url"] = chapter_info.chapter_url
        if chapter_info.download_order < len(chapters_info_list):
            progress_data["next_chapter_to_download_url"] = chapters_info_list[chapter_info.download_order].chapter_url
        else:
            progress_data["next_chapter_to_download_url"] = None


    progress_data["downloaded_chapters"] = processed_chapter_details # Replace with the newly processed list

    # 5. Save Final Progress
    print("Saving final progress status...")
    try:
        save_progress(s_id, progress_data, workspace_root)
        print(f"Progress saved to {os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, s_id, 'progress_status.json')}")
    except Exception as e:
        print(f"Error saving progress: {e}")

    print("Archiving process completed.")

if __name__ == '__main__':
    # Example usage:
    # This URL should match the one for which RoyalRoadFetcher has example HTML.
    test_story_url = "https://www.royalroad.com/fiction/117255/rend"

    # Define a test workspace directory (it will be created if it doesn't exist by save_progress)
    test_workspace = "temp_workspace_orchestrator"

    print(f"--- Running Orchestrator for: {test_story_url} ---")
    print(f"--- Output will be in (simulated): {test_workspace} ---")

    # Clean up old test workspace if it exists to ensure a fresh run for the example
    # More robust cleanup would be `shutil.rmtree(test_workspace, ignore_errors=True)`
    # but let's stick to os for now if shutil is not assumed.
    # For simplicity in this subtask, we'll let save_progress create it.
    # If you run this multiple times, the progress file will be overwritten.

    # Check if progress file exists from a previous run and remove it for a clean test
    # This is simplified; proper test setup/teardown is better.
    story_id_for_cleanup = generate_story_id(url=test_story_url) # Use the same title as in the test to get the same ID
    progress_file_path_for_cleanup = os.path.join(test_workspace, ARCHIVAL_STATUS_DIR, story_id_for_cleanup, "progress_status.json")
    if os.path.exists(progress_file_path_for_cleanup):
        print(f"Removing existing test progress file: {progress_file_path_for_cleanup}")
        os.remove(progress_file_path_for_cleanup)
        # Try to remove the story_id directory if it's empty
        try:
            os.rmdir(os.path.dirname(progress_file_path_for_cleanup))
        except OSError:
            pass # Fine if it's not empty or fails

    archive_story(test_story_url, workspace_root=test_workspace)

    print(f"--- Orchestrator Test Run Finished ---")
    print(f"Verify the content of '{progress_file_path_for_cleanup}' (if desired).")
    # You would typically add assertions here in a real test suite.
    # e.g., assert os.path.exists(progress_file_path_for_cleanup)
    # loaded_p_data = load_progress(story_id_for_cleanup, workspace_root=test_workspace)
    # assert loaded_p_data["original_title"] == "REND"
    # assert len(loaded_p_data["downloaded_chapters"]) > 0

    # Consider adding a prompt to manually clean up 'temp_workspace_orchestrator' or do it if empty.
    # For now, it will persist. If this were a unit test, teardown would handle it.
    print(f"Note: The directory '{test_workspace}' was used. You may want to inspect or remove it manually.")
