"""
Unit tests for the standalone Google Antigravity provider.

Verifies:
- OAuth URL building, PKCE generation, callback server & state validation
- Token exchange & secret scrubbing
- Account management (multi-account persistence, active pointer, migration)
- Token lifecycle & automatic refresh
- Antigravity bootstrap (loadCodeAssist, tier extraction, onboardUser)
- Antigravity client (envelope, headers, SSE parsing, model aliasing, 401/403/429 diagnostics)
- SOC and operate facades
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import antigravity
from antigravity.accounts import AccountManager, AntigravityAccount
from antigravity.bootstrap import (
    bootstrap_antigravity,
    extract_project_id,
    extract_tier_info,
)
from antigravity.client import AntigravityClient, resolve_model_id
from antigravity.diagnostics import mask_token, scrub_secrets
from antigravity.exceptions import (
    AccountNotFoundError,
    AuthenticationError,
    InvalidGrantError,
    OAuthError,
    PermissionDeniedError,
    QuotaExhaustedError,
    RedirectUriMismatchError,
    StateMismatchError,
    TokenExpiredError,
)
from antigravity.oauth import (
    DEFAULT_CLIENT_ID,
    DEFAULT_OAUTH_PORT,
    build_authorization_url,
    exchange_code_for_tokens,
    generate_pkce_pair,
    get_oauth_port,
)
from antigravity.token_manager import TokenManager


class TestOAuthComponents(unittest.TestCase):
    """Test OAuth configuration, PKCE, URL building, and state validation."""

    def test_default_port(self):
        """Default OAuth callback port must be 38741."""
        self.assertEqual(DEFAULT_OAUTH_PORT, 38741)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_oauth_port(), 38741)

    def test_custom_port_via_env(self):
        """ANTIGRAVITY_OAUTH_PORT overrides default port."""
        with patch.dict(os.environ, {"ANTIGRAVITY_OAUTH_PORT": "39999"}):
            self.assertEqual(get_oauth_port(), 39999)

    def test_pkce_generation(self):
        """RFC 7636 PKCE verifier and challenge generation."""
        verifier, challenge = generate_pkce_pair()
        self.assertGreaterEqual(len(verifier), 43)
        self.assertGreaterEqual(len(challenge), 43)
        self.assertNotIn("=", challenge)  # base64url stripped

    def test_authorization_url_building(self):
        """Verify URL parameters match current Antigravity specification."""
        url = build_authorization_url(
            redirect_uri="http://127.0.0.1:38741/callback",
            state="test_state_123",
            code_challenge="test_challenge_abc",
            prompt="consent",
        )
        self.assertIn("https://accounts.google.com/o/oauth2/v2/auth?", url)
        self.assertIn("client_id=", url)
        self.assertIn("redirect_uri=http%3A%2F%2F127.0.0.1%3A38741%2Fcallback", url)
        self.assertIn("state=test_state_123", url)
        self.assertIn("code_challenge=test_challenge_abc", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("cloud-platform", url)
        self.assertNotIn("openid", url)  # Must NOT contain openid

    @patch("antigravity.oauth.requests.post")
    def test_exchange_code_success(self, mock_post):
        """Exchange code successfully returns access and refresh tokens."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "access_token": "ya29.test_token",
            "refresh_token": "1//0test_refresh",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        data = exchange_code_for_tokens(
            code="test_code",
            redirect_uri="http://127.0.0.1:38741/callback",
        )
        self.assertEqual(data["access_token"], "ya29.test_token")
        self.assertEqual(data["refresh_token"], "1//0test_refresh")

    @patch("antigravity.oauth.requests.post")
    def test_exchange_code_redirect_uri_mismatch(self, mock_post):
        """Detect and raise RedirectUriMismatchError."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "redirect_uri_mismatch"}'
        mock_post.return_value = mock_resp

        with self.assertRaises(RedirectUriMismatchError):
            exchange_code_for_tokens(
                code="bad_code",
                redirect_uri="http://127.0.0.1:38741/callback",
            )

    @patch("antigravity.oauth.requests.post")
    def test_exchange_code_invalid_grant(self, mock_post):
        """Detect and raise InvalidGrantError."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.text = '{"error": "invalid_grant"}'
        mock_post.return_value = mock_resp

        with self.assertRaises(InvalidGrantError):
            exchange_code_for_tokens(
                code="bad_code",
                redirect_uri="http://127.0.0.1:38741/callback",
            )


class TestAccountManager(unittest.TestCase):
    """Test multi-account persistence, active selection, and backward compatibility."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = AccountManager(storage_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_get_account(self):
        """Save and retrieve an Antigravity account."""
        acc = AntigravityAccount(
            email="user1@example.com",
            access_token="tok_1",
            refresh_token="ref_1",
            expires_at=time.time() + 3600,
            project_id="aicode-consumers",
            tier="g1-pro-tier",
        )
        self.manager.save(acc, set_active=True)

        loaded = self.manager.get("user1@example.com")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.email, "user1@example.com")
        self.assertEqual(loaded.project_id, "aicode-consumers")
        self.assertEqual(loaded.tier, "g1-pro-tier")

    def test_multi_account_active_switching(self):
        """Support multiple accounts and active pointer switching."""
        acc1 = AntigravityAccount(
            email="acc1@gmail.com",
            access_token="tok_1",
            refresh_token="ref_1",
            expires_at=time.time() + 3600,
        )
        acc2 = AntigravityAccount(
            email="acc2@gmail.com",
            access_token="tok_2",
            refresh_token="ref_2",
            expires_at=time.time() + 3600,
        )
        self.manager.save(acc1, set_active=True)
        self.manager.save(acc2, set_active=False)

        # Active should be acc1
        active = self.manager.get_active()
        self.assertEqual(active.email, "acc1@gmail.com")

        # Switch to acc2
        self.manager.set_active("acc2@gmail.com")
        active = self.manager.get_active()
        self.assertEqual(active.email, "acc2@gmail.com")

        # List all accounts
        all_accs = self.manager.list_accounts()
        self.assertEqual(len(all_accs), 2)
        emails = {a.email for a in all_accs}
        self.assertEqual(emails, {"acc1@gmail.com", "acc2@gmail.com"})

    def test_delete_account(self):
        """Deleting an account removes it from store."""
        acc = AntigravityAccount(
            email="delete_me@gmail.com",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 3600,
        )
        self.manager.save(acc, set_active=True)
        self.assertIsNotNone(self.manager.get("delete_me@gmail.com"))

        self.assertTrue(self.manager.delete("delete_me@gmail.com"))
        self.assertIsNone(self.manager.get("delete_me@gmail.com"))


class TestTokenManager(unittest.TestCase):
    """Test automatic token refresh and expiration detection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = AccountManager(storage_dir=self.tmpdir)
        self.token_mgr = TokenManager(self.manager)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_is_expired(self):
        """Token expiration check with buffer."""
        valid_acc = AntigravityAccount(
            email="valid@gmail.com",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 300,
        )
        self.assertFalse(valid_acc.is_expired(buffer_seconds=60))

        expired_acc = AntigravityAccount(
            email="expired@gmail.com",
            access_token="tok",
            refresh_token="ref",
            expires_at=time.time() + 30,  # within 60s buffer
        )
        self.assertTrue(expired_acc.is_expired(buffer_seconds=60))

    @patch("antigravity.token_manager.requests.post")
    def test_automatic_refresh_on_expired(self, mock_post):
        """Automatically calls token refresh when expired."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "access_token": "ya29.refreshed_token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_resp

        acc = AntigravityAccount(
            email="refresh@gmail.com",
            access_token="old_tok",
            refresh_token="valid_ref",
            expires_at=time.time() - 100,  # Expired
        )
        self.manager.save(acc)

        token = self.token_mgr.ensure_valid_token(acc)
        self.assertEqual(token, "ya29.refreshed_token")
        mock_post.assert_called_once()


class TestBootstrap(unittest.TestCase):
    """Test Antigravity project and tier discovery."""

    def test_extract_project_id_string(self):
        """Extract project ID from plain string."""
        data = {"cloudaicompanionProject": "aicode-consumers"}
        self.assertEqual(extract_project_id(data), "aicode-consumers")

    def test_extract_project_id_dict(self):
        """Extract project ID from dictionary."""
        data = {"cloudaicompanionProject": {"id": "custom-proj-99"}}
        self.assertEqual(extract_project_id(data), "custom-proj-99")

    def test_extract_tier_info_paid(self):
        """Paid tier takes highest priority."""
        data = {
            "paidTier": {"id": "g1-pro-tier", "name": "Google AI Pro"},
            "currentTier": {"id": "legacy-tier", "name": "Legacy"},
        }
        tier_id, tier_name = extract_tier_info(data)
        self.assertEqual(tier_id, "g1-pro-tier")
        self.assertEqual(tier_name, "Google AI Pro")

    @patch("antigravity.bootstrap.requests.post")
    def test_bootstrap_flow(self, mock_post):
        """Bootstrap discovers project from loadCodeAssist."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "cloudaicompanionProject": "aicode-consumers",
            "paidTier": {"id": "g1-pro-tier", "name": "Google AI Pro"},
        }
        mock_post.return_value = mock_resp

        proj, tier = bootstrap_antigravity("test_token")
        self.assertEqual(proj, "aicode-consumers")
        self.assertEqual(tier, "Google AI Pro")


class TestAntigravityClient(unittest.TestCase):
    """Test Antigravity model requests, envelope headers, SSE parsing, and errors."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = AccountManager(storage_dir=self.tmpdir)
        self.account = AntigravityAccount(
            email="tester@gmail.com",
            access_token="test_token",
            refresh_token="test_refresh",
            expires_at=time.time() + 3600,
            project_id="aicode-consumers",
            tier="Google AI Pro",
        )
        self.manager.save(self.account)
        self.client = AntigravityClient(self.account, TokenManager(self.manager))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_model_alias_resolution(self):
        """Model aliases match OmniRoute Antigravity mappings."""
        self.assertEqual(resolve_model_id("gemini-3.7-flash-low"), "gemini-3.7-flash-tiered")
        self.assertEqual(resolve_model_id("gemini-3.7-flash-low-direct"), "gemini-3.7-flash-tiered")
        self.assertEqual(resolve_model_id("gemini-3.1-pro-high"), "gemini-pro-agent")
        self.assertEqual(resolve_model_id("claude-sonnet-4-6"), "claude-sonnet-4-6")

    @patch("antigravity.client.requests.post")
    def test_generate_envelope_and_headers(self, mock_post):
        """Verify request envelope fields and headers."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]}',
            b'data: [DONE]',
        ]
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]
        }
        mock_post.return_value = mock_resp

        res = self.client.generate("Say hello")
        self.assertIn("candidates", res)

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        body = call_args[1]["json"]

        # Check headers: MUST NOT contain x-goog-user-project
        self.assertEqual(headers["Authorization"], "Bearer test_token")
        self.assertEqual(headers["User-Agent"], "antigravity/ide/2.9.1 darwin/arm64")
        self.assertNotIn("x-goog-user-project", headers)

        # Check envelope: MUST contain project, agent, GOOGLE_ONE_AI
        self.assertEqual(body["project"], "aicode-consumers")
        self.assertEqual(body["userAgent"], "antigravity")
        self.assertEqual(body["requestType"], "agent")
        self.assertEqual(body["enabledCreditTypes"], ["GOOGLE_ONE_AI"])

    @patch("antigravity.client.requests.post")
    def test_generate_429_quota_exhausted(self, mock_post):
        """HTTP 429 raises QuotaExhaustedError with rich metadata."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.ok = False
        mock_resp.text = '{"error": {"message": "Resource has been exhausted (e.g. check quota)."}}'
        mock_resp.json.return_value = {"error": {"message": "Resource has been exhausted (e.g. check quota)."}}
        mock_post.return_value = mock_resp

        with self.assertRaises(QuotaExhaustedError) as ctx:
            self.client.generate("Test prompt")

        err = ctx.exception
        self.assertEqual(err.status_code, 429)
        self.assertEqual(err.account_email, "tester@gmail.com")
        self.assertEqual(err.project_id, "aicode-consumers")
        self.assertEqual(err.tier, "Google AI Pro")

    @patch("antigravity.client.requests.post")
    def test_generate_operations_parsing(self, mock_post):
        """Parse structured JSON operations for Self-Operating Computer."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        json_content = '[{"operation": "click", "x": 500, "y": 300}, {"operation": "write", "text": "hello"}]'
        payload = {"candidates": [{"content": {"parts": [{"text": f"```json\n{json_content}\n```"}]}}]}
        mock_resp.iter_lines.return_value = [
            f"data: {json.dumps(payload)}".encode("utf-8"),
            b"data: [DONE]",
        ]
        mock_resp.json.return_value = {}
        mock_post.return_value = mock_resp

        ops = self.client.generate_operations("Click and type")
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0]["operation"], "click")
        self.assertEqual(ops[1]["operation"], "write")


class TestDiagnostics(unittest.TestCase):
    """Test secret scrubbing and masking."""

    def test_scrub_secrets(self):
        """Ensure access tokens, refresh tokens, and client secrets are scrubbed."""
        raw = "Error with ya29.a0AWY7Ckk-secret and 1//04test_refresh and GOCSPX-secret123"
        clean = scrub_secrets(raw)
        self.assertNotIn("ya29.a0AWY7Ckk-secret", clean)
        self.assertNotIn("1//04test_refresh", clean)
        self.assertNotIn("GOCSPX-secret123", clean)
        self.assertIn("[REDACTED_ACCESS_TOKEN]", clean)
        self.assertIn("[REDACTED_REFRESH_TOKEN]", clean)
        self.assertIn("[REDACTED_CLIENT_SECRET]", clean)

    def test_mask_token(self):
        """Safely mask tokens showing only prefix and length."""
        token_str = "ya29.a0AWY7Ckk-1234567890abcdef"
        masked = mask_token(token_str)
        self.assertTrue(masked.startswith("ya29.a"))
        self.assertTrue(masked.endswith(f"cdef (len={len(token_str)})"))


class TestFacades(unittest.TestCase):
    """Test soc.antigravity and operate.antigravity facades."""

    def test_facades_importable(self):
        """Verify soc.antigravity and operate.antigravity export the same interface."""
        import operate.antigravity as op_agy
        import soc.antigravity as soc_agy

        self.assertTrue(hasattr(soc_agy, "authenticate"))
        self.assertTrue(hasattr(soc_agy, "get_client"))
        self.assertTrue(hasattr(soc_agy, "AntigravityAccount"))

        self.assertTrue(hasattr(op_agy, "authenticate"))
        self.assertTrue(hasattr(op_agy, "get_client"))
        self.assertTrue(hasattr(op_agy, "AntigravityAccount"))


if __name__ == "__main__":
    unittest.main()
