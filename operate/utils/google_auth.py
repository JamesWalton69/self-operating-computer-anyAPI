"""
Google OAuth 2.0 Manager for Self-Operating Computer
Handles authorization, token exchange, secure storage via Windows DPAPI,
and automatic background token rotation.
"""
import base64
import ctypes
import ctypes.wintypes
import json
import os
import platform
import re
import time
import threading
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass


# Platform detection (used by DPAPI and encryption backend selection)
_IS_WINDOWS = platform.system() == "Windows"

# --- Windows DPAPI Encryption ---

class _DPAPI_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.c_void_p),
    ]


# Set proper 64-bit argument types for LocalFree
if _IS_WINDOWS:
    ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p


def _dpapi_encrypt(plaintext: str) -> str:
    """Encrypt a string using Windows DPAPI (CryptProtectData). Only the current user can decrypt."""
    data = plaintext.encode("utf-8")
    blob_in = _DPAPI_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.c_void_p))
    blob_out = _DPAPI_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("DPAPI CryptProtectData failed")
    encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return base64.b64encode(encrypted).decode("ascii")


def _dpapi_decrypt(ciphertext_b64: str) -> str:
    """Decrypt a DPAPI-encrypted base64 string back to plaintext."""
    data = base64.b64decode(ciphertext_b64)
    blob_in = _DPAPI_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.c_void_p))
    blob_out = _DPAPI_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("DPAPI CryptUnprotectData failed")
    decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return decrypted.decode("utf-8")


def _fallback_encrypt(plaintext: str) -> str:
    """Simple base64 obfuscation fallback for non-Windows platforms."""
    return base64.b64encode(plaintext.encode("utf-8")).decode("ascii")


def _fallback_decrypt(ciphertext_b64: str) -> str:
    """Simple base64 decode fallback for non-Windows platforms."""
    return base64.b64decode(ciphertext_b64).decode("utf-8")


# Select encryption backend based on platform
encrypt_token = _dpapi_encrypt if _IS_WINDOWS else _fallback_encrypt
decrypt_token = _dpapi_decrypt if _IS_WINDOWS else _fallback_decrypt


# --- Token Storage ---

_DEFAULT_TOKEN_DIR = os.path.join(os.path.expanduser("~"), ".self-operating-computer")
_DEFAULT_TOKEN_FILE = "google_oauth_token.enc"


def _get_token_path() -> str:
    token_dir = os.environ.get("SOC_TOKEN_DIR", _DEFAULT_TOKEN_DIR)
    os.makedirs(token_dir, exist_ok=True)
    return os.path.join(token_dir, _DEFAULT_TOKEN_FILE)


# --- Google OAuth Manager ---

class GoogleOAuthManager:
    """
    Manages Google OAuth 2.0 flow:
    - Authorization URL generation (offline access, forced consent)
    - Code extraction from user-pasted input (raw code or callback URL)
    - Token exchange (authorization_code -> access_token + refresh_token)
    - Secure local storage of refresh_token via DPAPI
    - Automatic background token rotation when access_token expires
    """

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    DEFAULT_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    OOB_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"

    def __init__(self, client_id=None, client_secret=None, scopes=None):
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.scopes = scopes or self.DEFAULT_SCOPES
        self.redirect_uri = self.OOB_REDIRECT_URI

        # Runtime token state (in-memory only, never persisted)
        self._access_token = None
        self._token_expiry = 0.0  # Unix timestamp
        self._user_email = None
        self._lock = threading.Lock()

        # Try to load existing refresh token
        self._refresh_token = self._load_refresh_token()

    # --- Authorization URL ---

    def get_authorization_url(self, redirect_uri=None) -> str:
        """Build the Google OAuth consent URL."""
        self.redirect_uri = redirect_uri or self.OOB_REDIRECT_URI
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"

    def open_consent_in_browser(self, redirect_uri=None):
        """Open the Google consent page in the user's default browser."""
        url = self.get_authorization_url(redirect_uri)
        webbrowser.open(url)
        return url

    # --- Code Extraction ---

    @staticmethod
    def extract_code_from_input(user_input: str) -> str:
        """Extract the authorization code from raw code string or full callback URL."""
        user_input = user_input.strip()
        if not user_input:
            raise ValueError("Empty input provided")

        # Try parsing as URL with ?code= parameter
        if "://" in user_input or user_input.startswith("http"):
            parsed = urlparse(user_input)
            qs = parse_qs(parsed.query)
            if "code" in qs:
                return qs["code"][0]
            # Check fragment
            frag_qs = parse_qs(parsed.fragment)
            if "code" in frag_qs:
                return frag_qs["code"][0]

        # Try extracting code= from query string fragment
        code_match = re.search(r'[?&]code=([^&\s]+)', user_input)
        if code_match:
            return code_match.group(1)

        # Assume it's a raw authorization code
        if len(user_input) > 10 and " " not in user_input:
            return user_input

        raise ValueError(f"Could not extract authorization code from input: {user_input[:50]}...")

    # --- Token Exchange ---

    def exchange_code_for_tokens(self, code_or_url: str) -> dict:
        """Exchange an authorization code for access and refresh tokens."""
        code = self.extract_code_from_input(code_or_url)

        data = urlencode({
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        req = urllib.request.Request(
            self.GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Token exchange failed ({e.code}): {body}")

        # Store tokens
        with self._lock:
            self._access_token = result.get("access_token")
            expires_in = result.get("expires_in", 3600)
            self._token_expiry = time.time() + int(expires_in) - 60  # 60s buffer

            refresh_token = result.get("refresh_token")
            if refresh_token:
                self._refresh_token = refresh_token
                self._save_refresh_token(refresh_token)

        # Fetch user info
        try:
            self._user_email = self._fetch_user_email()
        except Exception:
            self._user_email = "Connected"

        return result

    # --- Token Refresh ---

    def refresh_access_token(self) -> str:
        """Use the stored refresh_token to obtain a new access_token."""
        if not self._refresh_token:
            raise RuntimeError("No refresh token available. Please re-authenticate.")

        data = urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(
            self.GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Token refresh failed ({e.code}): {body}")

        with self._lock:
            self._access_token = result.get("access_token")
            expires_in = result.get("expires_in", 3600)
            self._token_expiry = time.time() + int(expires_in) - 60

            # Some providers rotate refresh tokens
            new_refresh = result.get("refresh_token")
            if new_refresh:
                self._refresh_token = new_refresh
                self._save_refresh_token(new_refresh)

        return self._access_token

    # --- Access Token Getter (with auto-rotation) ---

    def get_valid_access_token(self) -> str:
        """Return a valid access token, silently refreshing if expired or near expiry."""
        with self._lock:
            if self._access_token and time.time() < self._token_expiry:
                return self._access_token

        # Token expired or missing — refresh
        if self._refresh_token:
            return self.refresh_access_token()

        return None

    # --- State Queries ---

    def is_authenticated(self) -> bool:
        """Check if a refresh token is available (user has connected)."""
        return bool(self._refresh_token)

    def get_user_email(self) -> str:
        return self._user_email or ""

    # --- Revoke & Logout ---

    def revoke_and_logout(self):
        """Revoke the refresh token and clear all stored credentials."""
        token = self._refresh_token or self._access_token
        if token:
            try:
                data = urlencode({"token": token}).encode("utf-8")
                req = urllib.request.Request(
                    self.GOOGLE_REVOKE_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass  # Best effort

        with self._lock:
            self._access_token = None
            self._token_expiry = 0.0
            self._refresh_token = None
            self._user_email = None

        # Delete stored token file
        try:
            path = _get_token_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    # --- Private Helpers ---

    def _save_refresh_token(self, token: str):
        """Encrypt and persist refresh token to disk."""
        try:
            encrypted = encrypt_token(token)
            path = _get_token_path()
            with open(path, "w", encoding="utf-8") as f:
                f.write(encrypted)
        except Exception as e:
            print(f"[GoogleOAuthManager] Warning: Could not save refresh token: {e}")

    def _load_refresh_token(self) -> str:
        """Load and decrypt refresh token from disk."""
        try:
            path = _get_token_path()
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                encrypted = f.read().strip()
            if not encrypted:
                return None
            return decrypt_token(encrypted)
        except Exception as e:
            print(f"[GoogleOAuthManager] Warning: Could not load refresh token: {e}")
            return None

    def _fetch_user_email(self) -> str:
        """Fetch the authenticated user's email from Google userinfo endpoint."""
        token = self._access_token
        if not token:
            return None
        req = urllib.request.Request(
            self.GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        return info.get("email", "Connected")
