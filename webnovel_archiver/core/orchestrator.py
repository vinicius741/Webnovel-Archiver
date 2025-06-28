import os
import shutil
import datetime
import copy
from typing import Dict, Any, Optional, Callable, Union

import requests

from webnovel_archiver.utils.logger import get_logger
from .fetchers.fetcher_factory import FetcherFactory
from .fetchers.exceptions import UnsupportedSourceError
from .builders.epub_generator import EPUBGenerator
from .storage.progress_manager import load_progress, save_progress
from .storage.index_manager import IndexManager
from .migration_manager import MigrationManager
from .parsers.html_cleaner import HTMLCleaner
from .modifiers.sentence_remover import SentenceRemover
from .path_manager import PathManager

ProgressCallback = Callable[[Union[str, Dict[str, Any]]], None]
logger = get_logger(__name__)


def archive_story(
    story_url: str,
    workspace_root: str,
    chapters_per_volume: Optional[int] = None,
    ebook_title_override: Optional[str] = None,
    keep_temp_files: bool = False,
    force_reprocessing: bool = False,
    sentence_removal_file: Optional[str] = None,
    no_sentence_removal: bool = False,
    progress_callback: Optional[ProgressCallback] = None,
    epub_contents: Optional[str] = 'all'
) -> Optional[Dict[str, Any]]:
    def _call_progress_callback(message: Union[str, Dict[str, Any]]) -> None:
        if progress_callback:
            try:
                progress_callback(message)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}", exc_info=True)

    _call_progress_callback({"status": "info", "message": "Starting archival process..."})
    logger.info(f"Starting archiving process for: {story_url}")

    index_manager = IndexManager(workspace_root)
    migration_manager = MigrationManager(workspace_root, index_manager)
    migration_manager.migrate_if_needed()

    _call_progress_callback({"status": "info", "message": "Initializing content fetcher..."})
    logger.info(f"Attempting to get fetcher for URL: {story_url}")
    try:
        fetcher = FetcherFactory.get_fetcher(story_url)
        logger.info(f"Successfully obtained fetcher: {type(fetcher).__name__}")
    except (UnsupportedSourceError, ValueError) as e:
        logger.error(f"Cannot archive story: {e}")
        _call_progress_callback({"status": "error", "message": str(e)})
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while initializing the fetcher: {e}", exc_info=True)
        _call_progress_callback({"status": "error", "message": f"Failed to initialize fetcher: {e}"})
        return None

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
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching story metadata for URL: {story_url}. Error: {e}")
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching story metadata: {e}"})
        return None

    story_id = metadata.story_id
    if not story_id:
        logger.error("Could not determine story ID. Aborting.")
        _call_progress_callback({"status": "error", "message": "Could not determine story ID."})
        return None

    pm = PathManager(workspace_root, index_manager)
    pm.set_story(story_id, metadata.original_title)

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
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching chapter list for: {metadata.original_title}. Error: {e}")
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching chapter list: {e}"})
        return None

    progress_data = load_progress(pm.get_progress_filepath())
    progress_data["story_id"] = story_id
    progress_data["story_url"] = story_url
    progress_data["original_title"] = metadata.original_title
    progress_data["original_author"] = metadata.original_author
    progress_data["cover_image_url"] = metadata.cover_image_url
    progress_data["synopsis"] = metadata.synopsis
    progress_data["estimated_total_chapters_source"] = metadata.estimated_total_chapters_source
    progress_data["sentence_removal_config_used"] = None

    if progress_data.get("next_chapter_to_download_url") is None and progress_data.get("last_downloaded_chapter_url"):
        last_known_url = progress_data["last_downloaded_chapter_url"]
        logger.info(f"No next chapter URL in progress. Checking for new chapters from the last downloaded page: {last_known_url}")
        try:
            next_page_url = fetcher.get_next_chapter_url_from_page(last_known_url)
            if next_page_url:
                logger.info(f"New chapter detected from last known chapter's page: {next_page_url}. Re-fetching chapter list.")
                _call_progress_callback({"status": "info", "message": "New chapter detected. Re-fetching chapter list..."})
                chapters_info_list = fetcher.get_chapter_urls(story_url)
                logger.info(f"Found {len(chapters_info_list)} chapters after refresh.")
                _call_progress_callback({"status": "info", "message": f"Found {len(chapters_info_list)} chapters after refresh."})
            else:
                logger.info("No new chapters found after checking the last downloaded chapter's page.")
                _call_progress_callback({"status": "info", "message": "No new chapters found by checking last chapter's page."})
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error when trying to check for new chapters from {last_known_url}: {e}")
            _call_progress_callback({"status": "warning", "message": f"Network error checking for new chapters: {e}"})
        except Exception as e:
            logger.error(f"Unexpected error when trying to check for new chapters from {last_known_url}: {e}", exc_info=True)
            _call_progress_callback({"status": "warning", "message": f"Unexpected error checking for new chapters: {e}"})

    html_cleaner = HTMLCleaner()
    successfully_processed_new_or_updated_count = 0
    existing_chapters_map = {}

    if force_reprocessing:
        logger.info("Force reprocessing is ON. All chapters will be fetched and processed anew.")
        progress_data["downloaded_chapters"] = []
    else:
        logger.info("Force reprocessing is OFF. Will attempt to skip already processed chapters if files are valid.")
        if "downloaded_chapters" in progress_data:
            for chap_entry in progress_data.get("downloaded_chapters", []):
                if isinstance(chap_entry, dict) and "chapter_url" in chap_entry:
                    existing_chapters_map[chap_entry["chapter_url"]] = chap_entry
                else:
                    logger.warning(f"Found malformed chapter entry in progress data: {chap_entry}")
        else:
            progress_data["downloaded_chapters"] = []

    updated_downloaded_chapters = []
    current_time_iso = datetime.datetime.utcnow().isoformat() + "Z"
    source_chapter_urls = {ch_info.chapter_url for ch_info in chapters_info_list}
    existing_chapter_urls_in_progress = {ch_entry["chapter_url"] for ch_entry in progress_data.get("downloaded_chapters", []) if isinstance(ch_entry, dict) and "chapter_url" in ch_entry}

    for chapter_entry in progress_data.get("downloaded_chapters", []):
        if not (isinstance(chapter_entry, dict) and "chapter_url" in chapter_entry):
            logger.warning(f"Skipping malformed chapter entry in progress: {chapter_entry}")
            continue

        chapter_url = chapter_entry["chapter_url"]
        if 'status' not in chapter_entry:
            chapter_entry['status'] = 'active'

        if chapter_url not in source_chapter_urls:
            if chapter_entry["status"] == "active":
                logger.info(f"Chapter '{chapter_entry.get('chapter_title', chapter_url)}' no longer in source list. Marking as 'archived'.")
                chapter_entry["status"] = "archived"
                _call_progress_callback({
                    "status": "info",
                    "message": f"Chapter '{chapter_entry.get('chapter_title', chapter_url)}' marked as 'archived'.",
                    "chapter_title": chapter_entry.get('chapter_title', chapter_url)
                })

        chapter_entry["last_checked_on"] = current_time_iso
        updated_downloaded_chapters.append(chapter_entry)

    total_source_chapters = len(chapters_info_list)
    for i, chapter_info in enumerate(chapters_info_list):
        _call_progress_callback({
            "status": "info",
            "message": f"Checking chapter: {chapter_info.chapter_title} ({i+1}/{total_source_chapters})",
            "current_chapter_num": i + 1,
            "total_chapters": total_source_chapters,
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

        needs_processing = False
        existing_entry_for_url = next((ch for ch in updated_downloaded_chapters if ch["chapter_url"] == chapter_info.chapter_url), None)

        if chapter_info.chapter_url not in existing_chapter_urls_in_progress:
            logger.info(f"New chapter detected: {chapter_info.chapter_title} (URL: {chapter_info.chapter_url})")
            needs_processing = True
        elif force_reprocessing:
            logger.info(f"Force reprocessing chapter: {chapter_info.chapter_title}")
            needs_processing = True
            if existing_entry_for_url:
                existing_entry_for_url.pop("local_raw_filename", None)
                existing_entry_for_url.pop("local_processed_filename", None)
        elif existing_entry_for_url:
            raw_filename = existing_entry_for_url.get("local_raw_filename")
            processed_filename = existing_entry_for_url.get("local_processed_filename")
            if not raw_filename or not processed_filename or not os.path.exists(pm.get_raw_content_chapter_filepath(raw_filename)) or not os.path.exists(pm.get_processed_content_chapter_filepath(processed_filename)):
                logger.info(f"Files missing for existing chapter '{chapter_info.chapter_title}'. Reprocessing.")
                needs_processing = True
            else:
                logger.info(f"Chapter '{chapter_info.chapter_title}' already processed and files exist. Skipping download and processing.")
                if existing_entry_for_url["status"] != "active":
                     existing_entry_for_url["status"] = "active"
                     logger.info(f"Chapter '{chapter_info.chapter_title}' status updated to 'active' as it reappeared in source.")

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
                    if existing_entry_for_url:
                        existing_entry_for_url["last_checked_on"] = current_time_iso
                    continue
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
            raw_file_directory = pm.get_raw_content_story_dir()
            os.makedirs(raw_file_directory, exist_ok=True)
            raw_filepath = pm.get_raw_content_chapter_filepath(raw_filename)

            try:
                with open(raw_filepath, 'w', encoding='utf-8') as f:
                    f.write(raw_html_content)
                logger.info(f"Saved raw content for {chapter_info.chapter_title} to {raw_filepath}")
            except IOError as e:
                logger.error(f"Error saving raw content for {chapter_info.chapter_title} to {raw_filepath}: {e}")
                if existing_entry_for_url: existing_entry_for_url["last_checked_on"] = current_time_iso
                continue

            cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad")

            if sentence_removal_file and not no_sentence_removal:
                try:
                    remover = SentenceRemover(sentence_removal_file)
                    if remover.remove_sentences or remover.remove_patterns:
                        cleaned_html_content = remover.remove_sentences_from_html(cleaned_html_content)
                        logger.info(f"Sentence removal applied to chapter: {chapter_info.chapter_title}")
                        progress_data["sentence_removal_config_used"] = sentence_removal_file
                    else:
                        logger.info(f"No sentences matched for removal in chapter: {chapter_info.chapter_title}")
                        progress_data["sentence_removal_config_used"] = sentence_removal_file
                except Exception as e:
                    logger.error(f"Failed to apply sentence removal for chapter '{chapter_info.chapter_title}': {e}", exc_info=True)
                    progress_data["sentence_removal_config_used"] = f"Error with {sentence_removal_file}: {e}"
            elif no_sentence_removal:
                progress_data["sentence_removal_config_used"] = "Disabled via --no-sentence-removal"

            processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
            processed_file_directory = pm.get_processed_content_story_dir()
            os.makedirs(processed_file_directory, exist_ok=True)
            processed_filepath = pm.get_processed_content_chapter_filepath(processed_filename)

            try:
                with open(processed_filepath, 'w', encoding='utf-8') as f:
                    f.write(cleaned_html_content)
                logger.info(f"Saved processed content for {chapter_info.chapter_title} to {processed_filepath}")
            except IOError as e:
                logger.error(f"Error saving processed content for {chapter_info.chapter_title} to {processed_filepath}: {e}")
                processed_filename = None

            if existing_entry_for_url:
                chapter_detail_entry = existing_entry_for_url
                chapter_detail_entry["status"] = "active"
                chapter_detail_entry["download_order"] = chapter_info.download_order
                chapter_detail_entry["chapter_title"] = chapter_info.chapter_title
            else:
                chapter_detail_entry = {
                    "source_chapter_id": chapter_info.source_chapter_id,
                    "chapter_url": chapter_info.chapter_url,
                    "first_seen_on": current_time_iso,
                }
                updated_downloaded_chapters.append(chapter_detail_entry)

            chapter_detail_entry["download_order"] = chapter_info.download_order
            chapter_detail_entry["chapter_title"] = chapter_info.chapter_title
            chapter_detail_entry["local_raw_filename"] = raw_filename
            chapter_detail_entry["local_processed_filename"] = processed_filename
            chapter_detail_entry["download_timestamp"] = current_time_iso
            chapter_detail_entry["last_checked_on"] = current_time_iso
            chapter_detail_entry["status"] = "active"
            successfully_processed_new_or_updated_count +=1

            current_chapter_index_in_source_list = chapters_info_list.index(chapter_info)
            progress_data["last_downloaded_chapter_url"] = chapter_info.chapter_url
            if current_chapter_index_in_source_list < len(chapters_info_list) - 1:
                progress_data["next_chapter_to_download_url"] = chapters_info_list[current_chapter_index_in_source_list + 1].chapter_url
            else:
                progress_data["next_chapter_to_download_url"] = None

    current_progress_chapters_map = {ch_entry["chapter_url"]: ch_entry for ch_entry in updated_downloaded_chapters}
    definitive_chapters_list = []

    for source_chapter_info in chapters_info_list:
        chapter_to_add = None
        if source_chapter_info.chapter_url in current_progress_chapters_map:
            chapter_to_add = current_progress_chapters_map.pop(source_chapter_info.chapter_url)
            chapter_to_add["status"] = "active"
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
            chapter_to_add["source_chapter_id"] = source_chapter_info.source_chapter_id
        else:
            logger.error(f"CRITICAL LOGIC FLAW: Chapter '{source_chapter_info.chapter_title}' (URL: {source_chapter_info.chapter_url}) from source was not found in 'updated_downloaded_chapters'.")
            continue

        if chapter_to_add:
            definitive_chapters_list.append(chapter_to_add)

    archived_chapters_to_add = sorted(current_progress_chapters_map.values(), key=lambda ch: (ch.get("download_order", float('inf')), ch.get("first_seen_on", "")))
    for archived_chapter in archived_chapters_to_add:
        archived_chapter["status"] = "archived"
        definitive_chapters_list.append(archived_chapter)
        logger.info(f"Appending archived chapter '{archived_chapter.get('chapter_title', archived_chapter['chapter_url'])}' to the definitive list.")

    for i, chapter_entry in enumerate(definitive_chapters_list):
        chapter_entry["download_order"] = i + 1
        logger.debug(f"Final order assignment: {chapter_entry['download_order']} -> {chapter_entry.get('chapter_title', chapter_entry['chapter_url'])} (Status: {chapter_entry['status']})")

    progress_data["downloaded_chapters"] = definitive_chapters_list

    if ebook_title_override:
        logger.info(f"Overriding ebook title with: '{ebook_title_override}'")
        progress_data["effective_title"] = ebook_title_override
    else:
        progress_data["effective_title"] = progress_data.get("original_title", "Untitled Story")

    _call_progress_callback({"status": "info", "message": "Starting EPUB generation..."})
    logger.info(f"Starting EPUB generation for story ID: {story_id}")

    progress_data_for_epub: Dict[str, Any]
    if epub_contents == 'active-only':
        logger.info("EPUB generation set to 'active-only', filtering chapters.")
        _call_progress_callback({"status": "info", "message": "Filtering chapters for EPUB: including 'active' only."})
        progress_data_for_epub = copy.deepcopy(progress_data)
        original_chapter_count = len(progress_data_for_epub.get("downloaded_chapters", []))
        active_chapters = [ch for ch in progress_data_for_epub.get("downloaded_chapters", []) if isinstance(ch, dict) and ch.get("status") == "active"]
        progress_data_for_epub["downloaded_chapters"] = active_chapters
        filtered_count = original_chapter_count - len(active_chapters)
        logger.info(f"Filtered out {filtered_count} non-active chapters for EPUB generation.")
        _call_progress_callback({"status": "info", "message": f"Filtered out {filtered_count} non-active chapters. Using {len(active_chapters)} for EPUB."})
    else:
        logger.info("EPUB generation set to 'all', including all downloaded chapters.")
        _call_progress_callback({"status": "info", "message": "Including all downloaded chapters in EPUB."})
        progress_data_for_epub = progress_data

    epub_generator = EPUBGenerator(pm)
    generated_epub_files = epub_generator.generate_epub(progress_data_for_epub, chapters_per_volume)

    if not isinstance(progress_data.get("last_epub_processing"), dict):
        progress_data["last_epub_processing"] = {}

    progress_data["last_epub_processing"]["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    progress_data["last_epub_processing"]["generated_epub_files"] = generated_epub_files
    progress_data["last_epub_processing"]["chapters_included_in_last_volume"] = None

    if generated_epub_files:
        logger.info(f"Successfully generated {len(generated_epub_files)} EPUB file(s) for story ID {story_id}: {generated_epub_files}")
        _call_progress_callback({"status": "info", "message": f"Successfully generated EPUB file(s): {generated_epub_files}", "file_paths": generated_epub_files})
    else:
        logger.warning(f"No EPUB files were generated for story ID {story_id}.")
        _call_progress_callback({"status": "warning", "message": "No EPUB files were generated."})
        progress_data["last_epub_processing"]["generated_epub_files"] = []

    logger.info("Saving final progress status...")
    try:
        progress_data["last_archived_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_progress(pm.get_progress_filepath(), progress_data)
        logger.info(f"Progress saved to {pm.get_progress_filepath()}")
    except Exception as e:
        logger.error(f"Error saving progress for story ID {story_id}: {e}")

    if not keep_temp_files:
        _call_progress_callback({"status": "info", "message": "Cleaning up temporary files..."})
        logger.info(f"Attempting to remove temporary content directories for story ID: {story_id}")
        raw_story_dir = pm.get_raw_content_story_dir()
        processed_story_dir = pm.get_processed_content_story_dir()

        try:
            if os.path.exists(raw_story_dir):
                shutil.rmtree(raw_story_dir)
                logger.info(f"Successfully removed raw content directory: {raw_story_dir}")
            if os.path.exists(processed_story_dir):
                shutil.rmtree(processed_story_dir)
                logger.info(f"Successfully removed processed content directory: {processed_story_dir}")
            _call_progress_callback({"status": "info", "message": "Successfully cleaned up temporary files."})
        except OSError as e:
            logger.error(f"Error removing temporary content directories for story ID {story_id}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Error cleaning up temporary files: {e}"})
        except Exception as e:
            logger.error(f"An unexpected error occurred during temporary file cleanup for story ID {story_id}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"An unexpected error occurred during temporary file cleanup: {e}"})
    else:
        logger.info(f"Keeping temporary content directories for story ID: {story_id} as per 'keep_temp_files' flag.")

    _call_progress_callback({"status": "info", "message": "Archival process completed."})
    logger.info(f"Archiving process completed for story ID: {story_id}")

    summary = {
        "story_id": story_id,
        "title": progress_data.get("effective_title", metadata.original_title),
        "chapters_processed": successfully_processed_new_or_updated_count,
        "epub_files": [os.path.abspath(f) for f in generated_epub_files if f],
        "workspace_root": os.path.abspath(workspace_root)
    }
    return summary
