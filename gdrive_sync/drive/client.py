"""
Google Drive API v3 client wrapper with resumable uploads, chunked downloads,
folder tree discovery, and delta changes polling.
"""

from __future__ import annotations
import io
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


class GoogleDriveClient:
    """High-level client for Google Drive API operations."""

    FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

    def __init__(self, credentials: Optional[Credentials] = None):
        self.credentials = credentials
        self._service = None
        if credentials:
            self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            raise RuntimeError("GoogleDriveClient is not authenticated. Please log in first.")
        return self._service

    def get_about(self) -> Dict[str, Any]:
        """Returns user info and storage quota."""
        res = self.service.about().get(
            fields="user(displayName,emailAddress,photoLink),storageQuota(limit,usage,usageInDrive)"
        ).execute()
        return res

    # -------------------------------------------------------------------------
    # Selective Sync / Folder Tree Discovery
    # -------------------------------------------------------------------------

    def list_all_folders(self) -> List[Dict[str, Any]]:
        """
        Retrieves all folders in the drive to construct the folder hierarchy.
        Returns a list of dicts: [{'id': ..., 'name': ..., 'parents': [...]}]
        """
        folders = []
        page_token = None
        q = f"mimeType = '{self.FOLDER_MIME_TYPE}' and trashed = false"

        while True:
            response = self.service.files().list(
                q=q,
                spaces="drive",
                fields="nextPageToken, files(id, name, parents, modifiedTime)",
                pageToken=page_token,
                pageSize=1000,
            ).execute()

            folders.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return folders

    def build_folder_paths(self, folders: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Given a list of folder objects, calculates relative paths from root.
        Returns a mapping of {folder_id: "relative/path"}.
        """
        id_to_folder = {f["id"]: f for f in folders}
        cache_paths: Dict[str, str] = {}

        def get_path(fid: str) -> str:
            if fid in cache_paths:
                return cache_paths[fid]
            if fid not in id_to_folder:
                return ""
            f = id_to_folder[fid]
            parents = f.get("parents", [])
            name = f.get("name", "Unknown")
            if not parents or parents[0] == "root":
                cache_paths[fid] = name
                return name
            parent_path = get_path(parents[0])
            full = f"{parent_path}/{name}" if parent_path else name
            cache_paths[fid] = full
            return full

        for f in folders:
            get_path(f["id"])

        return cache_paths

    # -------------------------------------------------------------------------
    # Changes / Delta Polling
    # -------------------------------------------------------------------------

    def get_start_page_token(self) -> str:
        """Retrieves a startPageToken to track future changes."""
        response = self.service.changes().getStartPageToken().execute()
        return response.get("startPageToken")

    def list_changes(self, page_token: str) -> Tuple[List[Dict[str, Any]], str]:
        """
        Fetches all changes since the given page_token.
        Returns (changes_list, new_page_token).
        """
        changes = []
        current_token = page_token

        while True:
            response = self.service.changes().list(
                pageToken=current_token,
                spaces="drive",
                fields="nextPageToken, newStartPageToken, changes(fileId, removed, file(id, name, mimeType, trashed, parents, md5Checksum, size, modifiedTime))",
                pageSize=1000,
            ).execute()

            changes.extend(response.get("changes", []))
            if "nextPageToken" in response:
                current_token = response["nextPageToken"]
            else:
                new_token = response.get("newStartPageToken", current_token)
                return changes, new_token

    # -------------------------------------------------------------------------
    # File Operations (Upload / Download / Delete)
    # -------------------------------------------------------------------------

    def create_folder(self, name: str, parent_id: str = "root") -> str:
        """Creates a remote folder and returns its fileId."""
        meta = {
            "name": name,
            "mimeType": self.FOLDER_MIME_TYPE,
            "parents": [parent_id],
        }
        res = self.service.files().create(body=meta, fields="id").execute()
        return res["id"]

    def upload_file(
        self,
        local_path: Path | str,
        parent_id: Optional[str] = "root",
        existing_file_id: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Uploads or updates a file using resumable media upload.
        """
        p = Path(local_path)
        mime_type, _ = mimetypes.guess_type(str(p))
        if mime_type is None:
            mime_type = "application/octet-stream"

        media = MediaFileUpload(str(p), mimetype=mime_type, resumable=True)

        if existing_file_id:
            # Update existing file content & timestamp
            request = self.service.files().update(
                fileId=existing_file_id,
                media_body=media,
                fields="id, name, mimeType, md5Checksum, size, modifiedTime",
            )
        else:
            # Create new file
            body = {
                "name": p.name,
                "parents": [parent_id or "root"],
            }
            request = self.service.files().create(
                body=body,
                media_body=media,
                fields="id, name, mimeType, md5Checksum, size, modifiedTime",
            )

        response = None
        total_size = p.stat().st_size
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(int(status.progress() * total_size), total_size)

        if progress_callback:
            progress_callback(total_size, total_size)

        return response

    def download_file(
        self,
        drive_id: str,
        dest_local_path: Path | str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Downloads a file using chunked streaming into a temporary file,
        then atomically moves it into destination to avoid corruptions.
        """
        dest = Path(dest_local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_dest = dest.with_suffix(dest.suffix + ".sync_tmp")

        request = self.service.files().get_media(fileId=drive_id)

        with open(tmp_dest, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status and progress_callback:
                    progress_callback(int(status.resumable_progress), int(status.total_size))

        # Atomically replace destination
        if dest.exists():
            dest.unlink()
        shutil.move(str(tmp_dest), str(dest))
        return dest

    def trash_file(self, drive_id: str) -> None:
        """Sends a file or folder to the trash in Google Drive."""
        self.service.files().update(fileId=drive_id, body={"trashed": True}).execute()

    def get_file_metadata(self, drive_id: str) -> Dict[str, Any]:
        """Gets metadata for a specific file or folder."""
        return self.service.files().get(
            fileId=drive_id,
            fields="id, name, mimeType, trashed, parents, md5Checksum, size, modifiedTime",
        ).execute()
