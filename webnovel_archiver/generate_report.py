import os
import json
import datetime
import sys
import re
import html # For escaping HTML content
import webbrowser # Added to open the report in a browser

# Adjust path to import sibling modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from webnovel_archiver.core.config_manager import ConfigManager
from webnovel_archiver.core.storage.progress_manager import load_progress, get_epub_file_details # Removed constants
# from webnovel_archiver.core.path_manager import PathManager # For ARCHIVAL_STATUS_DIR_NAME
from webnovel_archiver.core.path_manager import PathManager # Import PathManager to access its constants
from webnovel_archiver.utils.logger import get_logger
from .report.utils import format_timestamp, sanitize_for_css_class
from .report.html_generator import generate_story_card_html, get_html_skeleton
from .report.processor import process_story_for_report

# Initialize logger
logger = get_logger(__name__)

def get_embedded_css():
    css_path = os.path.join(os.path.dirname(__file__), 'report', 'report.css')
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"CSS file not found: {css_path}")
        return "/* Error: report.css not found. */"
    except Exception as e:
        logger.error(f"Error reading CSS file {css_path}: {e}", exc_info=True)
        return f"/* Error loading report.css: {str(e).replace('`', '')} */"


def get_javascript():
    script_path = os.path.join(os.path.dirname(__file__), 'report_scripts.js')
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"JavaScript file not found: {script_path}")
        return "console.error('Error: report_scripts.js not found.');"
    except Exception as e:
        logger.error(f"Error reading JavaScript file {script_path}: {e}", exc_info=True)
        return f"console.error('Error loading report_scripts.js: {str(e).replace('`', '')}');"


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
    formatted_last_download_ts = format_timestamp(last_download_ts_raw)

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

def main():
    logger.info("HTML report generation script started.")

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
        if not workspace_root:
            logger.error("Workspace root could not be determined. Exiting.")
            return

        path_manager = PathManager(workspace_root)
        index_path = path_manager.index_path
        reports_dir = os.path.join(workspace_root, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_html_path = os.path.join(reports_dir, "archive_report_new.html")

        logger.info(f"Workspace root: {workspace_root}")
        logger.info(f"Index path: {index_path}")
        logger.info(f"Report will be saved to: {report_html_path}")

    except Exception as e:
        logger.error(f"Error during path determination: {e}", exc_info=True)
        return

    if not os.path.exists(index_path):
        logger.error(f"Index file not found at {index_path}. Cannot generate report.")
        print(f"Error: Story index '{index_path}' not found. Please run the archiver at least once to create it.")
        return

    try:
        with open(index_path, 'r', encoding='utf-8') as f:
            story_index = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load or parse index file: {e}", exc_info=True)
        return

    if not story_index:
        logger.info("Story index is empty. No stories to report.")
        story_index = {}

    logger.info(f"Found {len(story_index)} stories in the index.")

    all_story_data = []
    for permanent_id, story_folder_name in story_index.items():
        logger.debug(f"Processing story: Permanent ID: {permanent_id}, Folder: {story_folder_name}")
        try:
            progress_data = load_progress(story_folder_name, workspace_root)
            if progress_data and progress_data.get("story_id"):
                # Add permanent_id to the data for use in the report
                progress_data['permanent_id'] = permanent_id
                all_story_data.append(progress_data)
            else:
                logger.warning(f"Failed to load valid progress data for story: {story_folder_name}. Skipping.")
        except Exception as e:
            logger.error(f"Error loading progress for story {story_folder_name}: {e}", exc_info=True)

    logger.info(f"Successfully loaded data for {len(all_story_data)} stories.")

    processed_stories = []
    if all_story_data:
        logger.info(f"Processing {len(all_story_data)} stories for the report...")
        for story_data in all_story_data:
            try:
                processed_data = process_story_for_report(story_data, workspace_root)
                processed_stories.append(processed_data)
            except Exception as e:
                logger.error(f"Error processing story data for story_id {story_data.get('story_id', 'N/A')}: {e}", exc_info=True)
        logger.info(f"Successfully processed {len(processed_stories)} stories.")
    else:
        logger.info("No story data to process for the report.")

    story_cards_html_list = []
    if not processed_stories:
        story_cards_html = "<p class=\"no-items\">No stories found in the archive to report.</p>"
    else:
        logger.info(f"Generating HTML cards for {len(processed_stories)} stories...")
        for story_data in processed_stories:
            try:
                story_cards_html_list.append(generate_story_card_html(story_data, format_timestamp))
            except Exception as e:
                logger.error(f"Error generating HTML card for story_id {story_data.get('story_id', 'N/A')}: {e}", exc_info=True)
        story_cards_html = "".join(story_cards_html_list)
        logger.info(f"Successfully generated {len(story_cards_html_list)} HTML cards.")

    css_styles = get_embedded_css()
    header_controls = """
    <div class="search-sort-filter">
        <input type="text" id="searchInput" placeholder="Search by title, author, or status..." aria-label="Search stories">
        <select id="sortSelect" aria-label="Sort stories by">
            <option value="title">📖 Title (A-Z)</option>
            <option value="author">✍️ Author (A-Z)</option>
            <option value="last_updated_desc" selected>🕒 Last Download (Newest)</option>
            <option value="last_updated_asc">🕒 Last Download (Oldest)</option>
            <option value="progress_desc">📊 Progress (Highest)</option>
            <option value="progress_asc">📊 Progress (Lowest)</option>
        </select>
    </div>
    """

    # Get current timestamp for the report
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    main_body_content = f'''<div class="container">
        <div class="report-header">
            <h1 class="report-title">Webnovel Archive Report</h1>
            <p class="report-subtitle">Generated on {current_time} • {len(processed_stories)} stories archived</p>
        </div>
        {header_controls}
        <div id="storyListContainer">{story_cards_html}</div>
    </div>'''
    js_code = get_javascript()
    final_html = get_html_skeleton("Webnovel Archive Report", css_styles, main_body_content, js_code)
    logger.info("Successfully generated HTML content string.")

    if final_html:
        logger.info(f"Attempting to write HTML report to: {report_html_path}")
        try:
            with open(report_html_path, 'w', encoding='utf-8') as f:
                f.write(final_html)
            logger.info(f"Successfully wrote HTML report to: {report_html_path}")
            print(f"HTML report generated: {report_html_path}")
            try:
                webbrowser.open_new_tab(f"file:///{os.path.abspath(report_html_path)}")
                logger.info(f"Attempted to open HTML report in browser: {report_html_path}")
            except Exception as e_browser:
                logger.error(f"Failed to open report in browser: {e_browser}", exc_info=True)
                print(f"Note: Could not open report in browser. Error: {e_browser}")
        except IOError as e:
            logger.error(f"Failed to write HTML report due to IOError {report_html_path}: {e}", exc_info=True)
            print(f"Error: Could not write HTML report to {report_html_path}. Check logs for details.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while writing HTML report to {report_html_path}: {e}", exc_info=True)
            print(f"Error: An unexpected error occurred while writing HTML report. Check logs for details.")
    else:
        logger.warning("final_html string is empty. Report file will not be written.")
        print("Notice: No HTML content was generated, so the report file was not written.")

    logger.info("HTML report generation script finished.")

if __name__ == '__main__':
    main()
