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

# Initialize logger
logger = get_logger(__name__)

def format_timestamp(iso_timestamp_str):
    if not iso_timestamp_str:
        return None
    try:
        dt_obj = datetime.datetime.fromisoformat(iso_timestamp_str.replace('Z', '+00:00'))
        return dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z') # Include timezone
    except ValueError:
        logger.warning(f"Could not parse timestamp: {iso_timestamp_str}", exc_info=True)
        return iso_timestamp_str # Return original if parsing fails

def sanitize_for_css_class(text):
    if not text: return ""
    processed_text = str(text).lower()
    # Replace common separators with hyphens
    processed_text = processed_text.replace(' ', '-').replace('(', '').replace(')', '').replace('/', '-').replace('.', '')
    # Remove any remaining non-alphanumeric characters except hyphens
    processed_text = re.sub(r'[^a-z0-9-]', '', processed_text)
    return processed_text.strip('-')

def generate_epub_list_html(epub_files, story_id_sanitized):
    if not epub_files:
        return "<p class=\"no-items\">No EPUB files found.</p>"

    EPUB_DISPLAY_THRESHOLD = 3
    total_epubs = len(epub_files)
    output_html = "<ul class=\"file-list\">"

    for i, file_data in enumerate(epub_files):
        item_html = f"<li><a href=\"file:///{html.escape(file_data['path'])}\" title=\"{html.escape(file_data['path'])}\">{html.escape(file_data['name'])}</a></li>"
        if i < EPUB_DISPLAY_THRESHOLD:
            output_html += item_html
        else:
            if i == EPUB_DISPLAY_THRESHOLD: # Start of hidden items
                output_html += f"</ul><div id=\"more-epubs-{story_id_sanitized}\" style=\"display:none;\"><ul class=\"file-list\">"
            output_html += item_html
            if i == total_epubs - 1: # End of hidden items
                output_html += "</ul></div>"

    if total_epubs > EPUB_DISPLAY_THRESHOLD:
        if total_epubs - 1 < EPUB_DISPLAY_THRESHOLD : # only one hidden item, close first ul
             output_html += "</ul>" # close the main list if hidden part was not created
        # Add the button/link to toggle visibility
        remaining_count = total_epubs - EPUB_DISPLAY_THRESHOLD
        button_text = f"Show all {total_epubs} EPUBs" # Initial text shows total
        output_html += f"<button type=\"button\" class=\"toggle-epubs-btn\" onclick=\"toggleExtraEpubs('{story_id_sanitized}', this, {total_epubs}, {EPUB_DISPLAY_THRESHOLD})\">{button_text}</button>"
    else:
        output_html += "</ul>" # Close the main list if no hidden part

    return output_html

def generate_backup_files_html(backup_files_list, format_timestamp_func):
    if not backup_files_list:
        return "<p class=\"no-items\">No backup file details.</p>"
    items = ""
    for bf in backup_files_list:
        ts = format_timestamp_func(bf.get('last_backed_up_timestamp')) or 'N/A'
        local_path_display = html.escape(bf.get('local_path', 'N/A'))
        cloud_file_name_display = html.escape(bf.get('cloud_file_name', 'N/A'))
        status_display = html.escape(bf.get('status', 'N/A'))
        items += f"<li>{local_path_display} ({cloud_file_name_display}): {status_display} - Last backed up: {ts}</li>"
    return f"<ul class=\"file-list\">{items}</ul>"

def get_embedded_css():
    return '''
    :root {
        --primary-color: #007bff;
        --primary-hover-color: #0056b3;
        --secondary-color: #6c757d;
        --background-color: #f8f9fa;
        --card-background-color: #ffffff;
        --text-color: #212529;
        --light-text-color: #6c757d;
        --border-color: #dee2e6;
        --shadow-color: rgba(0, 0, 0, 0.05);
        --success-color: #28a745;
        --warning-color: #ffc107;
        --danger-color: #dc3545;
        --info-color: #17a2b8;
    }
    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        margin: 0;
        background-color: var(--background-color);
        color: var(--text-color);
        font-size: 16px;
        line-height: 1.6;
    }
    .container {
        max-width: 1400px;
        margin: 2rem auto;
        padding: 1rem;
    }
    .report-title {
        text-align: center;
        color: var(--text-color);
        margin-bottom: 2rem;
        font-size: 3em;
        font-weight: 600;
    }
    #storyListContainer {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 1.5rem;
    }
    .story-card {
        border: 1px solid var(--border-color);
        background-color: var(--card-background-color);
        border-radius: 12px;
        box-shadow: 0 4px 12px var(--shadow-color);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .story-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
    }
    .story-card-summary {
        display: flex;
        gap: 1rem;
        padding: 1.5rem;
        align-items: center;
    }
    .story-cover img {
        width: 100px;
        height: 140px;
        object-fit: cover;
        border-radius: 8px;
    }
    .story-summary-info {
        flex-grow: 1;
        min-width: 0;
    }
    .story-summary-info h2 {
        margin-top: 0;
        font-size: 1.4em;
        font-weight: 600;
        color: var(--primary-color);
        margin-bottom: 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .story-summary-info h2 a {
        text-decoration: none;
        color: inherit;
    }
    .story-summary-info h2 a:hover {
        text-decoration: underline;
    }
    .story-summary-info p {
        margin: 0.25rem 0;
        color: var(--light-text-color);
        font-size: 0.95em;
    }
    .view-details-btn {
        padding: 0.75rem 1.5rem;
        background-color: var(--primary-color);
        color: white !important;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        margin-top: 1rem;
        font-size: 1em;
        font-weight: 500;
        text-decoration: none;
        display: inline-block;
        text-align: center;
        transition: background-color 0.2s ease;
    }
    .view-details-btn:hover {
        background-color: var(--primary-hover-color);
    }
    .modal {
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.5);
        animation: fadeIn 0.3s;
    }
    @keyframes fadeIn {
        from {opacity: 0;}
        to {opacity: 1;}
    }
    .modal-content {
        background-color: var(--card-background-color);
        margin: 5% auto;
        padding: 2rem;
        border: 1px solid var(--border-color);
        width: 90%;
        max-width: 800px;
        border-radius: 12px;
        position: relative;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        animation: slideIn 0.4s;
    }
    @keyframes slideIn {
        from {transform: translateY(-50px);}
        to {transform: translateY(0);}
    }
    .modal-close-btn {
        color: var(--light-text-color);
        position: absolute;
        top: 1rem;
        right: 1.5rem;
        font-size: 2rem;
        font-weight: bold;
        cursor: pointer;
    }
    .modal-close-btn:hover,
    .modal-close-btn:focus {
        color: var(--text-color);
    }
    #modalBodyContent {
        max-height: 80vh;
        overflow-y: auto;
    }
    .section-title {
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        font-size: 1.2em;
        color: var(--text-color);
        border-bottom: 2px solid var(--primary-color);
        padding-bottom: 0.5rem;
    }
    .file-list {
        list-style: none;
        padding-left: 0;
    }
    .file-list li {
        font-size: 1em;
        margin-bottom: 0.5rem;
        padding: 0.75rem 1rem;
        background-color: var(--background-color);
        border-left: 4px solid var(--primary-color);
        border-radius: 4px;
    }
    .file-list li a {
        text-decoration: none;
        color: var(--primary-hover-color);
        font-weight: 500;
    }
    .badge {
        display: inline-block;
        padding: .4em .75em;
        font-size: .8em;
        font-weight: 600;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 20px;
    }
    .status-complete { background-color: var(--success-color); color: white; }
    .status-ongoing { background-color: var(--warning-color); color: var(--text-color); }
    .status-possibly-complete-total-unknown { background-color: var(--info-color); color: white; }
    .status-unknown-no-chapters-downloaded-total-unknown { background-color: var(--secondary-color); color: white; }
    .backup-ok { background-color: var(--success-color); color: white; }
    .backup-failed { background-color: var(--danger-color); color: white; }
    .backup-never-backed-up { background-color: var(--secondary-color); color: white; }
    .backup-partial-unknown { background-color: var(--warning-color); color: var(--text-color); }
    .backup-ok-timestamp-missing { background-color: var(--info-color); color: white; }
    .search-sort-filter {
        margin-bottom: 2rem;
        padding: 1.5rem;
        background-color: var(--card-background-color);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: center;
    }
    .search-sort-filter input, .search-sort-filter select {
        padding: 0.75rem 1rem;
        border-radius: 8px;
        border: 1px solid var(--border-color);
        font-size: 1em;
        background-color: #fff;
    }
    .search-sort-filter input:focus, .search-sort-filter select:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(0,123,255,.25);
        outline: none;
    }
    .search-sort-filter input[type="text"] {
        flex-grow: 1;
        min-width: 250px;
    }
    '''


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

def get_html_skeleton(title_text, css_styles, body_content, js_script=""):
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title_text)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        {css_styles}
    </style>
</head>
<body>
    {body_content}

    <div id="storyDetailModal" class="modal">
        <div class="modal-content">
            <span class="modal-close-btn">&times;</span>
            <div id="modalBodyContent">
                <!-- Story details will be injected here by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        {js_script}
    </script>
</body>
</html>
'''

def generate_story_card_html(story_data, format_timestamp_func):
    title = html.escape(story_data.get('title') or 'Untitled')
    author = html.escape(story_data.get('author') or 'Unknown Author')
    story_url = html.escape(story_data.get('story_url') or '#')
    cover_image_url = html.escape(story_data.get('cover_image_url') or 'https://via.placeholder.com/150x220.png?text=No+Cover')
    synopsis = html.escape(story_data.get('synopsis') or 'No synopsis available.')
    progress_text = html.escape(story_data.get('progress_text') or 'N/A')
    status_display_text = html.escape(story_data.get('status') or 'N/A')
    epub_gen_ts = html.escape(story_data.get('epub_generation_timestamp') or 'N/A')

    epub_files_list = story_data.get('epub_files', [])
    story_id_for_epub_toggle = sanitize_for_css_class(story_data.get('story_id') or '')
    story_id_display = html.escape(story_data.get('story_id') or 'N/A')
    backup_summary_display_text = html.escape(story_data.get('backup_status_summary') or 'N/A')
    backup_service = html.escape(story_data.get('backup_service') or 'N/A')
    backup_last_success_ts = html.escape(story_data.get('formatted_last_successful_backup_ts') or 'N/A')
    backup_files_detail_list = story_data.get('backup_files_status', [])
    last_updated = html.escape(story_data.get('formatted_last_updated_ts') or 'N/A')
    chapters_for_report = story_data.get('chapters_for_report', [])

    data_title = html.escape(story_data.get('title') or '')
    data_author = html.escape(story_data.get('author') or '')
    data_status = html.escape(story_data.get('status') or '')
    data_last_updated = html.escape(story_data.get('last_updated_timestamp') or '')
    data_progress = html.escape(str(story_data.get('progress_percentage', 0)))

    status_class = sanitize_for_css_class(story_data.get('status'))
    backup_summary_class = sanitize_for_css_class(story_data.get('backup_status_summary'))

    epub_list_html = generate_epub_list_html(epub_files_list, story_id_for_epub_toggle)
    story_id_for_modal = story_id_for_epub_toggle

    chapters_html = ""
    if chapters_for_report:
        chapter_items = []
        for chapter in chapters_for_report:
            title = html.escape(chapter.get('title', 'Untitled Chapter'))
            url = html.escape(chapter.get('url', '#'))
            status = chapter.get('status', 'active')
            downloaded = chapter.get('downloaded', False)

            status_marker = ""
            if status == 'archived':
                status_marker = " [Archived]"

            download_status_display = " (Downloaded)" if downloaded else " (Not Downloaded)"
            if url and url != '#':
                chapter_items.append(f'<li><a href="{url}" target="_blank">{title}</a>{status_marker}{download_status_display}</li>')
            else:
                chapter_items.append(f'<li>{title}{status_marker}{download_status_display}</li>')

        if chapter_items:
            chapters_html = f'''
            <p class="section-title">Chapters ({len(chapters_for_report)} total):</p>
            <ul class="file-list chapter-list">{' '.join(chapter_items)}</ul>
            '''
        else:
            chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'
    else:
        chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'

    card_html = f'''
    <div class="story-card" data-title="{data_title}" data-author="{data_author}" data-status="{data_status}" data-last-updated="{data_last_updated}" data-progress="{data_progress}">
        <div class="story-card-summary">
            <div class="story-cover">
                <img src="{cover_image_url}" alt="Cover for {title}">
            </div>
            <div class="story-summary-info">
                <h2><a href="{story_url}" target="_blank">{title}</a></h2>
                <p><strong>Author:</strong> {author}</p>
                <p><strong>Story ID:</strong> {story_id_display}</p>
                <p><strong>Progress:</strong> {progress_text}</p>
                <button class="view-details-btn" data-story-id="{story_id_for_modal}">View Details</button>
            </div>
        </div>
        <div class="story-card-modal-content" style="display: none;">
            <p class="section-title">Synopsis:</p>
            <div class="synopsis" onclick="toggleSynopsis(this)">{synopsis}</div>
            <span class="synopsis-toggle" onclick="toggleSynopsis(this.previousElementSibling)">(Read more)</span>

            <p class="section-title">Download Progress:</p>
            <p>{progress_text}</p>
            <p><strong>Story Status:</strong> <span class="badge status-{status_class}">{status_display_text}</span></p>

            {chapters_html}

            <p class="section-title">Local EPUBs (Generated: {epub_gen_ts}):</p>
            {epub_list_html}

            <p class="section-title">Cloud Backup:</p>
            <p><strong>Status:</strong> <span class="badge backup-{backup_summary_class}">{backup_summary_display_text}</span>
               (Service: {backup_service})
            </p>
            <p>Last Successful Backup: {backup_last_success_ts}</p>
            {generate_backup_files_html(backup_files_detail_list, format_timestamp)}

            <p class="section-title">Last Local Update:</p>
            <p>{last_updated}</p>
        </div>
    </div>
    '''
    return card_html


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
            is_downloaded = chapter.get('content_file') is not None # Assuming content_file means downloaded
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
        <input type="text" id="searchInput" onkeyup="filterStories()" placeholder="Search by title or author..." aria-label="Search stories">
        <select id="sortSelect" onchange="sortStories()" aria-label="Sort stories by">
            <option value="title">Sort by Title (A-Z)</option>
            <option value="last_updated_desc">Sort by Last Updated (Newest First)</option>
            <option value="last_updated_asc">Sort by Last Updated (Oldest First)</option>
            <option value="progress_desc">Sort by Progress (Highest First)</option>
        </select>
    </div>
    """

    main_body_content = f'''<div class="container">
        <h1 class="report-title">Webnovel Archive Report</h1>
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
