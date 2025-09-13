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
        /* Material Design 3 Color System */
        --primary-color: #6750a4;
        --primary-hover-color: #5a4a8a;
        --primary-container: #eaddff;
        --on-primary: #ffffff;
        --on-primary-container: #21005e;
        
        --secondary-color: #625b71;
        --secondary-container: #e8def8;
        --on-secondary: #ffffff;
        --on-secondary-container: #1d192b;
        
        --tertiary-color: #7d5260;
        --tertiary-container: #ffd8e4;
        --on-tertiary: #ffffff;
        --on-tertiary-container: #31111d;
        
        --background-color: #fef7ff;
        --surface-color: #fef7ff;
        --surface-variant: #e7e0ec;
        --on-surface: #1c1b1f;
        --on-surface-variant: #49454f;
        
        --outline: #79747e;
        --outline-variant: #cac4d0;
        
        --error-color: #ba1a1a;
        --error-container: #ffdad6;
        --on-error: #ffffff;
        --on-error-container: #410002;
        
        --success-color: #0d904f;
        --success-container: #d1f4e0;
        --warning-color: #f57c00;
        --warning-container: #ffe0b2;
        --info-color: #1976d2;
        --info-container: #e3f2fd;
        
        /* Status Colors */
        --status-complete: var(--success-color);
        --status-ongoing: var(--warning-color);
        --status-unknown: var(--secondary-color);
        --status-possibly-complete: var(--info-color);
        
        /* Backup Status Colors */
        --backup-ok: var(--success-color);
        --backup-failed: var(--error-color);
        --backup-never: var(--secondary-color);
        --backup-partial: var(--warning-color);
        --backup-ok-no-timestamp: var(--info-color);
        
        /* Shadows */
        --shadow-1: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
        --shadow-2: 0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23);
        --shadow-3: 0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.23);
        --shadow-4: 0 14px 28px rgba(0,0,0,0.25), 0 10px 10px rgba(0,0,0,0.22);
        
        /* Spacing */
        --spacing-xs: 0.25rem;
        --spacing-sm: 0.5rem;
        --spacing-md: 1rem;
        --spacing-lg: 1.5rem;
        --spacing-xl: 2rem;
        --spacing-2xl: 3rem;
        
        /* Border Radius */
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 24px;
        
        /* Typography */
        --font-size-xs: 0.75rem;
        --font-size-sm: 0.875rem;
        --font-size-base: 1rem;
        --font-size-lg: 1.125rem;
        --font-size-xl: 1.25rem;
        --font-size-2xl: 1.5rem;
        --font-size-3xl: 1.875rem;
        --font-size-4xl: 2.25rem;
        
        /* Z-Fold 7 Breakpoints */
        --fold-cover-width: 904px;
        --fold-main-width: 1812px;
    }
    
    /* Dark Mode Support */
    @media (prefers-color-scheme: dark) {
        :root {
            --background-color: #141218;
            --surface-color: #141218;
            --surface-variant: #49454f;
            --on-surface: #e6e1e5;
            --on-surface-variant: #cac4d0;
            
            --primary-container: #4f378b;
            --on-primary-container: #eaddff;
            --secondary-container: #4a4458;
            --on-secondary-container: #e8def8;
            --tertiary-container: #633b48;
            --on-tertiary-container: #ffd8e4;
            
            --outline: #938f99;
            --outline-variant: #49454f;
        }
    }
    
    * {
        box-sizing: border-box;
    }
    
    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        margin: 0;
        padding: 0;
        background-color: var(--background-color);
        color: var(--on-surface);
        font-size: var(--font-size-base);
        line-height: 1.6;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        overflow-x: hidden;
    }
    
    /* Container and Layout */
    .container {
        max-width: min(100vw, 1400px);
        margin: 0 auto;
        padding: var(--spacing-lg);
        min-height: 100vh;
    }
    
    .report-header {
        text-align: center;
        margin-bottom: var(--spacing-2xl);
        padding: var(--spacing-xl) 0;
    }
    
    .report-title {
        font-size: clamp(var(--font-size-3xl), 5vw, var(--font-size-4xl));
        font-weight: 700;
        color: var(--on-surface);
        margin: 0 0 var(--spacing-md) 0;
        letter-spacing: -0.025em;
    }
    
    .report-subtitle {
        font-size: var(--font-size-lg);
        color: var(--on-surface-variant);
        margin: 0;
        font-weight: 400;
    }
    
    /* Search and Filter Controls */
    .search-sort-filter {
        background-color: var(--surface-color);
        border: 1px solid var(--outline-variant);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        margin-bottom: var(--spacing-xl);
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-md);
        align-items: center;
        box-shadow: var(--shadow-1);
        backdrop-filter: blur(10px);
    }
    
    .search-sort-filter input,
    .search-sort-filter select {
        padding: var(--spacing-md) var(--spacing-lg);
        border: 1px solid var(--outline-variant);
        border-radius: var(--radius-md);
        font-size: var(--font-size-base);
        background-color: var(--surface-color);
        color: var(--on-surface);
        transition: all 0.2s ease;
        min-height: 48px;
    }
    
    .search-sort-filter input:focus,
    .search-sort-filter select:focus {
        outline: none;
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(103, 80, 164, 0.1);
    }
    
    .search-sort-filter input[type="text"] {
        flex: 1;
        min-width: 200px;
    }
    
    .search-sort-filter select {
        min-width: 180px;
    }
    
    /* Story Grid */
    #storyListContainer {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: var(--spacing-lg);
        margin-bottom: var(--spacing-2xl);
    }
    
    /* Z-Fold 7 Optimizations */
    @media (max-width: 904px) {
        /* Cover screen */
        #storyListContainer {
            grid-template-columns: 1fr;
            gap: var(--spacing-md);
        }
        
        .container {
            padding: var(--spacing-md);
        }
        
        .search-sort-filter {
            flex-direction: column;
            align-items: stretch;
        }
        
        .search-sort-filter input[type="text"] {
            min-width: auto;
        }
    }
    
    @media (min-width: 905px) and (max-width: 1812px) {
        /* Main screen */
        #storyListContainer {
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        }
    }
    
    @media (min-width: 1813px) {
        /* Large screens */
        #storyListContainer {
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
        }
    }
    
    /* Story Cards */
    .story-card {
        background-color: var(--surface-color);
        border: 1px solid var(--outline-variant);
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-1);
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        position: relative;
    }
    
    .story-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-3);
        border-color: var(--primary-color);
    }
    
    .story-card:active {
        transform: translateY(-2px);
        box-shadow: var(--shadow-2);
    }
    
    .story-card-summary {
        display: flex;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
        align-items: flex-start;
    }
    
    .story-cover {
        flex-shrink: 0;
    }
    
    .story-cover img {
        width: 80px;
        height: 120px;
        object-fit: cover;
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-2);
        transition: transform 0.2s ease;
    }
    
    .story-card:hover .story-cover img {
        transform: scale(1.05);
    }
    
    .story-summary-info {
        flex: 1;
        min-width: 0;
    }
    
    .story-summary-info h2 {
        margin: 0 0 var(--spacing-sm) 0;
        font-size: var(--font-size-xl);
        font-weight: 600;
        color: var(--primary-color);
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .story-summary-info h2 a {
        text-decoration: none;
        color: inherit;
        transition: color 0.2s ease;
    }
    
    .story-summary-info h2 a:hover {
        color: var(--primary-hover-color);
    }
    
    .story-summary-info p {
        margin: var(--spacing-xs) 0;
        font-size: var(--font-size-sm);
        color: var(--on-surface-variant);
        line-height: 1.4;
    }
    
    .story-summary-info .story-meta {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        margin-top: var(--spacing-md);
    }
    
    .story-meta-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
        font-size: var(--font-size-xs);
        color: var(--on-surface-variant);
    }
    
    .view-details-btn {
        background-color: var(--primary-color);
        color: var(--on-primary);
        border: none;
        border-radius: var(--radius-md);
        padding: var(--spacing-sm) var(--spacing-lg);
        font-size: var(--font-size-sm);
        font-weight: 500;
        cursor: pointer;
        margin-top: var(--spacing-md);
        transition: all 0.2s ease;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        min-height: 40px;
    }
    
    .view-details-btn:hover {
        background-color: var(--primary-hover-color);
        transform: translateY(-1px);
        box-shadow: var(--shadow-2);
    }
    
    .view-details-btn:active {
        transform: translateY(0);
    }
    
    /* Modal */
    .modal {
        display: none;
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(4px);
        animation: fadeIn 0.3s ease;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    .modal-content {
        background-color: var(--surface-color);
        margin: 5% auto;
        padding: var(--spacing-xl);
        border-radius: var(--radius-xl);
        width: 90%;
        max-width: 800px;
        max-height: 90vh;
        position: relative;
        box-shadow: var(--shadow-4);
        animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    @keyframes slideIn {
        from { 
            transform: translateY(-50px) scale(0.95);
            opacity: 0;
        }
        to { 
            transform: translateY(0) scale(1);
            opacity: 1;
        }
    }
    
    .modal-close-btn {
        position: absolute;
        top: var(--spacing-lg);
        right: var(--spacing-lg);
        background: none;
        border: none;
        font-size: var(--font-size-2xl);
        color: var(--on-surface-variant);
        cursor: pointer;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        z-index: 10;
    }
    
    .modal-close-btn:hover {
        background-color: var(--surface-variant);
        color: var(--on-surface);
    }
    
    #modalBodyContent {
        max-height: calc(90vh - 120px);
        overflow-y: auto;
        padding-right: var(--spacing-sm);
    }
    
    #modalBodyContent::-webkit-scrollbar {
        width: 6px;
    }
    
    #modalBodyContent::-webkit-scrollbar-track {
        background: var(--surface-variant);
        border-radius: 3px;
    }
    
    #modalBodyContent::-webkit-scrollbar-thumb {
        background: var(--outline);
        border-radius: 3px;
    }
    
    /* Modal Content Styles */
    .modal-header {
        text-align: center;
        margin-bottom: var(--spacing-xl);
        padding-bottom: var(--spacing-lg);
        border-bottom: 1px solid var(--outline-variant);
    }
    
    .modal-header h1 {
        font-size: var(--font-size-2xl);
        font-weight: 700;
        color: var(--on-surface);
        margin: 0 0 var(--spacing-sm) 0;
        line-height: 1.2;
    }
    
    .modal-subtitle {
        font-size: var(--font-size-lg);
        color: var(--on-surface-variant);
        margin: 0;
        font-weight: 400;
    }
    
    .section-title {
        font-weight: 600;
        margin: var(--spacing-xl) 0 var(--spacing-md) 0;
        font-size: var(--font-size-lg);
        color: var(--on-surface);
        border-bottom: 2px solid var(--primary-color);
        padding-bottom: var(--spacing-sm);
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
    }
    
    .section-title:first-child {
        margin-top: 0;
    }
    
    .synopsis {
        background-color: var(--surface-variant);
        padding: var(--spacing-lg);
        border-radius: var(--radius-md);
        margin-bottom: var(--spacing-sm);
        line-height: 1.6;
        position: relative;
        overflow: hidden;
        max-height: 120px;
        transition: max-height 0.3s ease;
    }
    
    .synopsis.expanded {
        max-height: none;
    }
    
    .synopsis-toggle {
        color: var(--primary-color);
        cursor: pointer;
        font-size: var(--font-size-sm);
        font-weight: 500;
        user-select: none;
    }
    
    .synopsis-toggle:hover {
        text-decoration: underline;
    }
    
    /* File Lists */
    .file-list {
        list-style: none;
        padding: 0;
        margin: 0;
    }
    
    .file-list li {
        background-color: var(--surface-variant);
        margin-bottom: var(--spacing-sm);
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        border-left: 4px solid var(--primary-color);
        transition: all 0.2s ease;
    }
    
    .file-list li:hover {
        background-color: var(--primary-container);
        transform: translateX(4px);
    }
    
    .file-list li a {
        text-decoration: none;
        color: var(--primary-color);
        font-weight: 500;
        word-break: break-word;
    }
    
    .file-list li a:hover {
        text-decoration: underline;
    }
    
    .chapter-list li {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        transition: background-color 0.2s ease;
    }
    
    .chapter-list li:hover {
        background-color: var(--surface-variant);
    }
    
    .chapter-title {
        flex: 1;
        min-width: 0;
        word-break: break-word;
    }
    
    .chapter-title a {
        color: var(--primary-color);
        text-decoration: none;
        font-weight: 500;
    }
    
    .chapter-title a:hover {
        text-decoration: underline;
    }
    
    .chapter-status {
        font-size: var(--font-size-xs);
        padding: var(--spacing-xs) var(--spacing-sm);
        border-radius: var(--radius-sm);
        font-weight: 500;
        white-space: nowrap;
        flex-shrink: 0;
    }
    
    .chapter-status.archived {
        background-color: var(--secondary-container);
        color: var(--on-secondary-container);
    }
    
    .chapter-status.downloaded {
        background-color: var(--success-container);
        color: var(--success-color);
    }
    
    .chapter-status.not-downloaded {
        background-color: var(--error-container);
        color: var(--error-color);
    }
    
    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: var(--spacing-xs) var(--spacing-sm);
        font-size: var(--font-size-xs);
        font-weight: 600;
        border-radius: var(--radius-sm);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-complete { 
        background-color: var(--success-container); 
        color: var(--success-color); 
    }
    
    .status-ongoing { 
        background-color: var(--warning-container); 
        color: var(--warning-color); 
    }
    
    .status-possibly-complete-total-unknown { 
        background-color: var(--info-container); 
        color: var(--info-color); 
    }
    
    .status-unknown-no-chapters-downloaded-total-unknown { 
        background-color: var(--secondary-container); 
        color: var(--secondary-color); 
    }
    
    .backup-ok { 
        background-color: var(--success-container); 
        color: var(--success-color); 
    }
    
    .backup-failed { 
        background-color: var(--error-container); 
        color: var(--error-color); 
    }
    
    .backup-never-backed-up { 
        background-color: var(--secondary-container); 
        color: var(--secondary-color); 
    }
    
    .backup-partial-unknown { 
        background-color: var(--warning-container); 
        color: var(--warning-color); 
    }
    
    .backup-ok-timestamp-missing { 
        background-color: var(--info-container); 
        color: var(--info-color); 
    }
    
    /* Progress Bar */
    .progress-container {
        margin: var(--spacing-md) 0;
    }
    
    .progress-bar {
        width: 100%;
        height: 8px;
        background-color: var(--surface-variant);
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: var(--spacing-xs);
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--primary-color), var(--primary-hover-color));
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    
    .progress-text {
        font-size: var(--font-size-sm);
        color: var(--on-surface-variant);
        text-align: center;
    }
    
    /* Empty State */
    .no-items {
        text-align: center;
        color: var(--on-surface-variant);
        font-style: italic;
        padding: var(--spacing-xl);
    }
    
    /* Loading State */
    .loading {
        display: flex;
        justify-content: center;
        align-items: center;
        padding: var(--spacing-2xl);
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 4px solid var(--surface-variant);
        border-top: 4px solid var(--primary-color);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* Touch Optimizations */
    @media (hover: none) and (pointer: coarse) {
        .story-card:hover {
            transform: none;
            box-shadow: var(--shadow-1);
        }
        
        .view-details-btn {
            min-height: 48px;
            padding: var(--spacing-md) var(--spacing-lg);
        }
        
        .modal-close-btn {
            width: 48px;
            height: 48px;
        }
    }
    
    /* Print Styles */
    @media print {
        .search-sort-filter,
        .view-details-btn,
        .modal-close-btn {
            display: none;
        }
        
        .story-card {
            break-inside: avoid;
            box-shadow: none;
            border: 1px solid #ccc;
        }
        
        .modal {
            position: static;
            background: none;
        }
        
        .modal-content {
            box-shadow: none;
            border: 1px solid #ccc;
        }
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#6750a4">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Webnovel Archive">
    <meta name="description" content="Webnovel Archive Report - View your archived webnovels">
    <meta name="format-detection" content="telephone=no">
    <title>{html.escape(title_text)}</title>
    
    <!-- Preload critical resources -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    
    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📚</text></svg>">
    
    <!-- Web App Manifest -->
    <link rel="manifest" href="manifest.json">
    
    <style>
        {css_styles}
    </style>
</head>
<body>
    {body_content}

    <div id="storyDetailModal" class="modal">
        <div class="modal-content">
            <button class="modal-close-btn" aria-label="Close modal">&times;</button>
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
    data_last_updated = html.escape(
        story_data.get('last_download_timestamp') or
        story_data.get('last_updated_timestamp') or
        story_data.get('last_archived_timestamp') or
        story_data.get('epub_generation_timestamp_raw') or
        ''
    )
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

            # Determine status class and icon
            status_class = "archived" if status == 'archived' else ("downloaded" if downloaded else "not-downloaded")
            status_icon = "📚" if status == 'archived' else ("✅" if downloaded else "⏳")
            status_text = "Archived" if status == 'archived' else ("Downloaded" if downloaded else "Not Downloaded")

            chapter_content = f'<span class="chapter-title">{title}</span>'
            if url and url != '#':
                chapter_content = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'

            chapter_items.append(f'''
                <li>
                    {chapter_content}
                    <span class="chapter-status {status_class}">
                        {status_icon} {status_text}
                    </span>
                </li>
            ''')

        if chapter_items:
            chapters_html = f'''
            <p class="section-title">Chapters ({len(chapters_for_report)} total):</p>
            <ul class="file-list chapter-list">{' '.join(chapter_items)}</ul>
            '''
        else:
            chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'
    else:
        chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'

    # Calculate progress percentage for progress bar
    progress_percentage = story_data.get('progress_percentage', 0)
    
    card_html = f'''
    <div class="story-card" data-title="{data_title}" data-author="{data_author}" data-status="{data_status}" data-last-updated="{data_last_updated}" data-progress="{data_progress}">
        <div class="story-card-summary">
            <div class="story-cover">
                <img src="{cover_image_url}" alt="Cover for {title}" loading="lazy">
            </div>
            <div class="story-summary-info">
                <h2><a href="{story_url}" target="_blank" rel="noopener">{title}</a></h2>
                <p><strong>Author:</strong> {author}</p>
                <p><strong>Story ID:</strong> {story_id_display}</p>
                
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {progress_percentage}%"></div>
                    </div>
                    <div class="progress-text">{progress_text}</div>
                </div>
                
                <div class="story-meta">
                    <div class="story-meta-item">
                        <span class="badge status-{status_class}">{status_display_text}</span>
                    </div>
                    <div class="story-meta-item">
                        <span>📅 {last_updated}</span>
                    </div>
                </div>
                
                <button class="view-details-btn" data-story-id="{story_id_for_modal}">
                    <span>📖</span>
                    View Details
                </button>
            </div>
        </div>
        <div class="story-card-modal-content" style="display: none;">
            <div class="modal-header">
                <h1>{title}</h1>
                <p class="modal-subtitle">by {author}</p>
            </div>
            
            <p class="section-title">📝 Synopsis</p>
            <div class="synopsis" onclick="toggleSynopsis(this)">{synopsis}</div>
            <span class="synopsis-toggle" onclick="toggleSynopsis(this.previousElementSibling)">(Read more)</span>

            <p class="section-title">📊 Download Progress</p>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress_percentage}%"></div>
                </div>
                <div class="progress-text">{progress_text}</div>
            </div>
            <p><strong>Story Status:</strong> <span class="badge status-{status_class}">{status_display_text}</span></p>

            {chapters_html}

            <p class="section-title">📚 Local EPUBs</p>
            <p><em>Generated: {epub_gen_ts}</em></p>
            {epub_list_html}

            <p class="section-title">☁️ Cloud Backup</p>
            <p><strong>Status:</strong> <span class="badge backup-{backup_summary_class}">{backup_summary_display_text}</span>
               <br><em>Service: {backup_service}</em>
            </p>
            <p><strong>Last Successful Backup:</strong> {backup_last_success_ts}</p>
            {generate_backup_files_html(backup_files_detail_list, format_timestamp)}

            <p class="section-title">🕒 Last Local Update</p>
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
