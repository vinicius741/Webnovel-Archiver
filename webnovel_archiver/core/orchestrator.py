import os
import shutil
import datetime
import copy
import json
from typing import Dict, Any, Optional, Callable, Union
import requests

from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.utils.slug_generator import generate_slug
from .fetchers.fetcher_factory import FetcherFactory
from .fetchers.exceptions import UnsupportedSourceError
from .builders.epub_generator import EPUBGenerator
from .storage.progress_manager import load_progress, save_progress
from .parsers.html_cleaner import HTMLCleaner
from .modifiers.sentence_remover import SentenceRemover
from .path_manager import PathManager

ProgressCallback = Callable[[Union[str, Dict[str, Any]]], None]
logger = get_logger(__name__)

def _process_chapters(
    fetcher: Any,
    pm: PathManager,
    html_cleaner: HTMLCleaner,
    sentence_removal_file: Optional[str],
    no_sentence_removal: bool,
    progress_data: Dict[str, Any],
    current_time_iso: str,
    chapters_info_list: list,
    force_reprocessing: bool,
    _call_progress_callback: ProgressCallback
) -> int:
    updated_downloaded_chapters = []
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
    return successfully_processed_new_or_updated_count

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

        _call_progress_callback({"status": "info", "message": "Fetching story metadata..."})
        metadata = fetcher.get_story_metadata()
        logger.info(f"Successfully fetched metadata. Title: {metadata.original_title}")

        _call_progress_callback({"status": "info", "message": "Fetching chapter information..."})
        chapters_info_list = fetcher.get_chapter_urls()
        logger.info(f"Successfully fetched {len(chapters_info_list)} chapters.")

    except (UnsupportedSourceError, ValueError, NotImplementedError) as e:
        logger.error(f"Cannot archive story: {e}")
        _call_progress_callback({"status": "error", "message": f"Cannot archive story: {e}"})
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch story metadata for URL: {story_url}. Network error: {e}")
        _call_progress_callback({"status": "error", "message": f"Failed to fetch story metadata. Network error: {e}"})
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
    pm = PathManager(workspace_root, story_folder_name)

    expected_folder_slug = generate_slug(metadata.original_title)

    if story_folder_name:
        logger.info(f"Found existing story. Permanent ID: {permanent_id}, Current Folder: {story_folder_name}")
        if story_folder_name != expected_folder_slug:
            old_story_path = os.path.join(workspace_root, story_folder_name)
            new_story_path = os.path.join(workspace_root, expected_folder_slug)
            
            if os.path.exists(old_story_path):
                try:
                    shutil.move(old_story_path, new_story_path)
                    logger.info(f"Renamed story folder from '{story_folder_name}' to '{expected_folder_slug}'.")
                    _call_progress_callback({"status": "info", "message": f"Renamed story folder to '{expected_folder_slug}'."})
                    story_folder_name = expected_folder_slug
                except OSError as e:
                    logger.error(f"Failed to rename folder from '{old_story_path}' to '{new_story_path}': {e}", exc_info=True)
                    _call_progress_callback({"status": "error", "message": f"Failed to rename story folder: {e}"})
                    return None
            else:
                logger.warning(f"Expected story folder '{old_story_path}' not found. Creating new folder with expected slug.")
                story_folder_name = expected_folder_slug
        else:
            logger.info(f"Story folder name '{story_folder_name}' is already synchronized with title slug.")
    else:
        logger.info(f"New story detected. Permanent ID: {permanent_id}. Initializing with folder: {expected_folder_slug}")
        story_folder_name = expected_folder_slug
    
    # Update index with the potentially new or confirmed folder name
    if index.get(permanent_id) != story_folder_name:
        index[permanent_id] = story_folder_name
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=4)
            logger.info(f"Updated index for {permanent_id} to point to {story_folder_name}")
        except IOError as e:
            logger.error(f"Failed to write to index file at {index_path}: {e}", exc_info=True)
            _call_progress_callback({"status": "error", "message": f"Failed to update story index: {e}"})
            return None

    pm = PathManager(workspace_root, story_folder_name)

    progress_data = load_progress(story_folder_name, workspace_root)
    progress_data["story_id"] = permanent_id
    progress_data["story_url"] = story_url
    progress_data["original_title"] = metadata.original_title
    progress_data["original_author"] = metadata.original_author
    progress_data["cover_image_url"] = metadata.cover_image_url
    progress_data["synopsis"] = metadata.synopsis
    progress_data["estimated_total_chapters_source"] = metadata.estimated_total_chapters_source
    progress_data["effective_title"] = ebook_title_override if ebook_title_override else metadata.original_title

    html_cleaner = HTMLCleaner()
    current_time_iso = datetime.datetime.utcnow().isoformat() + "Z"

    successfully_processed_new_or_updated_count = _process_chapters(
        fetcher, pm, html_cleaner, sentence_removal_file, no_sentence_removal,
        progress_data, current_time_iso, chapters_info_list, force_reprocessing,
        _call_progress_callback
    )
    
    progress_data["last_archived_timestamp"] = current_time_iso
    save_progress(story_folder_name, progress_data, workspace_root)
    logger.info(f"Progress saved for {story_folder_name}.")

    # EPUB Generation
    generated_epub_files = []
    if successfully_processed_new_or_updated_count > 0 or force_reprocessing:
        _call_progress_callback({"status": "info", "message": "Generating EPUB..."})
        epub_generator = EPUBGenerator(pm)
        
        # Filter chapters based on epub_contents setting
        chapters_for_epub = []
        if epub_contents == 'active-only':
            chapters_for_epub = [ch for ch in progress_data["downloaded_chapters"] if ch.get("status") == "active"]
            logger.info(f"EPUB generation set to 'active-only'. Including {len(chapters_for_epub)} active chapters.")
        else: # 'all' or any other value
            chapters_for_epub = progress_data["downloaded_chapters"]
            logger.info(f"EPUB generation set to 'all'. Including {len(chapters_for_epub)} chapters (active and archived). ")

        # Create a temporary progress_data for EPUB generation that only contains the filtered chapters
        epub_progress_data = copy.deepcopy(progress_data)
        epub_progress_data["downloaded_chapters"] = chapters_for_epub

        generated_epub_files = epub_generator.generate_epub(epub_progress_data, chapters_per_volume=chapters_per_volume)
        if generated_epub_files:
            _call_progress_callback({"status": "info", "message": f"EPUB generated: {len(generated_epub_files)} file(s)."})
        else:
            _call_progress_callback({"status": "warning", "message": "EPUB generation completed, but no files were produced."})
    else:
        logger.info("No new chapters processed and no force reprocessing. Skipping EPUB generation.")
        _call_progress_callback({"status": "info", "message": "No new content to process. Skipping EPUB generation."})

    # Clean up temporary files
    if not keep_temp_files:
        try:
            temp_cover_dir = pm.get_temp_cover_story_dir()
            if os.path.exists(temp_cover_dir):
                shutil.rmtree(temp_cover_dir)
                logger.info(f"Cleaned up temporary cover directory: {temp_cover_dir}")
        except OSError as e:
            logger.warning(f"Failed to clean up temporary cover directory {temp_cover_dir}: {e}")

    return {
        "title": progress_data.get("effective_title", progress_data.get("original_title", "Unknown Title")),
        "story_id": permanent_id,
        "chapters_processed": successfully_processed_new_or_updated_count,
        "epub_files": generated_epub_files,
        "workspace_root": workspace_root
    }
    

