

# **Refined V2: Webnovel Archiver Architecture**


## **Introduction**

This architecture proposal aims to detail the structure and design for Version 2 (V2) of the Webnovel Archiver. The main focus of V2 is to refactor the system into a highly modular architecture, consolidate essential functionalities into a robust workflow, and introduce a dedicated command for cloud backup. This architecture is designed to facilitate maintenance, testability, and future expansion to new content sources.


## **I. Core Architecture and Design**

The cornerstone of V2 is a modular architecture with low coupling and high cohesion components. This will allow for independent development and testing of each part of the system, as well as simplify the addition of new features, such as support for different webnovel sources.


### **1. Extreme Modularization**

The system will be divided into the following main modules, each with clearly defined responsibilities:



* **core/**: Contains the central business logic of the application.
    * **core/fetchers/**: Responsible for fetching content from webnovel sources.
        * base_fetcher.py: An abstract base class or interface defining the contract that all specific fetchers must follow (e.g., get_story_metadata(), get_chapter_list(), download_chapter_content()).
        * royalroad_fetcher.py: Concrete implementation for fetching content from RoyalRoad. Inherits from BaseFetcher.
        * *(Future) another_source_fetcher.py: Implementation for a new source, also inheriting from BaseFetcher.*
    * **core/parsers/**: Responsible for parsing and cleaning raw HTML content.
        * html_cleaner.py: Contains logic to remove unnecessary HTML tags, scripts, styles, and other unwanted elements, leaving only the main story content. It can be configurable for different cleaning levels.
    * **core/modifiers/**: Responsible for applying modifications to the processed content.
        * sentence_remover.py: Implements the logic to remove specific sentences from HTML content, based on a JSON configuration file. It will operate on intermediate HTML files before EPUB generation.
    * **core/builders/**: Responsible for building output formats (e.g., EPUB).
        * epub_generator.py: Generates EPUB files from processed HTML content and story metadata. It will manage division into volumes based on user configuration.
    * **core/storage/**: Manages application state, download progress, and metadata.
        * progress_manager.py: Abstracts the reading and writing of the progress_status.json file for each story. It will control downloaded chapters, the next chapter to download, and essential metadata.
    * **core/cloud_sync/**: Module for synchronization with cloud storage services.
        * base_sync_service.py: Interface or base class for synchronization services.
        * gdrive_sync.py: Specific implementation for synchronization with Google Drive. It will manage authentication, file uploads (EPUBs, progress_status.json), and folder structure on Drive.
    * **core/orchestrator.py**: Module responsible for coordinating the actions of other modules in the archive-story command. It will invoke the fetcher, parser, modifier (if applicable), and builder in the correct sequence.
    * **core/config_manager.py**: Manages global application settings and story-specific configurations if necessary (e.g., workspace path).
* **cli/**: Contains the command-line interface logic.
    * main.py: Entry point for the CLI, using a library like argparse or click to define commands, subcommands, and arguments.
    * handlers.py: Contains the functions that are executed when a CLI command is invoked. These functions will use the Orchestrator and other core modules.
* **utils/**: Generic utility modules (e.g., logging, file manipulation, validations).


### **2. Content Source Abstraction**

The key to extensibility is abstraction in the core/fetchers module.



* A BaseFetcher class will be defined with abstract methods such as:
    * get_story_metadata(url: str) -> StoryMetadata: Returns metadata like title, author, slug, cover URL, synopsis.
    * get_chapter_urls(story_url: str) -> list[ChapterInfo]: Returns a list of chapter URLs and titles. ChapterInfo could be a dataclass with url, title, source_chapter_id, order.
    * download_chapter_content(chapter_url: str) -> str: Downloads the raw HTML content of a chapter.
* Each specific fetcher (e.g., RoyalRoadFetcher) will implement these methods. The Orchestrator will select the appropriate fetcher based on the provided URL or a configuration.


### **3. State and Progress Management**

The ProgressManager will be central to tracking. The progress_status.json file for each story will contain:

{ \
  "story_id": "unique-story-identifier", \
  "story_url": "URL of the main story page (e.g., overview_url)", \
  "original_title": "Original Story Title from Source (e.g., story_title)", \
  "original_author": "Original Author from Source (e.g., author_name)", \
  "cover_image_url": "URL of the cover image (if available)", \
  "synopsis": "Story synopsis (if available)", \
  "estimated_total_chapters_source": 150, \
  "last_downloaded_chapter_url": "URL of the last successfully downloaded chapter", \
  "next_chapter_to_download_url": "URL of the next chapter to download (can be null if it's the last or unknown)", \
  "downloaded_chapters": [ \
    { \
      "source_chapter_id": "Original_chapter_ID_from_source_or_download_order", \
      "download_order": 1, \
      "chapter_url": "Original chapter URL", \
      "chapter_title": "Chapter Title", \
      "local_raw_filename": "chapter_001.html", \
      "local_processed_filename": "chapter_001_clean.html", \
      "download_timestamp": "YYYY-MM-DDTHH:MM:SSZ", \
      "next_chapter_url_from_page": "URL of the next chapter found on this chapter's page (if any)" \
    } \
  ], \
  "last_epub_processing": { \
    "timestamp": "YYYY-MM-DDTHH:MM:SSZ", \
    "chapters_included_in_last_volume": 50, \
    "generated_epub_files": [ \
        "StoryName_Vol_01.epub" \
    ] \
  }, \
  "sentence_removal_config_used": "path/to/removal_file.json", \
  "cloud_backup_status": { \
    "last_successful_sync_timestamp": "YYYY-MM-DDTHH:MM:SSZ", \
    "service_name": "gdrive", \
    "uploaded_epubs": [ \
        {"filename": "StoryName_Vol_01.epub", "upload_timestamp": "YYYY-MM-DDTHH:MM:SSZ", "cloud_file_id": "gdrive_file_id_1"}, \
        {"filename": "StoryName_Vol_02.epub", "upload_timestamp": "YYYY-MM-DDTHH:MM:SSZ", "cloud_file_id": "gdrive_file_id_2"} \
    ], \
    "progress_file_uploaded_timestamp": "YYYY-MM-DDTHH:MM:SSZ", \
    "cloud_progress_file_id": "gdrive_progress_file_id" \
  } \
} \
 \


This file will be stored at workspace/archival_status/&lt;story_id>/progress_status.json.

The story_id should be a filename/folder-safe slug derived from story_url or original_title.


## **II. CLI Functionalities and Commands**

The command-line interface will be the primary means of interaction with V2. Command names and options will also follow the English naming pattern.


### **1. Main Command: archive-story**

This command orchestrates the complete archiving process for a story.



* **Usage:** archiver archive-story &lt;story_url> [OPTIONS]
* **Required Argument:**
    * story_url: URL of the story's overview page (initially, RoyalRoad only).
* **Internal Workflow (orchestrated by core.Orchestrator):**
    1. **Fetcher Selection:** Determines the appropriate fetcher based on the URL.
    2. **Metadata and Content Fetching:**
        * Uses the fetcher to get story metadata (title, author, etc.) and the list of chapter URLs/info.
        * The ProgressManager is consulted to load the existing progress_status.json if any.
        * Compares the chapter list from the source with downloaded_chapters in progress_status.json.
        * New chapters are downloaded. Raw content is saved to workspace/raw_content/&lt;story_id>/&lt;local_raw_filename> (the local_raw_filename is defined in progress_status.json for the chapter).
        * The progress_status.json is incrementally updated with information for each newly downloaded chapter, including last_downloaded_chapter_url, next_chapter_to_download_url, and chapter details in the downloaded_chapters list.
    3. **HTML Cleaning:**
        * For each chapter (new or existing, if --force-reprocessing):
            * The HTMLCleaner processes the file from raw_content (whose name is in local_raw_filename for the chapter).
            * Cleaned content is saved to workspace/processed_content/&lt;story_id>/&lt;local_processed_filename> (the local_processed_filename is defined in progress_status.json for the chapter).
    4. **Sentence Removal (Optional):**
        * If the --sentence-removal-file option is provided (or a default is configured) and --no-sentence-removal is not present:
            * The SentenceRemover modifies HTML files in workspace/processed_content/.
            * The progress_status.json records which removal file was used in sentence_removal_config_used.
    5. **Ebook Generation:**
        * The EPUBGenerator uses the final HTML files from workspace/processed_content/ (referenced by local_processed_filename in downloaded_chapters) and metadata from progress_status.json to create EPUB file(s).
        * Epubs are saved to workspace/ebooks/&lt;story_id>/.
        * Volume division logic (--chapters-per-volume) will be applied. For growing stories, when updating:
            * If the last generated volume did not reach the chapters-per-volume limit and new chapters have been added, it can be regenerated/updated.
            * If the last volume was complete, new chapters will start a new volume.
        * The progress_status.json is updated with information about last_epub_processing, including the generated_epub_files list.
* **Configurable Options:**
    * --chapters-per-volume &lt;N> (Integer, Default: e.g., 50): Number of chapters per EPUB file.
    * --ebook-title "&lt;TITLE>" (String): Custom title for the EPUB(s). If not provided, uses original_title from progress_status.json.
    * --keep-temporary-files: (Flag) Does not delete raw_content and processed_content folders. Default is to delete after successful EPUB generation.
    * --sentence-removal-file &lt;JSON_PATH> (String): Specifies the JSON file for sentence removal.
    * --no-sentence-removal: (Flag) Disables the sentence removal step, even if a default removal file is configured.
    * --force-reprocessing: (Flag) Forces reprocessing of all chapters (cleaning, sentence removal), even if processed files already exist. Does not necessarily re-download unless combined with another option or if raw files are missing.
    * --output-dir &lt;FOLDER_PATH> (String, Default: workspace/): Allows specifying a different base working directory.


### **2. Backup Command: cloud-backup**

This command is responsible for backing up generated ebooks and status files to the cloud.



* **Usage:** archiver cloud-backup [OPTIONS] [story_id]
* **Optional Argument:**
    * story_id: The unique slug or identifier of the story to be backed up. If omitted, all managed stories (present in workspace/archival_status/) will be considered.
* **Functionality (using core.cloud_sync.GDriveSync or similar):**
    1. **Authentication:** Manages authentication with Google Drive (OAuth2). Tokens should be stored securely.
    2. **Story Selection:** Determines which stories to back up based on the provided story_id argument or by listing all directories in workspace/archival_status/.
    3. **Drive Structure:** For each story:
        * Creates/verifies the structure: "Webnovel Archiver Backups"/&lt;story_id>/
    4. **File Upload:**
        * Uploads EPUB files listed in last_epub_processing.generated_epub_files (from progress_status.json) located in workspace/ebooks/&lt;story_id>/ to the corresponding Drive folder.
        * Uploads the workspace/archival_status/&lt;story_id>/progress_status.json file.
    5. **Update:** Existing files on Drive with the same name will be updated if the local file is newer.
    6. **Status Update:** The local progress_status.json is updated with cloud_backup_status information (timestamp, service_name, the uploaded_epubs list with their names, upload timestamps, and cloud_file_id, and also progress_file_uploaded_timestamp and cloud_progress_file_id).
* **Configurable Options:**
    * --cloud-service &lt;NAME> (String, Default: gdrive): Allows specifying the cloud service (for future expansions).
    * --force-full-upload: (Flag) Uploads all files, even if they already exist and have not been modified (can be useful for restoring a backup).


## **III. Folder and File Structure (English Names)**

The folder structure will be organized to reflect modularity and facilitate data access. The root workspace/ folder (configurable) will contain:



* **workspace/**
    * **raw_content/**: Stores original downloaded HTML.
        * **&lt;story_id>/**
            * chapter_001.html (name as per local_raw_filename in progress_status.json)
            * chapter_002.html
            * ...
    * **processed_content/**: Stores HTML after cleaning and modifications.
        * **&lt;story_id>/**
            * chapter_001_clean.html (name as per local_processed_filename in progress_status.json)
            * chapter_002_clean.html
            * ...
    * **ebooks/**: Stores generated EPUB files.
        * **&lt;story_id>/**
            * StoryName_Vol_01.epub (name as per generated_epub_files in progress_status.json)
            * StoryName_Vol_02.epub
            * ...
    * **archival_status/**: Stores state and progress files.
        * **&lt;story_id>/**
            * progress_status.json
    * **logs/**: Application log files.
        * archiver.log
    * **config/**: Application configuration files (if needed, beyond CLI).
        * settings.ini (or .json, .yaml)
        * default_sentence_removal.json (default file for sentence removal if none is specified)

The &lt;story_id> will be a unique name derived from the story's URL or metadata (e.g., RoyalRoad slug, as defined in story_id in progress_status.json) to avoid conflicts and facilitate identification. The Google Drive folder name will also be changed to "Webnovel Archiver Backups".


## **IV. Additional Considerations**



* **Testing:** Modularity will facilitate writing unit tests for each component and integration tests for main workflows.
* **Logging:** Implement a robust logging system (Python's logging) to record important events, errors, and debugging information.
* **Error Handling:** Each module should handle its own errors gracefully and, when necessary, propagate them so the CLI can inform the user appropriately.
* **Dependencies:** Manage dependencies with requirements.txt or pyproject.toml (with Poetry or PDM).


## **Conclusion**

This V2 architecture proposes a solid and modular foundation for the Webnovel Archiver. By focusing on separation of responsibilities and content source abstraction, the system will be well-prepared for future evolutions, such as supporting new sources and, eventually, graphical interfaces. Clarity in CLI commands and folder structure will also contribute to a better user and developer experience.
