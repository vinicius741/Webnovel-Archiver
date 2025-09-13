from webnovel_archiver.utils.logger import get_logger
from .utils import format_timestamp
from webnovel_archiver.core.storage.progress_epub import get_epub_file_details

logger = get_logger(__name__)

def process_story_for_report(progress_data, workspace_root):
    logger.debug(f"Processing story for report: {progress_data.get('story_id')}")
    story_id = progress_data.get('story_id')

    # Download Progress & Chapter Status Analysis
    chapters = progress_data.get('chapters', [])
    downloaded_chapters_count = 0
    active_chapters_count = 0
    archived_chapters_count = 0
    processed_chapters_for_report = []

    if chapters: # If 'chapters' list exists and is not empty
        for chapter in chapters:
            is_downloaded = chapter.get('local_processed_filename') is not None # Assuming local_processed_filename means downloaded
            if is_downloaded:
                downloaded_chapters_count +=1

            status = chapter.get('status', 'active') # Default to active if status is missing
            if status == 'archived':
                archived_chapters_count += 1
            elif is_downloaded: # Count as active only if downloaded and not archived
                active_chapters_count +=1

            processed_chapters_for_report.append({
                'title': chapter.get('title', 'Untitled Chapter'),
                'url': chapter.get('url'),
                'status': status,
                'downloaded': is_downloaded
            })
    else: # Fallback to using 'downloaded_chapters' if 'chapters' is not available
        downloaded_chapters_list = progress_data.get('downloaded_chapters', [])
        downloaded_chapters_count = len(downloaded_chapters_list)
        # In this fallback, we can't determine active/archived status accurately
        # We might assume all downloaded are active if no other info
        active_chapters_count = downloaded_chapters_count

    total_chapters_source = progress_data.get('estimated_total_chapters_source') # From source (e.g. RoyalRoad)

    # If total_chapters_source is None, use the count of chapters from the 'chapters' list if available
    # This provides a more accurate total if the source estimate is missing but we have a full chapter list
    display_total_chapters = total_chapters_source
    if display_total_chapters is None and chapters:
        display_total_chapters = len(chapters)
    elif display_total_chapters is None: # Still None, means no source estimate and no 'chapters' list
        display_total_chapters = downloaded_chapters_count # Best guess is the number of downloaded chapters

    progress_percentage = 0
    if display_total_chapters and display_total_chapters > 0:
        progress_percentage = int((downloaded_chapters_count / display_total_chapters) * 100)

    progress_text = f"{downloaded_chapters_count} / {display_total_chapters if display_total_chapters is not None else 'N/A'} chapters downloaded"
    if chapters: # Only add active/archived breakdown if we have chapter details
        progress_text += f" ({active_chapters_count} Active, {archived_chapters_count} Archived)"
    elif downloaded_chapters_count > 0 and display_total_chapters is None: # Fallback for older progress files
         progress_text += " (total unknown)"
    elif downloaded_chapters_count == 0 and display_total_chapters is None:
         progress_text = "0 chapters (total unknown)"


    # Story Status
    next_chapter_url = progress_data.get('next_chapter_to_download_url')
    status = "Ongoing"
    if display_total_chapters is not None and downloaded_chapters_count >= display_total_chapters and not next_chapter_url:
        status = "Complete"
    elif display_total_chapters is None and not next_chapter_url and downloaded_chapters_count > 0:
        status = "Possibly Complete (Total Unknown)"
    elif not next_chapter_url and downloaded_chapters_count == 0 and display_total_chapters is None:
        status = "Unknown (No chapters downloaded, total unknown)"

    # Local EPUB Paths
    epub_generation_timestamp_raw = progress_data.get('last_epub_processing', {}).get('timestamp')
    epub_generation_timestamp = format_timestamp(epub_generation_timestamp_raw)

    epub_files = get_epub_file_details(progress_data, story_id, workspace_root)


    # Cloud Backup Status
    cloud_backup_info = progress_data.get('cloud_backup_status', {})
    last_successful_backup_ts_raw = cloud_backup_info.get('last_successful_backup_timestamp')
    formatted_last_successful_backup_ts = format_timestamp(last_successful_backup_ts_raw)
    backup_files_status = cloud_backup_info.get('backed_up_files', [])
    backup_status_summary = "Never Backed Up"
    backup_service = cloud_backup_info.get('service', 'N/A')
    story_cloud_folder_id = cloud_backup_info.get('story_cloud_folder_id')

    if backup_files_status:
        all_uploaded_or_skipped = all(f.get('status') in ['uploaded', 'skipped_up_to_date'] for f in backup_files_status)
        any_failed = any(f.get('status') == 'failed' for f in backup_files_status)
        if any_failed:
            backup_status_summary = "Failed"
        elif all_uploaded_or_skipped and last_successful_backup_ts_raw: # check raw ts here
            backup_status_summary = "OK"
        elif all_uploaded_or_skipped and not last_successful_backup_ts_raw:
            backup_status_summary = "OK (Timestamp Missing)"
        else:
            backup_status_summary = "Partial/Unknown"

    # Last Updated
    last_updated_ts_raw = progress_data.get('last_updated_timestamp')
    formatted_last_updated_ts = format_timestamp(last_updated_ts_raw)

    # Chapters for detailed listing (already processed)
    # processed_chapters_for_report is defined above

    # Calculate last download timestamp (most recent chapter download)
    last_download_ts_raw = None
    if chapters:
        # Find the maximum download_timestamp among downloaded chapters
        download_timestamps = []
        for chapter in chapters:
            if chapter.get('local_processed_filename') and chapter.get('download_timestamp'):
                download_timestamps.append(chapter.get('download_timestamp'))
        if download_timestamps:
            last_download_ts_raw = max(download_timestamps)
    else:
        # Fallback for old format using 'downloaded_chapters'
        download_timestamps = []
        for chapter in progress_data.get('downloaded_chapters', []):
            if chapter.get('download_timestamp'):
                download_timestamps.append(chapter.get('download_timestamp'))
        if download_timestamps:
            last_download_ts_raw = max(download_timestamps)

    formatted_last_download_ts = format_timestamp(last_download_ts_raw)

    # Other Fields
    cover_image_url = progress_data.get('cover_image_url')
    story_url = progress_data.get('story_url')
    title = progress_data.get('effective_title') or progress_data.get('original_title') or "Untitled"
    author = progress_data.get('original_author') or "Unknown Author"
    synopsis = progress_data.get('synopsis') or "No synopsis available."

    return {
        'story_id': story_id,
        'title': title,
        'author': author,
        'story_url': story_url,
        'cover_image_url': cover_image_url,
        'synopsis': synopsis,
        'progress_text': progress_text,
        'progress_percentage': progress_percentage,
        'status': status,
        'epub_files': epub_files,
        'epub_generation_timestamp': epub_generation_timestamp,
        'backup_status_summary': backup_status_summary,
        'formatted_last_successful_backup_ts': formatted_last_successful_backup_ts,
        'backup_service': backup_service,
        'story_cloud_folder_id': story_cloud_folder_id,
        'backup_files_status': backup_files_status,
        'formatted_last_updated_ts': formatted_last_updated_ts,
        'last_download_timestamp': last_download_ts_raw,
        'formatted_last_download_ts': formatted_last_download_ts,
        'chapters_for_report': processed_chapters_for_report, # Add this line
        'active_chapters_count': active_chapters_count, # Add this line
        'archived_chapters_count': archived_chapters_count, # Add this line
    }
