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

        raw_file_directory = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id)
        os.makedirs(raw_file_directory, exist_ok=True)
        raw_filepath = os.path.join(raw_file_directory, raw_filename)

        try:
            with open(raw_filepath, 'w', encoding='utf-8') as f:
                f.write(raw_html_content)
            print(f"Successfully saved raw content to: {raw_filepath}")
        except IOError as e:
            print(f"Error saving raw content to {raw_filepath}: {e}")
            # Decide if you want to continue to the next chapter or abort
            # For now, let's print error and continue
            continue

        processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
        # processed_filepath = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id, processed_filename)

        # Clean HTML
        print(f"Cleaning HTML for: {chapter_info.chapter_title}")
        cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad")

        processed_file_directory = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id)
        os.makedirs(processed_file_directory, exist_ok=True)
        processed_filepath = os.path.join(processed_file_directory, processed_filename)

        try:
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_html_content)
            print(f"Successfully saved processed content to: {processed_filepath}")
        except IOError as e:
            print(f"Error saving processed content to {processed_filepath}: {e}")
            # Decide if you want to update progress_data with this chapter if processed saving fails
            # For now, let's assume if raw is saved, we still record the chapter,
            # but processed_filename might be None or error noted.
            # The current structure adds chapter_detail_entry later, so it will include processed_filename
            # regardless. This might need refinement based on desired error handling.
            # For now, just print and continue.

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
    import shutil

    test_story_url = "https://www.royalroad.com/fiction/117255/rend"
    test_workspace = "temp_workspace_orchestrator_tests" # Changed name slightly for clarity

    story_id_for_run = generate_story_id(url=test_story_url)

    # --- Setup: Clean workspace before run ---
    print(f"--- Preparing Test Environment: Cleaning workspace '{test_workspace}' ---")
    if os.path.exists(test_workspace):
        shutil.rmtree(test_workspace)
    os.makedirs(test_workspace, exist_ok=True) # Create the base test workspace

    print(f"--- Running Orchestrator Test for: {test_story_url} ---")
    print(f"--- Workspace: {test_workspace} ---")

    archive_story(test_story_url, workspace_root=test_workspace)

    print(f"--- Orchestrator Test Run Finished ---")

    # --- Verification ---
    print("--- Verifying Created Files (Basic Checks) ---")
    progress_file_path = os.path.join(test_workspace, ARCHIVAL_STATUS_DIR, story_id_for_run, "progress_status.json")
    raw_dir_path = os.path.join(test_workspace, RAW_CONTENT_DIR, story_id_for_run)
    processed_dir_path = os.path.join(test_workspace, PROCESSED_CONTENT_DIR, story_id_for_run)

    if os.path.exists(progress_file_path):
        print(f"SUCCESS: Progress file found at {progress_file_path}")
        # Further check: load progress and see if it has chapters
        loaded_p_data = load_progress(story_id_for_run, workspace_root=test_workspace)
        if loaded_p_data.get("downloaded_chapters"):
            print(f"SUCCESS: Progress data contains {len(loaded_p_data['downloaded_chapters'])} chapter entries.")

            # Check for first chapter's raw and processed files (example)
            first_chapter_entry = loaded_p_data['downloaded_chapters'][0]
            raw_file_expected = os.path.join(raw_dir_path, first_chapter_entry['local_raw_filename'])
            processed_file_expected = os.path.join(processed_dir_path, first_chapter_entry['local_processed_filename'])

            if os.path.exists(raw_file_expected):
                print(f"SUCCESS: Raw file for first chapter found: {raw_file_expected}")
            else:
                print(f"FAILURE: Raw file for first chapter NOT found: {raw_file_expected}")

            if os.path.exists(processed_file_expected):
                print(f"SUCCESS: Processed file for first chapter found: {processed_file_expected}")
            else:
                print(f"FAILURE: Processed file for first chapter NOT found: {processed_file_expected}")
        else:
            print("WARNING: Progress data does not contain any downloaded chapters.")

    else:
        print(f"FAILURE: Progress file NOT found at {progress_file_path}")

    if os.path.exists(raw_dir_path) and os.listdir(raw_dir_path):
        print(f"SUCCESS: Raw content directory found and is not empty: {raw_dir_path}")
    else:
        print(f"FAILURE: Raw content directory NOT found or is empty: {raw_dir_path}")

    if os.path.exists(processed_dir_path) and os.listdir(processed_dir_path):
        print(f"SUCCESS: Processed content directory found and is not empty: {processed_dir_path}")
    else:
        print(f"FAILURE: Processed content directory NOT found or is empty: {processed_dir_path}")

    # --- Cleanup: Remove test workspace after run ---
    print(f"--- Cleaning up Test Environment: Removing workspace '{test_workspace}' ---")
    if os.path.exists(test_workspace):
        try:
            shutil.rmtree(test_workspace)
            print(f"Successfully removed test workspace: {test_workspace}")
        except Exception as e:
            print(f"Error removing test workspace {test_workspace}: {e}")
    else:
        print(f"Test workspace {test_workspace} not found, no cleanup needed or it failed to create.")

    print("--- Test Script Complete ---")
