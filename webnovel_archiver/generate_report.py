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
from webnovel_archiver.core.storage.progress_manager import load_progress, DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR, EBOOKS_DIR, get_epub_file_details
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
    return """
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 0; background-color: #f9f9f9; color: #212529; font-size: 16px; line-height: 1.6; }
    .container { max-width: 1200px; margin: 20px auto; padding: 25px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.075); }
    .report-title { text-align: center; color: #343a40; margin-bottom: 30px; font-size: 2.5em; font-weight: 300; }

    #storyListContainer { display: flex; flex-wrap: wrap; gap: 20px; justify-content: flex-start; }

    .story-card {
        flex-basis: 320px; /* Default width for cards, adjust as needed */
        flex-grow: 1;
        max-width: 100%; /* Ensure it doesn't overflow container on very small screens before wrapping */
        border: 1px solid #e0e0e0;
        background-color: #fff;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        /* margin-bottom: 20px; /* Replaced by gap in #storyListContainer */
        display: flex; /* This flex is for the card itself to be a flex item */
        flex-direction: column; /* Stacks summary and hidden modal content vertically */
        overflow: hidden; /* Prevents content like box shadow from breaking layout */
    }

    .story-card-summary {
        display: flex;
        gap: 15px;
        padding: 15px;
        align-items: flex-start; /* Align items at the start of the cross axis */
    }

    .story-cover {
        flex-basis: 100px; /* Smaller cover for card view */
        flex-shrink: 0;
        flex-grow: 0;
    }
    .story-cover img {
        width: 100%;
        height: auto;
        display: block; /* Removes extra space below img */
        border-radius: 4px;
        /* border: 1px solid #ced4da; /* Optional: border for cover image */
    }

    .story-summary-info {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        justify-content: flex-start; /* Content flows top to bottom */
        min-width: 0; /* Prevents text overflow issues in flex item */
    }
    .story-summary-info h2 {
        margin-top: 0;
        font-size: 1.2em; /* Adjusted for card layout */
        font-weight: 500;
        color: #007bff;
        margin-bottom: 8px;
        word-break: break-word; /* Prevent overflow */
    }
    .story-summary-info h2 a { text-decoration: none; color: inherit; }
    .story-summary-info h2 a:hover { text-decoration: underline; }
    .story-summary-info p {
        margin-top: 0;
        margin-bottom: 8px; /* Adjusted spacing */
        color: #495057;
        font-size: 0.9em;
        word-break: break-word; /* Prevent overflow */
    }

    .view-details-btn {
        padding: 8px 12px;
        background-color: #007bff;
        color: white !important; /* Important to override potential link styles if it were an <a> */
        border: none;
        border-radius: 4px;
        cursor: pointer;
        margin-top: auto; /* Pushes button to the bottom of its flex container (.story-summary-info) */
        font-size: 0.9em;
        text-decoration: none; /* In case it's an <a> styled as a button */
        display: inline-block; /* Or block if full width is desired */
        text-align: center;
    }
    .view-details-btn:hover {
        background-color: #0056b3;
        text-decoration: none;
    }

    /* .story-details { flex-grow: 1; min-width: 0; } /* This was for the old layout, content now in modal */
    /* General h2 and p inside story-card were too broad, now scoped to story-summary-info or apply to modal content */

    .synopsis { max-height: 6em; /* Approx 3-4 lines based on line-height */ overflow: hidden; transition: max-height 0.3s ease-out; margin-bottom: 0px; position: relative; cursor: pointer;}
    .synopsis.expanded { max-height: 500px; /* Sufficiently large */ }
    .synopsis-toggle { color: #007bff; cursor: pointer; display: block; margin-top: 0px; font-size: 0.9em; text-align: right; }
    .progress-bar-container { background-color: #e9ecef; border-radius: .25rem; height: 22px; overflow: hidden; margin-bottom: 8px; }
    .progress-bar { background-color: #28a745; height: 100%; line-height: 22px; color: white; text-align: center; font-weight: bold; transition: width 0.4s ease; font-size: 0.85em; }
    .badge { display: inline-block; padding: .35em .65em; font-size: .75em; font-weight: 700; line-height: 1; text-align: center; white-space: nowrap; vertical-align: baseline; border-radius: .25rem; }
    .status-complete { background-color: #28a745; color: white; }
    .status-ongoing { background-color: #ffc107; color: #212529; }
    .status-possibly-complete-total-unknown { background-color: #17a2b8; color: white; }
    .status-unknown-no-chapters-downloaded-total-unknown { background-color: #6c757d; color: white; }
    .backup-ok { background-color: #28a745; color: white; }
    .backup-failed { background-color: #dc3545; color: white; }
    .backup-never-backed-up { background-color: #6c757d; color: white; } /* Adjusted class name */
    .backup-partial-unknown { background-color: #ffc107; color: #212529; }
    .backup-ok-timestamp-missing { background-color: #17a2b8; color: white; }
    .section-title { font-weight: 600; margin-top: 12px; margin-bottom: 10px; font-size: 1em; color: #222; border-bottom: 1px solid #eaeaea; padding-bottom: 5px;}
    .file-list { list-style: none; padding-left: 0; margin-bottom: 10px; }
    .file-list li { font-size: 0.9em; margin-bottom: 6px; color: #495057; word-break: break-all; padding: 8px 12px; background-color: #f0f0f0; border: 1px solid #dcdcdc; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .file-list li a { text-decoration: none; color: #0056b3; }
    .file-list li a:hover { text-decoration: underline; }
    .no-items { color: #6c757d; font-style: italic; font-size: 0.9em; }
    .search-sort-filter { margin-bottom: 20px; padding: 20px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }
    .search-sort-filter input, .search-sort-filter select { padding: 12px; border-radius: 6px; border: 1px solid #ccc; font-size: 0.95em; }
    .search-sort-filter input:focus, .search-sort-filter select:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
    .search-sort-filter input[type="text"] { flex-grow: 1; min-width: 200px; }

    /* Toggle Epubs Button Style */
    .toggle-epubs-btn {
        background-color: #007bff;
        color: white !important;
        padding: 8px 15px;
        border: none;
        border-radius: 5px;
        text-decoration: none;
        cursor: pointer;
        display: inline-block;
        margin-top: 10px;
        font-size: 0.9em;
    }
    .toggle-epubs-btn:hover {
        background-color: #0056b3;
        text-decoration: none;
    }

    /* Modal Styles */
    .modal {
        display: none; /* Hidden by default */
        position: fixed; /* Stay in place */
        z-index: 1000; /* Sit on top */
        left: 0;
        top: 0;
        width: 100%; /* Full width */
        height: 100%; /* Full height */
        overflow: auto; /* Enable scroll if needed */
        background-color: rgba(0,0,0,0.4); /* Black w/ opacity */
    }
    .modal-content {
        background-color: #fefefe;
        margin: 10% auto; /* 10% from the top and centered */
        padding: 20px;
        border: 1px solid #888;
        width: 80%; /* Could be more or less, depending on screen size */
        border-radius: 8px;
        position: relative;
        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
    }
    .modal-close-btn {
        color: #aaa;
        float: right;
        font-size: 28px;
        font-weight: bold;
    }
    .modal-close-btn:hover,
    .modal-close-btn:focus {
        color: black;
        text-decoration: none;
        cursor: pointer;
    }
    #modalBodyContent {
        max-height: 70vh; /* Example: limit height and make it scrollable if content overflows */
        overflow-y: auto;
    }
    /* Ensure section titles and other elements within modalBodyContent are styled correctly */
    #modalBodyContent .section-title { /* Scoping section-title for modal if needed, but global one should be fine */
        margin-top: 15px; /* Add a bit more top margin for sections in modal */
    }
    #modalBodyContent .section-title:first-child {
        margin-top: 0; /* No extra margin for the very first section title in modal */
    }
    #modalBodyContent .file-list li { /* Example of adjusting list item padding in modal */
        padding: 6px 10px;
    }

    """

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
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title_text)}</title>
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
"""

def generate_story_card_html(story_data, format_timestamp_func):
    title = html.escape(story_data.get('title') or 'Untitled')
    author = html.escape(story_data.get('author') or 'Unknown Author')
    story_url = html.escape(story_data.get('story_url') or '#')
    cover_image_url = html.escape(story_data.get('cover_image_url') or 'https://via.placeholder.com/150x220.png?text=No+Cover')
    synopsis = html.escape(story_data.get('synopsis') or 'No synopsis available.')
    progress_percentage = story_data.get('progress_percentage', 0) # Keep as is, not directly escaped
    progress_text = html.escape(story_data.get('progress_text') or 'N/A')
    status_display_text = html.escape(story_data.get('status') or 'N/A') # For display
    epub_gen_ts = html.escape(story_data.get('epub_generation_timestamp') or 'N/A') # Already uses 'or'

    epub_files_list = story_data.get('epub_files', [])
    story_id_for_epub_toggle = sanitize_for_css_class(story_data.get('story_id') or '') # Sanitize story_id
    story_id_display = html.escape(story_data.get('story_id') or 'N/A')
    backup_summary_display_text = html.escape(story_data.get('backup_status_summary') or 'N/A')
    backup_service = html.escape(story_data.get('backup_service') or 'N/A')
    backup_last_success_ts = html.escape(story_data.get('formatted_last_successful_backup_ts') or 'N/A') # Already uses 'or'
    backup_files_detail_list = story_data.get('backup_files_status', []) # Not escaped directly, handled by generate_backup_files_html
    last_updated = html.escape(story_data.get('formatted_last_updated_ts') or 'N/A') # Already uses 'or'
    chapters_for_report = story_data.get('chapters_for_report', []) # Get the new chapter data

    # Data attributes for JS (raw values are fine, but escape them for safety in attributes)
    # Apply `or ''` pattern for data attributes to ensure they are strings.
    data_title = html.escape(story_data.get('title') or '')
    data_author = html.escape(story_data.get('author') or '')
    data_status = html.escape(story_data.get('status') or '') # Raw status for filtering logic
    data_last_updated = html.escape(story_data.get('last_updated_timestamp') or '') # Raw ISO for sorting
    data_progress = html.escape(str(progress_percentage)) # Already a string or number

    # CSS class names from statuses (these should not be HTML escaped, sanitize_for_css_class handles None)
    status_class = sanitize_for_css_class(story_data.get('status')) # Removed default from .get()
    backup_summary_class = sanitize_for_css_class(story_data.get('backup_status_summary')) # Removed default from .get()

    epub_list_html = generate_epub_list_html(epub_files_list, story_id_for_epub_toggle)
    story_id_for_modal = story_id_for_epub_toggle # Re-use sanitized ID

    # Generate HTML for chapter list
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

            # Display link if URL exists, otherwise just title. Add downloaded status.
            # Add class for styling based on status if needed later.
            download_status_display = " (Downloaded)" if downloaded else " (Not Downloaded)"
            if url and url != '#':
                chapter_items.append(f"<li><a href=\"{url}\" target=\"_blank\">{title}</a>{status_marker}{download_status_display}</li>")
            else:
                chapter_items.append(f"<li>{title}{status_marker}{download_status_display}</li>")

        if chapter_items:
            chapters_html = f"""
            <p class="section-title">Chapters ({len(chapters_for_report)} total):</p>
            <ul class="file-list chapter-list">{''.join(chapter_items)}</ul>
            """
        else:
            chapters_html = "<p class=\"section-title\">Chapters:</p><p class=\"no-items\">No chapter details available.</p>"
    else:
        chapters_html = "<p class=\"section-title\">Chapters:</p><p class=\"no-items\">No chapter details available.</p>"


    card_html = f"""
    <div class="story-card" data-title="{data_title}" data-author="{data_author}" data-status="{data_status}" data-last-updated="{data_last_updated}" data-progress="{data_progress}">
        <div class="story-card-summary">
            <div class="story-cover">
                <img src="{cover_image_url}" alt="Cover for {title}">
            </div>
            <div class="story-summary-info">
                <h2><a href="{story_url}" target="_blank">{title}</a></h2>
                <p><strong>Author:</strong> {author}</p>
                <p><strong>Story ID:</strong> {story_id_display}</p>
                <button class="view-details-btn" data-story-id="{story_id_for_modal}">View Details</button>
            </div>
        </div>
        <div class="story-card-modal-content" style="display: none;">
            <p class="section-title">Synopsis:</p>
            <div class="synopsis" onclick="toggleSynopsis(this)">{synopsis}</div>
            <span class="synopsis-toggle" onclick="toggleSynopsis(this.previousElementSibling)">(Read more)</span>

            <p class="section-title">Download Progress:</p>
            <div class="progress-bar-container">
                <div class="progress-bar" style="width:{progress_percentage}%;">{progress_percentage}%</div>
            </div>
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
    """
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

    print(f"DEBUG [process_story]: story_id for get_epub_file_details: {story_id}, workspace_root: {workspace_root}")
    epub_files = get_epub_file_details(progress_data, story_id, workspace_root)
    print(f"DEBUG [process_story]: epub_files returned: {epub_files}")


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
    # logger.info(f"WNA_WORKSPACE_ROOT env var from within main(): {os.getenv('WNA_WORKSPACE_ROOT')}") # Removed temp debug
    logger.info("HTML report generation script started.")

    logger.info("Determining workspace and report output paths...")
    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
        # workspace_root = "/app/test_workspace" # TEMP OVERRIDE FOR TESTING - REMOVED
        # logger.info(f"Using TEMPORARY workspace_root override: {workspace_root}") # Removed temp debug


        if not workspace_root: # Should not happen with default fallback in ConfigManager
            logger.error("Workspace root could not be determined. Exiting.")
            return

        archival_status_path = os.path.join(workspace_root, ARCHIVAL_STATUS_DIR)
        reports_dir = os.path.join(workspace_root, "reports")

        # Create reports directory if it doesn't exist
        os.makedirs(reports_dir, exist_ok=True)
        logger.info(f"Ensured reports directory exists at: {reports_dir}")

        report_html_path = os.path.join(reports_dir, "archive_report.html")

        logger.info(f"Workspace root: {workspace_root}")
        logger.info(f"Archival status path: {archival_status_path}")
        logger.info(f"Reports directory: {reports_dir}")
        logger.info(f"Report HTML will be saved to: {report_html_path}")

    except Exception as e:
        logger.error(f"Error during path determination: {e}", exc_info=True)
        return

    # Further implementation will go here (story discovery, processing, HTML generation)

    logger.info("Discovering and loading story progress data...")
    all_story_data = []

    if not os.path.exists(archival_status_path) or not os.path.isdir(archival_status_path):
        logger.error(f"Archival status path does not exist or is not a directory: {archival_status_path}")
        logger.info("No stories to process. Exiting.")
        return

    story_ids = [name for name in os.listdir(archival_status_path)
                 if os.path.isdir(os.path.join(archival_status_path, name))]

    if not story_ids:
        logger.info(f"No story subdirectories found in {archival_status_path}.")
        # Generate an empty report later, or just exit for now
        # For now, let's log and proceed to generate an empty report.
    else:
        logger.info(f"Found {len(story_ids)} potential story directories.")
        # print(f"DEBUG: Found {len(story_ids)} story IDs: {story_ids}") # TEMP DEBUG PRINT - REMOVED

    for story_id in story_ids:
        logger.debug(f"Processing story_id: {story_id}")
        try:
            # Pass workspace_root to load_progress as it's needed for resolving potential relative paths
            # within the progress file if any, or for default values.
            progress_data = load_progress(story_id, workspace_root)
            # print(f"DEBUG: Loaded progress for {story_id}: {progress_data.get('title', 'NO TITLE LOADED')} - Keys: {list(progress_data.keys())}") # TEMP DEBUG PRINT - REMOVED

            # Ensure that loaded_data is not None and contains story_id,
            # which load_progress should guarantee by returning a new structure if file is missing/corrupt.
            if progress_data and progress_data.get("story_id"):
                all_story_data.append(progress_data)
                logger.debug(f"Successfully loaded progress for story_id: {story_id}")
            else:
                # This case should ideally not be hit if load_progress always returns a valid structure
                logger.warning(f"Failed to load valid progress data for story_id: {story_id} or data is malformed. Skipping.")
        except Exception as e:
            logger.error(f"Error loading progress for story_id {story_id}: {e}", exc_info=True)
            # Decide if you want to skip this story or halt. For a report, skipping is better.

    logger.info(f"Successfully loaded data for {len(all_story_data)} out of {len(story_ids)} stories found.")

    # Store workspace_root and report_html_path to be accessible by other functions if needed
    # For now, they are local to main, which is fine as we'll pass them around.

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

    final_html = ""
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

    if final_html: # Ensure final_html was actually generated
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
        except IOError as e: # More specific exception for file I/O
            logger.error(f"Failed to write HTML report due to IOError {report_html_path}: {e}", exc_info=True)
            print(f"Error: Could not write HTML report to {report_html_path}. Check logs for details.")
        except Exception as e: # General exception
            logger.error(f"An unexpected error occurred while writing HTML report to {report_html_path}: {e}", exc_info=True)
            print(f"Error: An unexpected error occurred while writing HTML report. Check logs for details.")
    else:
        logger.warning("final_html string is empty. Report file will not be written.")
        print("Notice: No HTML content was generated, so the report file was not written.")

    logger.info("HTML report generation script finished.")

if __name__ == '__main__':
    main()
