import os
import json
import datetime
import sys
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
