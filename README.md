# Webnovel Archiver CLI

A command-line tool for archiving webnovels from various sources and managing your local archive.

## Features

*   Archive webnovels from supported sources.
*   Generate EPUB files for offline reading.
*   Manage archival progress.
*   Backup your archived stories to Google Drive.

## Our Philosophy: Preservation-First

Webnovel Archiver is built with a "preservation-first" approach. This means:

*   **Once Archived, Always Kept:** When a chapter is successfully downloaded and added to your local archive, it is considered "archived."
*   **Resilience to Source Changes:** Even if a chapter is later removed from the original webnovel source by the author or publisher, your archived copy remains untouched in your local storage. The tool will simply mark its status as 'archived' in your `progress.json` to reflect that it's no longer available at the source, but the content itself is preserved.
*   **Your Data, Your Control:** This philosophy ensures that your collection is protected against content takedowns or website unavailability, safeguarding the stories you've invested time in reading and archiving.

## Installation

It is recommended to install the Webnovel Archiver CLI in a virtual environment.

1.  **Create and Activate a Virtual Environment:**

    Open your terminal, navigate to the project directory, and run the following commands:

    ```bash
    # Create a virtual environment named 'venv'
    python3 -m venv venv
    ```

    Activate the virtual environment:
    *   **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
    *   **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```

2.  **Install the Package:**

    Once the virtual environment is activated, install the required packages from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

## Basic Usage

### Archiving a new story

```bash
webnovel-archiver archive-story <STORY_URL> [OPTIONS]
```

**Example:**

```bash
webnovel-archiver archive-story "https://www.royalroad.com/fiction/xxxxx/some-story-title"
```

**Key Options for `archive-story`:**

*   `--epub-contents [all|active-only]` (Default: `all`)
    *   Determines which chapters are included in the generated EPUB file(s).
    *   `all`: Includes all chapters that have been downloaded, regardless of their current status (active or archived). This is useful if you want a complete EPUB of everything you've ever captured for the story.
    *   `active-only`: Includes only chapters currently marked as 'active'. This means chapters that were once downloaded but have since been marked 'archived' (e.g., because they were removed from the source) will not be included. This is typically what you want for ongoing reading, as it reflects the current state of the story on the source.
*   `--output-dir PATH`
    *   Specifies a directory to save the archive, overriding the default workspace setting.
*   `--ebook-title-override TEXT`
    *   Overrides the title of the generated EPUB file(s).
*   `--chapters-per-volume INTEGER`
    *   Splits the EPUB into multiple volumes, each containing the specified number of chapters. If not set, a single EPUB file will be created for the entire story.
*   `--force-reprocessing`
    *   Forces the tool to re-process already downloaded chapter content.
*   `--sentence-removal-file PATH`
    *   Specifies a path to a custom JSON file with sentence removal rules.
*   `--no-sentence-removal`
    *   Disables the sentence removal feature, even if a default or custom rule file is available.
*   `--keep-temp-files`
    *   Prevents the deletion of temporary files (like raw HTML and processed chapter content) after the archiving process is complete.

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

### Migrating an Existing Archive

The `migrate` command helps update existing story archives to new formats or fix identifiers without re-downloading content. This is useful for handling site-specific changes, like updates to URL formats.

```bash
webnovel-archiver migrate [STORY_ID] --type <MIGRATION_TYPE>
```

**Arguments:**

*   `[STORY_ID]` (Optional): The specific ID of the story to migrate. If omitted, the tool will scan all archives and apply the migration where applicable.

**Options:**

*   `--type [royalroad-legacy-id]` (Required): Specifies the migration to perform.
    *   `royalroad-legacy-id`: This migration is for Royal Road stories that were archived using a numeric fiction ID in their URL. It updates the internal story identifier to the new slug-based format used by the site.

**Example:**

To apply the Royal Road legacy ID migration to all relevant stories:
```bash
webnovel-archiver migrate --type royalroad-legacy-id
```

### Generating an Archive Report

The `generate-report` command scans your archived stories and creates a comprehensive HTML file summarizing your webnovel collection. This report provides a visual dashboard of all archived webnovels, their download progress, completion status, EPUB file links, and cloud backup status.

```bash
webnovel-archiver generate-report
```

**Details:**

*   **Arguments/Options:** This command currently does not take any arguments or options.
*   **Output:**
    *   The script will process all stories found in your workspace's `archival_status` directory.
    *   The generated HTML report, named `archive_report.html`, will be saved in the `reports` subdirectory of your workspace (e.g., `your_workspace_root/reports/archive_report.html`).
    *   The path to the generated report will also be printed to the console upon successful completion.
*   **Functionality:**
    *   The report includes features like searching by title/author, sorting, and filtering by status directly within the HTML page using JavaScript.

### Restoring from EPUBs

The `restore-from-epubs` command provides a way to rebuild parts of your archive's metadata from existing EPUB files. This is particularly useful in recovery scenarios, for example, if your `progress_status.json` file was deleted but you still have the generated EPUBs.

```bash
webnovel-archiver restore-from-epubs
```

This command will scan the `ebooks` directory, and for any story, if it finds EPUBs but no corresponding `progress_status.json` file, it will create a new progress file and populate it with the chapter information it can extract from the EPUB's contents.

## Configuration

The Webnovel Archiver CLI uses a configuration file named `settings.ini` to manage settings.

**Default Location:**

By default, the application looks for this file at `workspace/config/settings.ini` relative to the project's root directory. If the file or its directory structure does not exist upon first run (or if `ConfigManager` is initialized without a specific path), a default `settings.ini` will be created with the following structure:

```ini
[General]
workspace_path = workspace/

[SentenceRemoval]
default_sentence_removal_file = workspace/config/default_sentence_removal.json
```

**Settings:**

*   **`workspace_path`**: (Under `[General]` section)
    *   Defines the primary directory where the application stores archived content, eBooks, and status files.
    *   If the path in `settings.ini` is relative, it's considered relative to the project root.
    *   Default: `workspace/` (a directory named `workspace` in the project root).
    *   **Note:** You can override this setting by setting the `WNA_WORKSPACE_ROOT` environment variable. If this environment variable is set, its value will be used as the workspace path, ignoring the value in `settings.ini`.

*   **`default_sentence_removal_file`**: (Under `[SentenceRemoval]` section)
    *   Specifies the path to a JSON file containing patterns for sentences to be removed during content processing.
    *   Default: `workspace/config/default_sentence_removal.json`.

**Google Drive Credentials:**

The `cloud-backup` command requires Google Drive API credentials (`credentials.json` and `token.json`). As described in the "Backing up to Cloud (Google Drive)" section, these files are expected by default in the current working directory from which you run the command, or their paths can be specified using the `--credentials-file` and `--token-file` options respectively. These are not configured via `settings.ini`.

## Contributing

We welcome contributions to the Webnovel Archiver CLI! If you'd like to contribute, please follow these general guidelines:

1.  **Fork the Repository:** Start by forking the official repository to your own GitHub account.
2.  **Create a Branch:** Create a new branch in your forked repository for your feature or bug fix. Use a descriptive name (e.g., `feature/add-new-source` or `fix/issue-123`).
3.  **Make Your Changes:** Implement your feature or fix the bug. Ensure your code adheres to common Python coding standards (e.g., PEP 8).
4.  **Add Tests:** If you're adding new functionality or fixing a bug, please add appropriate unit tests to verify your changes.
5.  **Ensure Tests Pass:** Run the existing test suite to make sure your changes haven't introduced any regressions.
6.  **Commit Your Changes:** Make clear, concise commit messages.
7.  **Submit a Pull Request:** Push your changes to your forked repository and then open a pull request to the main branch of the official repository. Provide a clear description of the changes you've made.

We appreciate your help in making this tool better!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
