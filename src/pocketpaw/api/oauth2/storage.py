# OAuth2 token and code storage.
# Created: 2026-02-20
#
# In-memory storage with optional file persistence for tokens.

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pocketpaw.api.oauth2.models import AuthorizationCode, OAuthClient, OAuthToken

logger = logging.getLogger(__name__)

# Default desktop client — always registered
DEFAULT_DESKTOP_CLIENT = OAuthClient(
    client_id="pocketpaw-desktop",
    client_name="PocketPaw Desktop",
    redirect_uris=["tauri://oauth-callback", "http://localhost:1420/oauth-callback"],
    allowed_scopes=["chat", "sessions", "settings:read", "settings:write", "channels", "memory"],
)


class OAuthStorage:
    """In-memory + file-backed OAuth2 storage."""

    def __init__(self, persist_path: Path | None = None):
        self._clients: dict[str, OAuthClient] = {
            DEFAULT_DESKTOP_CLIENT.client_id: DEFAULT_DESKTOP_CLIENT,
        }
        self._codes: dict[str, AuthorizationCode] = {}
        self._tokens: dict[str, OAuthToken] = {}  # keyed by access_token
        self._refresh_index: dict[str, str] = {}  # refresh_token → access_token
        self._persist_path = persist_path

    def get_client(self, client_id: str) -> OAuthClient | None:
        return self._clients.get(client_id)

    def store_code(self, code: AuthorizationCode) -> None:
        self._codes[code.code] = code

    def get_code(self, code: str) -> AuthorizationCode | None:
        return self._codes.get(code)

    def mark_code_used(self, code: str) -> None:
        if code in self._codes:
            self._codes[code].used = True

    def store_token(self, token: OAuthToken) -> None:
        self._tokens[token.access_token] = token
        self._refresh_index[token.refresh_token] = token.access_token

    def get_token(self, access_token: str) -> OAuthToken | None:
        return self._tokens.get(access_token)

    def get_token_by_refresh(self, refresh_token: str) -> OAuthToken | None:
        access_token = self._refresh_index.get(refresh_token)
        if access_token:
            return self._tokens.get(access_token)
        return None

    def revoke_token(self, access_token: str) -> bool:
        token = self._tokens.get(access_token)
        if token and not token.revoked:
            token.revoked = True
            return True
        return False

    def revoke_by_refresh(self, refresh_token: str) -> bool:
        access_token = self._refresh_index.get(refresh_token)
        if access_token:
            return self.revoke_token(access_token)
        return False

    def cleanup_expired(self) -> None:
        """Remove expired codes and tokens."""
        now = datetime.now(UTC)
        # Codes expire after 10 minutes
        expired_codes = [
            k
            for k, v in self._codes.items()
            if (now - v.created_at).total_seconds() > 600 or v.used
        ]
        for k in expired_codes:
            del self._codes[k]

        # Tokens expire based on expires_at
        expired_tokens = [
            k for k, v in self._tokens.items() if v.expires_at and now > v.expires_at
        ]
        for k in expired_tokens:
            token = self._tokens.pop(k)
            self._refresh_index.pop(token.refresh_token, None)
