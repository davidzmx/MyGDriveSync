"""
Secure cross-platform storage for OAuth 2.0 credentials.
Uses system Keyring (KWallet/Windows Credential Manager) with fallback to 0600 token.json.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
import keyring

from ..config import get_app_dir

KEYRING_SERVICE_NAME = "gdrive-sync"
KEYRING_USERNAME = "oauth_token"


class TokenStorage:
    """Manages saving and retrieving OAuth 2.0 credentials securely."""

    def __init__(self, fallback_path: Optional[Path] = None):
        self.fallback_file = fallback_path or (get_app_dir() / "token.json")

    def save_credentials(self, creds: Credentials) -> None:
        """Saves credentials into Keyring or fallback file."""
        data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes,
        }
        json_str = json.dumps(data)

        # 1. Try saving to Keyring
        keyring_saved = False
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME, json_str)
            keyring_saved = True
        except Exception as e:
            print(f"[TokenStorage] Keyring unavailable or failed: {e}")

        # 2. Always maintain secure fallback file
        try:
            self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.fallback_file, "w", encoding="utf-8") as f:
                f.write(json_str)

            # Enforce 0600 permissions on POSIX systems (Linux/KDE, macOS)
            if sys.platform != "win32":
                os.chmod(self.fallback_file, 0o600)
        except Exception as e:
            print(f"[TokenStorage] Failed to write fallback token file: {e}")
            if not keyring_saved:
                raise

    def load_credentials(self) -> Optional[Credentials]:
        """Loads credentials from Keyring or fallback file."""
        json_str = None

        # 1. Try Keyring
        try:
            json_str = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)
        except Exception as e:
            print(f"[TokenStorage] Could not load from keyring: {e}")

        # 2. Fallback to token file
        if not json_str and self.fallback_file.exists():
            try:
                with open(self.fallback_file, "r", encoding="utf-8") as f:
                    json_str = f.read()
            except Exception as e:
                print(f"[TokenStorage] Could not load from fallback file: {e}")

        if not json_str:
            return None

        try:
            data = json.loads(json_str)
            creds = Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=data.get("client_id"),
                client_secret=data.get("client_secret"),
                scopes=data.get("scopes"),
            )
            return creds
        except Exception as e:
            print(f"[TokenStorage] Invalid token data: {e}")
            return None

    def clear(self) -> None:
        """Removes saved credentials."""
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)
        except Exception:
            pass

        if self.fallback_file.exists():
            try:
                self.fallback_file.unlink()
            except Exception as e:
                print(f"[TokenStorage] Could not remove fallback token file: {e}")
