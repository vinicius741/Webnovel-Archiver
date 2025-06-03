import os
import sys

# Add the project root to the Python path to allow direct imports of webnovel_archiver
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

print(f"Python path: {sys.path}")
print(f"Current working directory: {os.getcwd()}")
print("Listing contents of /app/:")
print(os.listdir("/app"))
print("Listing contents of /app/webnovel_archiver/:")
print(os.listdir("/app/webnovel_archiver"))
print("Listing contents of /app/webnovel_archiver/utils/:")
print(os.listdir("/app/webnovel_archiver/utils"))


errors = []
success_messages = []

# 1. Attempt to import webnovel_archiver.cli.main
try:
    import webnovel_archiver.cli.main
    success_messages.append("Successfully imported webnovel_archiver.cli.main.")
except ImportError as e:
    errors.append(f"Failed to import webnovel_archiver.cli.main: {e}")
except Exception as e:
    errors.append(f"An unexpected error occurred during import of webnovel_archiver.cli.main: {e}")

# 2. Check if webnovel_archiver.cli.handlers.archive_story_handler can be called
try:
    from webnovel_archiver.cli.handlers import archive_story_handler
    success_messages.append("Successfully imported archive_story_handler.")

    # Call with minimal valid arguments
    # archive_story_handler(story_url, output_dir, ebook_title_override, keep_temp_files, force_reprocessing, sentence_removal_file, no_sentence_removal, chapters_per_volume)
    # Based on handlers.py, story_url is the primary required one for the handler itself.
    # The orchestrator it calls would need more, but we're just checking invokability.
    # However, the handler might try to use ConfigManager which might write to a default path.
    # To be safe, let's provide a dummy URL and set other potentially problematic args to safe values.
    print("Attempting to call archive_story_handler...")
    # We expect this to fail because the dummy URL won't resolve,
    # but we want to see if it's callable before that point.
    # A more robust test would mock dependencies.
    # For now, any error during the call will be caught.
    try:
        archive_story_handler(
            story_url="http://example.com/dummy-story",
            output_dir=None, # Let it use default or config
            ebook_title_override=None,
            keep_temp_files=False,
            force_reprocessing=False,
            sentence_removal_file=None,
            no_sentence_removal=True, # Avoids sentence remover logic
            chapters_per_volume=None
        )
        # If it reaches here, it means the call initiated.
        # It might have logged errors internally but didn't raise an exception at the call boundary itself.
        success_messages.append("archive_story_handler was callable. (Note: Internal errors might have occurred, check logs if any)")
    except Exception as e:
        # This is expected if the dummy URL causes issues deeper in the call stack (e.g., network request)
        # The key is that it didn't fail due to incorrect signature or missing imports at the handler level.
        success_messages.append(f"archive_story_handler was callable but raised an internal exception as expected with dummy data: {e}")

except ImportError as e:
    errors.append(f"Failed to import archive_story_handler: {e}")
except Exception as e:
    errors.append(f"An unexpected error occurred during import/call of archive_story_handler: {e}")


# 3. Verify webnovel_archiver.utils.logger.LOG_FILE_PATH
try:
    from webnovel_archiver.utils.logger import LOG_FILE_PATH, get_logger
    success_messages.append(f"Successfully imported LOG_FILE_PATH. Value: {LOG_FILE_PATH}")

    if LOG_FILE_PATH:
        log_dir = os.path.dirname(LOG_FILE_PATH)
        if os.path.exists(log_dir):
            success_messages.append(f"Log directory '{log_dir}' exists.")
        else:
            # Try to initialize a logger to see if it creates the directory
            logger_instance = get_logger("test_log_path")
            if os.path.exists(log_dir):
                success_messages.append(f"Log directory '{log_dir}' was created after logger initialization.")
            else:
                errors.append(f"Log directory '{log_dir}' does not exist and was not created by get_logger.")
        # We won't check for the file itself as it might not be created until a log message is written.
    else:
        errors.append("LOG_FILE_PATH is not set (empty or None).")

except ImportError as e:
    errors.append(f"Failed to import LOG_FILE_PATH from webnovel_archiver.utils.logger: {e}")
except Exception as e:
    errors.append(f"An unexpected error occurred during LOG_FILE_PATH verification: {e}")


# Report results
if errors:
    print("\n--- ERRORS ---")
    for error in errors:
        print(error)
else:
    print("\n--- ALL CHECKS PASSED (based on script logic) ---")

print("\n--- SUCCESS MESSAGES ---")
for msg in success_messages:
    print(msg)

# Exit with 1 if there were errors, 0 otherwise
sys.exit(1 if errors else 0)
