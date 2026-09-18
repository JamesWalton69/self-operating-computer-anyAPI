"""
Google Antigravity Multi-Account Model & Storage.

Manages persistent credentials for multiple Google accounts with automatic
refresh support, active account selection, and backward-compatible migration.
"""

import json
import os
import re
import stat
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from antigravity.diagnostics import log_event
from antigravity.exceptions import AccountNotFoundError


@dataclass
class AntigravityAccount:
    """Credential and project representation for an authenticated Antigravity account."""
    email: str
    access_token: str
    refresh_token: str
    expires_at: float
    project_id: str = ""
    tier: str = "legacy-tier"
    client_id: str = ""
    client_secret: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Return True if the access token has expired or is about to expire."""
        return time.time() + buffer_seconds >= self.expires_at

    def to_dict(self) -> dict:
        """Convert account to serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AntigravityAccount":
        """Reconstitute an account from storage dictionary."""
        return cls(
            email=data.get("email", ""),
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token", ""),
            expires_at=float(data.get("expires_at", data.get("expiry", 0.0))),
            project_id=data.get("project_id", data.get("projectId", "")),
            tier=data.get("tier", data.get("tierId", "legacy-tier")),
            client_id=data.get("client_id", ""),
            client_secret=data.get("client_secret", ""),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )


def _sanitize_filename(email: str) -> str:
    """Sanitize email for filesystem naming."""
    safe = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", email.lower().strip())
    return safe or "account_default"


class AccountManager:
    """Manages storage, retrieval, and active selection for multiple Antigravity accounts."""

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir:
            self.base_dir = os.path.abspath(storage_dir)
        elif os.getenv("ANTIGRAVITY_ACCOUNTS_DIR"):
            self.base_dir = os.path.abspath(os.getenv("ANTIGRAVITY_ACCOUNTS_DIR"))
        else:
            primary_dir = os.path.expanduser("~/.selfop")
            repo_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".selfop"))
            # If user home is accessible and writable, prefer it; otherwise use repo-local storage
            try:
                os.makedirs(os.path.join(primary_dir, "accounts"), exist_ok=True)
                self.base_dir = primary_dir
            except (PermissionError, OSError):
                self.base_dir = repo_dir

        self.accounts_dir = os.path.join(self.base_dir, "accounts")
        self.active_file = os.path.join(self.base_dir, "active_account.json")
        self.legacy_token_file = os.path.join(self.base_dir, "gemini_token.json")

        self._ensure_storage()
        self._migrate_legacy_if_needed()

    def _ensure_storage(self):
        """Create storage directories with restricted user-only permissions."""
        try:
            os.makedirs(self.accounts_dir, exist_ok=True)
            try:
                os.chmod(self.base_dir, stat.S_IRWXU)
                os.chmod(self.accounts_dir, stat.S_IRWXU)
            except OSError:
                pass
        except (PermissionError, OSError):
            # Fallback to local workspace if base_dir failed
            repo_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".selfop"))
            self.base_dir = repo_dir
            self.accounts_dir = os.path.join(self.base_dir, "accounts")
            self.active_file = os.path.join(self.base_dir, "active_account.json")
            self.legacy_token_file = os.path.join(self.base_dir, "gemini_token.json")
            os.makedirs(self.accounts_dir, exist_ok=True)

    def _migrate_legacy_if_needed(self):
        """Migrate legacy gemini_token.json to the new multi-account layout if not present."""
        if not os.path.exists(self.legacy_token_file):
            return
        try:
            with open(self.legacy_token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            email = data.get("email")
            if email and not self.get(email):
                account = AntigravityAccount.from_dict(data)
                self.save(account, set_active=True)
                log_event("Migrated legacy token to accounts store", {"email": email})
        except Exception:
            pass

    def _account_path(self, email: str) -> str:
        safe_name = _sanitize_filename(email)
        return os.path.join(self.accounts_dir, f"{safe_name}.json")

    def save(self, account: AntigravityAccount, set_active: bool = True):
        """Save or update an Antigravity account."""
        self._ensure_storage()
        now = time.time()
        if not account.created_at:
            account.created_at = now
        account.updated_at = now

        path = self._account_path(account.email)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(account.to_dict(), f, indent=2)

        try:
            os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

        os.replace(temp_path, path)

        if set_active:
            self.set_active(account.email)

        # Also write legacy file for backward compatibility with older components
        try:
            legacy_dict = account.to_dict()
            legacy_dict["expiry"] = account.expires_at
            legacy_dict["projectId"] = account.project_id
            with open(self.legacy_token_file, "w", encoding="utf-8") as f:
                json.dump(legacy_dict, f, indent=2)
        except Exception:
            pass

    def get(self, email: str) -> Optional[AntigravityAccount]:
        """Retrieve an account by email."""
        if not email:
            return None
        path = self._account_path(email)
        if not os.path.exists(path):
            # Check all accounts for matching email
            for acc in self.list_accounts():
                if acc.email.lower() == email.lower():
                    return acc
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AntigravityAccount.from_dict(data)
        except Exception:
            return None

    def get_active(self) -> Optional[AntigravityAccount]:
        """Get the currently active account, or the first available account."""
        if os.path.exists(self.active_file):
            try:
                with open(self.active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                active_email = data.get("active_email")
                if active_email:
                    account = self.get(active_email)
                    if account:
                        return account
            except Exception:
                pass

        # Fallback to the first account in storage
        accounts = self.list_accounts()
        if accounts:
            self.set_active(accounts[0].email)
            return accounts[0]

        return None

    def set_active(self, email: str) -> bool:
        """Set an account as the active default."""
        account = self.get(email)
        if not account:
            return False

        try:
            with open(self.active_file, "w", encoding="utf-8") as f:
                json.dump({"active_email": account.email, "updated_at": time.time()}, f, indent=2)
            return True
        except Exception:
            return False

    def list_accounts(self) -> List[AntigravityAccount]:
        """List all stored Antigravity accounts."""
        self._ensure_storage()
        results = []
        try:
            for fname in os.listdir(self.accounts_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(self.accounts_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        results.append(AntigravityAccount.from_dict(data))
                    except Exception:
                        continue
        except OSError:
            pass

        # Sort by updated_at descending
        results.sort(key=lambda a: a.updated_at, reverse=True)
        return results

    def delete(self, email: str) -> bool:
        """Delete an account from storage."""
        path = self._account_path(email)
        deleted = False
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted = True
            except OSError:
                pass

        # Clear active pointer if deleted
        active = self.get_active()
        if active and active.email.lower() == email.lower():
            try:
                if os.path.exists(self.active_file):
                    os.remove(self.active_file)
            except OSError:
                pass

        return deleted
