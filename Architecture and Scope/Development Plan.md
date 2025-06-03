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

## **Phase 1: Core Download and Processing Functionality (Focus on RoyalRoad) - COMPLETED**

The goal of this phase was to be able to download and process content from a RoyalRoad story.

1.  **Fetcher Abstraction:**
    * **`core/fetchers/base_fetcher.py`**: Defined the abstract class `BaseFetcher` with methods `get_story_metadata()`, `get_chapter_urls()`, and `download_chapter_content()`. Defined dataclasses for `StoryMetadata` and `ChapterInfo`.
2.  **Fetcher Implementation (RoyalRoad):**
    * **`core/fetchers/royalroad_fetcher.py`**: Implemented `RoyalRoadFetcher` inheriting from `BaseFetcher`.
        * Focused on getting story metadata.
        * Implemented fetching the list of chapter URLs.
        * Implemented downloading the raw HTML content of a chapter (initially simulated using placeholder content).
3.  **Progress Management:**
    * **`core/storage/progress_manager.py`**:
        * Defined the complete structure of `progress_status.json`.
        * Implemented functions to:
            * Load an existing `progress_status.json` for a `story_id`.
            * Create a new `progress_status.json` if it doesn't exist.
            * Save/update `progress_status.json`.
            * Generate `story_id` from the URL or title.
4.  **HTML Cleaning:**
    * **`core/parsers/html_cleaner.py`**: Implemented `HTMLCleaner` to remove unnecessary tags, scripts, and styles from raw HTML, focusing on the main story content.
5.  **Initial Orchestration:**
    * **`core/orchestrator.py`**:
        * Implemented an initial function for the `archive-story` workflow.
        * It:
            * Selected the `RoyalRoadFetcher` (hardcoded).
            * Used the fetcher to get metadata and chapter list.
            * Consulted/created `progress_status.json` using `ProgressManager`.
            * Iterated over chapters:
                * Downloaded raw content using the fetcher (simulated).
                * Saved raw content to `workspace/raw_content/<story_id>/<local_raw_filename>`.
                * Updated `progress_status.json` with downloaded chapter details.
            * Processed downloaded chapters with `HTMLCleaner`.
            * Saved processed content to `workspace/processed_content/<story_id>/<local_processed_filename>`.
            * Updated `progress_status.json`.

---

## **Phase 1.5: Initial Refinements and Preparation for Expansion**

This phase addresses immediate refinements based on Phase 1 and prepares for more complex functionalities.

1.  **Transition to Real HTTP Requests (Fetcher):**
    * Modify `core/fetchers/royalroad_fetcher.py`'s `download_chapter_content` method (and potentially `_fetch_html_content` or a new method for actual chapter page fetching) to perform actual HTTP requests using the `requests` library.
    * Implement basic error handling for network requests (e.g., connection errors, timeouts, non-200 status codes).
    * The `_fetch_html_content` in `RoyalRoadFetcher` which currently serves example story page HTML should also be updated or complemented to fetch live story pages.
2.  **Initial Unit Tests:**
    * Write basic unit tests for key functions implemented in `ProgressManager`, `HTMLCleaner`, and parsing logic within `RoyalRoadFetcher` (for metadata and chapter list from example HTML initially, then adaptable for live content).
3.  **Configuration Alignment (Logging):**
    * Align log file name: Change `app.log` in `utils/logger.py` to `archiver.log` for consistency with the `Architecture and Scope/Webnovel Archiver Architecture.md` document.
4.  **Refine Orchestrator for Real Content:**
    * Ensure `core/orchestrator.py` correctly handles the potentially larger and varied content from real HTTP requests.
    * Review error propagation from the fetcher to the orchestrator.

---

## **Phase 2: Ebook Generation (EPUB)**

1.  **EPUB Generator:**
    * **`core/builders/epub_generator.py`**: Implement `EPUBGenerator`.
        * Use a Python library for EPUB creation (e.g., `EbookLib`).
        * Read metadata from `progress_status.json`.
        * Read processed HTML files (now potentially from live fetched content) from `workspace/processed_content/`.
        * Generate a simple EPUB file initially, without volume division.
        * Save the EPUB to `workspace/ebooks/<story_id>/`.
2.  **Orchestrator Update:**
    * Integrate `EPUBGenerator` into `core/orchestrator.py`.
    * After chapter processing, invoke the EPUB generator.
    * Update `progress_status.json` with information about `last_epub_processing`.
3.  **Volume Logic (Refinement):**
    * Add volume division logic (`--chapters-per-volume`) to `EPUBGenerator` and `Orchestrator`.
    * Consider how to update existing volumes or create new ones when adding more chapters to a story.
4.  **Unit Tests:**
    * Write unit tests for `EPUBGenerator` logic.

---



 ## **Phase 3: Command Line Interface (CLI) - archive-story (Revised)**

This phase focuses on implementing the primary CLI command for story archiving, ensuring it can pass user-defined options to the core Orchestrator.



1. **CLI Setup:**
    * **cli/main.py**: Set up the CLI entry point (e.g., using click). Define the main archiver command group and the archive-story subcommand.
2. **Handler for archive-story:**
    * **cli/handlers.py**: Create the handler function for archive-story &lt;story_url> [OPTIONS].
        * This function will:
            * Receive story_url and parse all CLI options.
            * Determine the workspace_root (from --output-dir or ConfigManager).
            * Instantiate core.Orchestrator.
            * Call core.Orchestrator.archive_story(), passing arguments derived from CLI options.
            * Provide user feedback on progress and errors.
    * **core/orchestrator.py Modification**:
        * The archive_story method within core.Orchestrator **must be updated** to accept new parameters corresponding to the CLI options (e.g., ebook_title_override, keep_temp_files, force_reprocessing, sentence_removal_file, no_sentence_removal).
        * The Orchestrator will then use these parameters to modify its workflow (e.g., use the override title, skip deleting temp files, force reprocessing steps, conditionally call sentence removal).
3. **Sentence Removal (Optional):**
    * **core/modifiers/sentence_remover.py**: Implement SentenceRemover to remove sentences from HTML files based on a JSON config.
    * **Integration in core.Orchestrator**:
        * Conditionally invoke SentenceRemover based on the parameters passed from the CLI handler (sentence_removal_file, no_sentence_removal).
        * Update progress_status.json with sentence_removal_config_used.
    * **CLI Options**: Add --sentence-removal-file and --no-sentence-removal to the archive-story command.
4. **Unit and Integration Tests:**
    * Write unit tests for CLI handlers (mocking Orchestrator calls to verify correct parameter passing) and for SentenceRemover.
    * Develop integration tests for the archive-story command, covering various CLI option combinations and their effect on the Orchestrator's behavior and output.

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
4.  **Unit and Integration Tests:**
    * Write unit tests for `GDriveSync` (may require mocking).
    * Develop integration tests for the `cloud-backup` command.

---

## **Phase 5: Testing, Refinement, and Documentation**

This phase occurs in parallel with the others but intensifies here, focusing on areas not covered by phase-specific testing.

1.  **Comprehensive Integration Tests:**
    * Test complete workflows end-to-end with various scenarios (e.g., new story, updating story, different CLI options).
    * Test interaction between all core modules.
2.  **Error Handling and Robustness Review:**
    * Review and improve error handling across all modules, ensuring errors are caught, logged, and clearly communicated to the user via the CLI, especially for network operations and file I/O.
    * Implement the more systematic error handling strategy (see "General Considerations").
3.  **Performance Testing (Basic):**
    * Identify any major performance bottlenecks for very large stories (many chapters).
4.  **CLI Refinement:**
    * Improve usability, help messages, progress feedback based on testing.
5.  **Documentation:**
    * Create/update `README.md` with installation instructions, detailed usage for all commands and options, examples.
    * Finalize documentation for the architecture.
    * Consider generating code documentation (e.g., Sphinx).
6.  **Packaging and Distribution (Optional):**
    * Set up `setup.py` or `pyproject.toml` to allow package installation via `pip`.

---

## **General Considerations (Throughout the project)**

* **Error Handling Strategy:**
    * As the project evolves (especially with network requests and more complex file operations from Phase 1.5 onwards), develop a more systematic error handling strategy. This could include defining custom exceptions (e.g., in a new `utils/exceptions.py` file) for common issues such as fetching errors, parsing errors, or configuration problems. This will aid in providing clearer feedback to the user and simplify debugging.
* **Configuration:**
    * **HTMLCleaner Configuration:** Revisit making `HTMLCleaner` more configurable (e.g., via a JSON file specifying rules per site) as a later refinement if needed, possibly after supporting more than one source.
* **Iteration:** Build each functionality incrementally. Start simple and add complexity.
* **Code Review:** If possible, have someone else review the code.
* **Feedback:** If this is a project for others to use, get feedback early and often.
* **Configuration Maintenance:** Keep `requirements.txt` updated.
* **Future Extensibility:** When implementing `RoyalRoadFetcher`, always consider how one would add an `AnotherSourceFetcher` to ensure the `BaseFetcher` abstraction is robust.