import os
from typing import Optional, Dict, Any, Union
import json

from webnovel_archiver.core.config_manager import ConfigManager, DEFAULT_WORKSPACE_PATH
from webnovel_archiver.utils.logger import get_logger
from webnovel_archiver.core.path_manager import PathManager

logger = get_logger(__name__)

class ArchiveStoryContext:
    """
    Handles validation, configuration management, and argument preparation
    for the archive-story command.
    """
    def __init__(
        self,
        story_url: str,
        output_dir: Optional[str],
        ebook_title_override: Optional[str],
        keep_temp_files: bool,
        force_reprocessing: bool,
        cli_sentence_removal_file: Optional[str],
        no_sentence_removal: bool,
        chapters_per_volume: Optional[int],
        epub_contents: Optional[str]
    ):
        self.story_url = story_url
        self.output_dir_option: Optional[str] = output_dir
        self.ebook_title_override: Optional[str] = ebook_title_override
        self.keep_temp_files: bool = keep_temp_files
        self.force_reprocessing: bool = force_reprocessing
        self.cli_sentence_removal_file_option: Optional[str] = cli_sentence_removal_file
        self.no_sentence_removal: bool = no_sentence_removal
        self.chapters_per_volume: Optional[int] = chapters_per_volume
        self.epub_contents: Optional[str] = epub_contents

        self._config_manager: Optional[ConfigManager] = None
        self.error_messages: list[str] = []

        self.workspace_root: str = self._resolve_workspace_root()
        self.sentence_removal_file: Optional[str] = self._resolve_sentence_removal_file()

    @property
    def config_manager(self) -> ConfigManager:
        if self._config_manager is None:
            try:
                self._config_manager = ConfigManager()
            except Exception as e:
                logger.error(f"Failed to initialize ConfigManager: {e}")
                self.error_messages.append(f"Failed to initialize ConfigManager: {e}")
                # In case of ConfigManager failure, we might need a fallback or re-raise
                # For now, workspace_root resolution handles DEFAULT_WORKSPACE_PATH
                # and sentence_removal_file resolution handles missing config.
                # If ConfigManager is critical for other parts, this could be an issue.
                # A 'dummy' ConfigManager that provides defaults could be another option.
                # For now, allow it to be None if it fails, and let methods handle it.
                # However, for resolving paths, we try to create it ad-hoc if needed.
        return self._config_manager

    def _resolve_workspace_root(self) -> str:
        if self.output_dir_option:
            logger.info(f"Using provided output directory: {self.output_dir_option}")
            return self.output_dir_option
        else:
            try:
                # Attempt to create ConfigManager instance specifically for this resolution
                # if not already created or if creation failed previously.
                cm = ConfigManager() # This might raise an exception
                ws_path = cm.get_workspace_path()
                logger.info(f"Using workspace directory from config: {ws_path}")
                return ws_path
            except Exception as e:
                logger.warning(f"Failed to get workspace path from ConfigManager: {e}. Using default.")
                self.error_messages.append(f"Warning: Using default workspace path due to error: {DEFAULT_WORKSPACE_PATH} (Original error: {e})")
                return DEFAULT_WORKSPACE_PATH

    def _resolve_sentence_removal_file(self) -> Optional[str]:
        if self.no_sentence_removal:
            logger.info("Sentence removal explicitly disabled via --no-sentence-removal flag.")
            return None

        if self.cli_sentence_removal_file_option:
            if os.path.exists(self.cli_sentence_removal_file_option):
                logger.info(f"Using sentence removal file provided via CLI: {self.cli_sentence_removal_file_option}")
                return self.cli_sentence_removal_file_option
            else:
                logger.warning(f"Sentence removal file provided via CLI not found: {self.cli_sentence_removal_file_option}. Proceeding without sentence removal.")
                self.error_messages.append(f"Warning: Sentence removal file '{self.cli_sentence_removal_file_option}' (CLI) not found. No sentence removal will be applied.")
                return None
        else:
            try:
                # Attempt to create ConfigManager instance specifically for this resolution
                cm = ConfigManager() # This might raise an exception
                default_sr_file_path = cm.get_default_sentence_removal_file()
                if default_sr_file_path:
                    if os.path.exists(default_sr_file_path):
                        logger.info(f"Using default sentence removal file from config: {default_sr_file_path}")
                        return default_sr_file_path
                    else:
                        logger.warning(f"Default sentence removal file configured at '{default_sr_file_path}' not found. Proceeding without sentence removal.")
                        self.error_messages.append(f"Warning: Default sentence removal file '{default_sr_file_path}' (config) not found. No sentence removal will be applied.")
                        return None
                else:
                    logger.info("No sentence removal file provided via CLI and no default configured. Proceeding without sentence removal.")
                    return None
            except Exception as e:
                logger.warning(f"Failed to get default sentence removal file from ConfigManager: {e}. Proceeding without sentence removal.")
                self.error_messages.append(f"Warning: Error accessing config for sentence removal file: {e}. No sentence removal will be applied.")
                return None

    def get_orchestrator_kwargs(self) -> Dict[str, Any]:
        """Prepares and returns arguments for the orchestrator."""
        return {
            "story_url": self.story_url,
            "workspace_root": self.workspace_root,
            "ebook_title_override": self.ebook_title_override,
            "keep_temp_files": self.keep_temp_files,
            "force_reprocessing": self.force_reprocessing,
            "sentence_removal_file": self.sentence_removal_file,
            "no_sentence_removal": self.no_sentence_removal, # Pass through the direct flag
            "chapters_per_volume": self.chapters_per_volume,
            "epub_contents": self.epub_contents,
            # progress_callback is handled by the handler
        }

    def is_valid(self) -> bool:
        """
        Basic validation. For archive_story, most inputs are either optional
        or direct passthroughs. Workspace and sentence file resolution have fallbacks.
        This method can be expanded if more critical validations are needed
        that would prevent the command from running.
        """
        # Example: if story_url was missing, that would be invalid.
        if not self.story_url:
            self.error_messages.append("Error: Story URL is required.")
            return False
        # Currently, workspace_root always resolves to a value (even default).
        # Sentence_removal_file also resolves or becomes None.
        # So, basic validity holds. Add more checks if preconditions for orchestrator aren't met.
        return True

from webnovel_archiver.core.cloud_sync import GDriveSync, BaseSyncService
# Removed import of WORKSPACE_ARCHIVAL_STATUS_DIR and WORKSPACE_EBOOKS_DIR from progress_manager
# They will be replaced by PathManager constants.


class CloudBackupContext:
    """
    Handles validation, configuration management, and argument preparation
    for the cloud-backup command.
    """
    def __init__(
        self,
        story_id_option: Optional[str],
        cloud_service_name: str,
        force_full_upload: bool,
        gdrive_credentials_path: str,
        gdrive_token_path: str
    ):
        self.story_id_option: Optional[str] = story_id_option
        self.cloud_service_name: str = cloud_service_name
        self.force_full_upload: bool = force_full_upload
        self.gdrive_credentials_path: str = gdrive_credentials_path
        self.gdrive_token_path: str = gdrive_token_path

        self.error_messages: list[str] = []
        self.warning_messages: list[str] = [] # Specific for non-critical issues

        self._config_manager: Optional[ConfigManager] = None
        self.workspace_root: str = self._resolve_workspace_root()

        self.archival_status_dir: str = os.path.join(self.workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME)
        self.ebooks_base_dir: str = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME)

        self.sync_service: Optional[BaseSyncService] = self._initialize_sync_service()

        self.story_index: Dict[str, str] = self._load_story_index()
        self.story_ids_to_process: list[str] = []
        if self.sync_service: # Only try to list stories if sync service is up, to avoid cascading errors
            self._prepare_story_ids_to_process()

        self.cloud_base_folder_id: Optional[str] = None
        self.base_backup_folder_name: str = "New Webnovel Archiver Backups"
        if self.sync_service: # Only attempt if sync service is available
            self._ensure_cloud_base_folder()

    def _load_story_index(self) -> Dict[str, str]:
        index_path = os.path.join(self.workspace_root, PathManager.INDEX_FILENAME)
        if not os.path.exists(index_path):
            self.error_messages.append(f"Error: Story index file not found at {index_path}. Cannot proceed.")
            return {}
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.error_messages.append(f"Error: Failed to load or parse story index file: {e}")
            return {}


    def _resolve_workspace_root(self) -> str:
        # Similar to ArchiveStoryContext, but cloud-backup doesn't have an output_dir option
        try:
            cm = ConfigManager()
            ws_path = cm.get_workspace_path()
            logger.info(f"Using workspace directory from config: {ws_path}")
            return ws_path
        except Exception as e:
            logger.error(f"Failed to initialize ConfigManager or get workspace path: {e}")
            # For cloud backup, a valid workspace is more critical than for archive-story
            # as it's the source of truth. We could error out here, or let validation handle it.
            self.error_messages.append(f"Error: Could not determine workspace path from config: {e}. Cannot proceed without a valid workspace.")
            # Return a default but expect is_valid() to fail if this happens and an error is added.
            # Or, we could raise an exception here. For now, let's use default and rely on is_valid().
            return DEFAULT_WORKSPACE_PATH


    def _initialize_sync_service(self) -> Optional[BaseSyncService]:
        if self.cloud_service_name.lower() == 'gdrive':
            try:
                if not os.path.exists(self.gdrive_credentials_path) and not os.path.exists(self.gdrive_token_path):
                    self.warning_messages.append(f"Warning: Google Drive credentials ('{self.gdrive_credentials_path}') or token ('{self.gdrive_token_path}') not found. Authentication may fail or require interaction.")

                service = GDriveSync(credentials_path=self.gdrive_credentials_path, token_path=self.gdrive_token_path)
                logger.debug("Google Drive sync service initialized.")
                
                return service
            except FileNotFoundError as e: # Should be caught by the check above, but good to be explicit
                self.error_messages.append(f"Error: GDrive credentials file '{self.gdrive_credentials_path}' not found. Please provide it or ensure it's in the default location.")
                logger.error(f"GDrive credentials file not found: {self.gdrive_credentials_path}")
                return None
            except ConnectionError as e: # GDriveSync might raise this on init if it tries to connect early
                self.error_messages.append(f"Error: Could not connect to Google Drive during initialization: {e}")
                logger.error(f"GDrive connection error on init: {e}")
                return None
            except Exception as e:
                self.error_messages.append(f"Error initializing Google Drive service: {e}")
                logger.error(f"GDrive initialization error: {e}", exc_info=True)
                return None
        else:
            self.error_messages.append(f"Error: Cloud service '{self.cloud_service_name}' is not supported.")
            return None

    def _prepare_story_ids_to_process(self) -> None:
        if not self.story_index:
            self.warning_messages.append("No stories found in the index to back up.")
            return

        if self.story_id_option:
            if self.story_id_option not in self.story_index:
                self.error_messages.append(f"Error: Story ID '{self.story_id_option}' not found in the story index.")
                return
            self.story_ids_to_process.append(self.story_id_option)
        else:
            self.story_ids_to_process = sorted(list(self.story_index.keys()))
            if not self.story_ids_to_process:
                self.warning_messages.append("No stories found in the index to back up.")
            else:
                logger.info(f"Found {len(self.story_ids_to_process)} stories in the index to potentially back up.")

    def _ensure_cloud_base_folder(self) -> None:
        if not self.sync_service:
            self.error_messages.append("Cannot ensure cloud base folder: sync service not available.")
            return

        try:
            logger.info(f"Ensuring base cloud backup folder '{self.base_backup_folder_name}' exists...")
            folder_id = self.sync_service.create_folder_if_not_exists(self.base_backup_folder_name, parent_folder_id=None)
            if not folder_id:
                self.error_messages.append(f"Error: Failed to create or retrieve base cloud folder '{self.base_backup_folder_name}'.")
                logger.error(f"Failed to create/retrieve base cloud folder '{self.base_backup_folder_name}'.")
            else:
                self.cloud_base_folder_id = folder_id
                logger.info(f"Base cloud folder '{self.base_backup_folder_name}' ensured (ID: {self.cloud_base_folder_id}).")
        except ConnectionError as e:
            self.error_messages.append(f"Error: Connection error while creating base cloud folder '{self.base_backup_folder_name}': {e}.")
            logger.error(f"Connection error creating base cloud folder '{self.base_backup_folder_name}': {e}")
        except Exception as e:
            self.error_messages.append(f"Error: Unexpected error while creating base cloud folder '{self.base_backup_folder_name}': {e}.")
            logger.error(f"Unexpected error creating base cloud folder '{self.base_backup_folder_name}': {e}", exc_info=True)


    def is_workspace_valid(self) -> bool:
        """Checks if essential workspace directories exist."""
        valid = True
        if not os.path.isdir(self.workspace_root): # Check the root first
            self.error_messages.append(f"Error: Workspace root directory not found: {self.workspace_root}")
            valid = False
            # If root is invalid, sub-directories are also effectively invalid.
            # Avoid adding redundant messages for archival_status_dir and ebooks_base_dir if root is missing.
            return False

        if not os.path.isdir(self.archival_status_dir):
            self.error_messages.append(f"Error: Archival status directory not found: {self.archival_status_dir}")
            valid = False
        if not os.path.isdir(self.ebooks_base_dir):
            self.error_messages.append(f"Error: Ebooks directory not found: {self.ebooks_base_dir}")
            valid = False
        return valid

    def is_valid(self) -> bool:
        """Checks if the context is valid for proceeding with the backup operation."""
        # Run workspace validation first, as other things depend on it.
        if not self.is_workspace_valid():
            # is_workspace_valid already added messages.
            return False # Early exit if workspace is bad.

        if self.sync_service is None:
            # _initialize_sync_service should have added an error message.
            if not any("Error initializing Google Drive service" in msg for msg in self.error_messages) and \
               not any("Cloud service" in msg for msg in self.error_messages) and \
               not any("GDrive credentials file" in msg for msg in self.error_messages) and \
               not any("Could not connect to Google Drive" in msg for msg in self.error_messages):
                self.error_messages.append("Error: Sync service could not be initialized (unknown reason).")
            return False

        if not self.cloud_base_folder_id:
            # _ensure_cloud_base_folder should have added an error message.
            if not any("base cloud folder" in msg for msg in self.error_messages):
                self.error_messages.append("Error: Cloud base folder ID could not be established.")
            return False

        # If story_id_option was given but resulted in an error (e.g. not found), _prepare_story_ids should have added to errors.
        # If no stories are found (when story_id_option is None), it's a warning, not an error for is_valid.
        # The handler can decide to exit cleanly if story_ids_to_process is empty.

        return not self.error_messages # Valid if no critical errors accumulated


import re

# ... (other imports like os, Optional, List, ConfigManager, DEFAULT_WORKSPACE_PATH, logger should be there)
# Ensure WORKSPACE_ARCHIVAL_STATUS_DIR and WORKSPACE_EBOOKS_DIR are available if used directly by name
# or ensure they are part of ConfigManager or another central place if accessed that way.
# For this example, assuming they are directly available or defined as constants.
# from webnovel_archiver.core.storage.progress_manager import WORKSPACE_ARCHIVAL_STATUS_DIR, WORKSPACE_EBOOKS_DIR


class MigrationContext:
    """
    Handles validation, configuration management, and argument preparation
    for the migrate command.
    """
    SUPPORTED_MIGRATION_TYPES = ['royalroad-legacy-id']

    def __init__(
        self,
        story_id_option: Optional[str],
        migration_type: str
    ):
        self.story_id_option: Optional[str] = story_id_option
        self.migration_type: str = migration_type.lower() # Normalize type

        self.error_messages: list[str] = []
        self.warning_messages: list[str] = []

        self._config_manager: Optional[ConfigManager] = None # If needed in future
        self.workspace_root: str = self._resolve_workspace_root()

        self.archival_status_base_dir: str = os.path.join(self.workspace_root, PathManager.ARCHIVAL_STATUS_DIR_NAME)
        self.ebooks_base_dir: str = os.path.join(self.workspace_root, PathManager.EBOOKS_DIR_NAME)
        # Add other relevant base directories if they participate in migration
        # self.raw_content_base_dir = os.path.join(self.workspace_root, "raw_content") # Example
        # self.processed_content_base_dir = os.path.join(self.workspace_root, "processed_content") # Example


        self.legacy_story_ids_to_process: list[str] = []
        if self._validate_migration_type() and self._validate_workspace_readiness():
            self._prepare_legacy_story_ids_to_process()

    def _resolve_workspace_root(self) -> str:
        try:
            cm = ConfigManager()
            ws_path = cm.get_workspace_path()
            logger.info(f"Using workspace directory from config: {ws_path}")
            return ws_path
        except Exception as e:
            logger.error(f"MigrationContext: Failed to initialize ConfigManager or get workspace path: {e}")
            self.error_messages.append(f"Error: Could not determine workspace path from config: {e}. Migration cannot proceed.")
            return DEFAULT_WORKSPACE_PATH # Return default, but is_valid() should fail

    def _validate_migration_type(self) -> bool:
        if self.migration_type not in self.SUPPORTED_MIGRATION_TYPES:
            self.error_messages.append(
                f"Error: Migration type '{self.migration_type}' is not supported. "
                f"Currently, only '{', '.join(self.SUPPORTED_MIGRATION_TYPES)}' is available."
            )
            logger.error(f"Unsupported migration type requested: {self.migration_type}")
            return False
        return True

    def _validate_workspace_readiness(self) -> bool:
        """Checks if the primary directory for migration exists."""
        if not os.path.isdir(self.workspace_root): # Check root first
             self.error_messages.append(f"Error: Workspace root directory not found: {self.workspace_root}")
             return False
        if not os.path.isdir(self.archival_status_base_dir):
            # This is a critical directory for finding stories to migrate.
            # It might be acceptable for it not to exist if we are migrating *to* this structure,
            # but for 'royalroad-legacy-id', we expect it to contain the legacy IDs.
            self.error_messages.append(f"Error: Archival status directory not found: {self.archival_status_base_dir}. Nothing to migrate.")
            logger.error(f"Archival status directory {self.archival_status_base_dir} not found for migration.")
            return False
        # ebooks_base_dir might not exist if no ebooks were ever created, which could be fine.
        # The handler can check for individual story's ebook dirs.
        # For now, only archival_status_base_dir is critical for finding stories.
        return True


    def _prepare_legacy_story_ids_to_process(self) -> None:
        if self.migration_type == 'royalroad-legacy-id':
            if self.story_id_option:
                # Check if the provided story_id looks like a legacy one
                if not re.match(r"^\d+-[\w-]+$", self.story_id_option):
                    self.warning_messages.append(
                        f"Provided story ID '{self.story_id_option}' does not match the expected "
                        "legacy RoyalRoad format (e.g., '12345-some-title'). Skipping this ID."
                    )
                    logger.warning(f"Skipping migration for explicitly provided ID '{self.story_id_option}' as it doesn't match legacy format.")
                    return # Don't add it to list

                # Also check if it actually exists as a directory
                if not os.path.isdir(os.path.join(self.archival_status_base_dir, self.story_id_option)):
                    self.error_messages.append(f"Error: Specified legacy story ID directory '{self.story_id_option}' not found in {self.archival_status_base_dir}.")
                    return

                self.legacy_story_ids_to_process.append(self.story_id_option)
            else: # Scan all directories
                try:
                    for item_name in os.listdir(self.archival_status_base_dir):
                        item_path = os.path.join(self.archival_status_base_dir, item_name)
                        if os.path.isdir(item_path):
                            if re.match(r"^\d+-[\w-]+$", item_name):
                                self.legacy_story_ids_to_process.append(item_name)

                    if not self.legacy_story_ids_to_process:
                        self.warning_messages.append("No legacy RoyalRoad stories found to migrate during scan.")
                        logger.info("No legacy RoyalRoad story IDs found matching pattern during scan.")
                except OSError as e:
                    self.error_messages.append(f"Error listing stories in {self.archival_status_base_dir}: {e}")
                    logger.error(f"OSError while listing legacy stories in {self.archival_status_base_dir}: {e}")
        else:
            # Should be caught by _validate_migration_type, but defensive
            self.error_messages.append(f"Logic error: _prepare_legacy_story_ids called for unhandled type '{self.migration_type}'")


    def get_new_story_id(self, legacy_id: str) -> Optional[str]:
        if self.migration_type == 'royalroad-legacy-id':
            numerical_id_match = re.match(r"^(\d+)-", legacy_id)
            if not numerical_id_match:
                self.warning_messages.append(f"Warning: Could not extract numerical ID from '{legacy_id}' during new ID generation.")
                logger.warning(f"Could not extract numerical ID from legacy ID '{legacy_id}' for new ID.")
                return None
            numerical_id = numerical_id_match.group(1)
            return f"royalroad-{numerical_id}"
        return None

    def get_paths_to_migrate(self, legacy_id: str, new_story_id: str) -> list[tuple[str, str]]:
        """Returns a list of (old_path, new_path) tuples for a given story."""
        # Define paths for various directories that follow the <base_dir>/<story_id> pattern
        # Ensure these base directories are properties of the context if they vary or need checks
        paths = [
            (os.path.join(self.archival_status_base_dir, legacy_id), os.path.join(self.archival_status_base_dir, new_story_id)),
            (os.path.join(self.ebooks_base_dir, legacy_id), os.path.join(self.ebooks_base_dir, new_story_id)),
            # Example for other potential dirs:
            # (os.path.join(self.workspace_root, "raw_content", legacy_id), os.path.join(self.workspace_root, "raw_content", new_story_id)),
            # (os.path.join(self.workspace_root, "processed_content", legacy_id), os.path.join(self.workspace_root, "processed_content", new_story_id)),
        ]
        return paths

    def is_valid(self) -> bool:
        """Checks if the context is valid for proceeding with migration."""
        # Errors from _validate_migration_type, _validate_workspace_readiness,
        # or _prepare_legacy_story_ids_to_process (like OSError) would be in self.error_messages.
        if self.error_messages: # If any critical error was logged during init
            return False

        # If a specific story_id was provided but it led to an error (e.g. not found, not matching pattern)
        # and that error was added to self.error_messages by _prepare_legacy_story_ids_to_process,
        # then this will correctly return False.
        # If no stories are found (when story_id_option is None), it's a warning, not an error for is_valid.
        # The handler can decide to exit cleanly if legacy_story_ids_to_process is empty.
        return True
