import json
import os
import re
import datetime
from typing import Dict, Optional, List, Any
from urllib.parse import urlparse

# Define the root for workspace storage. This might be moved to a config manager later.
DEFAULT_WORKSPACE_ROOT = "workspace"
ARCHIVAL_STATUS_DIR = "archival_status"

def get_progress_filepath(story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> str:
    return os.path.join(workspace_root, ARCHIVAL_STATUS_DIR, story_id, "progress_status.json")

def _get_new_progress_structure(story_id: str, story_url: Optional[str] = None) -> Dict[str, Any]:
    """Returns a new, empty structure for progress_status.json."""
    return {
        "story_id": story_id,
        "story_url": story_url,
        "original_title": None,
        "original_author": None,
        "cover_image_url": None,
        "synopsis": None,
        "estimated_total_chapters_source": None,
        "last_downloaded_chapter_url": None,
        "next_chapter_to_download_url": None,
        "downloaded_chapters": [], # List of chapter detail dicts
        "last_epub_processing": { # Details about the last EPUB generation
            "timestamp": None,
            "chapters_included_in_last_volume": None, # Count
            "generated_epub_files": [] # List of filenames
        },
        "sentence_removal_config_used": None, # Path to the config file used
        "cloud_backup_status": { # Details about the last cloud backup
            "last_successful_sync_timestamp": None,
            "service_name": None, # e.g., "gdrive"
            "uploaded_epubs": [], # List of dicts: {"filename": "str", "upload_timestamp": "str", "cloud_file_id": "str"}
            "progress_file_uploaded_timestamp": None,
            "cloud_progress_file_id": None
        }
    }

def load_progress(story_id: str, workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> Dict[str, Any]:
    """
    Loads progress_status.json for a story_id.
    If it doesn't exist, returns a new structure.
    """
    filepath = get_progress_filepath(story_id, workspace_root)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Handle corrupted JSON file, perhaps by returning a new structure or raising error
            # For now, let's return a new one and overwrite later.
            print(f"Warning: Progress file for {story_id} is corrupted. Starting fresh.")
            return _get_new_progress_structure(story_id)
    else:
        return _get_new_progress_structure(story_id)

def save_progress(story_id: str, progress_data: Dict[str, Any], workspace_root: str = DEFAULT_WORKSPACE_ROOT) -> None:
    """Saves the progress_data to progress_status.json for a story_id."""
    filepath = get_progress_filepath(story_id, workspace_root)
    # Ensure the directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

def generate_story_id(url: Optional[str] = None, title: Optional[str] = None) -> str:
    """
    Generates a URL-safe/filename-safe ID from the story URL or title.
    Prefers URL for uniqueness if available.
    Example RoyalRoad URL: https://www.royalroad.com/fiction/12345/some-story-title
    We can try to extract '12345-some-story-title' or just '12345'.
    Using the fiction ID is often a good choice for sites that have it.
    """
    if url:
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]

        # RoyalRoad specific: /fiction/<id>/<slug_name>
        if "royalroad.com" in parsed_url.netloc and len(path_parts) >= 2 and path_parts[0] == "fiction":
            story_identifier = path_parts[1] # This is the fiction ID, e.g., "117255"
            if len(path_parts) > 2: # If there's a slug name
                 story_identifier += "-" + path_parts[2] # e.g., "117255-rend"
            # Sanitize it further, just in case
            story_identifier = re.sub(r'[^a-zA-Z0-9_-]+', '', story_identifier)
            if story_identifier:
                return story_identifier

        # Generic fallback for URLs: use the last significant part of the path
        if path_parts:
            base_id = path_parts[-1]
        else: # Or use the domain if path is empty
            base_id = parsed_url.netloc
            base_id = base_id.replace("www.", "") # Remove www
    elif title:
        base_id = title
    else:
        # Fallback to a timestamp-based ID if neither is provided, though this is not ideal for user-facing IDs
        return f"story_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    # Sanitize the base_id
    # Convert to lowercase
    s_id = base_id.lower()
    # Remove special characters, replace spaces with hyphens
    s_id = re.sub(r'\s+', '-', s_id)
    s_id = re.sub(r'[^a-z0-9_-]', '', s_id)
    # Truncate if too long (e.g., > 50 chars)
    s_id = s_id[:50]
    # Ensure it's not empty
    if not s_id:
        return f"story_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    return s_id.strip('-_')


# Example of how chapter details might be added (orchestrator would handle this)
# def add_downloaded_chapter_info(progress_data: Dict[str, Any],
#                                 source_chapter_id: str,
#                                 download_order: int,
#                                 chapter_url: str,
#                                 chapter_title: str,
#                                 local_raw_filename: str,
#                                 next_chapter_url_on_page: Optional[str] = None) -> None:
#     chapter_entry = {
#         "source_chapter_id": source_chapter_id,
#         "download_order": download_order,
#         "chapter_url": chapter_url,
#         "chapter_title": chapter_title,
#         "local_raw_filename": local_raw_filename,
#         "local_processed_filename": None, # To be filled later
#         "download_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
#         "next_chapter_url_from_page": next_chapter_url_on_page
#     }
#     progress_data["downloaded_chapters"].append(chapter_entry)
#     progress_data["last_downloaded_chapter_url"] = chapter_url
#     # Logic to determine next_chapter_to_download_url would be more complex,
#     # often from the chapter list or next_chapter_url_on_page

if __name__ == '__main__':
    # Test generate_story_id
    print("--- Testing generate_story_id ---")
    rr_url = "https://www.royalroad.com/fiction/117255/rend-a-tale-of-something"
    print(f"URL: {rr_url} -> ID: {generate_story_id(url=rr_url)}")

    generic_url = "https://www.somesite.com/stories/my-awesome-story-123/"
    print(f"URL: {generic_url} -> ID: {generate_story_id(url=generic_url)}")

    title_only = "My Super Awesome Story Title! With Punctuation?"
    print(f"Title: '{title_only}' -> ID: {generate_story_id(title=title_only)}")

    no_info_id = generate_story_id()
    print(f"No info -> ID: {no_info_id}")

    # Test load and save progress
    print("\n--- Testing load and save progress ---")
    test_story_id = generate_story_id(url=rr_url) # Use a generated ID for testing

    # Clean up any previous test file for this ID
    test_filepath = get_progress_filepath(test_story_id)
    if os.path.exists(test_filepath):
        os.remove(test_filepath)
    if os.path.exists(os.path.dirname(test_filepath)): # remove directory if empty
        if not os.listdir(os.path.dirname(test_filepath)):
            os.rmdir(os.path.dirname(test_filepath))

    # Load (should create new)
    progress = load_progress(test_story_id)
    print(f"Loaded initial progress for {test_story_id}:")
    # print(json.dumps(progress, indent=2))

    # Modify progress
    progress["original_title"] = "REND"
    progress["original_author"] = "Temple"
    progress["story_url"] = rr_url
    # Simulate adding a chapter (simplified)
    # In real use, use a helper or Orchestrator would populate this more carefully
    if not progress["downloaded_chapters"]: # Add a chapter only if none exists
        progress["downloaded_chapters"].append({
            "source_chapter_id": "2291798",
            "download_order": 1,
            "chapter_url": "https://www.royalroad.com/fiction/117255/rend/chapter/2291798/11-crappy-monday",
            "chapter_title": "1.1 Crappy Monday",
            "local_raw_filename": "chapter_001.html",
            "local_processed_filename": None,
            "download_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "next_chapter_url_from_page": "https://www.royalroad.com/fiction/117255/rend/chapter/2292710/12-crappy-monday"
        })
        progress["last_downloaded_chapter_url"] = "https://www.royalroad.com/fiction/117255/rend/chapter/2291798/11-crappy-monday"
        progress["next_chapter_to_download_url"] = "https://www.royalroad.com/fiction/117255/rend/chapter/2292710/12-crappy-monday"


    # Save
    save_progress(test_story_id, progress)
    print(f"Saved progress for {test_story_id} to {test_filepath}")

    # Load again (should reflect changes)
    loaded_again = load_progress(test_story_id)
    print(f"Loaded progress again for {test_story_id}:")
    # print(json.dumps(loaded_again, indent=2))

    assert loaded_again["original_title"] == "REND"
    if loaded_again["downloaded_chapters"]:
        assert loaded_again["downloaded_chapters"][0]["chapter_title"] == "1.1 Crappy Monday"
    print("Load/Save tests passed (basic assertions).")

    # Clean up the created test file and directory
    if os.path.exists(test_filepath):
        os.remove(test_filepath)
    if os.path.exists(os.path.dirname(test_filepath)):
         if not os.listdir(os.path.dirname(test_filepath)):
            os.rmdir(os.path.dirname(test_filepath))
    # Also remove parent 'archival_status' and 'workspace' if they became empty and were created by this test
    # This cleanup is basic, for more robust testing, a test framework would handle setup/teardown
    try:
        if os.path.exists(os.path.join(DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR)) and \
           not os.listdir(os.path.join(DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR)):
            os.rmdir(os.path.join(DEFAULT_WORKSPACE_ROOT, ARCHIVAL_STATUS_DIR))
        if os.path.exists(DEFAULT_WORKSPACE_ROOT) and not os.listdir(DEFAULT_WORKSPACE_ROOT):
            os.rmdir(DEFAULT_WORKSPACE_ROOT)
    except OSError as e:
        print(f"Note: Could not clean up all test directories (this is okay for simple test): {e}")
