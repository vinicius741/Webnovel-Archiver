# Webnovel Archiver CLI

A command-line tool for archiving webnovels from various sources and managing your local archive.

## Features

*   Archive webnovels from supported sources.
*   Generate EPUB files for offline reading.
*   Manage archival progress.
*   Backup your archived stories to Google Drive.

## Installation

(TODO: Add installation instructions - e.g., pip install ...)

## Basic Usage

### Archiving a new story

```bash
webnovel-archiver archive-story <STORY_URL> [OPTIONS]
```

**Example:**

```bash
webnovel-archiver archive-story "https://www.royalroad.com/fiction/xxxxx/some-story-title"
```

See `webnovel-archiver archive-story --help` for all available options.

### Backing up to Cloud (Google Drive)

The `cloud-backup` command allows you to back up your archived stories (EPUB files and progress status) to Google Drive.

```bash
webnovel-archiver cloud-backup [STORY_ID] [OPTIONS]
```

**Arguments:**

*   `[STORY_ID]` (Optional): The specific ID of the story to back up. If omitted, all stories found in your workspace will be processed. The `STORY_ID` is typically generated from the story URL or title during the initial archiving process and is used as the folder name within your workspace's `archival_status` and `ebooks` directories.

**Options:**

*   `--cloud-service [gdrive]` (Default: `gdrive`): The cloud service to use. Currently, only Google Drive (`gdrive`) is supported.
*   `--force-full-upload`: If set, all local files will be uploaded to the cloud, even if a version already exists on the cloud and appears to be up-to-date. Without this flag, the tool will attempt to upload only files that are new or newer than their cloud counterparts.
*   `--credentials-file PATH`: Path to your Google Drive API `credentials.json` file. Defaults to `credentials.json` in the current directory. This file is obtained from your Google Cloud Console when you set up OAuth 2.0 credentials.
*   `--token-file PATH`: Path to your Google Drive API `token.json` file. Defaults to `token.json` in the current directory. This file is generated automatically after successful authentication using your `credentials.json` file.

**First-time Google Drive Setup:**

1.  **Obtain `credentials.json`:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the "Google Drive API" for your project (APIs & Services > Library).
    *   Go to APIs & Services > Credentials.
    *   Click "Create Credentials" > "OAuth client ID".
    *   Choose "Desktop app" as the application type.
    *   Give it a name (e.g., "Webnovel Archiver CLI").
    *   Click "Create".
    *   Download the JSON file. Rename it to `credentials.json` and place it in your working directory or provide its path using the `--credentials-file` option.
2.  **Initial Authentication:**
    *   The first time you run the `cloud-backup` command, if a valid `token.json` is not found, your web browser will open, prompting you to log in with your Google account and authorize the application to access your Google Drive files.
    *   After successful authorization, a `token.json` file will be created (or updated) in the specified path (default: current directory). This token will be used for future authentications.

**Backup Process:**

*   For each story being backed up:
    *   A base folder named `"Webnovel Archiver Backups"` will be created in the root of your Google Drive (if it doesn't already exist).
    *   Inside this base folder, a subfolder named after the `STORY_ID` will be created (e.g., `"Webnovel Archiver Backups/my_story_id_123/"`).
    *   The `progress_status.json` file for the story will be uploaded to this story-specific folder.
    *   All EPUB files associated with the story (as listed in its `progress_status.json`) will be uploaded to this folder.
    *   The local `progress_status.json` file will be updated with information about the backup, including cloud file IDs and timestamps.

**Example:**

To back up a specific story:
```bash
webnovel-archiver cloud-backup my_story_id_123 --credentials-file path/to/my/credentials.json
```

To back up all stories:
```bash
webnovel-archiver cloud-backup
```

## Configuration

(TODO: Add details about any configuration files, e.g., for workspace path)

## Contributing

(TODO: Add guidelines for contributing)

## License

(TODO: Specify License - e.g., MIT)
