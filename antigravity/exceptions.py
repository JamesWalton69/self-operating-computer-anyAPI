"""
Google Antigravity Provider Exceptions.

Defines a clean, strongly-typed exception hierarchy for all OAuth, bootstrap,
credential, and upstream API errors in the standalone Antigravity provider.
"""

from typing import Optional


class AntigravityError(Exception):
    """Base exception for all Antigravity provider errors."""
    pass


class OAuthError(AntigravityError):
    """Base exception for OAuth flow failures."""
    pass


class StateMismatchError(OAuthError):
    """Raised when the OAuth callback state does not match the generated state."""
    def __init__(self, message: str = "OAuth state mismatch: potential CSRF attack or invalid session."):
        super().__init__(message)


class RedirectUriMismatchError(OAuthError):
    """Raised when Google rejects the redirect URI."""
    def __init__(self, redirect_uri: str, message: Optional[str] = None):
        msg = message or (
            f"Redirect URI mismatch for '{redirect_uri}'. "
            "Ensure the OAuth client allows loopback IP callbacks (http://127.0.0.1:<port>/callback)."
        )
        super().__init__(msg)
        self.redirect_uri = redirect_uri


class InvalidGrantError(OAuthError):
    """Raised when the authorization code or refresh token is invalid, expired, or revoked."""
    def __init__(self, message: str = "Invalid grant: token or code has expired, been revoked, or is malformed."):
        super().__init__(message)


class TokenExpiredError(OAuthError):
    """Raised when an access token has expired and cannot be refreshed."""
    pass


class AuthenticationError(AntigravityError):
    """Raised on HTTP 401 Unauthorized from Antigravity endpoints."""
    def __init__(self, message: str = "Authentication failed (HTTP 401): Token expired or revoked."):
        super().__init__(message)


class PermissionDeniedError(AntigravityError):
    """Raised on HTTP 403 Forbidden from Antigravity endpoints."""
    def __init__(self, message: str = "Permission denied (HTTP 403). Check project binding and API permissions."):
        super().__init__(message)


class QuotaExhaustedError(AntigravityError):
    """
    Raised on HTTP 429 Too Many Requests or RESOURCE_EXHAUSTED.
    Retains full server response and account metadata for diagnostics.
    """
    def __init__(
        self,
        message: str,
        status_code: int = 429,
        response_body: Optional[str] = None,
        account_email: Optional[str] = None,
        project_id: Optional[str] = None,
        tier: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or ""
        self.account_email = account_email or ""
        self.project_id = project_id or ""
        self.tier = tier or ""


class VerificationRequiredError(AntigravityError):
    """Raised when Google requires human / account validation before granting quota."""
    pass


class BootstrapError(AntigravityError):
    """Raised when Antigravity project discovery or onboarding fails."""
    pass


class AccountNotFoundError(AntigravityError):
    """Raised when a requested account is not found in local storage."""
    pass
