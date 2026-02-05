"""
Google Drive Service
Handles uploading salary images to Google Drive.
"""
import os
import json
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings


# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']


class GoogleDriveService:
    """Service for Google Drive operations."""

    def __init__(self):
        """Initialize Google Drive service."""
        self.service = None
        self.credentials = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the Google Drive API service."""
        creds_file = settings.google_credentials_file

        if not creds_file or not os.path.exists(creds_file):
            # Service not configured
            return

        try:
            # Try loading as service account credentials first
            self.credentials = ServiceAccountCredentials.from_service_account_file(
                creds_file,
                scopes=SCOPES
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
        except Exception:
            # Fall back to OAuth credentials
            self._initialize_oauth()

    def _initialize_oauth(self):
        """Initialize using OAuth credentials."""
        creds_file = settings.google_credentials_file
        token_file = os.path.join(os.path.dirname(creds_file), 'token.json')

        if os.path.exists(token_file):
            self.credentials = Credentials.from_authorized_user_file(token_file, SCOPES)

        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                self.credentials = flow.run_local_server(port=0)

            # Save credentials for future use
            with open(token_file, 'w') as token:
                token.write(self.credentials.to_json())

        self.service = build('drive', 'v3', credentials=self.credentials)

    def is_configured(self) -> bool:
        """Check if Google Drive service is properly configured."""
        return self.service is not None

    def upload_file(
        self,
        file_path: str,
        filename: str,
        folder_id: Optional[str] = None,
        create_date_folders: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a file to Google Drive.

        Args:
            file_path: Local path to the file
            filename: Name for the file in Drive
            folder_id: Parent folder ID (uses default if not specified)
            create_date_folders: Whether to create year/month subfolders

        Returns:
            Tuple of (file_id, web_view_link) or (None, None) on failure
        """
        if not self.is_configured():
            raise RuntimeError("Google Drive service not configured")

        # Use default folder if not specified
        if not folder_id:
            folder_id = settings.google_drive_folder_id

        # Create date-based folder structure if requested
        if create_date_folders and folder_id:
            folder_id = self._get_or_create_date_folder(folder_id)

        # Prepare file metadata
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        # Upload file
        media = MediaFileUpload(
            file_path,
            mimetype='image/png',
            resumable=True
        )

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        # Make file publicly viewable
        self.service.permissions().create(
            fileId=file.get('id'),
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        # Get direct download link
        file_id = file.get('id')
        direct_link = f"https://drive.google.com/uc?id={file_id}"

        return file_id, direct_link

    def _get_or_create_date_folder(self, parent_folder_id: str) -> str:
        """Get or create year/month folder structure."""
        now = datetime.now()
        year_str = str(now.year)
        month_str = f"{now.month:02d}"

        # Get or create year folder
        year_folder_id = self._get_or_create_folder(year_str, parent_folder_id)

        # Get or create month folder
        month_folder_id = self._get_or_create_folder(month_str, year_folder_id)

        return month_folder_id

    def _get_or_create_folder(self, folder_name: str, parent_id: str) -> str:
        """Get existing folder or create new one."""
        # Search for existing folder
        query = (
            f"name='{folder_name}' and "
            f"'{parent_id}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and "
            f"trashed=false"
        )

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])

        if files:
            return files[0]['id']

        # Create new folder
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }

        folder = self.service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()

        return folder.get('id')

    def delete_file(self, file_id: str) -> bool:
        """Delete a file from Google Drive."""
        if not self.is_configured():
            return False

        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception:
            return False

    def list_files(self, folder_id: Optional[str] = None, page_size: int = 100) -> list:
        """List files in a folder."""
        if not self.is_configured():
            return []

        query = "trashed=false"
        if folder_id:
            query = f"'{folder_id}' in parents and " + query

        results = self.service.files().list(
            q=query,
            pageSize=page_size,
            fields="files(id, name, mimeType, createdTime, webViewLink)"
        ).execute()

        return results.get('files', [])


# Singleton instance
gdrive_service = GoogleDriveService()
