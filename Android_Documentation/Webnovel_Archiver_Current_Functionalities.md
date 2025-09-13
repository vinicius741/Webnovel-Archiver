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

-   **URL-based Archiving**: Archive entire webnovels by providing the story URL.
-   **Metadata Extraction**: Automatically fetches story title, author, cover image, synopsis, and chapter count.
-   **Chapter Processing**:
    -   Downloads raw HTML content
    -   Cleans HTML (removes ads, scripts, etc.)
    -   Applies optional sentence removal based on user-defined rules
    -   Saves both raw and processed versions
-   **Progress Tracking**: Maintains detailed progress status for each story, including:
    -   Downloaded chapters list
    -   Chapter status (active/archived)
    -   Timestamps for downloads and checks
    -   EPUB generation history

### 2. EPUB Generation

-   **Automatic EPUB Creation**: Generates EPUB files after archiving new content.
-   **Flexible Content Inclusion**:
    -   `all`: Includes all downloaded chapters (active and archived)
    -   `active-only`: Includes only currently active chapters (mirrors source state)
-   **Volume Splitting**: Option to split long stories into multiple EPUB volumes.
-   **Metadata Integration**: Embeds story metadata, cover images, and chapter structure.

### 3. Content Management

-   **Incremental Updates**: Only processes new or changed chapters on subsequent runs.
-   **Force Reprocessing**: Option to re-download and reprocess all chapters.
-   **Status Management**: Automatically marks chapters as "archived" if removed from source.
-   **File Organization**: Structured directory layout for raw content, processed content, and EPUBs.

### 4. Cloud Backup

-   **Google Drive Integration**: Backup archived stories to Google Drive.
-   **Selective Backup**: Backup specific stories or all stories at once.
-   **Incremental Uploads**: Only uploads new or changed files (unless forced).
-   **Progress Tracking**: Updates local progress files with cloud backup information.

### 5. Reporting and Visualization

-   **HTML Report Generation**: Creates comprehensive HTML reports of the entire archive.
-   **Dashboard Features**:
    -   Search and filter by title/author
    -   Sort by various criteria
    -   Display completion status and EPUB links
    -   Cloud backup status indicators

### 6. Migration and Restoration

-   **Data Migration**: Migrate existing archives to new formats or structures.
-   **EPUB Restoration**: Restore processed chapter content from existing EPUB files.
-   **Legacy Support**: Handle changes in source website structures.

## CLI Commands

### archive-story

Archives a webnovel from a given URL.

```
webnovel-archiver archive-story <STORY_URL> [OPTIONS]
```

Options:

-   `--output-dir`: Custom output directory
-   `--ebook-title-override`: Override the EPUB title
-   `--keep-temp-files`: Preserve temporary files
-   `--force-reprocessing`: Reprocess all chapters
-   `--sentence-removal-file`: Path to sentence removal rules JSON
-   `--no-sentence-removal`: Disable sentence removal
-   `--chapters-per-volume`: Split EPUB into volumes
-   `--epub-contents`: Choose content inclusion (all/active-only)

### cloud-backup

Backs up archived stories to Google Drive.

```
webnovel-archiver cloud-backup [STORY_ID] [OPTIONS]
```

Options:

-   `--cloud-service`: Cloud service (currently only gdrive)
-   `--force-full-upload`: Upload all files regardless of changes
-   `--credentials-file`: Path to Google Drive credentials
-   `--token-file`: Path to Google Drive token

### generate-report

Generates an HTML report of archived webnovels.

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

Uses `settings.ini` file for configuration:

-   **workspace_path**: Directory for storing archives
-   **default_sentence_removal_file**: Path to sentence removal rules

## Technical Architecture

### Core Components

-   **Fetchers**: Handle source-specific data extraction (Royal Road, extensible)
-   **Parsers**: HTML cleaning and content processing
-   **Modifiers**: Sentence removal and content modification
-   **Builders**: EPUB generation
-   **Storage**: Progress tracking and file management
-   **Cloud Sync**: Google Drive integration

### Data Flow

1. URL → Fetcher → Metadata + Chapter URLs
2. Chapter URLs → Download → HTML Cleaning → Sentence Removal → Processed Content
3. Processed Content → EPUB Generation → Local Storage
4. Optional: Cloud Backup

### File Structure

-   `webnovel_archiver/`: Main package
    -   `cli/`: Command-line interface
    -   `core/`: Core functionality
        -   `fetchers/`: Source-specific fetchers
        -   `builders/`: EPUB generation
        -   `storage/`: Progress and file management
        -   `cloud_sync/`: Cloud backup services
    -   `report/`: HTML report generation
    -   `utils/`: Utilities (logging, slug generation)

## Dependencies and Requirements

-   Python 3.x
-   Key libraries: requests, beautifulsoup4, ebooklib, google-api-python-client
-   Virtual environment recommended

## Future Extensibility

The architecture supports:

-   Additional webnovel sources
-   New cloud storage providers
-   Enhanced content processing features
-   Mobile app versions (including Android)

This documentation serves as a complete reference for understanding the current capabilities of Webnovel Archiver, providing a solid foundation for Android app development.
