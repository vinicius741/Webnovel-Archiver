import abc
from typing import Optional

class BaseSyncService(abc.ABC):
    """Abstract base class for cloud synchronization services."""

    @abc.abstractmethod
    def authenticate(self) -> None:
        """Authenticates the service with the cloud provider."""
        pass

    @abc.abstractmethod
    def upload_file(self, local_file_path: str, remote_folder_id: str, remote_file_name: Optional[str] = None) -> dict:
        """
        Uploads a single file to the specified remote folder.

        Args:
            local_file_path: Path to the local file to upload.
            remote_folder_id: Identifier of the remote folder to upload to.
            remote_file_name: Optional name for the file in the remote storage.
                              If None, uses the local file name.

        Returns:
            A dictionary containing metadata of the uploaded file (e.g., file ID, name).
        """
        pass

    @abc.abstractmethod
    def create_folder_if_not_exists(self, folder_name: str, parent_folder_id: Optional[str] = None) -> str:
        """
        Creates a folder in the cloud storage if it doesn't already exist.

        Args:
            folder_name: The name of the folder to create.
            parent_folder_id: Optional identifier of the parent folder.
                              If None, creates the folder in the root.

        Returns:
            The ID of the created (or existing) folder.
        """
        pass

    @abc.abstractmethod
    def get_file_metadata(self, file_id: Optional[str] = None, file_name: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[dict]:
        """
        Retrieves metadata for a specific file.

        Must provide either file_id or both file_name and folder_id.

        Args:
            file_id: The unique ID of the file in the cloud storage.
            file_name: The name of the file.
            folder_id: The ID of the folder containing the file.

        Returns:
            A dictionary containing file metadata (e.g., id, name, modifiedTime)
            or None if the file is not found.
        """
        pass

    @abc.abstractmethod
    def list_files_in_folder(self, folder_id: str) -> list[dict]:
        """
        Lists all files in a given remote folder.

        Args:
            folder_id: The ID of the folder to list files from.

        Returns:
            A list of dictionaries, where each dictionary represents a file's metadata.
        """
        pass
