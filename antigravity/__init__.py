"""
Google Antigravity Standalone Authentication & Model Provider.

A fully standalone Google Antigravity connector for Self-Operating Computer (SOC)
that operates independently without OmniRoute or the Antigravity CLI ('agy').
"""

import time
from typing import List, Optional

from antigravity.accounts import AccountManager, AntigravityAccount
from antigravity.bootstrap import bootstrap_antigravity
from antigravity.client import AntigravityClient, resolve_model_id
from antigravity.diagnostics import log_event
from antigravity.exceptions import (
    AccountNotFoundError,
    AntigravityError,
    AuthenticationError,
    BootstrapError,
    InvalidGrantError,
    OAuthError,
    PermissionDeniedError,
    QuotaExhaustedError,
    RedirectUriMismatchError,
    StateMismatchError,
    TokenExpiredError,
    VerificationRequiredError,
)
from antigravity.oauth import (
    DEFAULT_OAUTH_HOST,
    DEFAULT_OAUTH_PORT,
    get_client_id,
    get_client_secret,
    get_oauth_host,
    get_oauth_port,
    run_oauth_flow,
)
from antigravity.token_manager import TokenManager

__all__ = [
    "AntigravityAccount",
    "AccountManager",
    "AntigravityClient",
    "TokenManager",
    "authenticate",
    "get_client",
    "list_accounts",
    "get_active_account",
    "set_active_account",
    "delete_account",
    "resolve_model_id",
    "AntigravityError",
    "OAuthError",
    "StateMismatchError",
    "RedirectUriMismatchError",
    "InvalidGrantError",
    "TokenExpiredError",
    "AuthenticationError",
    "PermissionDeniedError",
    "QuotaExhaustedError",
    "VerificationRequiredError",
    "BootstrapError",
    "AccountNotFoundError",
]


def authenticate(
    host: Optional[str] = None,
    port: Optional[int] = None,
    prompt: str = "consent",
    open_browser: bool = True,
    set_active: bool = True,
) -> AntigravityAccount:
    """
    Run the standalone Google OAuth flow on 127.0.0.1:38741, exchange tokens,
    bootstrap Antigravity companion project/tier, and persist the account.

    Returns:
        AntigravityAccount: Fully initialized and persisted account.
    """
    manager = AccountManager()
    token_mgr = TokenManager(manager)

    # 1. Run OAuth flow & exchange code for tokens
    token_data, email = run_oauth_flow(
        host=host,
        port=port,
        prompt=prompt,
        open_browser=open_browser,
    )

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    expires_at = time.time() + float(expires_in)

    if not email:
        email = f"google_account_{int(time.time())}@google.com"

    # 2. Run Antigravity Bootstrap (loadCodeAssist -> onboardUser)
    project_id, tier = bootstrap_antigravity(access_token)

    account = AntigravityAccount(
        email=email,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        project_id=project_id,
        tier=tier,
        client_id=get_client_id(),
        client_secret=get_client_secret(),
    )

    # 3. Persist account to secure storage
    manager.save(account, set_active=set_active)
    log_event("Account authenticated and ready", {"email": email, "project_id": project_id, "tier": tier})
    return account


def get_client(account: Optional[AntigravityAccount] = None) -> AntigravityClient:
    """
    Get an AntigravityClient instance.
    If no account is provided, loads the currently active account from storage.
    """
    manager = AccountManager()
    token_mgr = TokenManager(manager)

    if account is None:
        account = manager.get_active()

    if account is None:
        raise AccountNotFoundError(
            "No active Google Antigravity account found. Run authentication first: python -m antigravity auth"
        )

    return AntigravityClient(account=account, token_manager=token_mgr)


def list_accounts() -> List[AntigravityAccount]:
    """List all stored Antigravity accounts."""
    return AccountManager().list_accounts()


def get_active_account() -> Optional[AntigravityAccount]:
    """Get the currently active account."""
    return AccountManager().get_active()


def set_active_account(email: str) -> bool:
    """Set the active account by email."""
    return AccountManager().set_active(email)


def delete_account(email: str) -> bool:
    """Delete an account by email."""
    return AccountManager().delete(email)
