### **Development Plan: Robust Story Identification Architecture**

**1. Overview and Goals**

This document outlines the phased development plan to re-architect the story identification mechanism in the webnovel-archiver.

The primary goal is to **decouple the story's permanent identity from its filesystem folder name**. This will resolve the critical flaw where changes in a story's title cause data duplication and loss of history. This plan is designed to be executed in stages to ensure maximum safety, data integrity, and a seamless transition for users with large, existing archives.

**2. Guiding Principles**

-   **Data Safety First:** No operation should ever risk the loss of existing user data. All changes must be non-destructive first, and modifications (like renaming) should only occur after a stable state is confirmed.
-   **Idempotency:** The migration process must be idempotent. It should be runnable multiple times on the same archive without causing errors or incorrect data.
-   **User Transparency:** The system should provide clear logs about the migration process and any actions taken (like folder renaming).
-   **Forward Compatibility:** The new architecture must be the single source of truth for all commands, including reporting and cloud backups.

---

### **Phase 0: Legacy Migration and Index Creation (The "Safe Start" Phase)**

**Objective:** To create the new `index.json` from an existing archive **without modifying any existing files or folders**. This phase is purely additive and foundational.

-   **Task 0.1: Design the Migration Trigger Logic**

    -   **Description:** The application, on startup, must check for the existence of `workspace/index.json`. If the file does not exist, it must automatically trigger the one-time migration process before performing any other action.
    -   **Acceptance Criteria:** The migration process is initiated automatically and only once.

-   **Task 0.2: Implement the Core Migration Script**

    -   **Description:** This is the heart of the migration. The script will:
        1.  Create an empty `workspace/index.json` in memory.
        2.  Scan the `workspace` directory for all subfolders.
        3.  For each folder, it will attempt to read its `progress.json`.
        4.  From `progress.json`, it will extract the story's `url`.
        5.  Using the existing `fetcher` logic, it will extract the permanent, source-specific ID from the `url`.
        6.  It will then populate the in-memory index with the mapping: `"permanent-id": "current-folder-name"`.
        7.  Once all folders have been processed, the script will write the complete `index.json` to the disk.
    -   **Acceptance Criteria:** A valid `index.json` is created that accurately maps all existing stories to their permanent IDs.

-   **Task 0.3: Implement Robust Error Handling and Logging for Migration**
    -   **Description:** The migration script must be resilient. It needs to handle potential issues gracefully:
        -   **Corrupt `progress.json`:** If a `progress.json` file is unreadable or malformed, log a clear `WARNING` with the folder name and skip it.
        -   **Missing URL:** If the `url` key is missing in `progress.json`, log a `WARNING` and skip the folder.
        -   **Failed ID Extraction:** If the permanent ID cannot be extracted (e.g., unsupported source), log a `WARNING` and skip the folder.
    -   **Acceptance Criteria:**
        -   The migration process never crashes. It completes for all valid folders.
        -   A `workspace/migration.log` file is generated, detailing every successful mapping and every warning or skipped folder, giving the user a clear report of the process.

---

### **Phase 1: Core Logic and Command Integration (The "Read-Only" Phase)**

**Objective:** To refactor all parts of the application to **use `index.json` as the source of truth** for locating stories. No folder renaming occurs yet.

-   **Task 1.1: Refactor the Main Archiving Logic**

    -   **Description:** Modify the core orchestrator. When processing a URL, it will first extract the permanent ID and look it up in `index.json`. If found, it uses the mapped folder name to access the story data. This single change instantly prevents duplicate archives from being created due to title changes.
    -   **Acceptance Criteria:** The archiver correctly finds and updates existing stories using the index, even if their online titles have changed.

-   **Task 1.2: Adapt `archiver generate-report`**

    -   **Description:** The `generate-report` command must be updated. Instead of just scanning folders, it should first read `index.json`. This gives it access to both the permanent ID and the folder name.
    -   **Acceptance Criteria:**
        -   The report generation works correctly on a migrated archive.
        -   The generated report can (and should) now include the **Permanent ID** as a new column or field, providing a stable identifier in the user-facing output.

-   **Task 1.3: Adapt `archiver cloud-backup`**
    -   **Description:** This command must also be refactored to use `index.json`. Crucially, the backup strategy should be improved for stability.
    -   **Acceptance Criteria:**
        -   The `cloud-backup` command correctly identifies which local folders to back up by reading `index.json`.
        -   The destination path on the cloud storage **must use the permanent ID**, not the folder name (e.g., `s3://my-bucket/royalroad-12345/`). This prevents data duplication on the cloud if a local folder is renamed in the future.

---

### **Phase 2: Activating Folder Synchronization (The "Active Management" Phase)**

**Objective:** With the stable foundation from previous phases, we can now safely implement the folder renaming logic.

-   **Task 2.1: Implement Folder Renaming and Index Update**

    -   **Description:** Add a new step to the main archiving workflow. After identifying a story via its permanent ID, the system will fetch the latest metadata, generate a new "slug" from the current title, and compare it to the folder name in the index. If they differ, it will execute the rename.
    -   **Acceptance Criteria:**
        -   The system safely renames the folder on the filesystem.
        -   The `index.json` file is updated atomically with the new folder name.
        -   A clear `INFO` message is logged to inform the user of the rename.

-   **Task 2.2: Refactor New Story Creation**
    -   **Description:** The flow for adding a new story must now create the folder and add the entry to `index.json` as a single, cohesive operation.
    -   **Acceptance Criteria:** A new story is added with the correct folder name and a corresponding entry in the index.

---

### **Phase 3: Finalization and Code Cleanup (The "Polish" Phase)**

**Objective:** To remove old, fragile code and solidify the new architecture.

-   **Task 3.1: Remove `generate_story_id`**
    -   **Description:** The legacy title-based slug generation function (`generate_story_id`) and all its call sites must be completely removed from the codebase.
    -   **Acceptance Criteria:** The fragile ID generation logic no longer exists. The application now exclusively relies on the new, robust architecture. The system now requires a fetcher to be able to provide a permanent ID, making the entire system more robust by design.
