import os
import shutil
import datetime
import time # Added for time.sleep
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
    save_progress,
    DEFAULT_WORKSPACE_ROOT, # For constructing paths if needed for simulation
    ARCHIVAL_STATUS_DIR
)
from .parsers.html_cleaner import HTMLCleaner
from .modifiers.sentence_remover import SentenceRemover

# Define directories for simulated content saving (relative to workspace_root)
RAW_CONTENT_DIR = "raw_content"
PROCESSED_CONTENT_DIR = "processed_content"

# Define ProgressCallback type
ProgressCallback = Callable[[Union[str, Dict[str, Any]]], None]

# Initialize logger for this module
logger = get_logger(__name__)

def archive_story(
    story_url: str,
    workspace_root: str = DEFAULT_WORKSPACE_ROOT,
    chapters_per_volume: Optional[int] = None,
    ebook_title_override: Optional[str] = None,
    keep_temp_files: bool = False,
    force_reprocessing: bool = False,
    sentence_removal_file: Optional[str] = None, # Will be used fully later
    no_sentence_removal: bool = False,  # Will be used fully later
    progress_callback: Optional[ProgressCallback] = None,
    epub_contents: Optional[str] = 'all', # Added new parameter
    resume_from_url: Optional[str] = None,
    chapter_limit_for_run: Optional[int] = None
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

    progress_data = load_progress(s_id, workspace_root)

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
    # processed_chapters_for_this_run = [] # Initialize list for chapters processed in this execution. # Old logic
    # existing_chapters_map = {} # Old logic

    # Initialize for new chapter reconciliation
    existing_chapters_map = {}
    max_existing_order = 0
    if not force_reprocessing and progress_data.get("downloaded_chapters"): # Only populate if not force_reprocessing
        logger.info(f"Processing {len(progress_data['downloaded_chapters'])} existing chapter entries for reconciliation.")
        for chap_entry in progress_data["downloaded_chapters"]:
            if isinstance(chap_entry, dict) and "chapter_url" in chap_entry: # Ensure entry is valid
                existing_chapters_map[chap_entry["chapter_url"]] = chap_entry
                max_existing_order = max(max_existing_order, chap_entry.get("download_order", 0))
            else:
                logger.warning(f"Found malformed chapter entry in progress data, skipping: {chap_entry.get('chapter_title', 'N/A')}")
        logger.info(f"Max existing download_order initialized to: {max_existing_order}")
    elif force_reprocessing:
        logger.info("Force reprocessing is ON. Existing chapter entries will be ignored for initial mapping, and all chapters will be processed anew.")
        progress_data["downloaded_chapters"] = [] # Clear previous chapter progress if forcing
    else:
        logger.info("No existing downloaded chapters found in progress data or force_reprocessing is off. Starting fresh chapter list.")
        progress_data["downloaded_chapters"] = []


    total_chapters = len(chapters_info_list) # This is total from source, used for progress reporting
    # The loop below is the OLD chapter processing loop. It will be replaced.
    # For now, parts of it are commented out or adjusted to avoid conflict with the NEW logic that will be inserted later.
    # This is a temporary state during refactoring.

    # --- OLD CHAPTER PROCESSING LOOP (TO BE REPLACED) ---
    # for i, chapter_info in enumerate(chapters_info_list):
    #    _call_progress_callback({
    # ... (rest of the old loop, which will be removed) ...
    # The new logic will replace this loop structure.
    # For now, let's imagine this loop is bypassed and we jump to where the new logic would start.
    # The following lines are just to make the code runnable if the new logic isn't fully in place yet.
    # This entire for loop (the old one) needs to be removed and replaced.
    # For the purpose of this multi-turn application, we assume this old loop
    # from line ~180 to ~220 in the original snapshot is what we are replacing.
    # The following is a placeholder for the new logic's starting point.

    # --- START OF NEW RECONCILIATION LOGIC (replaces the above loop and subsequent old reconciliation) ---

    # total_chapters = len(chapters_info_list) # Already defined
    for i, chapter_info in enumerate(chapters_info_list): # This is a simplified loop for the purpose of the diff
        _call_progress_callback({
            "status": "info",
            "message": f"Processing chapter: {chapter_info.chapter_title} ({i+1}/{total_chapters})", # This message might need adjustment based on new loop context
            "current_chapter_num": i + 1, # This 'i' is from the new loop over chapters_info_list
            "total_chapters": total_chapters, # Total chapters from source
            "chapter_title": chapter_info.chapter_title
        })
        # logger.info(f"Processing chapter: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})") # Example of old log

        # The actual processing logic (downloading, cleaning, saving) will be part of the new loop structure.
        # This diff is primarily about setting up the initial `existing_chapters_map` and `max_existing_order`,
        # and preparing the ground for the new loop.
        # The old loop and its conditions (like checking force_reprocessing inside the loop for skipping)
        # are effectively being replaced.

    # --- END OF OLD CHAPTER PROCESSING LOGIC PLACEHOLDER ---

    # --- START OF NEW DETAILED RECONCILIATION AND PROCESSING LOGIC ---
    # This is where steps 2-5 of the plan will be implemented.
    # The loop `for i, chapter_info in enumerate(chapters_info_list):` above was part of the old structure
    # and will be replaced by a new loop as per the plan.
    # The `existing_chapters_map` and `max_existing_order` are now initialized correctly.

    # Step 2: Initialize updated_downloaded_chapters, current_time_iso, source_chapter_urls_on_fetcher
    updated_downloaded_chapters = []
    current_time_iso = datetime.datetime.utcnow().isoformat() + "Z"
    source_chapter_urls_on_fetcher = {chap_info.chapter_url for chap_info in chapters_info_list}

    chapters_processed_in_this_run = 0 # For chapter_limit_for_run
    chapters_downloaded_in_this_run = 0


    # Step 3: Iterate through chapters_info_list (chapters from the fetcher)
    # Sort chapters_info_list by order_id from source to ensure processing in intended sequence.
    # This is important for assigning `download_order` to new chapters correctly and for resume logic.
    chapters_info_list.sort(key=lambda c: c.download_order if c.download_order is not None else float('inf'))

    # Determine effective start index for chapter_limit_for_run, respecting resume_from_url
    effective_start_idx_for_limit = 0
    if resume_from_url and not force_reprocessing:
        for k, chap_info_resume_check in enumerate(chapters_info_list):
            if chap_info_resume_check.chapter_url == resume_from_url:
                effective_start_idx_for_limit = k
                logger.info(f"Chapter limit counting will effectively start from index {k} due to resume_from_url: {resume_from_url}")
                break

    for idx, chapter_info in enumerate(chapters_info_list):
        chapter_url = chapter_info.chapter_url

        if chapter_url is None: # Should have been caught earlier, but good to double check
            logger.warning(f"Chapter {chapter_info.chapter_title} (Order: {chapter_info.download_order}) has no URL in main processing loop. Skipping.")
            _call_progress_callback({"status": "warning", "message": f"Chapter {chapter_info.chapter_title} has no URL. Skipping."})
            continue

        _call_progress_callback({
            "status": "info",
            "message": f"Reconciling chapter: {chapter_info.chapter_title} ({idx+1}/{total_chapters})",
            "current_chapter_num": idx + 1,
            "total_chapters": total_chapters,
            "chapter_title": chapter_info.chapter_title
        })

        if chapter_url in existing_chapters_map:
            existing_chapter_entry = existing_chapters_map.pop(chapter_url) # Remove as it's found

            # Update existing entry
            existing_chapter_entry["status"] = "active" # Mark as active since it's in current source list
            existing_chapter_entry["last_checked_on"] = current_time_iso
            if existing_chapter_entry.get("chapter_title") != chapter_info.chapter_title:
                logger.info(f"Title change for chapter {chapter_url}: '{existing_chapter_entry.get('chapter_title')}' -> '{chapter_info.chapter_title}'")
                existing_chapter_entry["chapter_title"] = chapter_info.chapter_title
            if existing_chapter_entry.get("source_chapter_id") != chapter_info.source_chapter_id: # Assuming ChapterInfo has source_chapter_id
                logger.info(f"Source ID change for chapter {chapter_url}: '{existing_chapter_entry.get('source_chapter_id')}' -> '{chapter_info.source_chapter_id}'")
                existing_chapter_entry["source_chapter_id"] = chapter_info.source_chapter_id
            # download_order remains existing_chapter_entry["download_order"]

            needs_processing = False
            if force_reprocessing:
                needs_processing = True
                logger.info(f"Force reprocessing chapter: {existing_chapter_entry['chapter_title']}")
            elif existing_chapter_entry.get("status") in ["failed", "incomplete_download"]: # Assuming these statuses exist
                needs_processing = True
                logger.info(f"Reprocessing previously failed/incomplete chapter: {existing_chapter_entry['chapter_title']}")
            else:
                raw_file_exists = existing_chapter_entry.get("local_raw_filename") and \
                                  os.path.exists(os.path.join(workspace_root, RAW_CONTENT_DIR, s_id, existing_chapter_entry["local_raw_filename"]))
                processed_file_exists = existing_chapter_entry.get("local_processed_filename") and \
                                        os.path.exists(os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id, existing_chapter_entry["local_processed_filename"]))
                if not raw_file_exists or not processed_file_exists:
                    needs_processing = True
                    logger.info(f"Reprocessing chapter due to missing files: {existing_chapter_entry['chapter_title']}")
                    if not raw_file_exists: logger.debug(f"Missing raw file for {chapter_url}")
                    if not processed_file_exists: logger.debug(f"Missing processed file for {chapter_url}")

            if needs_processing:
                # Apply chapter_limit_for_run, but only count chapters that are actually processed (downloaded)
                # And only if current chapter index `idx` is at or after `effective_start_idx_for_limit`
                if chapter_limit_for_run > 0 and chapters_downloaded_in_this_run >= chapter_limit_for_run and idx >= effective_start_idx_for_limit:
                    logger.info(f"Chapter download limit ({chapter_limit_for_run}) reached for this run. Will resume later.")
                    # Add back to existing_chapters_map so it's handled as "not processed in this run"
                    existing_chapters_map[chapter_url] = existing_chapter_entry
                    break # Exit the loop over chapters_info_list

                logger.info(f"Processing content for existing chapter: {chapter_info.chapter_title}")
                # Download, clean, save (similar to lines 228-287 in original task, adapted)
                try:
                    # Filename generation (use existing download_order)
                    # slug_title = slugify(chapter_info.chapter_title if chapter_info.chapter_title else f"chapter-{existing_chapter_entry['download_order']}")
                    # base_filename = f"ch_{existing_chapter_entry['download_order']:04d}_{slug_title}"
                    # Using source_chapter_id and download_order for filenames
                    # Ensure download_order is available and numeric, or use a fallback.
                    order_for_filename = existing_chapter_entry.get('download_order', idx) # Use existing or current index as fallback
                    if not isinstance(order_for_filename, int): order_for_filename = idx # Ensure it's an int

                    # Filenames should be relative to their respective directories (RAW_CONTENT_DIR/s_id or PROCESSED_CONTENT_DIR/s_id)
                    # The main paths (e.g., raw_file_directory) are defined outside this part.
                    raw_filename_leaf = f"chapter_{str(order_for_filename).zfill(5)}_{chapter_info.source_chapter_id}.html"
                    processed_filename_leaf = f"chapter_{str(order_for_filename).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"

                    raw_file_abs_path = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id, raw_filename_leaf)
                    processed_file_abs_path = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id, processed_filename_leaf)
                    os.makedirs(os.path.dirname(raw_file_abs_path), exist_ok=True)
                    os.makedirs(os.path.dirname(processed_file_abs_path), exist_ok=True)

                    content_html = fetcher.download_chapter_content(chapter_info.chapter_url) # Assuming this method exists
                    if content_html == "Chapter content not found.": # Check for specific message from fetcher
                         raise ValueError("Chapter content not found by fetcher.")

                    with open(raw_file_abs_path, "w", encoding="utf-8") as f: f.write(content_html)
                    existing_chapter_entry["local_raw_filename"] = raw_filename_leaf
                    logger.debug(f"Raw content saved to {raw_filename_leaf}")

                    cleaned_html = html_cleaner.clean_html(content_html, source_site="royalroad") # TODO: make source_site dynamic
                    # Apply sentence removal if configured
                    if sentence_removal_file and not no_sentence_removal:
                        remover = SentenceRemover(sentence_removal_file)
                        if remover.remove_sentences or remover.remove_patterns:
                            cleaned_html = remover.remove_sentences_from_html(cleaned_html)
                            progress_data["sentence_removal_config_used"] = sentence_removal_file
                    elif no_sentence_removal:
                         progress_data["sentence_removal_config_used"] = "Disabled via --no-sentence-removal"


                    if not cleaned_html:
                        logger.warning(f"Cleaner returned no content for {chapter_info.chapter_title}. Skipping processed file saving.")
                        existing_chapter_entry["local_processed_filename"] = None
                    else:
                        with open(processed_file_abs_path, "w", encoding="utf-8") as f: f.write(cleaned_html)
                        existing_chapter_entry["local_processed_filename"] = processed_filename_leaf
                        logger.debug(f"Processed content saved to {processed_filename_leaf}")

                    existing_chapter_entry["download_timestamp"] = current_time_iso
                    existing_chapter_entry["error_info"] = None # Clear previous errors
                    chapters_downloaded_in_this_run += 1
                    # Callback
                    if progress_callback: progress_callback({"status": "info", "message": f"Successfully processed existing chapter: {chapter_info.chapter_title}"})


                except requests.exceptions.RequestException as re: # More specific exception
                    logger.error(f"Network error processing existing chapter {chapter_info.chapter_title}: {re}")
                    existing_chapter_entry["status"] = "failed" # Keep status as failed
                    existing_chapter_entry["error_info"] = {"type": "download_network_error", "message": str(re), "timestamp": current_time_iso}
                except ValueError as ve: # For content not found or empty
                    logger.error(f"Content error processing existing chapter {chapter_info.chapter_title}: {ve}")
                    existing_chapter_entry["status"] = "failed"
                    existing_chapter_entry["error_info"] = {"type": "content_error", "message": str(ve), "timestamp": current_time_iso}
                except Exception as e:
                    logger.error(f"Error processing existing chapter {chapter_info.chapter_title}: {e}", exc_info=True)
                    existing_chapter_entry["status"] = "failed" # Keep status as failed
                    existing_chapter_entry["error_info"] = {"type": "processing_error", "message": str(e), "timestamp": current_time_iso}
                finally:
                    time.sleep(0.1) # Small delay, consider making configurable (delay_between_chapters)
            else: # Files are fine, not reprocessing
                logger.info(f"Chapter '{existing_chapter_entry['chapter_title']}' already processed and files exist. Retaining existing data.")
                # Callback
                if progress_callback: progress_callback({"status": "info", "message": f"Skipped already processed chapter: {existing_chapter_entry['chapter_title']}"})


            updated_downloaded_chapters.append(existing_chapter_entry)
        else: # New chapter
            # Apply chapter_limit_for_run for new chapters too
            if chapter_limit_for_run > 0 and chapters_downloaded_in_this_run >= chapter_limit_for_run and idx >= effective_start_idx_for_limit:
                logger.info(f"Chapter download limit ({chapter_limit_for_run}) reached before processing new chapter: {chapter_info.chapter_title}. It will be picked up in the next run.")
                # This new chapter is not added to existing_chapters_map yet, so it will be naturally re-evaluated next time.
                break # Exit the loop over chapters_info_list

            max_existing_order += 1
            new_download_order = max_existing_order
            logger.info(f"New chapter detected: {chapter_info.chapter_title}. Assigning download_order: {new_download_order}")

            new_chapter_entry = {
                "source_chapter_id": chapter_info.source_chapter_id, # Assuming ChapterInfo has source_chapter_id
                "chapter_url": chapter_url,
                "chapter_title": chapter_info.chapter_title,
                "download_order": new_download_order,
                "local_raw_filename": None,
                "local_processed_filename": None,
                "status": "pending", # Initial status
                "first_seen_on": current_time_iso,
                "last_checked_on": current_time_iso,
                "download_timestamp": None,
                "error_info": None
            }

            try:
                # slug_title_new = slugify(chapter_info.chapter_title if chapter_info.chapter_title else f"chapter-{new_download_order}")
                # base_filename_new = f"ch_{new_download_order:04d}_{slug_title_new}"
                raw_filename_leaf_new = f"chapter_{str(new_download_order).zfill(5)}_{chapter_info.source_chapter_id}.html"
                processed_filename_leaf_new = f"chapter_{str(new_download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"

                raw_file_abs_path_new = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id, raw_filename_leaf_new)
                processed_file_abs_path_new = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id, processed_filename_leaf_new)
                os.makedirs(os.path.dirname(raw_file_abs_path_new), exist_ok=True)
                os.makedirs(os.path.dirname(processed_file_abs_path_new), exist_ok=True)

                content_html_new = fetcher.download_chapter_content(chapter_info.chapter_url)
                if content_html_new == "Chapter content not found.":
                     raise ValueError("Chapter content not found by fetcher for new chapter.")

                with open(raw_file_abs_path_new, "w", encoding="utf-8") as f: f.write(content_html_new)
                new_chapter_entry["local_raw_filename"] = raw_filename_leaf_new
                logger.debug(f"Raw content for new chapter saved to {raw_filename_leaf_new}")

                cleaned_html_new = html_cleaner.clean_html(content_html_new, source_site="royalroad") # TODO: make dynamic
                # Apply sentence removal if configured
                if sentence_removal_file and not no_sentence_removal:
                    remover = SentenceRemover(sentence_removal_file)
                    if remover.remove_sentences or remover.remove_patterns:
                        cleaned_html_new = remover.remove_sentences_from_html(cleaned_html_new)
                        progress_data["sentence_removal_config_used"] = sentence_removal_file
                elif no_sentence_removal:
                    progress_data["sentence_removal_config_used"] = "Disabled via --no-sentence-removal"


                if not cleaned_html_new:
                    logger.warning(f"Cleaner returned no content for new chapter {chapter_info.chapter_title}. Skipping processed file saving.")
                    new_chapter_entry["local_processed_filename"] = None
                else:
                    with open(processed_file_abs_path_new, "w", encoding="utf-8") as f: f.write(cleaned_html_new)
                    new_chapter_entry["local_processed_filename"] = processed_filename_leaf_new
                    logger.debug(f"Processed content for new chapter saved to {processed_filename_leaf_new}")

                new_chapter_entry["status"] = "active"
                new_chapter_entry["download_timestamp"] = current_time_iso
                chapters_downloaded_in_this_run += 1
                updated_downloaded_chapters.append(new_chapter_entry)
                # Callback
                if progress_callback: progress_callback({"status": "info", "message": f"Successfully processed new chapter: {chapter_info.chapter_title}"})


            except requests.exceptions.RequestException as re_new: # More specific exception
                logger.error(f"Network error processing new chapter {chapter_info.chapter_title}: {re_new}")
                # Don't add to updated_downloaded_chapters if critical download fails, or add with error status
                # For now, log and skip adding. It will be picked up as new again next run.
                # Or, add with status 'failed':
                new_chapter_entry["status"] = "failed"
                new_chapter_entry["error_info"] = {"type": "download_network_error_new", "message": str(re_new), "timestamp": current_time_iso}
                updated_downloaded_chapters.append(new_chapter_entry) # Add even if failed so progress is tracked
            except ValueError as ve_new: # For content not found or empty
                logger.error(f"Content error processing new chapter {chapter_info.chapter_title}: {ve_new}")
                new_chapter_entry["status"] = "failed"
                new_chapter_entry["error_info"] = {"type": "content_error_new", "message": str(ve_new), "timestamp": current_time_iso}
                updated_downloaded_chapters.append(new_chapter_entry)
            except Exception as e_new:
                logger.error(f"Error processing new chapter {chapter_info.chapter_title}: {e_new}", exc_info=True)
                # Log and skip adding, or add with error status
                new_chapter_entry["status"] = "failed"
                new_chapter_entry["error_info"] = {"type": "processing_error_new", "message": str(e_new), "timestamp": current_time_iso}
                updated_downloaded_chapters.append(new_chapter_entry) # Add with error status
            finally:
                time.sleep(0.1) # Small delay

        chapters_processed_in_this_run +=1 # Counts chapters attempted (both existing and new) within the limit


    # Step 4: Process chapters remaining in existing_chapters_map (these are now considered archived)
    for chapter_url_archived, archived_chapter_entry in existing_chapters_map.items():
        if archived_chapter_entry.get("status") == "active": # Only log and change if it was 'active'
            logger.info(f"Chapter '{archived_chapter_entry.get('chapter_title', chapter_url_archived)}' no longer in source list. Marking as 'archived'.")
            archived_chapter_entry["status"] = "archived"
            # Callback
            if progress_callback: progress_callback({"status": "info", "message": f"Chapter '{archived_chapter_entry.get('chapter_title', chapter_url_archived)}' marked as 'archived'."})

        archived_chapter_entry["last_checked_on"] = current_time_iso
        updated_downloaded_chapters.append(archived_chapter_entry)

    # Step 5: Finalize progress_data
    updated_downloaded_chapters.sort(key=lambda ch: ch.get("download_order", float('inf')))
    progress_data["downloaded_chapters"] = updated_downloaded_chapters

    logger.info(f"Total chapters in progress after update: {len(updated_downloaded_chapters)}")
    logger.info(f"Chapters processed (attempted download or confirmed skip) in this run: {chapters_processed_in_this_run}")
    logger.info(f"Chapters actually downloaded/redownloaded in this run: {chapters_downloaded_in_this_run}")


    # Update last_downloaded_chapter_url and next_chapter_to_download_url
    # This needs to be based on the *source order* (chapters_info_list) and actual successful processing status.
    new_last_downloaded_url = None
    new_next_chapter_url = None

    # Iterate through the source-ordered list to find the last successfully processed active chapter
    for i_src, chap_info_src in enumerate(chapters_info_list):
        # Find the corresponding entry in our *final* updated_downloaded_chapters
        entry_in_final_list = next((ch for ch in updated_downloaded_chapters if ch["chapter_url"] == chap_info_src.chapter_url), None)
        if entry_in_final_list and entry_in_final_list.get("status") == "active":
            new_last_downloaded_url = chap_info_src.chapter_url
            # If there's a next chapter in the source list, it's the candidate for next_chapter_to_download_url
            if i_src + 1 < len(chapters_info_list):
                new_next_chapter_url = chapters_info_list[i_src + 1].chapter_url
            else: # This was the last chapter in the source, so no more next.
                new_next_chapter_url = None
        elif entry_in_final_list and entry_in_final_list.get("status") != "active":
            # This chapter from source was processed but is not 'active' (e.g. 'failed', 'archived').
            # It should be the next one to target, assuming it's not archived.
            # If it's 'archived' it means it was removed from source, so this case might be rare unless status changes.
            if entry_in_final_list.get("status") != "archived":
                 new_next_chapter_url = chap_info_src.chapter_url
                 break # Found the first non-active chapter in source order
            # If 'archived', continue to find the next actual candidate
        else: # Chapter from source is not in our final list or not processed successfully
            new_next_chapter_url = chap_info_src.chapter_url # This is the one to target next
            break # Stop at the first chapter from source that wasn't successfully processed or is missing.

    progress_data["last_downloaded_chapter_url"] = new_last_downloaded_url
    progress_data["next_chapter_to_download_url"] = new_next_chapter_url

    if new_next_chapter_url:
        logger.info(f"Next chapter to download is set to: {new_next_chapter_url}")
    elif new_last_downloaded_url and new_last_downloaded_url == chapters_info_list[-1].chapter_url if chapters_info_list else False:
        logger.info("All available chapters from source appear to have been processed.")
    else:
        logger.info("Could not determine the next chapter to download, or all chapters processed.")


    # Ensure downloaded_chapters is sorted by download_order as expected by EPUB generator
    # The reconciliation and new chapter processing might alter order if not careful.
    # Best to sort based on the order from the source (chapters_info_list)
    source_url_to_order_map = {info.chapter_url: info.download_order for info in chapters_info_list}

    # Create a dictionary for quick lookup of chapters in updated_downloaded_chapters by URL
    processed_chapters_map = {ch["chapter_url"]: ch for ch in updated_downloaded_chapters}

    # Build the final sorted list based on chapters_info_list from the source
    final_sorted_chapters = []
    for chapter_info_from_source in chapters_info_list:
        if chapter_info_from_source.chapter_url in processed_chapters_map:
            # If chapter from source is in our processed map, use its latest data
            chapter_entry = processed_chapters_map[chapter_info_from_source.chapter_url]
            # Ensure download_order and title are updated from source if they changed
            chapter_entry["download_order"] = chapter_info_from_source.download_order
            chapter_entry["chapter_title"] = chapter_info_from_source.chapter_title
            final_sorted_chapters.append(chapter_entry)
            # Remove from map to identify chapters in progress not in source later
            del processed_chapters_map[chapter_info_from_source.chapter_url]

    # Add any remaining chapters from processed_chapters_map (these are chapters in progress but no longer in source, already marked as 'archived')
    # These should already be in final_sorted_chapters if they were handled by the reconciliation loop and picked up from updated_downloaded_chapters.
    # However, to be safe and ensure they are included if they were somehow missed by the source iteration:
    for archived_chapter_url, archived_chapter_entry in processed_chapters_map.items():
        if archived_chapter_entry.get("status") == "archived":
            # It's important to decide where these should go in the sort order.
            # Original download_order is probably best.
            final_sorted_chapters.append(archived_chapter_entry)
            logger.info(f"Ensuring archived chapter '{archived_chapter_entry.get('chapter_title', archived_chapter_url)}' is in the final list.")

    # Sort the final list by 'download_order' to ensure consistency
    final_sorted_chapters.sort(key=lambda ch: ch.get("download_order", float('inf')))


    progress_data["downloaded_chapters"] = final_sorted_chapters
    # progress_data["downloaded_chapters"] = final_sorted_chapters # This was from old logic attempt
    # The new logic correctly sets progress_data["downloaded_chapters"] = updated_downloaded_chapters (which is sorted)

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


    epub_generator = EPUBGenerator(workspace_root)
    generated_epub_files = epub_generator.generate_epub(s_id, progress_data_for_epub, chapters_per_volume)

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
        save_progress(s_id, progress_data, workspace_root)
        logger.info(f"Progress saved to {os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, s_id, 'progress_status.json')}")
    except Exception as e:
        logger.error(f"Error saving progress for story ID {s_id}: {e}")

    # 7. Clean up temporary files if not requested to keep them
    if not keep_temp_files:
        _call_progress_callback({"status": "info", "message": "Cleaning up temporary files..."})
        logger.info(f"Attempting to remove temporary content directories for story ID: {s_id}")
        raw_story_dir = os.path.join(workspace_root, RAW_CONTENT_DIR, s_id)
        processed_story_dir = os.path.join(workspace_root, PROCESSED_CONTENT_DIR, s_id)

        try:
            if os.path.exists(raw_story_dir):
                shutil.rmtree(raw_story_dir)
                logger.info(f"Successfully removed raw content directory: {raw_story_dir}")
            else:
                logger.info(f"Raw content directory not found, no need to remove: {raw_story_dir}")

            if os.path.exists(processed_story_dir):
                shutil.rmtree(processed_story_dir)
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
        "chapters_processed": len(processed_chapters_for_this_run),
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
