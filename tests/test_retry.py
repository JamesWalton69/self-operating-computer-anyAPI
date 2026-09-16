import unittest
from unittest.mock import MagicMock, patch
from operate.utils.retry import (
    is_retryable_exception,
    retry_with_backoff,
    call_with_retry,
    TRANSIENT_STATUS_CODES,
)


class MockAPIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class TestRetry(unittest.TestCase):
    def test_is_retryable_status_codes(self):
        for code in [503, 429, 500, 502, 504]:
            err = MockAPIError("Error occurred", status_code=code)
            self.assertTrue(is_retryable_exception(err), f"Expected {code} to be retryable")

    def test_non_retryable_status_codes(self):
        for code in [400, 401, 403, 404]:
            err = MockAPIError("Client Error", status_code=code)
            self.assertFalse(is_retryable_exception(err), f"Expected {code} to NOT be retryable")

    def test_is_retryable_message_keywords(self):
        messages = [
            "The model is overloaded. Please try again later.",
            "ResourceExhausted: 429 Resource has been exhausted (e.g. check quota).",
            "High model usage. Please retry.",
            "Service Unavailable: 503 Server Busy",
            "Deadline Exceeded in backend connection",
        ]
        for msg in messages:
            err = Exception(msg)
            self.assertTrue(is_retryable_exception(err), f"Expected '{msg}' to be retryable")

    @patch("time.sleep", return_value=None)
    def test_immediate_success_no_retries(self, mock_sleep):
        mock_func = MagicMock(return_value="success_result")
        result = call_with_retry(mock_func, max_retries=3, base_delay=0.1)
        self.assertEqual(result, "success_result")
        self.assertEqual(mock_func.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep", return_value=None)
    def test_retry_on_503_eventual_success(self, mock_sleep):
        mock_func = MagicMock(
            side_effect=[
                MockAPIError("The model is overloaded. Please try again later.", status_code=503),
                MockAPIError("503 Service Unavailable", status_code=503),
                {"choices": [{"message": {"content": "ok"}}]},
            ]
        )
        result = call_with_retry(mock_func, max_retries=3, base_delay=0.1)
        self.assertEqual(result, {"choices": [{"message": {"content": "ok"}}]})
        self.assertEqual(mock_func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_retry_exhausted_raises_exception(self, mock_sleep):
        mock_func = MagicMock(
            side_effect=MockAPIError("503 Model Overloaded", status_code=503)
        )
        with self.assertRaises(MockAPIError):
            call_with_retry(mock_func, max_retries=2, base_delay=0.1)
        # Attempt 1, Attempt 2 (retried), Attempt 3 (final attempt, max_retries=2 means 1 initial + 2 retries = 3 calls)
        self.assertEqual(mock_func.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_non_retryable_error_aborts_immediately(self, mock_sleep):
        mock_func = MagicMock(
            side_effect=MockAPIError("401 Unauthorized: Invalid API key", status_code=401)
        )
        with self.assertRaises(MockAPIError):
            call_with_retry(mock_func, max_retries=5, base_delay=0.1)
        self.assertEqual(mock_func.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
