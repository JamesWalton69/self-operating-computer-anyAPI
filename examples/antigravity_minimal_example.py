"""
Minimal Example: Using the Standalone Google Antigravity Provider with SOC.

This script demonstrates:
1. Loading the stored Google Antigravity account without OmniRoute or 'agy'.
2. Automatic token validation & refresh.
3. Sending a multimodal generation request to Google Cloud Code / Antigravity.
4. Parsing structured actions for Self-Operating Computer (SOC).
"""

import os
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import antigravity


def main():
    print("=" * 60)
    print("  Self-Operating Computer (SOC) - Antigravity Minimal Example")
    print("=" * 60)

    # 1. Check for authenticated accounts
    accounts = antigravity.list_accounts()
    if not accounts:
        print("\nNo Google account connected yet.")
        print("To authenticate a Google account, run:")
        print("    python -m soc.antigravity auth")
        return

    # 2. Get client for the active account
    client = antigravity.get_client()
    account = client.account

    print(f"\nActive Account:  {account.email}")
    print(f"Project ID:      {account.project_id or 'aicode-consumers'}")
    print(f"Subscription:    {account.tier}")
    print(f"Token Expiry:    {int(account.expires_at)} (auto-refreshed on demand)")

    # 3. Example 1: Direct text generation
    print("\n--- Example 1: Multimodal Query ---")
    prompt = "Explain in 1 concise sentence what Self-Operating Computer does."
    model = "gemini-3.7-flash-low"
    print(f"Prompt: '{prompt}' | Model: {model}")

    try:
        response = client.generate(prompt=prompt, model=model)
        candidates = response.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            print(f"Response:\n{text.strip()}")
        else:
            print("Response:", response)
    except Exception as e:
        print(f"Error during generation: {e}")

    # 4. Example 2: Parsing SOC action operations
    print("\n--- Example 2: Structured Operation Generation ---")
    action_prompt = (
        "Objective: Open Microsoft Edge.\n"
        "Return a JSON array of actions with format [{\"operation\": \"click\", \"x\": 50, \"y\": 50}]."
    )
    try:
        operations = client.generate_operations(prompt=action_prompt, model=model)
        print("Parsed SOC Operations:")
        for op in operations:
            print(f"  -> {op}")
    except Exception as e:
        print(f"Error during operation generation: {e}")

    print("\n✓ Standalone Antigravity pipeline demonstration complete.")


if __name__ == "__main__":
    main()
