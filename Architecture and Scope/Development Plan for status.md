# Development Plan: Transition to Status-Based Archiving Model

This document outlines the development plan for refactoring the Webnovel Archiver to a "preservation-first" model using a status-based system for chapter management. This change ensures that once a chapter is archived, it is never deleted from the progress file, even if it's removed from the source website.

## **Phase 0: Foundational Model and Interface Changes**

This phase lays the groundwork by defining the new data structures and updating the command-line interface, before altering the core application logic.

1.  **Redefine the Chapter Data Structure:**
    * **File:** `webnovel_archiver/core/storage/progress_manager.py`
    * **Task:** Modify the `_get_new_progress_structure` function and any related data structures to update the schema for entries within the `downloaded_chapters` list.
    * **New Chapter Schema:**
        ```json
        {
          "source_chapter_id": "...",
          "download_order": 1,
          "chapter_url": "...",
          "chapter_title": "...",
          "status": "active",
          "first_seen_on": "YYYY-MM-DDTHH:MM:SSZ",
          "last_checked_on": "YYYY-MM-DDTHH:MM:SSZ",
          "local_raw_filename": "...",
          "local_processed_filename": "..."
        }
        ```
        * **`status` (str):** Can be `'active'` (exists on source) or `'archived'` (removed from source).
        * **`first_seen_on` (str):** ISO 8601 timestamp for when the chapter was first archived.
        * **`last_checked_on` (str):** ISO 8601 timestamp for when the chapter was last verified against the source.

2.  **Update Command-Line Interface (CLI):**
    * **File:** `webnovel_archiver/cli/main.py`
    * **Task:** Add a new option to the `archive-story` command to control the contents of the generated EPUB.
    * **New Option:**
        ```python
        @click.option('--epub-contents', 
                      type=click.Choice(['all', 'active-only'], case_sensitive=False), 
                      default='all', 
                      help='Determines what to include in the EPUB: "all" (default) includes active and archived chapters; "active-only" mirrors the source website.')
        ```

3.  **Update CLI Handler:**
    * **File:** `webnovel_archiver/cli/handlers.py`
    * **Task:** Update the `archive_story_handler` function signature to accept the new `epub_contents` parameter and pass it down to the `core.orchestrator.archive_story` function.

## **Phase 1: Implement Migration for Existing Archives**

This phase ensures backward compatibility by automatically and safely upgrading existing `progress_status.json` files to the new format.

1.  **Implement Migration Logic:**
    * **File:** `webnovel_archiver/core/storage/progress_manager.py`
    * **Task:** Modify the `load_progress` function.
        * When a `progress_status.json` file is loaded, check if the chapter objects have the new `"status"` field.
        * If the field is missing, trigger the migration process:
            1.  Log an informational message about the migration.
            2.  **Crucially, create a backup** of the original file (e.g., `progress.json.bak`).
            3.  Iterate through each chapter in the `downloaded_chapters` list.
            4.  For each chapter, add the new fields:
                * `"status": "active"` (Assume all previously saved chapters were active at the time).
                * `"first_seen_on"`: Use the progress file's last modification date as an approximation. If this date is unavailable (e.g., due to OS/filesystem limitations or an error), use "N/A" as a fallback. Log a warning if the file modification date is unavailable and "N/A" is used.
                * `"last_checked_on"`: Use the progress file's last modification date as an approximation (mirroring `first_seen_on` for migrated entries). If this date is unavailable, use "N/A" as a fallback. Log a warning if the file modification date is unavailable and "N/A" is used.
        * Return the migrated data structure in memory for the application to use.

2.  **Create Migration Unit Tests:**
    * **File:** `tests/core/storage/test_progress_manager.py`
    * **Task:** Write a new test case specifically for the migration.
        * The test should create a temporary `progress.json` file in the old format.
        * Call `load_progress` on it.
        * Assert that the returned data structure contains the new fields (`status`, etc.).
        * Assert that a `progress.json.bak` file was created in the correct location.

## **Phase 2: Refactor Core Archiving Logic - STATUS: COMPLETED**

This is the main part of the implementation, changing the orchestrator to use the new status model.

1.  **Implement Reconciliation Logic in Orchestrator:**
    * **File:** `webnovel_archiver/core/orchestrator.py`
    * **Task:** Completely refactor the main chapter processing loop inside the `archive_story` function.
        * **Current Behavior:** The logic overwrites the `downloaded_chapters` list on every run.
        * **New Behavior:**
            1.  Load the existing chapters from `progress_manager` (which are now guaranteed to be in the new format thanks to Phase 1).
            2.  Fetch the current list of chapter URLs from the source.
            3.  Create a map or set of the source URLs for efficient lookup.
            4.  Initialize a new `updated_downloaded_chapters` list.
            5.  **Reconcile Existing Chapters:** Iterate through the chapters already in the progress file. If a chapter's URL is no longer in the source list, update its `status` to `'archived'`. Update the `last_checked_on` timestamp for all checked chapters. Add the updated chapter object to the `updated_downloaded_chapters` list.
            6.  **Process New Chapters:** Identify chapters that are in the source list but not in your progress file. Process them normally (download, clean, save) and add them to the `updated_downloaded_chapters` list with `status: 'active'`.
            7.  Replace the old `downloaded_chapters` list in `progress_data` with the newly built `updated_downloaded_chapters` list.

2.  **Update Orchestrator Unit Tests:**
    * **File:** `tests/core/test_orchestrator.py`
    * **Task:** Update existing tests and add new ones to cover the status-based logic.
        * Test case: A story is archived for the first time.
        * Test case: A story has new chapters added.
        * **Test case: A story has chapters removed.** (Assert that the status correctly changes to `'archived'`).
        * Test case: A story is run with no changes. (Assert that `last_checked_on` is updated).

## **Phase 3: Adapt EPUB Generation and Finalize Workflow**

This phase ensures the final output (the EPUB file) respects the new model and user choices.

1.  **Modify `EPUBGenerator`:** - STATUS: COMPLETED
    * **File:** `webnovel_archiver/core/builders/epub_generator.py`
    * **Task:** Update the `generate_epub` method.
        * It must now accept the `epub_contents` parameter (e.g., `'all'` or `'active-only'`).
        * At the beginning of the method, filter the list of chapters based on the `epub_contents` parameter and the `status` of each chapter.
        * If `epub_contents` is `'all'`, add a visual indicator (e.g., `[Archived]`) to the title of any chapter with `status: 'archived'` before adding it to the EPUB's Table of Contents and `<h1>` tag.
        * Note: The `EPUBGenerator` expects the chapter list (`downloaded_chapters`) to be pre-filtered by the `Orchestrator` if `epub_contents='active-only'` was specified. The generator's primary responsibility concerning chapter status is to add the `[Archived]` marker to titles if `status: 'archived'` chapters are present in the list it receives (typically when `epub_contents='all'` is used by the Orchestrator).

2.  **Update `EPUBGenerator` Unit Tests:** - STATUS: COMPLETED
    * **File:** `tests/core/builders/test_epub_generator.py`
    * **Task:** Create test cases that pass a list of chapters with mixed statuses (`active` and `archived`) to the generator.
        * Assert that the correct chapters are included when `epub_contents` is `'all'`.
        * Assert that only active chapters are included when `epub_contents` is `'active-only'`.
        * Assert that the `[Archived]` marker appears correctly in the generated EPUB.

3.  **Update Integration Tests:** - STATUS: COMPLETED (for CLI flag verification)
    * **File:** `tests/integration/test_cli_archive_story.py`
    * **Task:** Add tests for the end-to-end workflow using the new `--epub-contents` flag to ensure it's passed correctly and influences the final output.
    * Note: Current integration tests verify that the `--epub-contents` flag is correctly passed to the orchestrator. Direct inspection of EPUB content for the `[Archived]` marker within integration tests is a potential future enhancement.

## **Phase 4: Ancillary Systems and Documentation**

The final phase is to update all supporting parts of the project and document the new behavior.

1.  **Enhance HTML Report:**
    * **File:** `webnovel_archiver/generate_report.py`
    * **Task:** Modify the report generation to display the new status information. The report could show stats like "150 Chapters (145 Active, 5 Archived)" and visually differentiate archived chapters in any chapter lists.

2.  **Update All Documentation:**
    * **File:** `README.md`
        * Explain the new "preservation-first" philosophy.
        * Document the new `--epub-contents` flag with clear examples.
    * **File:** `Architecture and Scope/Webnovel Archiver Architecture.md`
        * Update the `progress_status.json` schema to reflect the new chapter object structure.
        * Update the description of the `Orchestrator`'s workflow to describe the new reconciliation logic.
    * **File:** `Architecture and Scope/Development Plan.md` (This original plan)
        * Update this file to mark relevant sections as completed or superseded by this new plan for clarity.
