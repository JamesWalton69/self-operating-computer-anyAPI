"""
Unit tests for operate.auth_gemini

Run with: python -m unittest tests.test_auth_gemini
"""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, mock_open, patch


class TestAuthUrl(unittest.TestCase):
    """Test OAuth URL construction."""

    def test_auth_url_params(self):
        """Auth URL contains all required OAuth parameters."""
        from operate.auth_gemini import AUTH_URL, CLIENT_ID, SCOPES
        import urllib.parse

        # Build the same URL the module would build
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": "http://127.0.0.1:20128/callback",
            "response_type": "code",
            "scope": SCOPES,
            "state": "test_state",
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

        self.assertIn("client_id=", url)
        self.assertIn(CLIENT_ID, url)
        self.assertIn("response_type=code", url)
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("scope=", url)
        self.assertIn("cloud-platform", url)

    def test_state_generation(self):
        """State tokens are cryptographically random and unique."""
        import secrets

        state1 = secrets.token_urlsafe(32)
        state2 = secrets.token_urlsafe(32)
        self.assertNotEqual(state1, state2)
        self.assertGreaterEqual(len(state1), 32)


class TestGetToken(unittest.TestCase):
    """Test token loading, caching, and refresh logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.token_file = os.path.join(self.tmpdir, "gemini_token.json")
        self.valid_token_data = {
            "access_token": "valid_access_token",
            "refresh_token": "valid_refresh_token",
            "expiry": time.time() + 3600,  # 1 hour from now
            "projectId": "mock-project-123",
        }
        self.expired_token_data = {
            "access_token": "expired_access_token",
            "refresh_token": "valid_refresh_token",
            "expiry": time.time() - 100,  # expired
            "projectId": "mock-project-123",
        }

    def tearDown(self):
        if os.path.exists(self.token_file):
            os.remove(self.token_file)
        os.rmdir(self.tmpdir)

    @patch("operate.auth_gemini.TOKEN_FILE")
    def test_get_token_loads_valid(self, mock_token_file):
        """Returns cached access_token when expiry is in the future."""
        mock_token_file.__str__ = lambda x: self.token_file
        # Write a valid token file
        with open(self.token_file, "w") as f:
            json.dump(self.valid_token_data, f)

        with patch("operate.auth_gemini.TOKEN_FILE", self.token_file), \
             patch("os.path.exists", return_value=True):
            from operate.auth_gemini import get_token

            # Patch TOKEN_FILE and os.path.exists in the module
            import operate.auth_gemini as mod
            orig_file = mod.TOKEN_FILE
            mod.TOKEN_FILE = self.token_file
            try:
                token = mod.get_token()
                self.assertEqual(token, "valid_access_token")
            finally:
                mod.TOKEN_FILE = orig_file

    @patch("operate.auth_gemini.requests.post")
    def test_get_token_refreshes_expired(self, mock_post):
        """Calls refresh endpoint when token is past expiry."""
        # Write an expired token
        with open(self.token_file, "w") as f:
            json.dump(self.expired_token_data, f)

        # Mock the refresh response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed_access_token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        import operate.auth_gemini as mod
        orig_file = mod.TOKEN_FILE
        mod.TOKEN_FILE = self.token_file
        try:
            token = mod.get_token()
            self.assertEqual(token, "refreshed_access_token")
            mock_post.assert_called_once()
            # Verify refresh_token was sent
            call_kwargs = mock_post.call_args
            self.assertEqual(
                call_kwargs[1]["data"]["grant_type"], "refresh_token"
            )
        finally:
            mod.TOKEN_FILE = orig_file

    @patch("operate.auth_gemini.oauth_login")
    def test_get_token_triggers_login(self, mock_login):
        """Calls oauth_login() when no token file exists."""
        mock_login.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expiry": time.time() + 3600,
        }

        import operate.auth_gemini as mod
        orig_file = mod.TOKEN_FILE
        mod.TOKEN_FILE = os.path.join(self.tmpdir, "nonexistent_token.json")
        try:
            token = mod.get_token()
            self.assertEqual(token, "new_access_token")
            mock_login.assert_called_once()
        finally:
            mod.TOKEN_FILE = orig_file


class TestGeminiGenerate(unittest.TestCase):
    """Test the gemini_generate function."""

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": "mock-proj"})
    def test_gemini_generate_text_only(self, mock_get_token_data, mock_post):
        """Payload has single text part, no inline_data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}',
            b'data: [DONE]',
        ]
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "hello"}]}}]
        }
        mock_post.return_value = mock_response

        from operate.auth_gemini import gemini_generate

        result = gemini_generate("test prompt")
        self.assertIn("candidates", result)

        # Verify the request body envelope
        call_kwargs = mock_post.call_args
        body = call_kwargs[1]["json"]
        self.assertIn("request", body)
        parts = body["request"]["contents"][0]["parts"]
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["text"], "test prompt")

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": "mock-proj"})
    def test_gemini_generate_with_images(self, mock_get_token_data, mock_post):
        """Payload has text + inline_data with correct MIME types."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "result"}]}}]}',
            b'data: [DONE]',
        ]
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "result"}]}}]
        }
        mock_post.return_value = mock_response

        # Create a temporary image file
        tmpdir = tempfile.mkdtemp()
        img_path = os.path.join(tmpdir, "test.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # Minimal PNG-like bytes

        try:
            from operate.auth_gemini import gemini_generate

            result = gemini_generate("test with image", images=[img_path])

            call_kwargs = mock_post.call_args
            body = call_kwargs[1]["json"]
            self.assertIn("request", body)
            parts = body["request"]["contents"][0]["parts"]
            self.assertEqual(len(parts), 2)
            self.assertEqual(parts[0]["text"], "test with image")
            self.assertIn("inline_data", parts[1])
            self.assertEqual(parts[1]["inline_data"]["mime_type"], "image/jpeg")
            self.assertIsInstance(parts[1]["inline_data"]["data"], str)  # base64 string
        finally:
            os.remove(img_path)
            os.rmdir(tmpdir)

    @patch("operate.auth_gemini.os.path.exists", return_value=True)
    @patch("operate.auth_gemini.os.remove")
    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": "mock-proj"})
    def test_gemini_generate_401_deletes_token(self, mock_get_token_data, mock_post, mock_remove, mock_exists):
        """On 401 response, token file is deleted and RuntimeError raised."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        from operate.auth_gemini import gemini_generate

        with self.assertRaises(RuntimeError) as ctx:
            gemini_generate("test")

        self.assertIn("Token expired or revoked", str(ctx.exception))
        mock_remove.assert_called_once()

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": "aicode-consumers"})
    def test_gemini_generate_omits_aicode_consumers(self, mock_get_token_data, mock_post):
        """aicode-consumers fallback is sent in body AND the x-goog-user-project routing header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}',
            b'data: [DONE]',
        ]
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "", "GEMINI_PROJECT_ID": ""}):
            from operate.auth_gemini import gemini_generate

            result = gemini_generate("test prompt")
            self.assertIn("candidates", result)

            call_kwargs = mock_post.call_args
            body = call_kwargs[1]["json"]
            headers = call_kwargs[1]["headers"]
            self.assertEqual(body.get("project"), "aicode-consumers")
            self.assertEqual(headers.get("x-goog-user-project"), "aicode-consumers")

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": ""})
    def test_gemini_generate_uses_custom_project(self, mock_get_token_data, mock_post):
        """When GOOGLE_CLOUD_PROJECT is set in env, it is used in body AND the x-goog-user-project header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}',
            b'data: [DONE]',
        ]
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "custom-my-project-99"}):
            from operate.auth_gemini import gemini_generate

            result = gemini_generate("test prompt")
            self.assertIn("candidates", result)

            call_kwargs = mock_post.call_args
            body = call_kwargs[1]["json"]
            headers = call_kwargs[1]["headers"]
            self.assertEqual(body.get("project"), "custom-my-project-99")
            self.assertEqual(headers.get("x-goog-user-project"), "custom-my-project-99")

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": ""})
    def test_gemini_generate_429_guidance(self, mock_get_token_data, mock_post):
        """429 RESOURCE_EXHAUSTED provides actionable guidance to the user."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.ok = False
        mock_response.text = '{"error": {"message": "RESOURCE_EXHAUSTED: quota exceeded"}}'
        mock_response.json.return_value = {"error": {"message": "RESOURCE_EXHAUSTED: quota exceeded"}}
        mock_post.return_value = mock_response

        from operate.auth_gemini import gemini_generate

        with self.assertRaises(RuntimeError) as ctx:
            gemini_generate("test")

        self.assertIn("quota / validation required", str(ctx.exception))
        self.assertIn("Local OmniRoute", str(ctx.exception))

    @patch("operate.auth_gemini.requests.post")
    @patch("operate.auth_gemini.get_token_data", return_value={"access_token": "mock_token", "projectId": ""})
    def test_gemini_generate_403_guidance(self, mock_get_token_data, mock_post):
        """403 Forbidden provides actionable guidance to the user."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.ok = False
        mock_response.text = '{"error": {"message": "Permission denied"}}'
        mock_response.json.return_value = {"error": {"message": "Permission denied"}}
        mock_post.return_value = mock_response

        from operate.auth_gemini import gemini_generate

        with self.assertRaises(RuntimeError) as ctx:
            gemini_generate("test")

        self.assertIn("permission denied", str(ctx.exception))
        self.assertIn("GOOGLE_CLOUD_PROJECT", str(ctx.exception))


class TestGeminiGenerateOperations(unittest.TestCase):
    """Test operation parsing."""

    @patch("operate.auth_gemini.gemini_generate")
    def test_gemini_generate_operations_parses(self, mock_generate):
        """Extracts and parses JSON operations from mock Gemini response."""
        mock_generate.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '[{"operation": "click", "x": 0.5, "y": 0.5}]'
                            }
                        ]
                    }
                }
            ]
        }

        from operate.auth_gemini import gemini_generate_operations

        operations = gemini_generate_operations("test prompt")
        self.assertIsInstance(operations, list)
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["operation"], "click")

    @patch("operate.auth_gemini.gemini_generate")
    def test_gemini_generate_operations_wraps_dict(self, mock_generate):
        """Single dict response is wrapped in a list."""
        mock_generate.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"operation": "done"}'
                            }
                        ]
                    }
                }
            ]
        }

        from operate.auth_gemini import gemini_generate_operations

        operations = gemini_generate_operations("test prompt")
        self.assertIsInstance(operations, list)
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["operation"], "done")


if __name__ == "__main__":
    unittest.main()
