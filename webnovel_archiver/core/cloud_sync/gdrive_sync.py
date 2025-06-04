import os
import datetime
from typing import Optional, Tuple

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .base_sync_service import BaseSyncService
from webnovel_archiver.utils.logger import get_logger

logger = get_logger(__name__)

# If modifying these SCOPES, delete token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']
# TODO: Make token path and credentials path configurable
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json' # Path to Google Cloud project OAuth 2.0 credentials

class GDriveSync(BaseSyncService):
    """Google Drive Synchronization Service."""

    def __init__(self, credentials_path: str = CREDENTIALS_PATH, token_path: str = TOKEN_PATH):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service: Optional[Resource] = None
        self.authenticate()

    def authenticate(self) -> None:
        """Authenticates with Google Drive API using OAuth 2.0."""
        creds = None
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load token from {self.token_path}: {e}. Need to re-authenticate.")
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Google API token refreshed.")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}. Need to re-authenticate.")
                    # Fallback to re-authentication by deleting potentially corrupt token
                    if os.path.exists(self.token_path):
                        os.remove(self.token_path)
                    creds = None # Force re-authentication
            else:
                if not os.path.exists(self.credentials_path):
                    logger.error(f"Credentials file not found at {self.credentials_path}. "
                                 f"Please download your OAuth 2.0 credentials from Google Cloud Console "
                                 f"and place it as '{self.credentials_path}'.")
                    # This is a critical error for authentication if no token exists
                    # Depending on CLI interaction model, might raise error or prompt user
                    raise FileNotFoundError(f"Credentials file {self.credentials_path} not found.")

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                    # TODO: This will block and require user interaction if run on a server.
                    # Consider alternative flows for non-interactive environments.
                    # For CLI, this is usually acceptable.
                    creds = flow.run_local_server(port=0)
                    logger.info("Google API authentication successful, token obtained.")
                except Exception as e:
                    logger.error(f"Failed to run InstalledAppFlow: {e}")
                    # Handle specific errors like FileNotFoundError for credentials_path more gracefully if needed
                    raise # Re-raise for now

            if creds:
                try:
                    with open(self.token_path, 'w') as token_file:
                        token_file.write(creds.to_json())
                    logger.info(f"Token saved to {self.token_path}")
                except IOError as e:
                    logger.error(f"Failed to save token to {self.token_path}: {e}")

        if not creds:
             # Should not happen if logic above is correct and exceptions are raised
            logger.error("Authentication failed: No valid credentials.")
            raise ConnectionError("Failed to authenticate with Google Drive.")

        try:
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive API service built successfully.")
        except Exception as e:
            logger.error(f"Failed to build Google Drive service: {e}")
            self.service = None # Ensure service is None if build fails
            raise ConnectionError(f"Failed to build Google Drive service: {e}")


    def _get_file_id(self, file_name: str, folder_id: str) -> Optional[str]:
        """Helper to get a file's ID by name within a specific folder."""
        if not self.service:
            logger.error("Drive service not initialized.")
            raise ConnectionError("Drive service not initialized during _get_file_id.")

        try:
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            response = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = response.get('files', [])
            if files:
                return files[0].get('id')
            return None
        except HttpError as error:
            logger.error(f"An API error occurred in _get_file_id: {error}")
            return None

    def upload_file(self, local_file_path: str, remote_folder_id: str, remote_file_name: Optional[str] = None) -> dict:
        """Uploads a file to the specified Google Drive folder."""
        if not self.service:
            logger.error("Drive service not initialized.")
            raise ConnectionError("Drive service not initialized during upload_file.")

        if not os.path.exists(local_file_path):
            logger.error(f"Local file {local_file_path} not found for upload.")
            raise FileNotFoundError(f"Local file {local_file_path} not found.")

        file_name = remote_file_name or os.path.basename(local_file_path)

        # Check if file already exists to update it
        existing_file_id = self._get_file_id(file_name, remote_folder_id)

        file_metadata = {
            'name': file_name,
            # 'parents': [remote_folder_id] # Set parent folder during create/update
        }
        if remote_folder_id: # Add parent only if it's not root (though for this app, it's always specified)
             file_metadata['parents'] = [remote_folder_id]

        media = MediaFileUpload(local_file_path, resumable=True)

        try:
            if existing_file_id:
                # File exists, update it
                logger.info(f"Updating existing file '{file_name}' (ID: {existing_file_id}) in Drive folder ID '{remote_folder_id}'.")
                # If updating an existing file, 'parents' should not be in the body.
                # The Drive API v3 update semantics state that a file's parents are not directly mutable with files.update.
                # Changes to parents must be done with addParents and removeParents parameters.
                # Since we are not changing the parent folder here, we remove 'parents' from metadata.
                if 'parents' in file_metadata:
                    del file_metadata['parents']
                updated_file = self.service.files().update(
                    fileId=existing_file_id,
                    body=file_metadata, # parents removed if present
                    media_body=media,
                    fields='id, name, webViewLink, modifiedTime'
                ).execute()
                logger.info(f"File '{updated_file.get('name')}' updated successfully. ID: {updated_file.get('id')}")
                return updated_file
            else:
                # File does not exist, create it
                logger.info(f"Uploading new file '{file_name}' to Drive folder ID '{remote_folder_id}'.")
                new_file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, webViewLink, modifiedTime'
                ).execute()
                logger.info(f"File '{new_file.get('name')}' uploaded successfully. ID: {new_file.get('id')}")
                return new_file
        except HttpError as error:
            logger.error(f"An API error occurred during file upload: {error}")
            # Consider more specific error handling or re-raising
            raise ConnectionError(f"Failed to upload file '{file_name}': {error}")


    def create_folder_if_not_exists(self, folder_name: str, parent_folder_id: Optional[str] = None) -> str:
        """Creates a folder on Google Drive if it doesn't exist, returns the folder ID."""
        if not self.service:
            logger.error("Drive service not initialized.")
            raise ConnectionError("Drive service not initialized during create_folder_if_not_exists.")

        # Check if folder already exists
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        else:
            # If no parent_folder_id, search in root.
            # For shared drives, you might need different logic or ensure parent_folder_id is always provided.
             query += " and 'root' in parents"


        try:
            response = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            folders = response.get('files', [])

            if folders:
                folder_id = folders[0].get('id')
                logger.info(f"Folder '{folder_name}' already exists with ID: {folder_id}.")
                return folder_id
            else:
                # Create the folder
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                if parent_folder_id:
                    file_metadata['parents'] = [parent_folder_id]

                logger.info(f"Creating folder '{folder_name}'" + (f" in parent ID '{parent_folder_id}'." if parent_folder_id else " in root."))
                folder = self.service.files().create(body=file_metadata, fields='id').execute()
                folder_id = folder.get('id')
                logger.info(f"Folder '{folder_name}' created successfully with ID: {folder_id}.")
                return folder_id
        except HttpError as error:
            logger.error(f"An API error occurred: {error}")
            raise ConnectionError(f"Failed to create or find folder '{folder_name}': {error}")

    def get_file_metadata(self, file_id: Optional[str] = None, file_name: Optional[str] = None, folder_id: Optional[str] = None) -> Optional[dict]:
        """Retrieves metadata for a file by ID or by name and folder ID."""
        if not self.service:
            logger.error("Drive service not initialized.")
            raise ConnectionError("Drive service not initialized during get_file_metadata.")

        if not file_id and not (file_name and folder_id):
            logger.error("Must provide either file_id or both file_name and folder_id to get_file_metadata.")
            raise ValueError("Invalid arguments: Provide file_id or (file_name and folder_id).")

        try:
            if file_id:
                logger.debug(f"Fetching metadata for file ID: {file_id}")
                file_meta = self.service.files().get(fileId=file_id, fields='id, name, modifiedTime, webViewLink, size').execute()
                return file_meta

            # If file_id not provided, use file_name and folder_id
            if file_name and folder_id:
                logger.debug(f"Fetching metadata for file name: '{file_name}' in folder ID: {folder_id}")
                # This reuses _get_file_id to find the file first, then fetches full metadata
                target_file_id = self._get_file_id(file_name, folder_id)
                if target_file_id:
                    file_meta = self.service.files().get(fileId=target_file_id, fields='id, name, modifiedTime, webViewLink, size').execute()
                    return file_meta
                else:
                    logger.info(f"File '{file_name}' not found in folder '{folder_id}'.")
                    return None
        except HttpError as error:
            if error.resp.status == 404:
                logger.info(f"File not found (file_id: {file_id}, file_name: {file_name}, folder_id: {folder_id}).")
                return None
            logger.error(f"An API error occurred while getting file metadata: {error}")
            # Consider re-raising for certain errors or returning None for others
            # For now, re-raise to indicate a problem beyond "not found"
            raise ConnectionError(f"API error fetching metadata: {error}")
        return None # Should be unreachable if logic is correct

    def list_files_in_folder(self, folder_id: str) -> list[dict]:
        """Lists all files in a given remote folder."""
        if not self.service:
            logger.error("Drive service not initialized.")
            raise ConnectionError("Drive service not initialized during list_files_in_folder.")

        files_list = []
        page_token = None
        try:
            while True:
                response = self.service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='nextPageToken, files(id, name, modifiedTime, size)',
                    pageToken=page_token
                ).execute()

                files_list.extend(response.get('files', []))
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
            logger.info(f"Found {len(files_list)} files in folder ID '{folder_id}'.")
            return files_list
        except HttpError as error:
            logger.error(f"An API error occurred while listing files in folder '{folder_id}': {error}")
            raise ConnectionError(f"API error listing files: {error}")

    # Helper to compare local and remote modification times
    def is_remote_older(self, local_file_path: str, remote_modified_time_str: str) -> bool:
        """
        Compares the local file's modification time with the remote file's modification time.
        Returns True if the remote file is older than the local file.
        """
        if not os.path.exists(local_file_path):
            # If local file doesn't exist, it can't be newer.
            # This case should ideally be handled before calling this.
            return False

        local_mtime_timestamp = os.path.getmtime(local_file_path)
        local_mtime_dt = datetime.datetime.fromtimestamp(local_mtime_timestamp, tz=datetime.timezone.utc)

        # Google Drive API returns modifiedTime in RFC 3339 format, e.g., "2023-08-21T10:00:00.000Z"
        # Need to parse this into a datetime object.
        # Ensure it's timezone-aware (UTC) for correct comparison.
        try:
            # Strip 'Z' and add '+00:00' for timezone offset if not already there
            if remote_modified_time_str.endswith('Z'):
                remote_modified_time_str = remote_modified_time_str[:-1] + '+00:00'

            remote_mtime_dt = datetime.datetime.fromisoformat(remote_modified_time_str)
            # Ensure remote time is UTC if no timezone info was parsed (though Drive API usually provides it)
            if remote_mtime_dt.tzinfo is None:
                remote_mtime_dt = remote_mtime_dt.replace(tzinfo=datetime.timezone.utc)

        except ValueError as e:
            logger.error(f"Error parsing remote modified time '{remote_modified_time_str}': {e}")
            # If remote time is unparseable, assume we need to upload (or handle as error)
            return True

        return local_mtime_dt > remote_mtime_dt
