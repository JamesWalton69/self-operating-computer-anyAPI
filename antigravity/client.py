"""
Google Antigravity Standalone API Client.

Direct streaming HTTP client for Antigravity multimodal generation
supporting Gemini 3.7, Gemini Pro, Claude Sonnet/Opus, and SOC operation parsing.
"""

import base64
import json
import mimetypes
import uuid
from typing import Any, Dict, List, Optional

import requests

from antigravity.accounts import AntigravityAccount
from antigravity.diagnostics import log_event
from antigravity.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    QuotaExhaustedError,
    VerificationRequiredError,
)
from antigravity.token_manager import TokenManager

STREAM_ENDPOINTS = [
    "https://daily-cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse",
    "https://cloudcode-pa.googleapis.com/v1internal:streamGenerateContent?alt=sse",
]

# Upstream Antigravity expects macOS darwin/arm64 client fingerprint
USER_AGENT = "antigravity/ide/2.9.1 darwin/arm64"

# Model remapping verified against current OmniRoute / Antigravity upstream
MODEL_ALIASES = {
    "gemini-3.7-flash": "gemini-3.7-flash-tiered",
    "gemini-3.7-flash-high": "gemini-3.7-flash-tiered",
    "gemini-3.7-flash-medium": "gemini-3.7-flash-tiered",
    "gemini-3.7-flash-low": "gemini-3.7-flash-tiered",
    "gemini-3.1-pro-high": "gemini-pro-agent",
    "gemini-claude-sonnet-4-5": "claude-sonnet-4-6",
    "gemini-claude-sonnet-4-5-thinking": "claude-sonnet-4-6",
    "gemini-claude-opus-4-5-thinking": "claude-opus-4-6-thinking",
}


def resolve_model_id(model_name: str) -> str:
    """Resolve user-facing model alias to Antigravity upstream model identifier."""
    clean = model_name.split("/")[-1] if "/" in model_name else model_name
    # Strip client grounding suffixes if present
    for suffix in ("-direct", "-with-som", "-som", "-with-ocr", "-ocr"):
        clean = clean.replace(suffix, "")
    return MODEL_ALIASES.get(clean, clean)


class AntigravityClient:
    """Standalone client for making Antigravity inference requests."""

    def __init__(self, account: AntigravityAccount, token_manager: Optional[TokenManager] = None):
        self.account = account
        self.token_manager = token_manager or TokenManager()

    def _parse_sse_response(self, resp: requests.Response) -> dict:
        """Parse Server-Sent Events (SSE) stream lines into a combined candidate response."""
        accumulated_text = ""
        last_response = {}

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if line_str.startswith("data: "):
                chunk_str = line_str[6:].strip()
                if chunk_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_str)
                    last_response = chunk
                    if "error" in chunk:
                        raise RuntimeError(f"Google Cloud Code streaming error: {chunk['error']}")

                    candidates = chunk.get("candidates", [])
                    if not candidates and "response" in chunk:
                        candidates = chunk["response"].get("candidates", [])

                    for cand in candidates:
                        for part in cand.get("content", {}).get("parts", []):
                            if isinstance(part, dict) and "text" in part:
                                accumulated_text += part["text"]
                except json.JSONDecodeError:
                    continue

        if accumulated_text:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": accumulated_text}],
                            "role": "model",
                        }
                    }
                ]
            }
        return last_response

    def generate(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        model: str = "gemini-3.7-flash-low",
        timeout: int = 45,
    ) -> dict:
        """
        Send a multimodal generation request to Google Antigravity.

        Args:
            prompt: Text prompt to send.
            images: Optional list of image file paths to include.
            model: Model name (e.g. gemini-3.7-flash-low, gemini-3.1-pro-low, claude-sonnet-4-6).
            timeout: Request timeout in seconds.

        Returns:
            dict: Raw parsed JSON response.
        """
        import time as _time

        # Ensure token is refreshed and valid
        access_token = self.token_manager.ensure_valid_token(self.account)

        # Build multimodal contents parts
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        if images:
            for img_path in images:
                with open(img_path, "rb") as img_file:
                    img_bytes = img_file.read()
                mime_type = mimetypes.guess_type(img_path)[0] or "image/png"
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                parts.append({"inline_data": {"mime_type": mime_type, "data": b64}})

        upstream_model = resolve_model_id(model)
        project = self.account.project_id or "aicode-consumers"
        request_id = f"agent/{int(_time.time()*1000)}/{uuid.uuid4().hex[:8]}"
        session_id = f"-{int(_time.time()*1000000) % 9000000000000000000}"

        # Request envelope matching Antigravity IDE standard
        body = {
            "project": project,
            "model": upstream_model,
            "userAgent": "antigravity",
            "requestType": "agent",
            "requestId": request_id,
            "enabledCreditTypes": ["GOOGLE_ONE_AI"],
            "request": {
                "contents": [{"role": "user", "parts": parts}],
                "sessionId": session_id,
                "generationConfig": {
                    "topK": 40,
                    "topP": 1.0,
                },
            },
        }

        # Headers matching Antigravity native profile (NO x-goog-user-project)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": USER_AGENT,
        }

        response = None
        last_error = None

        for endpoint in STREAM_ENDPOINTS:
            try:
                response = requests.post(endpoint, headers=headers, json=body, timeout=timeout, stream=True)
                if response.status_code == 200:
                    parsed = self._parse_sse_response(response)
                    if parsed and ("candidates" in parsed or "response" in parsed):
                        return parsed
                    try:
                        res_json = response.json()
                        if "response" in res_json and "candidates" in res_json["response"]:
                            return res_json["response"]
                        return res_json
                    except Exception:
                        return parsed
                elif response.status_code == 429:
                    # Retry once with GOOGLE_ONE_AI credits on 429 (OmniRoute tryCreditsRetry parity)
                    credits_body = dict(body)
                    credits_body["enabledCreditTypes"] = ["GOOGLE_ONE_AI"]
                    c_resp = requests.post(endpoint, headers=headers, json=credits_body, timeout=timeout, stream=True)
                    if c_resp.status_code == 200:
                        parsed = self._parse_sse_response(c_resp)
                        if parsed and ("candidates" in parsed or "response" in parsed):
                            return parsed
                        try:
                            res_json = c_resp.json()
                            if "response" in res_json and "candidates" in res_json["response"]:
                                return res_json["response"]
                            return res_json
                        except Exception:
                            return parsed
                    # If credits retry also failed on this endpoint, fall through to next endpoint
                    response = c_resp
            except requests.RequestException as e:
                last_error = e
                continue

        if response is None:
            raise RuntimeError(f"All Google Antigravity endpoints failed: {last_error}")

        if response.status_code == 401:
            raise AuthenticationError(
                f"Antigravity token for {self.account.email} was rejected (HTTP 401). Re-authentication required."
            )

        if not response.ok:
            err_body = response.text
            err_msg = err_body
            try:
                err_json = response.json()
                if "error" in err_json:
                    err_info = err_json["error"]
                    if isinstance(err_info, dict) and "message" in err_info:
                        err_msg = err_info["message"]
                    elif isinstance(err_info, str):
                        err_msg = err_info
            except Exception:
                pass

            if "VALIDATION_REQUIRED" in err_msg:
                raise VerificationRequiredError(
                    f"Google Antigravity account validation required for {self.account.email}: {err_msg}"
                )

            if response.status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg:
                raise QuotaExhaustedError(
                    message=(
                        f"Google Antigravity quota exhausted (HTTP 429) for account {self.account.email} "
                        f"[Tier: {self.account.tier}, Project: {project}]: {err_msg}"
                    ),
                    status_code=429,
                    response_body=err_body,
                    account_email=self.account.email,
                    project_id=project,
                    tier=self.account.tier,
                )

            if response.status_code == 403:
                raise PermissionDeniedError(
                    f"Google Antigravity permission denied (HTTP 403) for account {self.account.email} "
                    f"on project '{project}': {err_msg}"
                )

            raise RuntimeError(f"Google Cloud Code API error (HTTP {response.status_code}): {err_msg}")

        try:
            res_json = response.json()
            if "response" in res_json and "candidates" in res_json["response"]:
                return res_json["response"]
            return res_json
        except Exception:
            return {}

    def generate_operations(
        self,
        prompt: str,
        images: Optional[List[str]] = None,
        model: str = "gemini-3.7-flash-low",
    ) -> List[dict]:
        """
        Generate operations and parse the response text into structured action dicts for SOC.

        Returns:
            List of action dictionaries.
        """
        resp = self.generate(prompt=prompt, images=images, model=model)

        candidates = resp.get("candidates", [])
        if not candidates and "response" in resp:
            candidates = resp["response"].get("candidates", [])

        if not candidates:
            return [{"operation": "error", "error": "No response candidates from Antigravity"}]

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        if not text:
            return [{"operation": "error", "error": "Empty text in model response"}]

        # Extract JSON array from markdown code fence or raw text
        clean_text = text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

        # Fallback: scan for JSON array bracket boundaries
        start = clean_text.find("[")
        end = clean_text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(clean_text[start : end + 1])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        return [{"operation": "error", "error": f"Failed to parse operations from: {text[:200]}"}]
