# Webnovel Archiver - Current Functionalities Documentation

This document provides a comprehensive overview of the current functionalities of the Webnovel Archiver application, intended as a foundation for developing an Android version.

## Overview

Webnovel Archiver is a command-line tool designed for archiving webnovels from various online sources. It focuses on preservation, allowing users to download, process, and store webnovel content locally in EPUB format, with features for progress tracking, cloud backup, and content management.

## Core Philosophy

The application follows a "preservation-first" approach:

-   **Once Archived, Always Kept**: Downloaded chapters are preserved locally even if removed from the source.
-   **Resilience to Source Changes**: Protects user collections from content takedowns.
-   **User Data Control**: Ensures complete ownership of archived content.

## Supported Sources

Currently supports:

-   **Royal Road** (royalroad.com)
-   Extensible architecture for adding new sources (e.g., Scribble Hub planned)

## Main Functionalities

### 1. Story Archiving

-   **URL-based Archiving**: Archive entire webnovels by providing the story URL. The application uses a `Fetcher` specific to the source website to extract a permanent story ID, which is used for the folder name (e.g., `royalroad-12345`). An `index.json` file in the workspace root maps these IDs to their corresponding folder names.
-   **Metadata Extraction**: Automatically fetches story title, author, cover image, synopsis, and the total number of chapters from the source. This data is stored in the `progress.json` file for the story.
-   **Chapter Processing**:
    -   **Incremental Updates**: On subsequent runs, the archiver fetches the latest chapter list and compares it against the `downloaded_chapters` in `progress.json`. It only downloads new chapters or re-downloads chapters if their files are missing.
    -   **Status Management**: If a chapter URL from the local `progress.json` is no longer present in the source's chapter list, its status is changed from `active` to `archived`. This preserves the content while indicating it's no longer available online.
    -   **HTML Content**: Downloads the raw HTML content for each chapter.
    -   **HTML Cleaning**: Cleans the HTML by removing ads, scripts, and other non-content elements to prepare it for EPUB generation.
    -   **Sentence Removal**: Optionally applies sentence removal based on user-defined rules in a JSON file. This is useful for removing repetitive phrases (e.g., "Edited by...", "Join my Patreon...").
    -   **File Storage**: Saves both the raw and processed HTML content to disk in separate folders (`raw_content` and `processed_content`). Chapter filenames include the download order and source chapter ID for easy identification (e.g., `chapter_00001_12345.html`).
-   **Progress Tracking**: A detailed `progress.json` file is maintained for each story, tracking:
    -   Story metadata (title, author, URL).
    -   A list of all downloaded chapters, including their URL, title, download timestamp, and status (`active` or `archived`).
    -   Timestamps for the last archival run and the last EPUB generation.
    -   Cloud backup status and history.

### 2. EPUB Generation

-   **Automatic EPUB Creation**: Generates EPUB files automatically after new content has been successfully downloaded or when reprocessing is forced.
-   **Flexible Content Inclusion**: The `--epub-contents` option allows for two modes:
    -   `all`: Includes all downloaded chapters, both `active` and `archived`. This is the default.
    -   `active-only`: Includes only chapters that are currently `active` on the source website, mirroring its current state.
-   **Volume Splitting**: The `--chapters-per-volume` option can split long stories into multiple EPUB volumes. Filenames for volumes are appended with `_vol_X` (e.g., `My_Story_vol_1.epub`).
-   **Metadata Integration**: Embeds all fetched story metadata, including the cover image, synopsis, author, and a structured Table of Contents, into the EPUB file.
-   **Cover Image Handling**: The cover image is downloaded from its URL, and its file type is detected. It is then embedded into the EPUB. Temporary image files are deleted after the EPUB is generated.
-   **File Naming**: The EPUB filename is generated from the story's title, sanitized to be filesystem-friendly (e.g., "My Awesome Story" becomes `My_Awesome_Story.epub`).

### 3. Content Management

-   **Incremental Updates**: As described above, the tool is designed to be run repeatedly on the same story to fetch new chapters without re-downloading existing content.
-   **Force Reprocessing**: The `--force-reprocessing` option allows users to override the incremental check and re-download and reprocess all chapters from the source.
-   **Status Management**: The `active`/`archived` status system ensures that the local archive is a complete representation of all content that has ever been available, while still reflecting the current state of the source.

### 4. Cloud Backup

-   **Google Drive Integration**: Provides functionality to back up archived stories to a user's Google Drive.
-   **Authentication**:
    -   Uses the OAuth 2.0 protocol to securely access the user's Google Drive.
    -   On the first run, it uses a `credentials.json` file (obtained from the Google Cloud Console) to open a browser window for user authentication.
    -   After successful authentication, it saves a `token.json` file to be used for future, non-interactive sessions.
-   **File Organization**: Creates a root folder named `Webnovel_Archiver_Backups` on Google Drive. Inside this, it creates a sub-folder for each story using its permanent ID.
-   **Selective Backup**: Users can back up a specific story by providing its ID, or back up all stories at once.
-   **Incremental Uploads**: Before uploading a file (EPUB or `progress.json`), it compares the local file's modification time with the remote file's modification time. It only uploads the file if the local version is newer, unless a full upload is forced with `--force-full-upload`.
-   **Progress Tracking**: After a successful backup, the `progress.json` file is updated with information about the cloud backup, including timestamps and file details.

### 5. Reporting and Visualization

-   **HTML Report Generation**: Creates a single, self-contained HTML file that serves as a dashboard for the entire archive.
-   **Dashboard Features**:
    -   **Story Cards**: Each archived story is displayed as a card with its cover image, title, author, and key information.
    -   **Search and Filter**: Allows users to search by title or author and filter by various criteria.
    -   **Progress Visualization**: A progress bar shows the completion status (e.g., 50/100 chapters downloaded).
    -   **Status Badges**: Visual badges indicate the story's status (e.g., "Ongoing", "Completed") and cloud backup status ("Backed Up", "Out of Sync").
    -   **Modal Detail View**: Clicking a "View Details" button opens a modal window with comprehensive information about the story, including the full synopsis, a list of all chapters with their status, links to the generated EPUB files, and detailed cloud backup information.
    -   **Direct File Links**: EPUB file links use the `file:///` protocol for direct local access.

### 6. Migration and Restoration

-   **Data Migration**: Includes tools to migrate existing archives to new formats or directory structures as the application evolves.
-   **EPUB Restoration**: Provides a mechanism to restore processed chapter content from existing EPUB files, which can be useful for recovering data.
-   **Legacy Support**: Designed to handle changes in source website structures over time, although this may sometimes require updates to the fetchers.

## CLI Commands

### archive-story

Archives a webnovel from a given URL.

```
webnovel-archiver archive-story <STORY_URL> [OPTIONS]
```

Options:

-   `--output-dir`: Custom output directory for the workspace.
-   `--ebook-title-override`: Override the EPUB title, otherwise inferred from the source.
-   `--keep-temp-files`: Prevents the deletion of temporary files, such as the downloaded cover image.
-   `--force-reprocessing`: Forces the archiver to re-download and re-process all chapters, even if they already exist locally.
-   `--sentence-removal-file`: Path to a JSON file containing rules for sentence removal.
-   `--no-sentence-removal`: Disables the sentence removal feature, even if a default file is specified in `settings.ini`.
-   `--chapters-per-volume`: Splits the EPUB into multiple volumes, each containing the specified number of chapters.
-   `--epub-contents`: Determines which chapters to include in the EPUB (`all` or `active-only`).

### cloud-backup

Backs up archived stories to Google Drive.

```
webnovel-archiver cloud-backup [STORY_ID] [OPTIONS]
```

Options:

-   `--cloud-service`: The cloud service to use (currently only `gdrive` is supported).
-   `--force-full-upload`: Uploads all files regardless of whether they have changed since the last backup.
-   `--credentials-file`: Path to the Google Drive `credentials.json` file.
-   `--token-file`: Path to the Google Drive `token.json` file.

### generate-report

Generates an HTML report of all archived webnovels in the workspace.

```
webnovel-archiver generate-report
```

### migrate

Migrates existing archives to new formats.

```
webnovel-archiver migrate [STORY_ID] --type <MIGRATION_TYPE>
```

### restore-from-epubs

Restores chapter content from existing EPUB files.

```
webnovel-archiver restore-from-epubs
```

## Configuration

Uses a `settings.ini` file for global configuration:

-   **workspace_path**: The default directory where all archived stories are stored.
-   **default_sentence_removal_file**: A default path to a sentence removal rules JSON file to be used for all stories unless overridden.

## Technical Architecture

### Core Components

-   **`FetcherFactory`**: A factory class that takes a story URL and returns the appropriate `Fetcher` instance (e.g., `RoyalRoadFetcher`).
-   **`BaseFetcher`**: An abstract base class that defines the interface for all fetchers, including methods like `get_story_metadata()` and `get_chapter_urls()`.
-   **`Orchestrator`**: The central component that coordinates the entire archiving process, from fetching metadata to generating EPUBs.
-   **`HTMLCleaner`**: A utility class responsible for cleaning the raw HTML of chapters.
-   **`SentenceRemover`**: A modifier that removes specific sentences from the cleaned HTML based on a set of rules.
-   **`EPUBGenerator`**: The builder component responsible for creating the EPUB files, including handling volumes and embedding metadata.
-   **`ProgressManager`**: A storage component that manages the reading and writing of the `progress.json` files.
-   **`GDriveSync`**: The cloud sync service for handling all interactions with the Google Drive API.

### Data Flow

1.  **Initialization**: The user provides a story URL to the `archive-story` command.
2.  **Fetching**: The `FetcherFactory` selects the correct `Fetcher`. The `Fetcher` scrapes the story's main page for metadata and a list of all chapter URLs.
3.  **Processing**: The `Orchestrator` compares the fetched chapter list with the existing `progress.json` (if any). It then iterates through new or missing chapters, downloads the raw HTML, cleans it with `HTMLCleaner`, and applies `SentenceRemover` if configured.
4.  **Storage**: The raw and processed HTML for each chapter are saved to the appropriate directories. The `progress.json` file is updated with the new chapter information and timestamps.
5.  **EPUB Generation**: If new content was added or reprocessing was forced, the `EPUBGenerator` is called. It reads the processed HTML files, downloads the cover image, and generates one or more `.epub` files.
6.  **Cloud Backup (Optional)**: If the `cloud-backup` command is run, the `GDriveSync` service authenticates with Google Drive, checks for a story folder, and uploads the EPUB files and `progress.json` if they are newer than the remote versions.

### File Structure (for a single story)

```
workspace/
├── royalroad-12345/
│   ├── ebooks/
│   │   └── The_Perfect_Run.epub
│   ├── processed_content/
│   │   ├── chapter_00001_12345_clean.html
│   │   └── chapter_00002_67890_clean.html
│   ├── raw_content/
│   │   ├── chapter_00001_12345.html
│   │   └── chapter_00002_67890.html
│   └── progress.json
├── index.json
└── report.html
```

## Dependencies and Requirements

-   Python 3.x
-   Key libraries: `requests`, `beautifulsoup4`, `ebooklib`, `google-api-python-client`, `google-auth-oauthlib`.
-   A `virtualenv` is highly recommended to manage dependencies.

## Error Handling and Resilience

The application is designed to be resilient to common issues:

-   **Network Errors**: Uses standard `requests` library error handling. If a chapter download fails, it is logged, and the process continues with the next chapter.
-   **Source HTML Changes**: Since it relies on web scraping, changes to the source website's HTML structure can break a `Fetcher`. The architecture allows for updating a single fetcher to fix compatibility without affecting the rest of the application.
-   **Missing Files**: If a processed chapter file is found to be missing during a check, the application will re-download and re-process it.

## Future Extensibility

The architecture is designed to be modular and extensible:

-   **Adding a New Source**: To add a new source (e.g., Scribble Hub), a developer would need to:
    1.  Create a new class that inherits from `BaseFetcher` (e.g., `ScribbleHubFetcher`).
    2.  Implement the required methods for fetching metadata, chapter URLs, and chapter content.
    3.  Register the new fetcher in the `FetcherFactory` with its corresponding URL pattern.
-   **Adding a New Cloud Service**: To add a new cloud provider:
    1.  Create a new class that inherits from `BaseSyncService`.
    2.  Implement the required methods for authentication, file upload, and metadata retrieval.
    3.  Update the `cloud-backup` command to allow selection of the new service.

This documentation serves as a complete reference for understanding the current capabilities of Webnovel Archiver, providing a solid foundation for Android app development.
