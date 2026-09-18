"""
Google Antigravity Provider Diagnostics & Safe Logging.

Ensures sensitive values (access tokens, refresh tokens, auth codes, client secrets)
are NEVER logged or printed, while providing clear, structured lifecycle event diagnostics.
"""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("antigravity")

# Patterns for scrubbing credentials from error texts or raw payloads
_SECRET_PATTERNS = [
    (re.compile(r"ya29\.[A-Za-z0-9_\-]+", re.IGNORECASE), "[REDACTED_ACCESS_TOKEN]"),
    (re.compile(r"1//0[A-Za-z0-9_\-]+", re.IGNORECASE), "[REDACTED_REFRESH_TOKEN]"),
    (re.compile(r"GOCSPX-[A-Za-z0-9_\-]+", re.IGNORECASE), "[REDACTED_CLIENT_SECRET]"),
    (re.compile(r"4/[0-9A-Za-z_\-]+", re.IGNORECASE), "[REDACTED_AUTH_CODE]"),
]


def scrub_secrets(text: str) -> str:
    """Scrub known Google secret patterns from any text string."""
    if not text or not isinstance(text, str):
        return ""
    scrubbed = text
    for pattern, replacement in _SECRET_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def sanitize_payload(obj: Any) -> Any:
    """Recursively scrub secrets and redact tokens from any dict/list/string structure."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(sec in k_lower for sec in ("token", "secret", "password", "authorization", "key", "code")):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = sanitize_payload(v)
        return clean
    elif isinstance(obj, list):
        return [sanitize_payload(item) for item in obj]
    elif isinstance(obj, str):
        return scrub_secrets(obj)
    return obj


def mask_token(token: Optional[str]) -> str:
    """Safely mask a token showing only prefix and length, never content."""
    if not token or not isinstance(token, str):
        return "[NONE]"
    if len(token) <= 10:
        return "[MASKED]"
    return f"{token[:6]}...{token[-4:]} (len={len(token)})"


def log_event(event_name: str, details: Optional[Dict[str, Any]] = None, level: int = logging.INFO):
    """
    Log a structured diagnostic event.
    Automatically scrubs any secrets in the detail dictionary.
    """
    clean_details = {}
    if details:
        for k, v in details.items():
            # Never include raw secret keys
            if any(secret_key in k.lower() for secret_key in ("token", "secret", "code", "password", "key")):
                clean_details[k] = mask_token(str(v)) if v else "[NONE]"
            elif isinstance(v, str):
                clean_details[k] = scrub_secrets(v)
            else:
                clean_details[k] = v

    detail_str = " | ".join(f"{k}={v}" for k, v in clean_details.items()) if clean_details else ""
    msg = f"[Antigravity] {event_name}"
    if detail_str:
        msg = f"{msg} -> {detail_str}"
    
    logger.log(level, msg)
    print(msg)
