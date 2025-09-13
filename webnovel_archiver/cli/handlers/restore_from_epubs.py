import os
import click
import zipfile

from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
from webnovel_archiver.core.path_manager import PathManager
from webnovel_archiver.core.storage.progress_manager import get_progress_filepath, load_progress
from webnovel_archiver.utils.logger import get_logger

def handle_restore_from_epubs():
    """
    Restores processed chapter content from existing EPUB files into the
    workspace/processed_content/<story_id>/ directory.
    It uses progress.json to map EPUB chapters to their correct filenames.
    """
    logger_restore = get_logger(__name__ + ".restore_from_epubs") # More specific logger
    logger_restore.info("Starting restore from EPUBs process...")
    click.echo("Starting restore from EPUBs process...")

    try:
        config_manager = ConfigManager()
        workspace_root = config_manager.get_workspace_path()
        logger_restore.info(f"Using workspace: {workspace_root}")
    except Exception as e:
        logger_restore.error(f"Failed to initialize ConfigManager or get workspace path: {e}", exc_info=True)
        click.echo(click.style(f"Error: Could not determine workspace path. {e}", fg="red"), err=True)
        workspace_root = DEFAULT_WORKSPACE_PATH
        logger_restore.warning(f"Falling back to default workspace path: {workspace_root}")
        click.echo(click.style(f"Warning: Using default workspace path: {workspace_root}", fg="yellow"), err=True)

    archival_status_base_dir = os.path.join(workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME)
    ebooks_base_dir = os.path.join(workspace_root, PathManager.EBOOKS_DIR_NAME)
    processed_content_base_dir = os.path.join(workspace_root, PathManager.PROCESSED_CONTENT_DIR_NAME)

    logger_restore.info(f"Archival status directory: {archival_status_base_dir}")
    logger_restore.info(f"Ebooks directory: {ebooks_base_dir}")
    logger_restore.info(f"Processed content directory: {processed_content_base_dir}")

    if not os.path.isdir(archival_status_base_dir):
        logger_restore.error(f"Archival status directory not found: {archival_status_base_dir}. Cannot proceed.")
        click.echo(click.style(f"Error: Archival status directory not found: {archival_status_base_dir}", fg="red"), err=True)
        return

    story_ids_found = [
        item for item in os.listdir(archival_status_base_dir)
        if os.path.isdir(os.path.join(archival_status_base_dir, item))
    ]

    if not story_ids_found:
        logger_restore.info("No story IDs found in the archival status directory.")
        click.echo("No stories found to process.")
        return

    logger_restore.info(f"Found {len(story_ids_found)} potential story IDs: {story_ids_found}")
    click.echo(f"Found {len(story_ids_found)} potential stories. Scanning for EPUBs and progress files...")

    overall_stories_processed = 0
    overall_stories_restored_successfully = 0

    for story_id in story_ids_found:
        logger_restore.info(f"Processing story ID: {story_id}")
        click.echo(f"\nProcessing story: {story_id}")

        progress_json_path = get_progress_filepath(story_id, workspace_root)
        if not os.path.exists(progress_json_path):
            logger_restore.warning(f"Progress.json not found for story ID '{story_id}' at {progress_json_path}. Skipping.")
            click.echo(click.style(f"  Warning: Progress file not found for '{story_id}'. Skipping.", fg="yellow"))
            continue

        try:
            progress_data = load_progress(story_id, workspace_root)
            if not progress_data: # load_progress might return None on error
                logger_restore.warning(f"Failed to load progress data for story ID '{story_id}'. Skipping.")
                click.echo(click.style(f"  Warning: Could not load progress data for '{story_id}'. Skipping.", fg="yellow"))
                continue
        except Exception as e:
            logger_restore.error(f"Error loading progress.json for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  Error loading progress data for '{story_id}': {e}. Skipping.", fg="red"))
            continue

        story_title = progress_data.get('effective_title') or progress_data.get('original_title', 'Unknown Title')
        downloaded_chapters = progress_data.get('downloaded_chapters')

        if not isinstance(downloaded_chapters, list) or not downloaded_chapters:
            logger_restore.warning(f"No 'downloaded_chapters' list found or it's empty in progress.json for story ID '{story_id}'. Skipping.")
            click.echo(click.style(f"  Warning: No chapter information found in progress file for '{story_id}'. Skipping.", fg="yellow"))
            continue

        # Determine EPUB Path
        epub_path = None
        # Strategy 1: Look in story-specific ebook directory: workspace/ebooks/<story_id>/
        story_specific_ebook_dir = os.path.join(ebooks_base_dir, story_id)
        logger_restore.debug(f"Checking story-specific EPUB directory: {story_specific_ebook_dir}")
        if os.path.isdir(story_specific_ebook_dir):
            for item in os.listdir(story_specific_ebook_dir):
                if item.lower().endswith('.epub'):
                    epub_path = os.path.join(story_specific_ebook_dir, item)
                    logger_restore.info(f"Found EPUB in story-specific directory: {epub_path}")
                    click.echo(f"  Found EPUB: {epub_path}")
                    break # Use the first one found

        # Strategy 2: Look for EPUB named after story title (if Strategy 1 fails)
        if not epub_path and story_title != 'Unknown Title':
            potential_epub_name = f"{story_title}.epub"
            # Sanitize story_title for use as a filename if necessary (not done here, assuming titles are safe)
            path_strat2 = os.path.join(ebooks_base_dir, potential_epub_name)
            logger_restore.debug(f"Checking for EPUB by title: {path_strat2}")
            if os.path.isfile(path_strat2):
                epub_path = path_strat2
                logger_restore.info(f"Found EPUB by title: {epub_path}")
                click.echo(f"  Found EPUB: {epub_path}")

        if not epub_path:
            logger_restore.warning(f"EPUB file not found for story ID '{story_id}' (Title: '{story_title}'). Searched in '{story_specific_ebook_dir}' and as '{os.path.join(ebooks_base_dir, story_title + '.epub')}'. Skipping.")
            click.echo(click.style(f"  Warning: EPUB not found for '{story_id}'. Skipping.", fg="yellow"))
            continue

        # Create Destination Directory
        processed_story_dir = os.path.join(processed_content_base_dir, story_id)
        try:
            os.makedirs(processed_story_dir, exist_ok=True)
            logger_restore.info(f"Ensured processed content directory exists: {processed_story_dir}")
        except OSError as e:
            logger_restore.error(f"Failed to create destination directory '{processed_story_dir}' for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  Error: Could not create destination directory for '{story_id}': {e}. Skipping.", fg="red"))
            continue

        # Extract from EPUB
        try:
            with zipfile.ZipFile(epub_path, 'r') as epub_archive:
                all_files_in_epub = epub_archive.namelist()

                excluded_structural_files = ['nav.xhtml', 'toc.xhtml', 'cover.xhtml', 'titlepage.xhtml', 'copyright.xhtml', 'landmarks.xhtml', 'loitoc.xhtml']

                chapter_patterns = [
                    # More specific patterns first
                    (lambda f: f.lower().startswith('oebps/chapter') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/chapter*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/chapter') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/chapter*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('oebps/item') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/item*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/item') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/item*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('oebps/page') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/page*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('ops/page') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "OPS/page*.xhtml/html (excluding structural)"),
                    (lambda f: f.lower().startswith('xhtml/') and f.lower().endswith('.xhtml') and os.path.basename(f.lower()) not in excluded_structural_files, "xhtml/*.xhtml (excluding structural)"),
                    (lambda f: f.lower().startswith('html/') and f.lower().endswith('.html') and os.path.basename(f.lower()) not in excluded_structural_files, "html/*.html (excluding structural)"),

                    # Broader patterns that are more likely to catch structural files, so exclusion is important
                    (lambda f: (f.lower().startswith('oebps/') or f.lower().startswith('ops/')) and f.lower().endswith('.xhtml') and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/*.xhtml or OPS/*.xhtml (excluding structural)"),
                    (lambda f: (f.lower().startswith('oebps/') or f.lower().startswith('ops/')) and f.lower().endswith('.html') and os.path.basename(f.lower()) not in excluded_structural_files, "OEBPS/*.html or OPS/*.html (excluding structural)"),

                    # Last resort pattern with robust exclusion
                    (lambda f: not f.lower().startswith('meta-inf/') and (f.lower().endswith('.xhtml') or f.lower().endswith('.html')) and os.path.basename(f.lower()) not in excluded_structural_files, "Non-META-INF *.xhtml/html (excluding structural, last resort)"),
                ]

                chapter_files_in_epub = []
                used_pattern_description = "None"

                for pattern_fn, pattern_desc in chapter_patterns:
                    potential_chapters = sorted([f for f in all_files_in_epub if pattern_fn(f)])
                    if potential_chapters:
                        logger_restore.info(f"Pattern '{pattern_desc}' found {len(potential_chapters)} potential chapter files for story '{story_id}'.")
                        # Basic check: if a pattern yields an unusually high number of files (e.g. more than total chapters + reasonable overhead)
                        # it might be too broad. For now, we accept the first match.
                        # A more sophisticated check could compare against num_chapters_in_progress here if desired,
                        # but that might prematurely discard a valid pattern if progress.json is off.
                        chapter_files_in_epub = potential_chapters
                        used_pattern_description = pattern_desc
                        click.echo(f"  Discovered {len(chapter_files_in_epub)} chapter files using pattern: {pattern_desc}.")
                        break

                if not chapter_files_in_epub:
                    logger_restore.warning(f"No chapter files found within EPUB '{epub_path}' after trying all patterns. Skipping story '{story_id}'.")
                    click.echo(click.style(f"  Warning: No chapter files found in '{os.path.basename(epub_path)}' after trying all patterns. Skipping.", fg="yellow"))
                    continue

                # Chapter Count Validation
                num_chapters_in_progress = len(downloaded_chapters)
                num_chapters_in_epub = len(chapter_files_in_epub)

                if num_chapters_in_progress == 0: # Already checked 'not downloaded_chapters' but defensive.
                    logger_restore.warning(f"No chapters listed in progress.json for story '{story_id}', nothing to restore.")
                    click.echo(click.style(f"  Warning: No chapters in progress file for '{story_id}'. Skipping.", fg="yellow"))
                    continue

                if num_chapters_in_progress != num_chapters_in_epub:
                    logger_restore.critical(f"Chapter count mismatch for story ID '{story_id}' (Title: '{story_title}'). Progress.json has {num_chapters_in_progress}, EPUB ('{os.path.basename(epub_path)}') has {num_chapters_in_epub} (found with pattern '{used_pattern_description}'). Skipping restoration for this story.")
                    click.echo(click.style(f"  CRITICAL: Chapter count mismatch for '{story_id}'. Progress: {num_chapters_in_progress}, EPUB: {num_chapters_in_epub} (Pattern: '{used_pattern_description}'). Skipping.", fg="red"))
                    # Log more details if count mismatches, this can help diagnose pattern issues
                    if num_chapters_in_epub > 0 : # Only log if files were actually found
                        logger_restore.debug(f"Files found by pattern '{used_pattern_description}' for '{story_id}': {chapter_files_in_epub[:10]}") # Log first 10
                    if abs(num_chapters_in_progress - num_chapters_in_epub) > 5 and num_chapters_in_epub > num_chapters_in_progress : # Arbitrary threshold for "too many files"
                        logger_restore.warning(f"Pattern '{used_pattern_description}' yielded significantly more files ({num_chapters_in_epub}) than expected ({num_chapters_in_progress}) for story '{story_id}'. This pattern might be too broad for this EPUB structure.")

                    continue

                # Restore Chapter Files
                restored_files_count = 0
                for i, chapter_info in enumerate(downloaded_chapters):
                    if not isinstance(chapter_info, dict):
                        logger_restore.warning(f"Malformed chapter_info entry at index {i} for story '{story_id}'. Skipping this chapter entry.")
                        click.echo(click.style(f"  Warning: Malformed chapter data at index {i} for '{story_id}'. Skipping entry.", fg="yellow"))
                        continue

                    target_filename = chapter_info.get('local_processed_filename')
                    if not target_filename:
                        logger_restore.warning(f"Missing 'local_processed_filename' for chapter {chapter_info.get('chapter_title', 'Unknown Title')} (index {i}) in story '{story_id}'. Skipping this chapter.")
                        click.echo(click.style(f"  Warning: Missing target filename for chapter index {i} ('{chapter_info.get('chapter_title', 'N/A')}') in '{story_id}'. Skipping.", fg="yellow"))
                        continue

                    # This assumes a direct 1-to-1 mapping by order.
                    epub_chapter_source_path = chapter_files_in_epub[i]
                    target_path = os.path.join(processed_story_dir, target_filename)

                    try:
                        chapter_content_bytes = epub_archive.read(epub_chapter_source_path)
                        with open(target_path, 'wb') as f_out:
                            f_out.write(chapter_content_bytes)
                        # logger_restore.debug(f"Restored '{target_filename}' from '{epub_chapter_source_path}'")
                        restored_files_count += 1
                    except KeyError:
                        logger_restore.error(f"File '{epub_chapter_source_path}' not found in EPUB archive for story '{story_id}', though it was listed. Skipping this chapter.", exc_info=True)
                        click.echo(click.style(f"  Error: EPUB chapter file '{epub_chapter_source_path}' gone missing for '{story_id}'. Skipping.", fg="red"))
                        # This might indicate a flaw in chapter_files_in_epub logic or a very strange EPUB.
                        # Consider if this should halt the story's restoration. For now, skip chapter.
                    except IOError as e:
                        logger_restore.error(f"IOError writing file '{target_path}' for story '{story_id}': {e}", exc_info=True)
                        click.echo(click.style(f"  Error writing file '{target_filename}' for '{story_id}': {e}. Skipping chapter.", fg="red"))
                        # If one file fails to write, we might skip the whole story or just this chapter.
                        # For now, skip chapter.

                if restored_files_count == num_chapters_in_progress and num_chapters_in_progress > 0:
                    logger_restore.info(f"Successfully restored {restored_files_count} chapter files for story ID '{story_id}' (Title: '{story_title}') to '{processed_story_dir}'.")
                    click.echo(click.style(f"  ✓ Successfully restored {restored_files_count} files for '{story_id}' ('{story_title}').", fg="green"))
                    overall_stories_restored_successfully += 1
                elif restored_files_count > 0: # Partial success
                    logger_restore.warning(f"Partially restored story ID '{story_id}': {restored_files_count}/{num_chapters_in_progress} files restored to '{processed_story_dir}'.")
                    click.echo(click.style(f"  Warning: Partially restored '{story_id}': {restored_files_count}/{num_chapters_in_progress} files.", fg="yellow"))
                else: # No files restored, even if counts matched initially but individual steps failed
                    logger_restore.error(f"No files were restored for story ID '{story_id}' despite initial checks passing. Check warnings/errors for individual chapters.")
                    click.echo(click.style(f"  Error: No files restored for '{story_id}'. Check logs.", fg="red"))


        except zipfile.BadZipFile:
            logger_restore.error(f"'{epub_path}' is not a valid EPUB (zip) file for story ID '{story_id}'. Skipping.", exc_info=True)
            click.echo(click.style(f"  Error: '{os.path.basename(epub_path)}' is not a valid EPUB file for '{story_id}'. Skipping.", fg="red"))
            continue
        except FileNotFoundError: # Should be caught by epub_path check, but defensive.
            logger_restore.error(f"EPUB file '{epub_path}' not found when trying to open for story ID '{story_id}'. Skipping.", exc_info=True)
            click.echo(click.style(f"  Error: EPUB file '{os.path.basename(epub_path)}' not found for '{story_id}'. Skipping.", fg="red"))
            continue
        except Exception as e: # Catch-all for other issues during EPUB processing for a story
            logger_restore.error(f"An unexpected error occurred processing EPUB '{epub_path}' for story ID '{story_id}': {e}", exc_info=True)
            click.echo(click.style(f"  An unexpected error occurred with EPUB for '{story_id}': {e}. Skipping.", fg="red"))
            continue
        finally:
            overall_stories_processed +=1


    logger_restore.info(f"Restore from EPUBs process completed. Processed {overall_stories_processed} stories. Successfully restored {overall_stories_restored_successfully} stories fully.")
    click.echo(f"\nRestore from EPUBs process finished.")
    click.echo(f"Summary: Processed {overall_stories_processed} stories. Successfully restored content for {overall_stories_restored_successfully} stories.")
    if overall_stories_processed > 0 and overall_stories_restored_successfully < overall_stories_processed:
        click.echo(click.style("  Some stories may have been skipped or had issues. Please check logs for details.", fg="yellow"))
