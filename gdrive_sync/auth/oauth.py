"""
OAuth 2.0 PKCE / Loopback authentication flow for Google Drive.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .token_storage import TokenStorage
from ..config import AppConfig

SCOPES: List[str] = [
    "https://www.googleapis.com/auth/drive",
]


class OAuthManager:
    """Handles obtaining, refreshing, and persisting Google Drive OAuth 2.0 tokens."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.storage = TokenStorage(fallback_path=self.config.token_file)

    def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Retrieves saved credentials. Refreshes them if expired.
        Returns None if not authenticated or refresh failed.
        """
        creds = self.storage.load_credentials()
        if not creds:
            return None

        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self.storage.save_credentials(creds)
            except Exception as e:
                print(f"[OAuthManager] Failed to refresh token: {e}")
                return None

        return creds if creds.valid else None

    def start_auth_flow(
        self,
        client_config_path: Optional[Path] = None,
        client_config_dict: Optional[Dict[str, Any]] = None,
        open_browser: bool = True,
    ) -> Credentials:
        """
        Launches local server and web browser to authorize with Google Drive.
        """
        if client_config_dict:
            flow = InstalledAppFlow.from_client_config(client_config_dict, scopes=SCOPES)
        elif client_config_path and client_config_path.exists():
            flow = InstalledAppFlow.from_client_secrets_file(str(client_config_path), scopes=SCOPES)
        elif self.config.client_secrets_file.exists():
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.config.client_secrets_file), scopes=SCOPES
            )
        else:
            raise FileNotFoundError(
                f"No client_secrets.json found at {self.config.client_secrets_file}. "
                "Please configure your Google Cloud OAuth Client credentials."
            )

        # Run local server on an open port on 127.0.0.1
        creds = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            authorization_prompt_message=(
                "Abriendo navegador para iniciar sesión en Google Drive..."
            ),
            success_message=(
                "<html><head><meta charset='utf-8'><title>Autenticación Exitosa</title></head>"
                "<body style='font-family: sans-serif; text-align: center; padding: 50px; background-color: #f7f9fa;'>"
                "<h1 style='color: #1a73e8;'>¡Autenticación exitosa!</h1>"
                "<p>Tu cuenta ha sido vinculada correctamente. Ya puedes cerrar esta pestaña y volver a la aplicación.</p>"
                "</body></html>"
            ),
            open_browser=open_browser,
        )

        self.storage.save_credentials(creds)
        return creds

    def logout(self) -> None:
        """Removes saved credentials."""
        self.storage.clear()
