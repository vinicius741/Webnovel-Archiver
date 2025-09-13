from typing import Dict, Any
from webnovel_archiver.utils.logger import get_logger
from .progress_manager import _get_new_progress_structure

logger = get_logger(__name__)

def get_cloud_backup_status(progress_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves the cloud backup status data from progress_data.
    Initializes with default structure if not present or incomplete.
    """
    default_backup_status = _get_new_progress_structure("dummy")["cloud_backup_status"]

    current_backup_status = progress_data.get("cloud_backup_status")
    if not isinstance(current_backup_status, dict):
        progress_data["cloud_backup_status"] = default_backup_status
        return default_backup_status

    # Ensure all keys from default structure are present
    updated = False
    for key, default_value in default_backup_status.items():
        if key not in current_backup_status:
            current_backup_status[key] = default_value
            updated = True

    # if updated: # No, this function should not modify progress_data directly unless it's the one loading it.
    #    logger.info("Initialized missing keys in cloud_backup_status.")

    return current_backup_status

def update_cloud_backup_status(progress_data: Dict[str, Any], backup_info: Dict[str, Any]) -> None:
    """
    Updates the cloud backup status in progress_data.
    `backup_info` should be a dictionary matching the structure defined
    for `cloud_backup_status`.
    """
    # Ensure the cloud_backup_status key exists and is a dict.
    if "cloud_backup_status" not in progress_data or not isinstance(progress_data["cloud_backup_status"], dict):
        progress_data["cloud_backup_status"] = _get_new_progress_structure("dummy")["cloud_backup_status"]

    progress_data["cloud_backup_status"].update(backup_info)
    logger.debug(f"Cloud backup status updated for story {progress_data.get('story_id', 'N/A')}")
