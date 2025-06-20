import os
import shutil
import datetime
import copy # Added for deepcopy
from typing import Dict, Any, Optional, Callable, Union # Added Callable and Union
import requests # For specific exception types like requests.exceptions.RequestException

from webnovel_archiver.utils.logger import get_logger # Import logger
from .fetchers.royalroad_fetcher import RoyalRoadFetcher
from .builders.epub_generator import EPUBGenerator # Added EPUBGenerator import
# Assuming StoryMetadata and ChapterInfo will be used from base_fetcher if needed directly
# from .fetchers.base_fetcher import StoryMetadata, ChapterInfo
from .storage.progress_manager import (
    generate_story_id,
    load_progress,
    save_progress
    # DEFAULT_WORKSPACE_ROOT, # Removed
    # ARCHIVAL_STATUS_DIR # Removed
)
from .parsers.html_cleaner import HTMLCleaner
from .modifiers.sentence_remover import SentenceRemover
from .path_manager import PathManager # Added PathManager

# Define directories for simulated content saving (relative to workspace_root)
# RAW_CONTENT_DIR = "raw_content" # Removed
# PROCESSED_CONTENT_DIR = "processed_content" # Removed

# Define ProgressCallback type
ProgressCallback = Callable[[Union[str, Dict[str, Any]]], None]

# Initialize logger for this module
logger = get_logger(__name__)

def archive_story( # Removed DEFAULT_WORKSPACE_ROOT default for workspace_root
    story_url: str,
    workspace_root: str,
    chapters_per_volume: Optional[int] = None,
    ebook_title_override: Optional[str] = None,
    keep_temp_files: bool = False,
    force_reprocessing: bool = False,
    sentence_removal_file: Optional[str] = None, # Will be used fully later
    no_sentence_removal: bool = False,  # Will be used fully later
    progress_callback: Optional[ProgressCallback] = None,
    epub_contents: Optional[str] = 'all' # Added new parameter
) -> Optional[Dict[str, Any]]:
    """
    Orchestrates the archiving process for a given story URL.
    Handles fetching, cleaning, saving, and progress management.
    """
    def _call_progress_callback(message: Union[str, Dict[str, Any]]) -> None:
        if progress_callback:
            try:
                progress_callback(message)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}", exc_info=True)

    _call_progress_callback({"status": "info", "message": "Starting archival process..."})
    logger.info(f"Starting archiving process for: {story_url}")
    logger.info(f"Parameter 'keep_temp_files' is set to: {keep_temp_files}")
    # No explicit deletion logic to modify for now, this is for future reference
    # and to acknowledge the parameter.

    # 1. Fetcher Initialization
    fetcher = RoyalRoadFetcher() # Later, select based on URL or config.

    # 2. Metadata Fetching
    _call_progress_callback({"status": "info", "message": "Fetching story metadata..."})
    logger.info(f"Fetching story metadata for URL: {story_url}")
    try:
        metadata = fetcher.get_story_metadata(story_url)
        logger.info(f"Successfully fetched metadata. Title: {metadata.original_title}")
        _call_progress_callback({"status": "info", "message": f"Successfully fetched metadata: {metadata.original_title}"})
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch story metadata for URL: {story_url}. Network error: {e}")
        _call_progress_callback({"status": "error", "message": f"Failed to fetch story metadata. Network error: {e}"})
        return None
    except Exception as e: # Catch other potential errors from fetcher
        logger.error(f"An unexpected error occurred while fetching story metadata for URL: {story_url}. Error: {e}")
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching story metadata: {e}"})
        return None

    # 3. Chapter List Fetching
    _call_progress_callback({"status": "info", "message": "Fetching chapter list..."})
    logger.info(f"Fetching chapter list for: {metadata.original_title}")
    try:
        chapters_info_list = fetcher.get_chapter_urls(story_url)
        logger.info(f"Found {len(chapters_info_list)} chapters.")
        _call_progress_callback({"status": "info", "message": f"Found {len(chapters_info_list)} chapters."})
        if not chapters_info_list:
            logger.warning("No chapters found. Aborting archival for this story.")
            _call_progress_callback({"status": "warning", "message": "No chapters found. Aborting archival."})
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch chapter list for: {metadata.original_title}. Network error: {e}")
        _call_progress_callback({"status": "error", "message": f"Failed to fetch chapter list. Network error: {e}"})
        return None
    except Exception as e: # Catch other potential errors
        logger.error(f"An unexpected error occurred while fetching chapter list for: {metadata.original_title}. Error: {e}")
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching chapter list: {e}"})
        return None

    # 4. Progress Management (Initial Setup)
    s_id = generate_story_id(url=story_url, title=metadata.original_title)
    metadata.story_id = s_id
    logger.info(f"Generated story ID: {s_id}")

    # Instantiate PathManager
    pm = PathManager(workspace_root, s_id)

    progress_data = load_progress(s_id, workspace_root) # workspace_root is now required

    # Update progress_data with fetched metadata (if not already there or to refresh)
    progress_data["story_id"] = s_id
    progress_data["story_url"] = story_url # or metadata.story_url if it was set by fetcher
    progress_data["original_title"] = metadata.original_title
    progress_data["original_author"] = metadata.original_author
    progress_data["cover_image_url"] = metadata.cover_image_url
    progress_data["synopsis"] = metadata.synopsis
    progress_data["estimated_total_chapters_source"] = metadata.estimated_total_chapters_source
    progress_data["sentence_removal_config_used"] = None # Default if not used

    # Check if we need to look for new chapters from the last known chapter's page
    if progress_data.get("next_chapter_to_download_url") is None and \
       progress_data.get("last_downloaded_chapter_url"):
        last_known_url = progress_data["last_downloaded_chapter_url"]
        logger.info(f"No next chapter URL in progress. Checking for new chapters from the last downloaded page: {last_known_url}")
        try:
            next_page_url = fetcher.get_next_chapter_url_from_page(last_known_url)
            if next_page_url:
                logger.info(f"New chapter detected from last known chapter's page: {next_page_url}. Re-fetching chapter list.")
                _call_progress_callback({"status": "info", "message": "New chapter detected. Re-fetching chapter list..."})

                # Re-fetch the chapter list
                chapters_info_list = fetcher.get_chapter_urls(story_url)
                logger.info(f"Found {len(chapters_info_list)} chapters after refresh.")
                _call_progress_callback({"status": "info", "message": f"Found {len(chapters_info_list)} chapters after refresh."})

                # Potentially update progress_data's view of total chapters if it's stored and used for UI
                # For now, chapters_info_list is updated, which is the primary driver for the loop.
            else:
                logger.info("No new chapters found after checking the last downloaded chapter's page.")
                _call_progress_callback({"status": "info", "message": "No new chapters found by checking last chapter's page."})
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error when trying to check for new chapters from {last_known_url}: {e}")
            _call_progress_callback({"status": "warning", "message": f"Network error checking for new chapters: {e}"})
        except Exception as e:
            logger.error(f"Unexpected error when trying to check for new chapters from {last_known_url}: {e}", exc_info=True)
            _call_progress_callback({"status": "warning", "message": f"Unexpected error checking for new chapters: {e}"})

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
    # processed_chapters_for_this_run = [] # Initialize list for chapters processed in this execution. - NO LONGER USED FOR SUMMARY
    successfully_processed_new_or_updated_count = 0 # For summary reporting
    existing_chapters_map = {}

    if force_reprocessing:
        logger.info("Force reprocessing is ON. All chapters will be fetched and processed anew.")
        progress_data["downloaded_chapters"] = [] # Clear previous chapter progress
    else:
        logger.info("Force reprocessing is OFF. Will attempt to skip already processed chapters if files are valid.")
        if "downloaded_chapters" in progress_data:
            for chap_entry in progress_data.get("downloaded_chapters", []):
                # Index by chapter_url for quick lookup. Ensure chap_entry is a dict and has 'chapter_url'.
                if isinstance(chap_entry, dict) and "chapter_url" in chap_entry:
                    existing_chapters_map[chap_entry["chapter_url"]] = chap_entry
                else:
                    logger.warning(f"Found malformed chapter entry in progress data: {chap_entry}")
        else:
            # If "downloaded_chapters" isn't in progress_data, it's like a first run or cleared progress.
            progress_data["downloaded_chapters"] = []

    total_chapters = len(chapters_info_list)
    for i, chapter_info in enumerate(chapters_info_list):
        _call_progress_callback({
            "status": "info",
            "message": f"Processing chapter: {chapter_info.chapter_title} ({i+1}/{total_chapters})",
            "current_chapter_num": i + 1,
            "total_chapters": total_chapters,
            "chapter_title": chapter_info.chapter_title
        })
        logger.info(f"Processing chapter: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")

        if chapter_info.chapter_url is None:
            logger.warning(f"Chapter {chapter_info.chapter_title} (Order: {chapter_info.download_order}) has no URL. Skipping.")
            _call_progress_callback({
                "status": "warning",
                "message": f"Chapter {chapter_info.chapter_title} has no URL. Skipping.",
                "chapter_title": chapter_info.chapter_title
            })
            continue

        if not force_reprocessing and chapter_info.chapter_url in existing_chapters_map:
            existing_chapter_details = existing_chapters_map[chapter_info.chapter_url]
            # Check if local_raw_filename and local_processed_filename exist and are not None or empty
            raw_filename = existing_chapter_details.get("local_raw_filename")
            processed_filename = existing_chapter_details.get("local_processed_filename")

            if raw_filename and processed_filename:
                raw_file_expected_path = pm.get_raw_content_chapter_filepath(raw_filename)
                processed_file_expected_path = pm.get_processed_content_chapter_filepath(processed_filename)

                if os.path.exists(raw_file_expected_path) and os.path.exists(processed_file_expected_path):
                    logger.info(f"Skipping chapter (already processed, files exist): {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")
                    # Instead of appending to processed_chapters_for_this_run directly,
                    # we will handle this in the new reconciliation logic.
                    # For now, this path means the chapter is considered "processed" for this run.
                    # We need to ensure it's correctly added to updated_downloaded_chapters later.
                    # The old logic of processed_chapters_for_this_run is being replaced.
                else:
                    logger.info(f"Chapter {chapter_info.chapter_title} found in progress, but local files are missing. Reprocessing.")
            else:
                logger.info(f"Chapter {chapter_info.chapter_title} found in progress, but file records are incomplete. Reprocessing.")
        # The main loop for processing chapters will be replaced by the new logic below.

    # New chapter processing logic starts here
    updated_downloaded_chapters = []
    current_time_iso = datetime.datetime.utcnow().isoformat() + "Z"
    source_chapter_urls = {ch_info.chapter_url for ch_info in chapters_info_list}
    existing_chapter_urls_in_progress = {ch_entry["chapter_url"] for ch_entry in progress_data.get("downloaded_chapters", []) if isinstance(ch_entry, dict) and "chapter_url" in ch_entry}

    # Reconcile existing chapters
    for chapter_entry in progress_data.get("downloaded_chapters", []):
        if not (isinstance(chapter_entry, dict) and "chapter_url" in chapter_entry):
            logger.warning(f"Skipping malformed chapter entry in progress: {chapter_entry}")
            continue

        chapter_url = chapter_entry["chapter_url"]
        # Ensure 'status' exists, default to 'unknown' or 'active' if not present
        if 'status' not in chapter_entry:
            chapter_entry['status'] = 'active' # Default for old entries

        if chapter_url not in source_chapter_urls:
            if chapter_entry["status"] == "active": # Only change if it was active
                logger.info(f"Chapter '{chapter_entry.get('chapter_title', chapter_url)}' no longer in source list. Marking as 'archived'.")
                chapter_entry["status"] = "archived"
                _call_progress_callback({
                    "status": "info",
                    "message": f"Chapter '{chapter_entry.get('chapter_title', chapter_url)}' marked as 'archived'.",
                    "chapter_title": chapter_entry.get('chapter_title', chapter_url)
                })

        chapter_entry["last_checked_on"] = current_time_iso
        updated_downloaded_chapters.append(chapter_entry)

    # Process new chapters
    total_source_chapters = len(chapters_info_list)
    for i, chapter_info in enumerate(chapters_info_list):
        _call_progress_callback({
            "status": "info",
            "message": f"Checking chapter: {chapter_info.chapter_title} ({i+1}/{total_source_chapters})",
            "current_chapter_num": i + 1,
            "total_chapters": total_source_chapters, # This is total source chapters, not just new ones
            "chapter_title": chapter_info.chapter_title
        })

        if chapter_info.chapter_url is None:
            logger.warning(f"Chapter {chapter_info.chapter_title} (Order: {chapter_info.download_order}) has no URL. Skipping.")
            _call_progress_callback({
                "status": "warning",
                "message": f"Chapter {chapter_info.chapter_title} has no URL. Skipping.",
                "chapter_title": chapter_info.chapter_title
            })
            continue

        # If chapter is new or needs reprocessing (e.g. due to missing files, or force_reprocessing)
        needs_processing = False
        existing_entry_for_url = next((ch for ch in updated_downloaded_chapters if ch["chapter_url"] == chapter_info.chapter_url), None)

        if chapter_info.chapter_url not in existing_chapter_urls_in_progress:
            logger.info(f"New chapter detected: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")
            needs_processing = True
        elif force_reprocessing:
            logger.info(f"Force reprocessing chapter: {chapter_info.chapter_title}")
            needs_processing = True
            # If force reprocessing, we might want to clear old file references if they change
            if existing_entry_for_url: # Should exist if we are here due to force_reprocessing an existing chapter
                existing_entry_for_url.pop("local_raw_filename", None)
                existing_entry_for_url.pop("local_processed_filename", None)
        elif existing_entry_for_url:
            # Check for missing files for existing (non-new) chapters if not force_reprocessing
            raw_filename = existing_entry_for_url.get("local_raw_filename")
            processed_filename = existing_entry_for_url.get("local_processed_filename")
            if not raw_filename or not processed_filename or \
               not os.path.exists(pm.get_raw_content_chapter_filepath(raw_filename)) or \
               not os.path.exists(pm.get_processed_content_chapter_filepath(processed_filename)):
                logger.info(f"Files missing for existing chapter '{chapter_info.chapter_title}'. Reprocessing.")
                needs_processing = True
            else:
                logger.info(f"Chapter '{chapter_info.chapter_title}' already processed and files exist. Skipping download and processing.")
                # Ensure 'status' is active if it was previously processed and files are okay
                if existing_entry_for_url["status"] != "active": # e.g. if it was 'archived' but reappeared
                     existing_entry_for_url["status"] = "active"
                     logger.info(f"Chapter '{chapter_info.chapter_title}' status updated to 'active' as it reappeared in source.")
                # last_checked_on was already updated for all existing chapters earlier.

        if needs_processing:
            logger.info(f"Processing chapter: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")
            _call_progress_callback({
                "status": "info",
                "message": f"Processing chapter: {chapter_info.chapter_title}",
                "chapter_title": chapter_info.chapter_title
            })

            raw_html_content = None
            try:
                raw_html_content = fetcher.download_chapter_content(chapter_info.chapter_url)
                if raw_html_content == "Chapter content not found.":
                    logger.warning(f"Content div not found for chapter: {chapter_info.chapter_title}. Skipping processing.")
                    _call_progress_callback({
                        "status": "warning",
                        "message": f"Content not found for chapter: {chapter_info.chapter_title}. Skipping.",
                        "chapter_title": chapter_info.chapter_title
                    })
                    # If it was an existing chapter that failed now, its status might need adjustment
                    # or it's kept as is from the reconciliation phase. For new chapters, they just don't get added.
                    if existing_entry_for_url: # If it was an existing chapter
                        existing_entry_for_url["last_checked_on"] = current_time_iso # Ensure it's updated
                        # It will be added to updated_downloaded_chapters via the reconciliation loop's copy
                        # No new entry is created or added here.
                    continue # Skip this chapter
            except requests.exceptions.HTTPError as e:
                logger.error(f"Failed to download chapter: {chapter_info.chapter_title}. HTTP Error: {e}")
                _call_progress_callback({"status": "error", "message": f"Failed to download chapter: {chapter_info.chapter_title}. HTTP Error: {e}", "chapter_title": chapter_info.chapter_title})
                if existing_entry_for_url: existing_entry_for_url["last_checked_on"] = current_time_iso
                continue
            except Exception as e:
                logger.error(f"An unexpected error occurred while downloading chapter: {chapter_info.chapter_title}. Error: {e}")
                _call_progress_callback({"status": "error", "message": f"An unexpected error while downloading: {e}", "chapter_title": chapter_info.chapter_title})
                if existing_entry_for_url: existing_entry_for_url["last_checked_on"] = current_time_iso
                continue

            raw_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}.html"
            # raw_file_directory = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id) # Replaced
            raw_file_directory = pm.get_raw_content_story_dir()
            os.makedirs(raw_file_directory, exist_ok=True)
            # raw_filepath = os.path.join(raw_file_directory, raw_filename) # Replaced
            raw_filepath = pm.get_raw_content_chapter_filepath(raw_filename)

            try:
                with open(raw_filepath, 'w', encoding='utf-8') as f:
                    f.write(raw_html_content)
                logger.info(f"Saved raw content for {chapter_info.chapter_title} to {raw_filepath}")
            except IOError as e:
                logger.error(f"Error saving raw content for {chapter_info.chapter_title} to {raw_filepath}: {e}")
                if existing_entry_for_url: existing_entry_for_url["last_checked_on"] = current_time_iso
                continue

            cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad") # Adapt as needed

            if sentence_removal_file and not no_sentence_removal:
                try:
                    remover = SentenceRemover(sentence_removal_file)
                    if remover.remove_sentences or remover.remove_patterns:
                        cleaned_html_content = remover.remove_sentences_from_html(cleaned_html_content)
                        logger.info(f"Sentence removal applied to chapter: {chapter_info.chapter_title}")
                        progress_data["sentence_removal_config_used"] = sentence_removal_file
                    else:
                        logger.info(f"No sentences matched for removal in chapter: {chapter_info.chapter_title}")
                        progress_data["sentence_removal_config_used"] = sentence_removal_file # Still note config was checked
                except Exception as e:
                    logger.error(f"Failed to apply sentence removal for chapter '{chapter_info.chapter_title}': {e}", exc_info=True)
                    progress_data["sentence_removal_config_used"] = f"Error with {sentence_removal_file}: {e}"
            elif no_sentence_removal:
                progress_data["sentence_removal_config_used"] = "Disabled via --no-sentence-removal"


            processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
            # processed_file_directory = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id) # Replaced
            processed_file_directory = pm.get_processed_content_story_dir()
            os.makedirs(processed_file_directory, exist_ok=True)
            # processed_filepath = os.path.join(processed_file_directory, processed_filename) # Replaced
            processed_filepath = pm.get_processed_content_chapter_filepath(processed_filename)

            try:
                with open(processed_filepath, 'w', encoding='utf-8') as f:
                    f.write(cleaned_html_content)
                logger.info(f"Saved processed content for {chapter_info.chapter_title} to {processed_filepath}")
            except IOError as e:
                logger.error(f"Error saving processed content for {chapter_info.chapter_title} to {processed_filepath}: {e}")
                processed_filename = None # Mark as None if saving failed

            # Update or create chapter entry
            if existing_entry_for_url: # If we are reprocessing an existing chapter
                chapter_detail_entry = existing_entry_for_url
                chapter_detail_entry["status"] = "active" # Ensure it's active after reprocessing
                chapter_detail_entry["download_order"] = chapter_info.download_order # Update order if it changed
                chapter_detail_entry["chapter_title"] = chapter_info.chapter_title # Update title if it changed
                # first_seen_on remains from its original addition
            else: # New chapter
                chapter_detail_entry = {
                    "source_chapter_id": chapter_info.source_chapter_id,
                    "chapter_url": chapter_info.chapter_url,
                    "first_seen_on": current_time_iso,
                    # Add to updated_downloaded_chapters directly if it's truly new
                }
                updated_downloaded_chapters.append(chapter_detail_entry)

            # Common fields for both new and reprocessed existing chapters
            chapter_detail_entry["download_order"] = chapter_info.download_order
            chapter_detail_entry["chapter_title"] = chapter_info.chapter_title
            chapter_detail_entry["local_raw_filename"] = raw_filename
            chapter_detail_entry["local_processed_filename"] = processed_filename
            chapter_detail_entry["download_timestamp"] = current_time_iso # Timestamp of this processing action
            chapter_detail_entry["last_checked_on"] = current_time_iso
            chapter_detail_entry["status"] = "active"
            successfully_processed_new_or_updated_count +=1


            # Update last/next downloaded chapter URLs (simplified)
            # This part needs to be accurate based on the full, ordered list from source
            current_chapter_index_in_source_list = chapters_info_list.index(chapter_info)
            progress_data["last_downloaded_chapter_url"] = chapter_info.chapter_url # Last processed in this run
            if current_chapter_index_in_source_list < len(chapters_info_list) - 1:
                progress_data["next_chapter_to_download_url"] = chapters_info_list[current_chapter_index_in_source_list + 1].chapter_url
            else:
                progress_data["next_chapter_to_download_url"] = None
        # else: chapter already processed and files are fine, or it's an old chapter that's now archived.
        # Its entry in updated_downloaded_chapters (copied from existing) has already been updated (status, last_checked_on).

    # Consolidate and re-order chapters for progress data
    # Step 1: Create a map of all chapters currently in updated_downloaded_chapters (which reflects the latest state after processing)
    # for efficient lookup and modification.
    current_progress_chapters_map = {ch_entry["chapter_url"]: ch_entry for ch_entry in updated_downloaded_chapters}

    # Step 2: Build the new definitive chapter list.
    definitive_chapters_list = []

    # Add chapters that are currently on the source, in the order they appear on the source.
    # Their details (like title, source_chapter_id) should be up-to-date from 'updated_downloaded_chapters'.
    for source_chapter_info in chapters_info_list:
        chapter_to_add = None
        if source_chapter_info.chapter_url in current_progress_chapters_map:
            # This chapter from the source exists in our processed list.
            chapter_to_add = current_progress_chapters_map.pop(source_chapter_info.chapter_url) # Remove from map as it's placed
            # Ensure its status is 'active' as it's currently in the source list.
            chapter_to_add["status"] = "active"
            # Update title and source_chapter_id from the latest fetch, in case they changed on the source.
            old_title = chapter_to_add.get("chapter_title")
            new_title = source_chapter_info.chapter_title
            if old_title != new_title:
                logger.info(f"Chapter title updated for URL '{source_chapter_info.chapter_url}'. From: '{old_title}', To: '{new_title}'.")
                _call_progress_callback({
                    "status": "info",
                    "message": f"Chapter title updated for '{old_title}' to '{new_title}'.",
                    "chapter_url": source_chapter_info.chapter_url,
                    "old_chapter_title": old_title,
                    "new_chapter_title": new_title
                })
            chapter_to_add["chapter_title"] = new_title

            # Similarly, check and log source_chapter_id changes if necessary, though less common for users to track.
            # old_source_id = chapter_to_add.get("source_chapter_id")
            # new_source_id = source_chapter_info.source_chapter_id
            # if old_source_id != new_source_id:
            #     logger.info(f"Chapter source ID updated for URL '{source_chapter_info.chapter_url}'. From: '{old_source_id}', To: '{new_source_id}'.")
            chapter_to_add["source_chapter_id"] = source_chapter_info.source_chapter_id
        else:
            # This implies a chapter is in the source list but was NOT in updated_downloaded_chapters.
            # This should ideally not happen if the main processing loop correctly added all new/reprocessed chapters
            # to updated_downloaded_chapters. This is a safeguard or indicates a potential prior logic gap.
            logger.error(f"CRITICAL LOGIC FLAW: Chapter '{source_chapter_info.chapter_title}' (URL: {source_chapter_info.chapter_url}) "
                         f"from source was not found in 'updated_downloaded_chapters'. This chapter will be missing "
                         f"from the final EPUB and progress data unless handled. This indicates an issue in the main "
                         f"chapter processing loop where new or reprocessed chapters are added/updated in 'updated_downloaded_chapters'.")
            # For now, we skip adding it as we don't have its full details (like local file paths).
            continue

        if chapter_to_add:
            definitive_chapters_list.append(chapter_to_add)

    # Step 3: Add remaining chapters from current_progress_chapters_map.
    # These are chapters that were in 'updated_downloaded_chapters' but are no longer on the source
    # (i.e., they should be marked 'archived').
    # They are added after the active chapters. We sort them by their original 'download_order'
    # (or another field like 'first_seen_on' if 'download_order' is unreliable for archived items)
    # to maintain their relative order as much as possible.
    archived_chapters_to_add = sorted(current_progress_chapters_map.values(), key=lambda ch: (ch.get("download_order", float('inf')), ch.get("first_seen_on", "")))
    for archived_chapter in archived_chapters_to_add:
        archived_chapter["status"] = "archived" # Ensure status is correctly set
        definitive_chapters_list.append(archived_chapter)
        logger.info(f"Appending archived chapter '{archived_chapter.get('chapter_title', archived_chapter['chapter_url'])}' to the definitive list.")

    # Step 4: Re-assign 'download_order' sequentially to the entire definitive_chapters_list.
    # This ensures unique, sequential ordering for EPUB generation and for storage in progress.json.
    for i, chapter_entry in enumerate(definitive_chapters_list):
        chapter_entry["download_order"] = i + 1
        logger.debug(f"Final order assignment: {chapter_entry['download_order']} -> {chapter_entry.get('chapter_title', chapter_entry['chapter_url'])} (Status: {chapter_entry['status']})")

    progress_data["downloaded_chapters"] = definitive_chapters_list
    # The old `processed_chapters_for_this_run` variable is no longer used for this assignment.

    # 5. EPUB Generation
    if ebook_title_override:
        logger.info(f"Overriding ebook title with: '{ebook_title_override}'")
        progress_data["effective_title"] = ebook_title_override
    else:
        # Use original_title if override is not provided, ensure it exists or use a default
        progress_data["effective_title"] = progress_data.get("original_title", "Untitled Story")

    # The EPUBGenerator will need to be aware of "effective_title".
    # For now, this subtask focuses on adding it to progress_data.
    # A later step or a note for EPUBGenerator modification might be needed if it
    # strictly uses "original_title" and cannot be configured.

    _call_progress_callback({"status": "info", "message": "Starting EPUB generation..."})
    logger.info(f"Starting EPUB generation for story ID: {s_id}")

    # Filter chapters for EPUB generation based on epub_contents
    progress_data_for_epub: Dict[str, Any]
    if epub_contents == 'active-only':
        logger.info("EPUB generation set to 'active-only', filtering chapters.")
        _call_progress_callback({"status": "info", "message": "Filtering chapters for EPUB: including 'active' only."})
        progress_data_for_epub = copy.deepcopy(progress_data)

        original_chapter_count = len(progress_data_for_epub.get("downloaded_chapters", []))
        active_chapters = [
            ch for ch in progress_data_for_epub.get("downloaded_chapters", [])
            if isinstance(ch, dict) and ch.get("status") == "active"
        ]
        progress_data_for_epub["downloaded_chapters"] = active_chapters
        filtered_count = original_chapter_count - len(active_chapters)
        logger.info(f"Filtered out {filtered_count} non-active chapters for EPUB generation.")
        _call_progress_callback({"status": "info", "message": f"Filtered out {filtered_count} non-active chapters. Using {len(active_chapters)} for EPUB."})
    else:
        logger.info("EPUB generation set to 'all', including all downloaded chapters.")
        _call_progress_callback({"status": "info", "message": "Including all downloaded chapters in EPUB."})
        # No need to deepcopy if we are not modifying the chapter list for EPUB generation specifically
        # However, if EPUBGenerator modifies progress_data internally, a deepcopy might be safer.
        # For now, assuming EPUBGenerator reads but does not modify progress_data in ways that affect the original.
        progress_data_for_epub = progress_data


    epub_generator = EPUBGenerator(pm) # Pass PathManager instance
    generated_epub_files = epub_generator.generate_epub(progress_data_for_epub, chapters_per_volume) # s_id and workspace_root are in pm

    # Initialize progress_data["last_epub_processing"] if it's not a dict
    if not isinstance(progress_data.get("last_epub_processing"), dict):
        progress_data["last_epub_processing"] = {}

    progress_data["last_epub_processing"]["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    progress_data["last_epub_processing"]["generated_epub_files"] = generated_epub_files
    progress_data["last_epub_processing"]["chapters_included_in_last_volume"] = None # Per schema guidance

    if generated_epub_files:
        logger.info(f"Successfully generated {len(generated_epub_files)} EPUB file(s) for story ID {s_id}: {generated_epub_files}")
        _call_progress_callback({"status": "info", "message": f"Successfully generated EPUB file(s): {generated_epub_files}", "file_paths": generated_epub_files})
    else:
        logger.warning(f"No EPUB files were generated for story ID {s_id}.")
        _call_progress_callback({"status": "warning", "message": "No EPUB files were generated."})
        # Ensure generated_epub_files is an empty list in progress_data if none were made
        progress_data["last_epub_processing"]["generated_epub_files"] = []


    # 6. Save Final Progress
    logger.info("Saving final progress status...")
    try:
        # Update last_archived_timestamp before final save
        progress_data["last_archived_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_progress(s_id, progress_data, workspace_root) # workspace_root is required
        logger.info(f"Progress saved (including last_archived_timestamp) to {pm.get_progress_filepath()}")
    except Exception as e:
        logger.error(f"Error saving progress for story ID {s_id}: {e}")

    # 7. Clean up temporary files if not requested to keep them
    if not keep_temp_files:
        _call_progress_callback({"status": "info", "message": "Cleaning up temporary files..."})
        logger.info(f"Attempting to remove temporary content directories for story ID: {s_id}")
        raw_story_dir = pm.get_raw_content_story_dir()
        processed_story_dir = pm.get_processed_content_story_dir()

        try:
            if os.path.exists(raw_story_dir):
                shutil.rmtree(raw_story_dir)
                logger.info(f"Successfully removed raw content directory: {raw_story_dir}")
            else:
                logger.info(f"Raw content directory not found, no need to remove: {raw_story_dir}")

            if os.path.exists(processed_story_dir):
                shutil.rmtree(processed_story_dir) # Ensuring this is active for cleanup
                logger.info(f"Successfully removed processed content directory: {processed_story_dir}")
            else:
                logger.info(f"Processed content directory not found, no need to remove: {processed_story_dir}")
            _call_progress_callback({"status": "info", "message": "Successfully cleaned up temporary files."})
        except OSError as e: # shutil.rmtree can raise OSError
            logger.error(f"Error removing temporary content directories for story ID {s_id}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Error cleaning up temporary files: {e}"})
        except Exception as e: # Catch any other unexpected errors during cleanup
            logger.error(f"An unexpected error occurred during temporary file cleanup for story ID {s_id}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"An unexpected error occurred during temporary file cleanup: {e}"})
    else:
        logger.info(f"Keeping temporary content directories for story ID: {s_id} as per 'keep_temp_files' flag.")

    _call_progress_callback({"status": "info", "message": "Archival process completed."})
    logger.info(f"Archiving process completed for story ID: {s_id}")

    summary = {
        "story_id": s_id,
        "title": progress_data.get("effective_title", metadata.original_title), # effective_title is set before EPUB gen
        "chapters_processed": successfully_processed_new_or_updated_count, # Use the new counter
        "epub_files": [os.path.abspath(f) for f in generated_epub_files if f], # Ensure absolute paths and filter None
        "workspace_root": os.path.abspath(workspace_root)
    }
    return summary

if __name__ == '__main__':
    import shutil
    # Setup basic logging for the __main__ block if you want to see Orchestrator logs
    # This is separate from the logger used within the Orchestrator module itself if it's configured.

    test_story_url = "https://www.royalroad.com/fiction/117255/rend"
    test_workspace = "temp_workspace_orchestrator_tests"

    story_id_for_run = generate_story_id(url=test_story_url) # For verification path
    # Instantiate PathManager for the test block
    pm_test = PathManager(test_workspace, story_id_for_run)

    logger.info(f"--- Preparing Test Environment: Cleaning workspace '{test_workspace}' ---")
    if os.path.exists(test_workspace):
        shutil.rmtree(test_workspace)
    os.makedirs(test_workspace, exist_ok=True)

    logger.info(f"--- Running Orchestrator Test for: {test_story_url} ---")
    logger.info(f"--- Workspace: {test_workspace} ---")

    # workspace_root is now a required argument for archive_story
    archive_story(test_story_url, workspace_root=test_workspace, keep_temp_files=True) # keep_temp_files for verification

    logger.info(f"--- Orchestrator Test Run Finished ---")

    logger.info("--- Verifying Created Files (Basic Checks) ---")
    progress_file_path = pm_test.get_progress_filepath()
    raw_dir_path = pm_test.get_raw_content_story_dir()
    processed_dir_path = pm_test.get_processed_content_story_dir()

    if os.path.exists(progress_file_path):
        logger.info(f"SUCCESS: Progress file found at {progress_file_path}")
        loaded_p_data = load_progress(story_id_for_run, workspace_root=test_workspace) # workspace_root required
        if loaded_p_data.get("downloaded_chapters"):
            logger.info(f"SUCCESS: Progress data contains {len(loaded_p_data['downloaded_chapters'])} chapter entries.")
            if loaded_p_data['downloaded_chapters']: # Check if not empty
                first_chapter_entry = loaded_p_data['downloaded_chapters'][0]
                # Use PathManager to construct expected file paths
                raw_file_expected = pm_test.get_raw_content_chapter_filepath(first_chapter_entry['local_raw_filename'])
                processed_file_expected = pm_test.get_processed_content_chapter_filepath(first_chapter_entry['local_processed_filename'])
                if os.path.exists(raw_file_expected): logger.info(f"SUCCESS: Raw file for first chapter found: {raw_file_expected}")
                else: logger.error(f"FAILURE: Raw file for first chapter NOT found: {raw_file_expected}")
                if processed_file_expected and os.path.exists(processed_file_expected): logger.info(f"SUCCESS: Processed file for first chapter found: {processed_file_expected}")
                elif processed_file_expected: logger.error(f"FAILURE: Processed file for first chapter NOT found: {processed_file_expected}")
                # If processed_file_expected is None (due to saving error), it's an expected state for this test if that error occurs.
        else:
            logger.warning("WARNING: Progress data does not contain any downloaded chapters.")
    else:
        logger.error(f"FAILURE: Progress file NOT found at {progress_file_path}")

    # Check raw_dir_path and processed_dir_path existence after keep_temp_files=True
    if os.path.exists(raw_dir_path) and os.listdir(raw_dir_path):
        logger.info(f"SUCCESS: Raw content directory found and is not empty: {raw_dir_path}")
    else:
        logger.error(f"FAILURE: Raw content directory NOT found or is empty: {raw_dir_path}")

    if os.path.exists(processed_dir_path) and os.listdir(processed_dir_path):
        logger.info(f"SUCCESS: Processed content directory found and is not empty: {processed_dir_path}")
    else:
        logger.error(f"FAILURE: Processed content directory NOT found or is empty: {processed_dir_path}")


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
