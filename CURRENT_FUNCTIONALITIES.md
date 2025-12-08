# Webnovel Archiver - Current Functionalities & Android Porting Guide

This document outlines the current functionalities of the Webnovel Archiver CLI application and provides specific considerations for porting these features to an Android environment.

## 1. Core Archiving Engine

The core purpose of the application is to download, process, and archive webnovels.

### Current Functionality
-   **Source Support:** Currently supports **RoyalRoad**. The system uses a `FetcherFactory` to select the appropriate fetcher based on the URL.
-   **Download Process:**
    -   Fetches story metadata (title, author, cover image, synopsis).
    -   Fetches the list of chapters.
    -   Downloads chapter content sequentially.
    -   **Resumable:** Tracks progress in `progress_status.json`. Skips already downloaded chapters unless `force-reprocessing` is enabled.
-   **Content Processing:**
    -   **HTML Cleaning:** Removes scripts, ads, and platform-specific clutter using `BeautifulSoup`.
    -   **Sentence Removal:** Optionally removes specific sentences (e.g., Patreon solicitations) based on a configured JSON rules file.
-   **Data Organization:**
    -   **Workspace:** All data is stored in a user-defined workspace directory.
    -   **Story Index:** A `story_index.json` maps permanent story IDs to their local folder names.
    -   **File Structure:**
        -   `Raw/`: Original HTML files.
        -   `Processed/`: Cleaned HTML files.
        -   `progress_status.json`: Metadata and chapter status.

### Android Considerations
-   **Network Operations:** Network requests (`requests` library) must run on a background thread (e.g., Coroutines/WorkManager) to avoid blocking the Main UI thread.
-   **Storage Access:**
    -   Android 10+ (Scoped Storage) restricts direct file system access.
    -   **Recommendation:** Use the App's Private Storage (`Context.getFilesDir()`) for the internal workspace to avoid permission issues.
    -   For exporting EPUBs to the user, use the **Storage Access Framework (SAF)** or `MediaStore`.
-   **Background Processing:** Downloading hundreds of chapters takes time. Use **WorkManager** to ensure the process continues even if the user minimizes the app.

---

## 2. EPUB Generation

The system compiles processed chapters into standard EPUB ebook files.

### Current Functionality
-   **Library:** Uses `EbookLib` (Python).
-   **Modes:**
    -   **All:** Includes all downloaded chapters.
    -   **Active Only:** Includes only chapters currently "active" on the source site (useful if authors delete chapters).
-   **Volume Splitting:** Can split the story into multiple EPUB volumes based on a chapter count limit.
-   **Separation:** Can generate separate EPUBs for "Active" and "Archived" (deleted from source) content.
-   **Metadata:** Embeds cover image, title, and author into the EPUB.

### Android Considerations
-   **Library Selection:** You cannot directly use Python's `EbookLib` in native Android (Kotlin/Java).
    -   **Alternative:** Use a Java/Kotlin EPUB library (e.g., **Epublib** or build manually using ZIP/XML libraries).
-   **Image Handling:** Processing cover images for EPUBs usually requires an image library. Android has native `Bitmap` support, or use libraries like **Coil** or **Glide** for fetching and resizing before embedding.
-   **Performance:** Generating large EPUBs can be memory-intensive. Ensure this runs in a background service/worker.

---

## 3. Cloud Backup (Google Drive)

Backs up the local archive to Google Drive.

### Current Functionality
-   **Authentication:** Uses Google OAuth 2.0 flow for installed applications (`run_local_server`). Stores credentials in `token.json`.
-   **Scope:** `drive.file` (only accesses files created by the app).
-   **Logic:**
    -   Checks for a `Webnovel_Archive` folder in the user's Drive.
    -   Creates subfolders for each story.
    -   Uploads `progress_status.json` and generated EPUB files.
    -   **Smart Sync:** Checks file modification timestamps (`modifiedTime`) to avoid re-uploading unchanged files.
    -   Uploads the HTML Report.

### Android Considerations
-   **Authentication Flow:** **Do NOT** use the Python `run_local_server` approach.
    -   **Native Solution:** Use **Google Sign-In for Android** and the **Google Drive API for Android (REST)**.
    -   The auth flow will use Android Intents to prompt the user.
-   **Sync Logic:** The logic of comparing timestamps remains valid, but you will use Android's `File` API and Drive API responses.
-   **Background Sync:** Use **WorkManager** with constraints (e.g., "only on Wi-Fi", "only when charging") for robust background backup.

---

## 4. Reporting System

Generates a visual library of archived content.

### Current Functionality
-   **Format:** A single, self-contained HTML file (`archive_report_new.html`).
-   **Features:**
    -   Lists all stories with cover images and progress bars.
    -   **Search/Filter:** Embedded JavaScript allows searching by title/author and sorting by progress/date.
    -   **Links:** Provides links to the local EPUB files (works on local file systems).

### Android Considerations
-   **UI Paradigm Shift:** An HTML report is less relevant for a native Android app.
    -   **Replacement:** The App **IS** the report.
    -   **Main Activity:** A `RecyclerView` listing the stories (Cards with covers).
    -   **Search/Filter:** Use a `SearchView` in the `Toolbar` and filter the adapter data.
-   **Viewing EPUBs:** Instead of file links, the "Read" button should launch an Intent to open the EPUB in the user's preferred E-Reader app.

---

## 5. Command Line Interface (CLI) vs Android UI

Mapping current CLI commands to Android UI interactions.

| CLI Command | Android Equivalent | Description |
| :--- | :--- | :--- |
| `archive-story <URL>` | **"Add Story" Button (FAB)** | Opens a dialog to paste the URL. Triggers the download Service. |
| `cloud-backup` | **"Sync" Menu Item** | Manually triggers the Cloud Sync WorkManager task. |
| `generate-report` | **Home Screen** | The main list view of the app automatically reflects the current state. |
| `migrate` | **App Update Logic** | Database migrations should run automatically `onUpgrade` or on first launch. |
| `restore-from-epubs` | **Import Feature** | "Import EPUB" option to populate the library from existing files. |

## 6. Data Structure & Storage

### Current Data Model (`progress_status.json`)
```json
{
  "story_id": "12345",
  "original_title": "Example Story",
  "downloaded_chapters": [
    {
      "chapter_title": "Chapter 1",
      "status": "active",
      "local_processed_filename": "chapter_00001_123_clean.html"
    }
  ]
}
```

### Android Considerations
-   **Database:** While JSON files work, Android apps typically use **SQLite** (via **Room** persistence library).
    -   **Migration:** Consider migrating the `progress_status.json` structure to a relational database (Story Table, Chapter Table) for better performance and easier UI binding (`LiveData`/`Flow`).
-   **File Storage:** Continue using internal files for HTML content, but store metadata in the database.
