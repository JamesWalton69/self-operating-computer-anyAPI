"""
Google Antigravity Account Bootstrap & Project Discovery.

Replicates the exact loadCodeAssist -> tier inspection -> onboardUser discovery
flow from OmniRoute to assign and discover the Cloud Code companion project.
"""

import time
from typing import Dict, List, Optional, Tuple

import requests

from antigravity.diagnostics import log_event
from antigravity.exceptions import BootstrapError

LOAD_CODE_ASSIST_ENDPOINTS = [
    "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
    "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist",
]

ONBOARD_USER_ENDPOINTS = [
    "https://cloudcode-pa.googleapis.com/v1internal:onboardUser",
    "https://daily-cloudcode-pa.googleapis.com/v1internal:onboardUser",
]

DEFAULT_TIER = "legacy-tier"
ANTIGRAVITY_METADATA = {"ideType": "ANTIGRAVITY"}
# Pin OS/arch to darwin/arm64 matching OmniRoute upstream fingerprint
USER_AGENT = "antigravity/ide/2.9.1 darwin/arm64"


def _get_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def extract_project_id(data: dict) -> str:
    """Extract cloudaicompanionProject identifier from API response."""
    if not isinstance(data, dict):
        return ""
    proj = data.get("cloudaicompanionProject")
    if isinstance(proj, str) and proj.strip():
        return proj.strip()
    if isinstance(proj, dict) and isinstance(proj.get("id"), str) and proj["id"].strip():
        return proj["id"].strip()
    return ""


def extract_tier_info(data: dict) -> Tuple[str, str]:
    """
    Extract (tier_id, tier_name) from loadCodeAssist response.
    Mirrors OmniRoute codeAssistSubscription.ts:
    Prioritizes paidTier -> currentTier (if eligible) -> default allowedTier -> currentTier -> legacy-tier.
    """
    if not isinstance(data, dict):
        return DEFAULT_TIER, DEFAULT_TIER

    sub = data.get("subscription") or data.get("subscriptionInfo") or data
    if not isinstance(sub, dict):
        sub = data

    ineligible = sub.get("ineligibleTiers")
    is_ineligible = isinstance(ineligible, list) and len(ineligible) > 0

    # 1. Paid tier (e.g. Google AI Pro / g1-pro-tier)
    paid = sub.get("paidTier")
    if isinstance(paid, dict):
        p_id = (paid.get("id") or "").strip()
        p_name = (paid.get("name") or p_id).strip()
        if p_id:
            return p_id, p_name

    # 2. Current tier (if not ineligible)
    current = sub.get("currentTier")
    if not is_ineligible and isinstance(current, dict):
        c_id = (current.get("id") or "").strip()
        c_name = (current.get("name") or c_id).strip()
        if c_id:
            return c_id, c_name

    # 3. Allowed tiers default
    allowed = sub.get("allowedTiers")
    if isinstance(allowed, list):
        for item in allowed:
            if isinstance(item, dict) and item.get("isDefault"):
                a_id = (item.get("id") or "").strip()
                a_name = (item.get("name") or a_id).strip()
                if a_id:
                    suffix = " (Restricted)" if is_ineligible else ""
                    return a_id, f"{a_name}{suffix}"

    # 4. Fallback current tier even if ineligible
    if isinstance(current, dict):
        c_id = (current.get("id") or "").strip()
        c_name = (current.get("name") or c_id).strip()
        if c_id:
            return c_id, c_name

    return DEFAULT_TIER, DEFAULT_TIER


def call_load_code_assist(access_token: str, timeout: int = 10) -> Optional[dict]:
    """Call loadCodeAssist on primary and secondary endpoints."""
    headers = _get_headers(access_token)
    payload = {"metadata": ANTIGRAVITY_METADATA}

    for url in LOAD_CODE_ASSIST_ENDPOINTS:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.ok:
                data = resp.json()
                log_event("loadCodeAssist succeeded", {"endpoint": url})
                return data
            else:
                log_event("loadCodeAssist failed", {"endpoint": url, "status": resp.status_code})
        except Exception as e:
            log_event("loadCodeAssist endpoint error", {"endpoint": url, "error": str(e)})

    return None


def call_onboard_user(access_token: str, tier_id: str, timeout: int = 15) -> Tuple[bool, Optional[str]]:
    """
    Call onboardUser to initialize project assignment.
    Returns (success_bool, optional_discovered_project_id).
    """
    headers = _get_headers(access_token)
    payload = {"tier_id": tier_id, "metadata": ANTIGRAVITY_METADATA}

    for url in ONBOARD_USER_ENDPOINTS:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.ok:
                log_event("onboarding succeeded", {"endpoint": url, "tier_id": tier_id})
                data = resp.json() if resp.content else {}
                proj_id = extract_project_id(data)
                return True, proj_id
            else:
                log_event("onboarding failed", {"endpoint": url, "status": resp.status_code})
        except Exception as e:
            log_event("onboarding endpoint error", {"endpoint": url, "error": str(e)})

    return False, None


def bootstrap_antigravity(access_token: str) -> Tuple[str, str]:
    """
    Run the full Antigravity bootstrap sequence for an authenticated token:
    1. Try loadCodeAssist to discover existing companion project & tier.
    2. If no project discovered, run onboardUser with discovered tier.
    3. Retry loadCodeAssist post-onboard.
    4. Return (project_id, tier_name).
    """
    data = call_load_code_assist(access_token)
    project_id = ""
    tier_id, tier_name = DEFAULT_TIER, DEFAULT_TIER

    if data:
        project_id = extract_project_id(data)
        tier_id, tier_name = extract_tier_info(data)
        log_event("tier discovered", {"tier_id": tier_id, "tier_name": tier_name})

    if project_id:
        log_event("project discovered", {"project_id": project_id})
        # Bounded onboard keep-alive in background
        try:
            call_onboard_user(access_token, tier_id, timeout=8)
        except Exception:
            pass
        return project_id, tier_name

    # Step 2: Onboard user if not yet provisioned
    log_event("Account not yet onboarded. Attempting onboardUser...")
    onboard_ok, onboard_proj = call_onboard_user(access_token, tier_id)
    if onboard_proj:
        log_event("project discovered from onboard", {"project_id": onboard_proj})
        return onboard_proj, tier_name

    # Step 3: Retry loadCodeAssist
    time.sleep(1.0)
    retry_data = call_load_code_assist(access_token)
    if retry_data:
        project_id = extract_project_id(retry_data)
        if project_id:
            log_event("project discovered", {"project_id": project_id})
            return project_id, tier_name

    # Step 4: Default companion project for consumer/personal Google accounts
    # Personal accounts with Google One AI Pro are mapped by Google to "aicode-consumers"
    default_proj = "aicode-consumers"
    log_event("project discovered", {"project_id": default_proj, "note": "consumer_companion"})
    return default_proj, tier_name
