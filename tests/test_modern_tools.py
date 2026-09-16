"""
Tests for the modernized OperatingSystem tools and Google OAuth module.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOperatingSystem(unittest.TestCase):
    """Unit tests for the modernized OperatingSystem class."""

    def setUp(self):
        with patch("pyautogui.size", return_value=(1920, 1080)):
            from operate.utils.operating_system import OperatingSystem
            self.os = OperatingSystem()

    def test_has_all_methods(self):
        """Verify all 12 modern methods exist."""
        methods = [
            "mouse", "click_at_percentage", "double_click", "right_click",
            "middle_click", "write", "paste", "press", "scroll", "wait",
            "launch", "drag",
        ]
        for method in methods:
            self.assertTrue(hasattr(self.os, method), f"Missing method: {method}")

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.click")
    def test_mouse_click(self, mock_click, mock_size):
        """Test basic left click at percentage coordinates."""
        self.os.mouse({"x": 0.5, "y": 0.5})
        mock_click.assert_called_once_with(960, 540)

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.doubleClick")
    def test_double_click(self, mock_double, mock_size):
        """Test double-click at percentage coordinates."""
        self.os.double_click({"x": 0.25, "y": 0.75})
        mock_double.assert_called_once_with(480, 810)

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.rightClick")
    def test_right_click(self, mock_right, mock_size):
        """Test right-click at percentage coordinates."""
        self.os.right_click({"x": 0.1, "y": 0.9})
        mock_right.assert_called_once_with(192, 972)

    @patch("pyautogui.size", return_value=(1920, 1080))
    @patch("pyautogui.middleClick")
    def test_middle_click(self, mock_middle, mock_size):
        """Test middle-click."""
        self.os.middle_click({"x": 0.5, "y": 0.5})
        mock_middle.assert_called_once_with(960, 540)

    @patch("pyautogui.press")
    def test_press_single_key(self, mock_press):
        """Test pressing a single key."""
        self.os.press(["enter"])
        mock_press.assert_called_once_with("enter")

    @patch("pyautogui.hotkey")
    def test_press_hotkey(self, mock_hotkey):
        """Test pressing a key combination."""
        self.os.press(["ctrl", "l"])
        mock_hotkey.assert_called_once_with("ctrl", "l")

    @patch("pyautogui.scroll")
    def test_scroll_down(self, mock_scroll):
        """Test scrolling down."""
        self.os.scroll(direction="down", amount=5)
        mock_scroll.assert_called_once_with(-5)

    @patch("pyautogui.scroll")
    def test_scroll_up(self, mock_scroll):
        """Test scrolling up."""
        self.os.scroll(direction="up", amount=3)
        mock_scroll.assert_called_once_with(3)

    @patch("time.sleep")
    def test_wait(self, mock_sleep):
        """Test explicit wait."""
        self.os.wait(2.5)
        mock_sleep.assert_called_once_with(2.5)

    @patch("time.sleep")
    def test_wait_minimum(self, mock_sleep):
        """Test wait enforces minimum 0.1s."""
        self.os.wait(0.01)
        mock_sleep.assert_called_once_with(0.1)

    @patch("os.startfile", create=True)
    @patch("time.sleep")
    def test_launch_windows(self, mock_sleep, mock_startfile):
        """Test launching an app on Windows uses resolved executable."""
        with patch("platform.system", return_value="Windows"):
            self.os.launch("notepad")
            mock_startfile.assert_called_once()
            # Verify the resolved path contains notepad
            called_arg = mock_startfile.call_args[0][0]
            self.assertIn("notepad", called_arg.lower())


class TestOperateDispatcher(unittest.TestCase):
    """Test that operate() dispatches all new action types correctly."""

    def test_dispatch_all_operation_types(self):
        """Verify all operation types are handled without hitting the 'unknown' branch."""
        from operate.operate import operate

        operation_types = [
            {"operation": "click", "x": 0.5, "y": 0.5},
            {"operation": "double_click", "x": 0.5, "y": 0.5},
            {"operation": "right_click", "x": 0.5, "y": 0.5},
            {"operation": "middle_click", "x": 0.5, "y": 0.5},
            {"operation": "paste", "content": "Hello World"},
            {"operation": "scroll", "direction": "down", "amount": 3},
            {"operation": "wait", "seconds": 0.1},
            {"operation": "launch", "target": "notepad"},
            {"operation": "write", "content": "test"},
            {"operation": "press", "keys": ["enter"]},
        ]

        for op in operation_types:
            with patch("operate.operate.operating_system") as mock_os:
                with patch("operate.operate.time"):
                    with patch("operate.operate.config") as mock_cfg:
                        mock_cfg.verbose = False
                        result = operate([op], "test-model")
                        self.assertFalse(result, f"Operation '{op['operation']}' should not signal done")

    def test_dispatch_done(self):
        """Verify 'done' operation returns True."""
        from operate.operate import operate

        with patch("operate.operate.operating_system"):
            with patch("operate.operate.time"):
                with patch("operate.operate.config") as mock_cfg:
                    mock_cfg.verbose = False
                    result = operate(
                        [{"operation": "done", "summary": "finished"}],
                        "test-model"
                    )
                    self.assertTrue(result)


class TestGoogleOAuthManager(unittest.TestCase):
    """Unit tests for GoogleOAuthManager."""

    def test_extract_code_from_raw(self):
        """Test extracting a raw authorization code."""
        from operate.utils.google_auth import GoogleOAuthManager
        code = GoogleOAuthManager.extract_code_from_input("4/0AanRRrsDkmKhIxGe_vDw")
        self.assertEqual(code, "4/0AanRRrsDkmKhIxGe_vDw")

    def test_extract_code_from_url(self):
        """Test extracting code from a callback URL."""
        from operate.utils.google_auth import GoogleOAuthManager
        url = "http://localhost:8080/callback?code=4/0AanRRrs&scope=openid"
        code = GoogleOAuthManager.extract_code_from_input(url)
        self.assertEqual(code, "4/0AanRRrs")

    def test_extract_code_empty_raises(self):
        """Test that empty input raises ValueError."""
        from operate.utils.google_auth import GoogleOAuthManager
        with self.assertRaises(ValueError):
            GoogleOAuthManager.extract_code_from_input("")

    def test_authorization_url_contains_required_params(self):
        """Test that auth URL includes offline access and consent prompt."""
        from operate.utils.google_auth import GoogleOAuthManager
        mgr = GoogleOAuthManager(client_id="test-id", client_secret="test-secret")
        url = mgr.get_authorization_url()
        self.assertIn("access_type=offline", url)
        self.assertIn("prompt=consent", url)
        self.assertIn("client_id=test-id", url)

    def test_is_authenticated_false_by_default(self):
        """Test that a fresh manager is not authenticated."""
        from operate.utils.google_auth import GoogleOAuthManager
        mgr = GoogleOAuthManager(client_id="test", client_secret="test")
        # Remove any existing token file
        self.assertFalse(mgr.is_authenticated() if not mgr._refresh_token else True)


class TestDPAPIEncryption(unittest.TestCase):
    """Test DPAPI encryption/decryption on Windows."""

    @unittest.skipUnless(sys.platform == "win32", "DPAPI only available on Windows")
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt -> decrypt returns original plaintext."""
        from operate.utils.google_auth import encrypt_token, decrypt_token
        original = "test-refresh-token-abc123"
        encrypted = encrypt_token(original)
        self.assertNotEqual(encrypted, original)
        decrypted = decrypt_token(encrypted)
        self.assertEqual(decrypted, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
