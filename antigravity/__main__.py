"""
CLI entry point for Google Antigravity standalone provider.

Supports:
    python -m antigravity auth
    python -m antigravity list
    python -m antigravity switch <email>
    python -m antigravity test
    python -m antigravity status
"""

import argparse
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import antigravity
from antigravity.oauth import (
    DEFAULT_OAUTH_HOST,
    DEFAULT_OAUTH_PORT,
    get_oauth_host,
    get_oauth_port,
)


def cmd_auth(args):
    """Run Google OAuth authentication on port 38741."""
    host = args.host or get_oauth_host()
    port = args.port or get_oauth_port()
    prompt = args.prompt or "select_account consent"

    print("=" * 60)
    print("  Google Antigravity Standalone Authentication")
    print(f"  Callback Listener: http://{host}:{port}/callback")
    print("=" * 60)
    print()

    try:
        account = antigravity.authenticate(host=host, port=port, prompt=prompt)
        print()
        print("✓ Authentication & Bootstrap Complete!")
        print(f"  Email:      {account.email}")
        print(f"  Project:    {account.project_id}")
        print(f"  Tier:       {account.tier}")
        print(f"  Expires:    in {int(account.expires_at - time.time())} seconds (auto-refreshed)")
        print()
    except Exception as e:
        print(f"✗ Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List stored Google Antigravity accounts."""
    accounts = antigravity.list_accounts()
    active = antigravity.get_active_account()

    print("=" * 60)
    print("  Stored Google Antigravity Accounts")
    print("=" * 60)
    if not accounts:
        print("  No accounts found. Run: python -m antigravity auth")
        return

    for idx, acc in enumerate(accounts, 1):
        is_active = active and active.email.lower() == acc.email.lower()
        marker = "🟢 [ACTIVE]" if is_active else "⚪"
        exp = int(acc.expires_at - time.time())
        exp_str = f"expires in {exp}s" if exp > 0 else "expired (will auto-refresh)"
        print(f"  {marker} #{idx}: {acc.email}")
        print(f"       Project: {acc.project_id or 'aicode-consumers'}")
        print(f"       Tier:    {acc.tier}")
        print(f"       Status:  {exp_str}")
        print()


def cmd_switch(args):
    """Switch active Google account."""
    if not args.email:
        print("Error: Specify email to switch to: python -m antigravity switch <email>", file=sys.stderr)
        sys.exit(1)
    if antigravity.set_active_account(args.email):
        print(f"✓ Switched active Antigravity account to: {args.email}")
    else:
        print(f"✗ Account '{args.email}' not found in storage.", file=sys.stderr)
        sys.exit(1)


def cmd_test(args):
    """Test full pipeline: load account -> token refresh check -> test inference."""
    print("=" * 60)
    print("  Testing Google Antigravity Client & Pipeline")
    print("=" * 60)
    try:
        client = antigravity.get_client()
        print(f"  Active Account: {client.account.email}")
        print(f"  Project:        {client.account.project_id}")
        print(f"  Tier:           {client.account.tier}")
        print()
        print("[1/2] Verifying token validity and automatic refresh...")
        valid_token = client.token_manager.ensure_valid_token(client.account)
        print("✓ Token is valid and ready.")
        print()
        print("[2/2] Sending test query to Google Antigravity...")
        model = args.model or "gemini-3.7-flash-low"
        resp = client.generate(
            prompt="Reply with the exact word 'READY' and nothing else.",
            model=model,
        )
        candidates = resp.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            print(f"✓ Response received from model [{model}]:")
            print(f"  {text.strip()}")
            print()
            print("✓ Antigravity pipeline verification succeeded!")
        else:
            print("✗ Received empty candidate response from server.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"✗ Test failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Display active account status and token health."""
    active = antigravity.get_active_account()
    if not active:
        print("Status: Not authenticated. Run: python -m antigravity auth")
        return

    exp = int(active.expires_at - time.time())
    print("Google Antigravity Status:")
    print(f"  Active Account: {active.email}")
    print(f"  Project ID:     {active.project_id}")
    print(f"  Tier:           {active.tier}")
    print(f"  Token Expiry:   {exp}s remaining")


def cmd_debug(args):
    """Comprehensive diagnostic run for Antigravity bootstrap and model inference."""
    import json
    import uuid
    import requests
    from antigravity.diagnostics import sanitize_payload, mask_token, scrub_secrets
    from antigravity.bootstrap import (
        LOAD_CODE_ASSIST_ENDPOINTS,
        ONBOARD_USER_ENDPOINTS,
        extract_project_id,
        extract_tier_info,
    )
    from antigravity.client import resolve_model_id

    print("=" * 70)
    print("  Google Antigravity Safe Diagnostic Protocol")
    print("  (All tokens, secrets, and auth headers are strictly redacted)")
    print("=" * 70)
    print()

    active = antigravity.get_active_account()
    if not active:
        print("✗ No active account found. Please authenticate first: python -m antigravity auth")
        return

    print(f"Active Account:     {active.email}")
    print(f"Stored Project ID:  {active.project_id or '[EMPTY]'}")
    print(f"Stored Tier:        {active.tier}")
    exp = int(active.expires_at - time.time())
    print(f"Token Expiry:       {exp}s remaining ({'EXPIRED' if exp <= 0 else 'VALID'})")
    print()

    # Step 1: Token verification / refresh
    print("[DIAG 1/4] Checking Token Health & Refresh...")
    token_mgr = antigravity.TokenManager()
    access_token = token_mgr.ensure_valid_token(active)
    print(f"  Access Token:     {mask_token(access_token)}")
    print(f"  Refresh Token:    {mask_token(active.refresh_token)}")
    print(f"  Client ID:        {active.client_id or '[DEFAULT Antigravity IDE]'}")
    print("✓ Token refresh check passed.")
    print()

    # Step 2: Protocol Check - loadCodeAssist
    print("[DIAG 2/4] Querying loadCodeAssist Upstream...")
    ua_darwin = "antigravity/ide/2.9.1 darwin/arm64"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": ua_darwin,
    }
    body_load = {"metadata": {"ideType": "ANTIGRAVITY"}}

    load_url = LOAD_CODE_ASSIST_ENDPOINTS[0]
    print(f"  Endpoint:         {load_url}")
    print(f"  Method:           POST")
    print(f"  User-Agent:       {ua_darwin}")
    print(f"  Request Headers:  {{'Content-Type': 'application/json', 'User-Agent': '{ua_darwin}', 'Authorization': 'Bearer [REDACTED]'}}")
    print(f"  Request Body:     {json.dumps(body_load)}")

    load_resp_data = None
    try:
        resp = requests.post(load_url, headers=headers, json=body_load, timeout=12)
        print(f"  Response Status:  HTTP {resp.status_code}")
        try:
            load_resp_data = resp.json()
            safe_resp = sanitize_payload(load_resp_data)
            print(f"  Response Body:    {json.dumps(safe_resp, indent=2)}")
        except Exception:
            print(f"  Response Body:    {scrub_secrets(resp.text[:500])}")
    except Exception as e:
        print(f"  loadCodeAssist Error: {e}")

    # Inspect discovered fields
    extracted_proj = ""
    discovered_tier_id = "legacy-tier"
    discovered_tier_name = "legacy-tier"
    allowed_tiers = []
    default_tier = None
    ineligible_tiers = []
    paid_tier = None
    current_tier = None

    if load_resp_data and isinstance(load_resp_data, dict):
        extracted_proj = extract_project_id(load_resp_data)
        sub = load_resp_data.get("subscription") or load_resp_data.get("subscriptionInfo") or load_resp_data
        if isinstance(sub, dict):
            paid_tier = sub.get("paidTier")
            current_tier = sub.get("currentTier")
            allowed_tiers = sub.get("allowedTiers") or []
            ineligible_tiers = sub.get("ineligibleTiers") or []
            if isinstance(allowed_tiers, list):
                for t in allowed_tiers:
                    if isinstance(t, dict) and t.get("isDefault"):
                        default_tier = t

        discovered_tier_id, discovered_tier_name = extract_tier_info(load_resp_data)

    print()
    print("  --- Extracted Entitlement Fields ---")
    print(f"  cloudaicompanionProject: {extracted_proj or '[NULL / NOT ASSIGNED]'}")
    print(f"  paidTier:                {json.dumps(sanitize_payload(paid_tier)) if paid_tier else '[NONE]'}")
    print(f"  currentTier:             {json.dumps(sanitize_payload(current_tier)) if current_tier else '[NONE]'}")
    print(f"  defaultTier:             {json.dumps(sanitize_payload(default_tier)) if default_tier else '[NONE]'}")
    print(f"  allowedTiers:            {json.dumps(sanitize_payload(allowed_tiers)) if allowed_tiers else '[NONE]'}")
    print(f"  ineligibleTiers:         {json.dumps(sanitize_payload(ineligible_tiers)) if ineligible_tiers else '[NONE]'}")
    print(f"  selectedTier:            id='{discovered_tier_id}', name='{discovered_tier_name}'")
    print()

    # Step 3: Quota Probe via fetchAvailableModels
    print("[DIAG 3/4] Probing Upstream Quota via fetchAvailableModels...")
    quota_url = "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
    project_to_test = extracted_proj or active.project_id or "aicode-consumers"
    try:
        q_resp = requests.post(quota_url, headers=headers, json={"project": project_to_test}, timeout=10)
        print(f"  Quota Endpoint:   {quota_url}")
        print(f"  Response Status:  HTTP {q_resp.status_code}")
        if q_resp.ok:
            models_dict = q_resp.json().get("models", {})
            print(f"  Total Models:     {len(models_dict)}")
            for test_mid in ("gemini-3.7-flash-low", "gemini-3.7-flash-tiered", "gemini-3.1-pro-low", "gemini-pro-agent", "claude-sonnet-4-6"):
                m_info = models_dict.get(test_mid)
                if m_info:
                    q_info = m_info.get("quotaInfo") or {}
                    rem = q_info.get("remainingFraction")
                    reset = q_info.get("resetTime")
                    print(f"    - {test_mid:<25} remaining={rem} (100% available) | reset={reset}")
        else:
            print(f"  Quota Error Body: {scrub_secrets(q_resp.text[:300])}")
    except Exception as e:
        print(f"  fetchAvailableModels Error: {e}")
    print()

    # Step 4: Model generation probes (Flash and Pro, with and without credits)
    print("[DIAG 4/4] Probing Model Generation Endpoints (Flash & Pro, standard & credits)...")
    from antigravity.client import STREAM_ENDPOINTS

    test_models = [
        ("Flash (gemini-3.7-flash-low)", "gemini-3.7-flash-low"),
        ("Pro (gemini-3.1-pro-low)", "gemini-3.1-pro-low"),
    ]

    for model_label, model_id in test_models:
        upstream_id = resolve_model_id(model_id)
        print(f"\n  --- Testing Model: {model_label} (Upstream: {upstream_id}, Project: {project_to_test}) ---")

        for use_credits in (False, True):
            credit_label = "WITH credits (GOOGLE_ONE_AI)" if use_credits else "WITHOUT credits"
            print(f"\n  [Probe: {model_label} -> {credit_label}]")

            envelope = {
                "project": project_to_test,
                "model": upstream_id,
                "userAgent": "antigravity",
                "requestType": "agent",
                "requestId": f"agent/{int(time.time()*1000)}/{uuid.uuid4().hex[:8]}",
                "request": {
                    "contents": [{"role": "user", "parts": [{"text": "Reply with 'OK'"}]}],
                    "sessionId": f"-{int(time.time()*1000000) % 9000000000000000000}",
                    "generationConfig": {
                        "topK": 40,
                        "topP": 1.0,
                    },
                },
            }
            if use_credits:
                envelope["enabledCreditTypes"] = ["GOOGLE_ONE_AI"]

            gen_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "User-Agent": ua_darwin,
            }

            safe_envelope = sanitize_payload(envelope)
            print(f"  Envelope:       {json.dumps(safe_envelope)}")

            for stream_url in STREAM_ENDPOINTS:
                print(f"  Trying URL:     {stream_url}")
                try:
                    m_resp = requests.post(stream_url, headers=gen_headers, json=envelope, timeout=15, stream=True)
                    print(f"    Status:       HTTP {m_resp.status_code}")
                    lines = []
                    for line in m_resp.iter_lines():
                        if line:
                            lines.append(line.decode("utf-8", errors="replace"))
                        if len(lines) >= 3:
                            break
                    first_content = "\n".join(lines)
                    print(f"    Response:     {scrub_secrets(first_content[:400])}")
                    if m_resp.status_code == 200:
                        print("    ✓ Stream response received successfully!")
                        break
                except Exception as e:
                    print(f"    Error:        {e}")

    print()
    print("=" * 70)
    print("  Diagnostic Run Completed")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        prog="antigravity",
        description="Standalone Google Antigravity Authentication & Client Provider",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # auth
    auth_parser = subparsers.add_parser("auth", help="Authenticate a Google account")
    auth_parser.add_argument("--host", default=None, help=f"OAuth host (default: {DEFAULT_OAUTH_HOST})")
    auth_parser.add_argument("--port", type=int, default=None, help=f"OAuth port (default: {DEFAULT_OAUTH_PORT})")
    auth_parser.add_argument("--prompt", default="select_account consent", help="OAuth prompt mode")

    # list
    subparsers.add_parser("list", help="List stored accounts")

    # switch
    switch_parser = subparsers.add_parser("switch", help="Switch active account")
    switch_parser.add_argument("email", help="Account email address")

    # test
    test_parser = subparsers.add_parser("test", help="Test active account and inference")
    test_parser.add_argument("-m", "--model", default="gemini-3.7-flash-low", help="Model to test")

    # status
    subparsers.add_parser("status", help="Show active connection status")

    # debug
    subparsers.add_parser("debug", help="Run comprehensive safe diagnostics on active account")

    args = parser.parse_args()
    if args.command == "auth":
        cmd_auth(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "switch":
        cmd_switch(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "debug":
        cmd_debug(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

