import os
import shutil
import datetime
import copy
import json
from typing import Dict, Any, Optional, Callable, Union
import requests

from webnovel_archiver.utils.logger import get_logger
from .fetchers.fetcher_factory import FetcherFactory
from .fetchers.exceptions import UnsupportedSourceError
from .builders.epub_generator import EPUBGenerator
from .storage.progress_manager import load_progress, save_progress
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

    try:
        fetcher = FetcherFactory.get_fetcher(story_url)
        permanent_id = fetcher.get_permanent_id()
        logger.info(f"Successfully obtained fetcher: {type(fetcher).__name__} and permanent ID: {permanent_id}")
    except (UnsupportedSourceError, ValueError, NotImplementedError) as e:
        logger.error(f"Cannot archive story: {e}")
        _call_progress_callback({"status": "error", "message": f"Cannot archive story: {e}"})
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while initializing the fetcher: {e}", exc_info=True)
        _call_progress_callback({"status": "error", "message": f"Failed to initialize fetcher: {e}"})
        return None

    workspace_path_manager = PathManager(workspace_root)
    index_path = workspace_path_manager.index_path
    index = {}
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load or parse index file at {index_path}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Failed to load story index: {e}"})
            return None

    story_folder_name = index.get(permanent_id)
    if story_folder_name:
        logger.info(f"Found existing story. Permanent ID: {permanent_id}, Folder: {story_folder_name}")
    else:
        logger.info(f"New story detected. Permanent ID: {permanent_id}")
        story_folder_name = permanent_id
        index[permanent_id] = story_folder_name
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=4)
            logger.info(f"Updated index with new story: {permanent_id} -> {story_folder_name}")
        except IOError as e:
            logger.error(f"Failed to write to index file at {index_path}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Failed to update story index: {e}"})
            return None

    pm = PathManager(workspace_root, story_folder_name)
    
    _call_progress_callback({"status": "info", "message": "Fetching story metadata..."})
    try:
        metadata = fetcher.get_story_metadata()
        logger.info(f"Successfully fetched metadata. Title: {metadata.original_title}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch story metadata for URL: {story_url}. Network error: {e}")
        _call_progress_callback({"status": "error", "message": f"Failed to fetch story metadata. Network error: {e}"})
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching story metadata for URL: {story_url}. Error: {e}", exc_info=True)
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching story metadata: {e}"})
        return None

    _call_progress_callback({"status": "info", "message": "Fetching chapter list..."})
    try:
        chapters_info_list = fetcher.get_chapter_urls()
        logger.info(f"Found {len(chapters_info_list)} chapters.")
        if not chapters_info_list:
            logger.warning("No chapters found. Aborting archival for this story.")
            _call_progress_callback({"status": "warning", "message": "No chapters found. Aborting archival."})
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch chapter list for: {metadata.original_title}. Network error: {e}")
        _call_progress_callback({"status": "error", "message": f"Failed to fetch chapter list. Network error: {e}"})
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching chapter list for: {metadata.original_title}. Error: {e}", exc_info=True)
        _call_progress_callback({"status": "error", "message": f"An unexpected error occurred while fetching chapter list: {e}"})
        return None

    progress_data = load_progress(story_folder_name, workspace_root)
    progress_data["story_id"] = permanent_id
    progress_data["story_url"] = story_url
    progress_data["original_title"] = metadata.original_title
    progress_data["original_author"] = metadata.original_author
    progress_data["cover_image_url"] = metadata.cover_image_url
    progress_data["synopsis"] = metadata.synopsis
    progress_data["estimated_total_chapters_source"] = metadata.estimated_total_chapters_source

    html_cleaner = HTMLCleaner()
    updated_downloaded_chapters = []
    current_time_iso = datetime.datetime.utcnow().isoformat() + "Z"
    source_chapter_urls = {ch_info.chapter_url for ch_info in chapters_info_list}
    
    if force_reprocessing:
        logger.info("Force reprocessing is ON. All chapters will be fetched and processed anew.")
        progress_data["downloaded_chapters"] = []
    
    existing_chapters_map = {ch_entry["chapter_url"]: ch_entry for ch_entry in progress_data.get("downloaded_chapters", []) if isinstance(ch_entry, dict) and "chapter_url" in ch_entry}

    for chapter_entry in progress_data.get("downloaded_chapters", []):
        if not (isinstance(chapter_entry, dict) and "chapter_url" in chapter_entry):
            continue
        if chapter_entry["chapter_url"] not in source_chapter_urls and chapter_entry.get("status") == "active":
            chapter_entry["status"] = "archived"
            logger.info(f"Chapter '{chapter_entry.get('chapter_title', chapter_entry['chapter_url'])}' no longer in source list. Marking as 'archived'.")
        chapter_entry["last_checked_on"] = current_time_iso
        updated_downloaded_chapters.append(chapter_entry)

    successfully_processed_new_or_updated_count = 0
    for i, chapter_info in enumerate(chapters_info_list):
        _call_progress_callback({
            "status": "info",
            "message": f"Checking chapter: {chapter_info.chapter_title} ({i+1}/{len(chapters_info_list)})",
            "current_chapter_num": i + 1,
            "total_chapters": len(chapters_info_list),
            "chapter_title": chapter_info.chapter_title
        })

        if chapter_info.chapter_url is None:
            logger.warning(f"Chapter {chapter_info.chapter_title} has no URL. Skipping.")
            continue

        needs_processing = False
        existing_entry = existing_chapters_map.get(chapter_info.chapter_url)

        if not existing_entry:
            needs_processing = True
            logger.info(f"New chapter detected: {chapter_info.chapter_title}")
        elif force_reprocessing:
            needs_processing = True
            logger.info(f"Force reprocessing chapter: {chapter_info.chapter_title}")
        elif existing_entry:
            raw_path = pm.get_raw_content_chapter_filepath(existing_entry.get("local_raw_filename", ""))
            proc_path = pm.get_processed_content_chapter_filepath(existing_entry.get("local_processed_filename", ""))
            if not os.path.exists(raw_path) or not os.path.exists(proc_path):
                needs_processing = True
                logger.info(f"Files missing for existing chapter '{chapter_info.chapter_title}'. Reprocessing.")
            else:
                logger.info(f"Chapter '{chapter_info.chapter_title}' already processed and files exist. Skipping.")
                if existing_entry.get("status") != "active":
                    existing_entry["status"] = "active"

        if needs_processing:
            try:
                raw_html_content = fetcher.download_chapter_content(chapter_info.chapter_url)
                if raw_html_content == "Chapter content not found.":
                    logger.warning(f"Content not found for chapter: {chapter_info.chapter_title}. Skipping.")
                    continue
                
                raw_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}.html"
                os.makedirs(pm.get_raw_content_story_dir(), exist_ok=True)
                with open(pm.get_raw_content_chapter_filepath(raw_filename), 'w', encoding='utf-8') as f:
                    f.write(raw_html_content)

                cleaned_html_content = html_cleaner.clean_html(raw_html_content, source_site="royalroad")
                
                if sentence_removal_file and not no_sentence_removal:
                    remover = SentenceRemover(sentence_removal_file)
                    cleaned_html_content = remover.remove_sentences_from_html(cleaned_html_content)
                    progress_data["sentence_removal_config_used"] = sentence_removal_file

                processed_filename = f"chapter_{str(chapter_info.download_order).zfill(5)}_{chapter_info.source_chapter_id}_clean.html"
                os.makedirs(pm.get_processed_content_story_dir(), exist_ok=True)
                with open(pm.get_processed_content_chapter_filepath(processed_filename), 'w', encoding='utf-8') as f:
                    f.write(cleaned_html_content)

                if existing_entry:
                    chapter_detail_entry = existing_entry
                else:
                    chapter_detail_entry = {"first_seen_on": current_time_iso}
                    updated_downloaded_chapters.append(chapter_detail_entry)

                chapter_detail_entry.update({
                    "source_chapter_id": chapter_info.source_chapter_id,
                    "chapter_url": chapter_info.chapter_url,
                    "download_order": chapter_info.download_order,
                    "chapter_title": chapter_info.chapter_title,
                    "local_raw_filename": raw_filename,
                    "local_processed_filename": processed_filename,
                    "download_timestamp": current_time_iso,
                    "last_checked_on": current_time_iso,
                    "status": "active"
                })
                successfully_processed_new_or_updated_count += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to download/process chapter: {chapter_info.chapter_title}. Error: {e}")
                continue
            except Exception as e:
                logger.error(f"An unexpected error occurred while processing chapter: {chapter_info.chapter_title}. Error: {e}", exc_info=True)
                continue

    definitive_chapters_list = []
    processed_urls = set()
    for ch_info in chapters_info_list:
        entry = existing_chapters_map.get(ch_info.chapter_url)
        if entry:
            entry["status"] = "active"
            definitive_chapters_list.append(entry)
            processed_urls.add(ch_info.chapter_url)

    archived_chapters = sorted(
        [ch for ch in updated_downloaded_chapters if ch["chapter_url"] not in processed_urls],
        key=lambda ch: ch.get("download_order", float('inf'))
    )
    definitive_chapters_list.extend(archived_chapters)

    for i, chapter_entry in enumerate(definitive_chapters_list):
        chapter_entry["download_order"] = i + 1
    
    progress_data["downloaded_chapters"] = definitive_chapters_list
    
    if ebook_title_override:
        progress_data["effective_title"] = ebook_title_override
    else:
        progress_data["effective_title"] = progress_data.get("original_title", "Untitled Story")

    _call_progress_callback({"status": "info", "message": "Starting EPUB generation..."})
    
    progress_data_for_epub = copy.deepcopy(progress_data)
    if epub_contents == 'active-only':
        progress_data_for_epub["downloaded_chapters"] = [ch for ch in progress_data_for_epub["downloaded_chapters"] if ch.get("status") == "active"]

    epub_generator = EPUBGenerator(pm)
    generated_epub_files = epub_generator.generate_epub(progress_data_for_epub, chapters_per_volume)
    
    if "last_epub_processing" not in progress_data:
        progress_data["last_epub_processing"] = {}
    progress_data["last_epub_processing"]["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    progress_data["last_epub_processing"]["generated_epub_files"] = generated_epub_files or []

    if generated_epub_files:
        _call_progress_callback({"status": "info", "message": f"Successfully generated EPUB file(s): {generated_epub_files}"})
    else:
        _call_progress_callback({"status": "warning", "message": "No EPUB files were generated."})

    progress_data["last_archived_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_progress(story_folder_name, progress_data, workspace_root)
    logger.info(f"Progress saved to {pm.get_progress_filepath()}")

    if not keep_temp_files:
        _call_progress_callback({"status": "info", "message": "Cleaning up temporary files..."})
        try:
            shutil.rmtree(pm.get_raw_content_story_dir())
            shutil.rmtree(pm.get_processed_content_story_dir())
            _call_progress_callback({"status": "info", "message": "Successfully cleaned up temporary files."})
        except OSError as e:
            logger.error(f"Error removing temporary content directories: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Error cleaning up temporary files: {e}"})

    _call_progress_callback({"status": "info", "message": "Archival process completed."})
    logger.info(f"Archiving process completed for story ID: {permanent_id}")

    return {
        "story_id": permanent_id,
        "title": progress_data.get("effective_title"),
        "chapters_processed": successfully_processed_new_or_updated_count,
        "epub_files": [os.path.abspath(f) for f in generated_epub_files if f],
        "workspace_root": os.path.abspath(workspace_root)
    }

