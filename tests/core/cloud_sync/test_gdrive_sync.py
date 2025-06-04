import os
import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import datetime
import builtins # Required for mocking 'open'

# Import GDriveSync from the correct location
from webnovel_archiver.core.cloud_sync.gdrive_sync import GDriveSync, SCOPES

# It's good practice to define these at the top if they are constants in the tested module
# and you want to ensure your tests use the same ones.
# However, GDriveSync uses them as defaults in its __init__ if not provided.
# For testing, we'll often provide dummy paths directly to the constructor.

# --- Mock Google API client libraries ---
# Create mock objects for each Google library module
mock_google_oauth2_credentials = MagicMock()
mock_google_auth_transport_requests = MagicMock()
mock_google_auth_oauthlib_flow = MagicMock()
mock_googleapiclient_discovery = MagicMock()
mock_googleapiclient_errors = MagicMock()
mock_googleapiclient_http = MagicMock()

# These will allow us to access attributes like Credentials, Request, HttpError as if they were from the real modules
Credentials = mock_google_oauth2_credentials.Credentials
Request = mock_google_auth_transport_requests.Request
InstalledAppFlow = mock_google_auth_oauthlib_flow.InstalledAppFlow
build = mock_googleapiclient_discovery.build
HttpError = mock_googleapiclient_errors.HttpError # This should be the class/exception type itself
MediaFileUpload = mock_googleapiclient_http.MediaFileUpload

# Apply the patch to sys.modules. This decorator will handle starting and stopping the patch for the class.
@patch.dict('sys.modules', {
    'google.oauth2.credentials': mock_google_oauth2_credentials,
    'google.auth.transport.requests': mock_google_auth_transport_requests,
    'google_auth_oauthlib.flow': mock_google_auth_oauthlib_flow,
    'googleapiclient.discovery': mock_googleapiclient_discovery,
    'googleapiclient.errors': mock_googleapiclient_errors,
    'googleapiclient.http': mock_googleapiclient_http,
})
class TestGDriveSync(unittest.TestCase):

    def setUp(self):
        # Reset all mocks that might have been called or had return_values set
        mock_google_oauth2_credentials.reset_mock()
        mock_google_auth_transport_requests.reset_mock()
        mock_google_auth_oauthlib_flow.reset_mock()
        mock_googleapiclient_discovery.reset_mock()
        mock_googleapiclient_errors.reset_mock()
        mock_googleapiclient_http.reset_mock()

        # Specifically reset the attributes we use as classes/functions
        Credentials.reset_mock()
        Request.reset_mock()
        InstalledAppFlow.reset_mock()
        build.reset_mock()
        HttpError.reset_mock() # Reset the mock for the HttpError class
        MediaFileUpload.reset_mock()

        self.mock_service = MagicMock()
        build.return_value = self.mock_service

        self.mock_creds = MagicMock()
        self.mock_creds.valid = True
        self.mock_creds.expired = False
        self.mock_creds.refresh_token = 'dummy_refresh_token'
        self.mock_creds.to_json.return_value = '{"token_data": "dummy"}'

        Credentials.from_authorized_user_file.return_value = self.mock_creds

        self.mock_flow_instance = MagicMock()
        self.mock_flow_instance.run_local_server.return_value = self.mock_creds
        InstalledAppFlow.from_client_secrets_file.return_value = self.mock_flow_instance

        self.token_path = 'dummy_token.json'
        self.credentials_path = 'dummy_credentials.json'

    @patch('os.path.exists')
    def test_authenticate_token_exists_and_valid(self, mock_os_path_exists):
        mock_os_path_exists.return_value = True # token.json exists

        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)

        Credentials.from_authorized_user_file.assert_called_once_with(self.token_path, SCOPES)
        self.mock_creds.refresh.assert_not_called()
        InstalledAppFlow.from_client_secrets_file.assert_not_called()
        build.assert_called_once_with('drive', 'v3', credentials=self.mock_creds)
        self.assertIsNotNone(gdrive_sync.service)

    @patch('os.path.exists')
    @patch('os.remove') # To check if os.remove is called on refresh failure
    @patch('builtins.open', new_callable=mock_open)
    def test_authenticate_token_expired_refresh_success(self, mock_file_open, mock_os_remove, mock_os_path_exists):
        mock_os_path_exists.return_value = True
        self.mock_creds.valid = False
        self.mock_creds.expired = True
        self.mock_creds.refresh.return_value = None # Simulate successful refresh

        GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)

        Credentials.from_authorized_user_file.assert_called_once_with(self.token_path, SCOPES)
        self.mock_creds.refresh.assert_called_once_with(Request())
        mock_file_open.assert_called_once_with(self.token_path, 'w') # Token saved after refresh
        mock_file_open().write.assert_called_once_with(self.mock_creds.to_json())
        mock_os_remove.assert_not_called() # os.remove should not be called on successful refresh
        build.assert_called_once_with('drive', 'v3', credentials=self.mock_creds)

    @patch('os.path.exists')
    @patch('os.remove')
    @patch('builtins.open', new_callable=mock_open)
    def test_authenticate_token_expired_refresh_fail_then_new_flow(self, mock_file_open, mock_os_remove, mock_os_path_exists):
        mock_os_path_exists.side_effect = [True, True] # token.json exists, then credentials.json exists

        expired_creds_instance = MagicMock()
        expired_creds_instance.valid = False
        expired_creds_instance.expired = True
        expired_creds_instance.refresh_token = 'a_refresh_token'
        expired_creds_instance.refresh.side_effect = Exception("Simulated refresh failure") # Refresh fails
        Credentials.from_authorized_user_file.return_value = expired_creds_instance

        new_creds_from_flow = MagicMock() # Different instance for new creds
        new_creds_from_flow.to_json.return_value = '{"new_token_data": "fresh"}'
        self.mock_flow_instance.run_local_server.return_value = new_creds_from_flow # Flow provides new creds

        GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)

        Credentials.from_authorized_user_file.assert_called_once_with(self.token_path, SCOPES)
        expired_creds_instance.refresh.assert_called_once_with(Request())
        mock_os_remove.assert_called_once_with(self.token_path) # Old token removed

        InstalledAppFlow.from_client_secrets_file.assert_called_once_with(self.credentials_path, SCOPES)
        self.mock_flow_instance.run_local_server.assert_called_once_with(port=0)

        # Check that open was called to write the new token
        mock_file_open.assert_called_once_with(self.token_path, 'w')
        mock_file_open().write.assert_called_once_with('{"new_token_data": "fresh"}')

        build.assert_called_once_with('drive', 'v3', credentials=new_creds_from_flow)


    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_authenticate_no_token_new_flow_success(self, mock_file_open, mock_os_path_exists):
        mock_os_path_exists.side_effect = [False, True] # token.json no, credentials.json yes

        # self.mock_creds is returned by self.mock_flow_instance.run_local_server
        GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)

        Credentials.from_authorized_user_file.assert_not_called()
        InstalledAppFlow.from_client_secrets_file.assert_called_once_with(self.credentials_path, SCOPES)
        self.mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        mock_file_open.assert_called_once_with(self.token_path, 'w')
        mock_file_open().write.assert_called_once_with(self.mock_creds.to_json())
        build.assert_called_once_with('drive', 'v3', credentials=self.mock_creds)

    @patch('os.path.exists', side_effect=[False, False]) # token & credentials.json not found
    def test_authenticate_no_token_no_credentials_file_raises_error(self, mock_os_path_exists):
        with self.assertRaises(FileNotFoundError) as context:
            GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        self.assertIn(self.credentials_path, str(context.exception))

    def test_create_folder_if_not_exists_already_exists(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        self.mock_service.files().list().execute.return_value = {'files': [{'id': 'existing_folder_id', 'name': 'MyFolder'}]}

        folder_id = gdrive_sync.create_folder_if_not_exists('MyFolder', parent_folder_id='parent_id')

        self.mock_service.files().list.assert_called_once_with(
            q="mimeType='application/vnd.google-apps.folder' and name='MyFolder' and trashed=false and 'parent_id' in parents",
            spaces='drive',
            fields='files(id, name)'
        )
        self.mock_service.files().create.assert_not_called()
        self.assertEqual(folder_id, 'existing_folder_id')

    def test_create_folder_if_not_exists_creates_new(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        self.mock_service.files().list().execute.return_value = {'files': []}
        self.mock_service.files().create().execute.return_value = {'id': 'new_folder_id'}

        folder_id = gdrive_sync.create_folder_if_not_exists('NewFolder', parent_folder_id='parent_id')

        expected_metadata = {'name': 'NewFolder', 'mimeType': 'application/vnd.google-apps.folder', 'parents': ['parent_id']}
        self.mock_service.files().create.assert_called_once_with(body=expected_metadata, fields='id')
        self.assertEqual(folder_id, 'new_folder_id')

    @patch('os.path.exists', return_value=True)
    def test_upload_file_new_file(self, mock_os_path_exists):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        self.mock_service.files().list().execute.return_value = {'files': []}

        mock_uploaded_file_meta = {'id': 'new_file_id', 'name': 'test_file.txt', 'modifiedTime': 'some_iso_time'}
        self.mock_service.files().create().execute.return_value = mock_uploaded_file_meta

        mock_media_instance = MagicMock()
        MediaFileUpload.return_value = mock_media_instance

        result = gdrive_sync.upload_file('local/test_file.txt', 'remote_folder_id')

        MediaFileUpload.assert_called_once_with('local/test_file.txt', resumable=True)
        expected_metadata = {'name': 'test_file.txt', 'parents': ['remote_folder_id']}
        self.mock_service.files().create.assert_called_once_with(
            body=expected_metadata, media_body=mock_media_instance, fields='id, name, webViewLink, modifiedTime'
        )
        self.assertEqual(result, mock_uploaded_file_meta)

    @patch('os.path.exists', return_value=True)
    def test_upload_file_update_existing(self, mock_os_path_exists):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        # Simulate _get_file_id finding an existing file
        self.mock_service.files().list().execute.return_value = {'files': [{'id': 'existing_file_id', 'name': 'test_file.txt'}]}

        mock_updated_file_meta = {'id': 'existing_file_id', 'name': 'test_file.txt', 'modifiedTime': 'new_iso_time'}
        self.mock_service.files().update().execute.return_value = mock_updated_file_meta

        mock_media_instance = MagicMock()
        MediaFileUpload.return_value = mock_media_instance

        # Note: The method name in the original code is `upload_file`, not `upload__file`
        result = gdrive_sync.upload_file('local/test_file.txt', 'remote_folder_id')

        MediaFileUpload.assert_called_once_with('local/test_file.txt', resumable=True)
        expected_metadata = {'name': 'test_file.txt', 'parents': ['remote_folder_id']}
        self.mock_service.files().update.assert_called_once_with(
            fileId='existing_file_id', body=expected_metadata, media_body=mock_media_instance, fields='id, name, webViewLink, modifiedTime'
        )
        self.assertEqual(result, mock_updated_file_meta)

    @patch('os.path.exists', return_value=True)
    def test_upload_file_update_existing_removes_parents_from_metadata(self, mock_os_path_exists):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)

        # Simulate _get_file_id finding an existing file
        # This mock ensures that the 'existing_file_id' path is taken in upload_file
        self.mock_service.files().list().execute.return_value = {'files': [{'id': 'existing_file_id', 'name': 'test_file.txt'}]}

        mock_updated_file_meta = {'id': 'existing_file_id', 'name': 'test_file.txt', 'modifiedTime': 'new_iso_time'}
        self.mock_service.files().update().execute.return_value = mock_updated_file_meta

        mock_media_instance = MagicMock()
        MediaFileUpload.return_value = mock_media_instance

        local_path = 'local/test_file.txt'
        remote_folder_id = 'remote_folder_id_123'

        result = gdrive_sync.upload_file(local_path, remote_folder_id)

        # Check that MediaFileUpload was called correctly
        MediaFileUpload.assert_called_once_with(local_path, resumable=True)

        # Assert that update was called
        self.mock_service.files().update.assert_called_once()

        # Get the arguments passed to update
        # call_args is a tuple (args, kwargs) or None if not called
        _, update_kwargs = self.mock_service.files().update.call_args

        # Check fileId
        self.assertEqual(update_kwargs.get('fileId'), 'existing_file_id')

        # Check media_body
        self.assertEqual(update_kwargs.get('media_body'), mock_media_instance)

        # Crucially, check the 'body' (file_metadata) for the absence of 'parents'
        metadata_body = update_kwargs.get('body')
        self.assertIsNotNone(metadata_body)
        self.assertNotIn('parents', metadata_body, "The 'parents' key should have been removed from metadata for an update.")
        self.assertEqual(metadata_body.get('name'), 'test_file.txt') # Ensure other metadata like name is still there

        # Check fields
        self.assertEqual(update_kwargs.get('fields'), 'id, name, webViewLink, modifiedTime')

        # Check the result of the upload_file call
        self.assertEqual(result, mock_updated_file_meta)

        # Ensure create() was not called
        self.mock_service.files().create.assert_not_called()

    @patch('os.path.exists', return_value=False)
    def test_upload_file_local_file_not_found_raises_error(self, mock_os_path_exists):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        with self.assertRaises(FileNotFoundError):
            gdrive_sync.upload_file('non_existent.txt', 'remote_folder_id')

    def test_get_file_metadata_by_id(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        mock_meta = {'id': 'file123', 'name': 'file.txt', 'modifiedTime': 'time_str'}
        self.mock_service.files().get().execute.return_value = mock_meta

        result = gdrive_sync.get_file_metadata(file_id='file123')
        self.mock_service.files().get.assert_called_once_with(fileId='file123', fields='id, name, modifiedTime, webViewLink, size')
        self.assertEqual(result, mock_meta)

    def test_get_file_metadata_by_name_and_folder(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        self.mock_service.files().list().execute.return_value = {'files': [{'id': 'file_abc'}]}
        mock_meta = {'id': 'file_abc', 'name': 'target.txt', 'modifiedTime': 'time_str_2'}
        self.mock_service.files().get().execute.return_value = mock_meta

        result = gdrive_sync.get_file_metadata(file_name='target.txt', folder_id='folder_xyz')

        self.mock_service.files().list.assert_called_once_with(
            q="name='target.txt' and 'folder_xyz' in parents and trashed=false", spaces='drive', fields='files(id, name)'
        )
        self.mock_service.files().get.assert_called_once_with(fileId='file_abc', fields='id, name, modifiedTime, webViewLink, size')
        self.assertEqual(result, mock_meta)

    def test_get_file_metadata_not_found_returns_none(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        mock_resp = MagicMock()
        mock_resp.status = 404 # Set the status attribute on the mock response object

        # HttpError instance needs 'resp' and 'content'
        # The HttpError class mock itself needs to be a callable that returns an HttpError instance
        # or the side_effect should be an instance of HttpError.
        http_error_instance = HttpError(resp=mock_resp, content=b'Not Found')
        self.mock_service.files().get().execute.side_effect = http_error_instance

        result = gdrive_sync.get_file_metadata(file_id='non_existent_id')
        self.assertIsNone(result)

    def test_list_files_in_folder(self):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        page1 = {'files': [{'id': 'f1', 'name': '1.txt'}], 'nextPageToken': 'p2'}
        page2 = {'files': [{'id': 'f2', 'name': '2.txt'}]}
        self.mock_service.files().list().execute.side_effect = [page1, page2]

        result = gdrive_sync.list_files_in_folder('folder123')

        calls = [
            call(q="'folder123' in parents and trashed=false", spaces='drive', fields='nextPageToken, files(id, name, modifiedTime, size)', pageToken=None),
            call(q="'folder123' in parents and trashed=false", spaces='drive', fields='nextPageToken, files(id, name, modifiedTime, size)', pageToken='p2')
        ]
        self.mock_service.files().list().assert_has_calls(calls)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '1.txt')

    @patch('os.path.getmtime')
    @patch('os.path.exists', return_value=True)
    def test_is_remote_older(self, mock_os_exists, mock_os_getmtime):
        gdrive_sync = GDriveSync(token_path=self.token_path, credentials_path=self.credentials_path)
        dt_newer = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        dt_older = datetime.datetime(2023, 1, 1, 9, 0, 0, tzinfo=datetime.timezone.utc)

        mock_os_getmtime.return_value = dt_newer.timestamp()
        self.assertTrue(gdrive_sync.is_remote_older('file.txt', "2023-01-01T10:00:00.000Z"))

        mock_os_getmtime.return_value = dt_older.timestamp()
        self.assertFalse(gdrive_sync.is_remote_older('file.txt', "2023-01-01T10:00:00.000Z"))

        mock_os_getmtime.return_value = dt_newer.timestamp() # local is 12:00 UTC
        # Remote is also 12:00 UTC, so remote is NOT older
        self.assertFalse(gdrive_sync.is_remote_older('file.txt', "2023-01-01T12:00:00.000Z"))

        # Test invalid remote time string
        self.assertTrue(gdrive_sync.is_remote_older('file.txt', "invalid-time-string"))

if __name__ == '__main__':
    unittest.main()
