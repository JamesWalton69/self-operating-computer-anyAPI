"""
Google Antigravity Token Refresh & Lifecycle Management.

Handles automatic, thread-safe token refresh before expiration without
exposing refresh or access tokens in logs.
"""

import threading
import time
from typing import Optional

import requests

from antigravity.accounts import AccountManager, AntigravityAccount
from antigravity.diagnostics import log_event
from antigravity.exceptions import InvalidGrantError, TokenExpiredError
from antigravity.oauth import TOKEN_URL, get_client_id, get_client_secret

_REFRESH_LOCK = threading.Lock()


class TokenManager:
    """Manages token validation and automatic refresh for Antigravity accounts."""

    def __init__(self, account_manager: Optional[AccountManager] = None):
        self.account_manager = account_manager or AccountManager()

    def refresh(self, account: AntigravityAccount) -> AntigravityAccount:
        """
        Force refresh the access token using the stored refresh token.
        Never logs or prints tokens.
        """
        if not account.refresh_token:
            raise TokenExpiredError(
                f"No refresh token available for {account.email}. Re-authentication required."
            )

        client_id = account.client_id or get_client_id()
        client_secret = account.client_secret or get_client_secret()

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            payload["client_secret"] = client_secret

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "antigravity/ide/2.9.1 windows/amd64",
        }

        try:
            resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
        except requests.RequestException as e:
            log_event("token refresh failed", {"email": account.email, "error": str(e)})
            raise TokenExpiredError(f"Network error while refreshing token: {e}")

        if not resp.ok:
            err_text = resp.text
            log_event("token refresh failed", {"email": account.email, "status": resp.status_code, "body": err_text})
            if "invalid_grant" in err_text:
                raise InvalidGrantError(
                    f"Refresh token for {account.email} is invalid, expired, or has been revoked. Re-authentication required."
                )
            raise TokenExpiredError(f"Token refresh failed (HTTP {resp.status_code}): {err_text}")

        data = resp.json()
        account.access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", 3600)
        account.expires_at = time.time() + float(expires_in)
        if "refresh_token" in data:
            account.refresh_token = data["refresh_token"]

        self.account_manager.save(account, set_active=False)
        log_event("token refresh succeeded", {"email": account.email, "expires_in": expires_in})
        return account

    def ensure_valid_token(self, account: AntigravityAccount, buffer_seconds: int = 120) -> str:
        """
        Ensure the account's access token is valid, refreshing it if expired or expiring soon.
        Returns the valid access token string.
        """
        if account.is_expired(buffer_seconds=buffer_seconds):
            with _REFRESH_LOCK:
                # Double-check inside lock
                if account.is_expired(buffer_seconds=buffer_seconds):
                    account = self.refresh(account)
        return account.access_token
