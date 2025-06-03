# Development Plan: Webnovel Archiver V2

This plan focuses on an incremental approach, building the system module by module, starting with the core and expanding to full functionality.

---

## **Phase 0: Preparation and Initial Setup**

1.  **Development Environment:**
    * Set up a Python virtual environment (e.g., `venv`).
    * Initialize a Git repository for version control.
    * Create a `requirements.txt` file (or `pyproject.toml` if using Poetry/PDM) to manage dependencies. Initially add libraries for CLI (like `click` or `argparse`) and for HTTP requests (like `requests` and `beautifulsoup4`).
2.  **Initial Folder Structure:**
    * Create the main folder structure as per the document:
        * `webnovel_archiver/` (application code root)
            * `core/`
                * `fetchers/`
                * `parsers/`
                * `modifiers/`
                * `builders/`
                * `storage/`
                * `cloud_sync/`
            * `cli/`
            * `utils/`
        * `workspace/` (for generated data, can be added to `.gitignore` initially)
            * `archival_status/`
            * `raw_content/`
            * `processed_content/`
            * `ebooks/`
            * `logs/`
            * `config/`
        * `tests/` (for unit and integration tests)
3.  **Basic Configuration:**
    * **`core/config_manager.py`**: Implement an initial version to load basic configurations (e.g., default workspace path). This could be a simple INI, JSON, or YAML file in `workspace/config/settings.ini`.
    * **`utils/logger.py`**: Set up basic logging for the application.

---

## **Phase 1: Core Download and Processing Functionality (Focus on RoyalRoad)**

The goal of this phase is to be able to download and process content from a RoyalRoad story.

1.  **Fetcher Abstraction:**
    * **`core/fetchers/base_fetcher.py`**: Define the abstract class `BaseFetcher` with methods `get_story_metadata()`, `get_chapter_urls()`, and `download_chapter_content()`. Define dataclasses for `StoryMetadata` and `ChapterInfo`.
2.  **Fetcher Implementation (RoyalRoad):**
    * **`core/fetchers/royalroad_fetcher.py`**: Implement `RoyalRoadFetcher` inheriting from `BaseFetcher`.
        * Focus on getting story metadata.
        * Implement fetching the list of chapter URLs.
        * Implement downloading the raw HTML content of a chapter.
3.  **Progress Management:**
    * **`core/storage/progress_manager.py`**:
        * Define the complete structure of `progress_status.json` as specified in the document.
        * Implement functions to:
            * Load an existing `progress_status.json` for a `story_id`.
            * Create a new `progress_status.json` if it doesn't exist.
            * Save/update `progress_status.json`.
            * Generate `story_id` from the URL or title.
4.  **HTML Cleaning:**
    * **`core/parsers/html_cleaner.py`**: Implement `HTMLCleaner` to remove unnecessary tags, scripts, and styles from raw HTML, focusing on the main story content. Making it configurable can be a later refinement.
5.  **Initial Orchestration:**
    * **`core/orchestrator.py`**:
        * Implement an initial function for the `archive-story` workflow.
        * It should:
            * Select the `RoyalRoadFetcher` (can be hardcoded initially).
            * Use the fetcher to get metadata and chapter list.
            * Consult/create `progress_status.json` using `ProgressManager`.
            * Iterate over chapters:
                * Download raw content using the fetcher.
                * Save raw content to `workspace/raw_content/<story_id>/<local_raw_filename>`.
                * Update `progress_status.json` with downloaded chapter details (including `local_raw_filename`).
            * Process downloaded chapters with `HTMLCleaner`.
            * Save processed content to `workspace/processed_content/<story_id>/<local_processed_filename>`.
            * Update `progress_status.json` with `local_processed_filename`.

---

## **Phase 2: Ebook Generation (EPUB)**

1.  **EPUB Generator:**
    * **`core/builders/epub_generator.py`**: Implement `EPUBGenerator`.
        * Use a Python library for EPUB creation (e.g., `EbookLib`).
        * Read metadata from `progress_status.json`.
        * Read processed HTML files from `workspace/processed_content/`.
        * Generate a simple EPUB file initially, without volume division.
        * Save the EPUB to `workspace/ebooks/<story_id>/`.
2.  **Orchestrator Update:**
    * Integrate `EPUBGenerator` into `core/orchestrator.py`.
    * After chapter processing, invoke the EPUB generator.
    * Update `progress_status.json` with information about `last_epub_processing`.
3.  **Volume Logic (Refinement):**
    * Add volume division logic (`--chapters-per-volume`) to `EPUBGenerator` and `Orchestrator`.
    * Consider how to update existing volumes or create new ones when adding more chapters to a story.

---

## **Phase 3: Command Line Interface (CLI) - `archive-story`**

1.  **CLI Setup:**
    * **`cli/main.py`**: Set up the CLI entry point using `argparse` or `click`. Define the main `archiver` command.
2.  **Handler for `archive-story`:**
    * **`cli/handlers.py`**: Create the handler function for the `archive-story <story_url> [OPTIONS]` subcommand.
    * This function should:
        * Receive `story_url` and other options.
        * Instantiate and call `core.Orchestrator` to execute the archiving workflow.
        * Process CLI options:
            * `--chapters-per-volume`
            * `--ebook-title`
            * `--keep-temporary-files`
            * `--force-reprocessing`
            * `--output-dir` (pass to `ConfigManager` or directly to relevant modules)
        * Provide user feedback on progress and any errors.
3.  **Sentence Removal (Optional):**
    * **`core/modifiers/sentence_remover.py`**: Implement `SentenceRemover` to remove sentences from HTML files based on a JSON config.
    * Integrate into `core/orchestrator.py`, conditional on `--sentence-removal-file` and `--no-sentence-removal` options.
    * Update `progress_status.json` with `sentence_removal_config_used`.
    * Add `--sentence-removal-file` and `--no-sentence-removal` options to the `archive-story` handler in the CLI.

---

## **Phase 4: Cloud Backup Functionality (Google Drive)**

1.  **Sync Service Abstraction:**
    * **`core/cloud_sync/base_sync_service.py`**: Define an interface or base class for synchronization services.
2.  **Google Drive Sync Implementation:**
    * **`core/cloud_sync/gdrive_sync.py`**: Implement `GDriveSync`.
        * Manage OAuth2 authentication with Google Drive (store tokens securely).
        * Implement file upload (EPUBs, `progress_status.json`).
        * Create/verify folder structure on Drive: `"Webnovel Archiver Backups/<story_id>/"`.
        * Logic to update existing files if the local one is newer.
3.  **`cloud-backup` Command in CLI:**
    * Add the `cloud-backup [OPTIONS] [story_id]` subcommand in `cli/main.py`.
    * **`cli/handlers.py`**: Create the handler function for `cloud-backup`.
        * Handle the optional `story_id` argument (if omitted, process all stories).
        * Use `GDriveSync` (or other service selected by `--cloud-service` option).
        * For each selected story:
            * Upload EPUBs listed in `progress_status.json` from `workspace/ebooks/<story_id>/`.
            * Upload `progress_status.json` from `workspace/archival_status/<story_id>/`.
            * Update the local `progress_status.json` with `cloud_backup_status` (timestamps, cloud file IDs, etc.).
        * Process options: `--cloud-service`, `--force-full-upload`.

---

## **Phase 5: Testing, Refinement, and Documentation**

This phase occurs in parallel with the others but intensifies here.

1.  **Unit Tests:**
    * Write unit tests for each module in `core/`, `cli/`, and `utils/`. Focus on testing the logic of each component in isolation.
    * Examples: test parsing logic of `RoyalRoadFetcher`, cleaning by `HTMLCleaner`, EPUB generation with different scenarios.
2.  **Integration Tests:**
    * Test complete workflows:
        * `archive-story` command end-to-end for a test story (can be a set of local HTML files to avoid constant network dependency in tests).
        * `cloud-backup` command (may require mocking the cloud service or a dedicated test environment).
3.  **Error Handling:**
    * Review and improve error handling in all modules, ensuring errors are caught, logged, and clearly communicated to the user via the CLI.
4.  **CLI Refinement:**
    * Improve usability, help messages, progress feedback.
5.  **Documentation:**
    * Create/update `README.md` with installation instructions, usage, command examples.
    * Document the architecture (the provided file is already a great start).
    * Consider generating code documentation (e.g., Sphinx).
6.  **Packaging and Distribution (Optional):**
    * Set up `setup.py` or `pyproject.toml` to allow package installation via `pip`.

---

## **Additional Considerations (Throughout the project)**

* **Iteration:** Build each functionality incrementally. Start simple and add complexity.
* **Code Review:** If possible, have someone else review the code.
* **Feedback:** If this is a project for others to use, get feedback early and often.
* **Configuration Maintenance:** Keep `requirements.txt` updated.
* **Future Extensibility:** When implementing `RoyalRoadFetcher`, always consider how one would add an `AnotherSourceFetcher` to ensure the `BaseFetcher` abstraction is robust.