import functools
import os
import random
import time
from typing import Any, Callable, Optional

from operate.utils.style import ANSI_BRIGHT_MAGENTA, ANSI_GREEN, ANSI_RED, ANSI_YELLOW, ANSI_RESET

# Common transient HTTP status codes indicating server overload or temporary unavailability
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

# Keywords indicating model overload, rate limits, or server exhaustion
OVERLOAD_KEYWORDS = [
    "503",
    "overloaded",
    "high model usage",
    "resourceexhausted",
    "resource exhausted",
    "rate limit",
    "ratelimit",
    "rate_limit",
    "service unavailable",
    "temporarily unavailable",
    "deadline exceeded",
    "try again later",
    "internal server error",
]


def is_retryable_exception(exc: Exception) -> bool:
    """
    Check if an exception represents a transient overload or network/server error
    that should be automatically retried (e.g., Google 503 model overloaded, 429 rate limit).
    """
    if exc is None:
        return False

    # Check status_code or code attribute (common in openai and google-api exceptions)
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(exc, "code", None)
        if callable(status_code):
            try:
                status_code = status_code()
            except Exception:
                status_code = None

    if status_code is None and hasattr(exc, "response"):
        resp = getattr(exc, "response", None)
        status_code = getattr(resp, "status_code", None)

    if status_code is not None:
        try:
            if int(status_code) in TRANSIENT_STATUS_CODES:
                return True
        except (ValueError, TypeError):
            pass

    # Check exception class names commonly associated with transient issues
    cls_name = exc.__class__.__name__
    transient_class_names = {
        "ServiceUnavailable",
        "ResourceExhausted",
        "InternalServerError",
        "BadGateway",
        "GatewayTimeout",
        "RateLimitError",
        "APIConnectionError",
        "APITimeoutError",
        "Timeout",
        "ConnectionError",
        "TransientServerError",
    }
    if cls_name in transient_class_names:
        return True

    # Check exception message, repr, and body content
    msg_parts = [
        str(exc),
        repr(exc),
        str(getattr(exc, "message", "")),
        str(getattr(exc, "body", "")),
    ]
    combined_msg = " ".join(msg_parts).lower()
    for kw in OVERLOAD_KEYWORDS:
        if kw in combined_msg:
            return True

    return False


def retry_with_backoff(
    func: Optional[Callable] = None,
    *,
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    caller_name: str = "Model API",
    **call_kwargs: Any,
) -> Any:
    """
    Execute a callable with automatic retry and exponential backoff + jitter
    when transient errors (e.g. 503 High Model Usage / Overloaded) occur.

    Can be used either directly:
        response = retry_with_backoff(client.chat.completions.create, model="...", messages=[...])
    or as a decorator:
        @retry_with_backoff(max_retries=5, caller_name="Google Gemini")
        def my_call(...): ...

    Configuration via environment variables:
        OPERATE_MAX_RETRIES: default 5
        OPERATE_RETRY_BASE_DELAY: default 2.0 (seconds)
        OPERATE_RETRY_MAX_DELAY: default 60.0 (seconds)
    """
    # Resolve default configurations
    if max_retries is None:
        try:
            max_retries = int(os.getenv("OPERATE_MAX_RETRIES", "5"))
        except ValueError:
            max_retries = 5

    if base_delay is None:
        try:
            base_delay = float(os.getenv("OPERATE_RETRY_BASE_DELAY", "2.0"))
        except ValueError:
            base_delay = 2.0

    if max_delay is None:
        try:
            max_delay = float(os.getenv("OPERATE_RETRY_MAX_DELAY", "60.0"))
        except ValueError:
            max_delay = 60.0

    def run_with_retry(target_func: Callable, *args: Any, **kwargs: Any) -> Any:
        attempts = 0
        while True:
            try:
                return target_func(*args, **kwargs)
            except Exception as exc:
                attempts += 1
                if not is_retryable_exception(exc) or attempts > max_retries:
                    # Not a transient error or retries exhausted
                    if attempts > max_retries and is_retryable_exception(exc):
                        print(
                            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[{caller_name}] Exceeded maximum retry attempts ({max_retries}). Last error: {exc}{ANSI_RESET}"
                        )
                    raise

                # Calculate exponential backoff with jitter: delay = min(base * 2^(attempt-1), max_delay)
                delay = min(base_delay * (2 ** (attempts - 1)), max_delay)
                # Add +/- 20% random jitter
                jitter = delay * random.uniform(-0.2, 0.2)
                sleep_time = max(0.5, delay + jitter)

                print(
                    f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[{caller_name}] Model server overloaded or busy (503/transient). "
                    f"Retrying in {sleep_time:.1f}s (Attempt {attempts}/{max_retries})...{ANSI_RESET}"
                )
                time.sleep(sleep_time)

    # If called as a direct wrapper: retry_with_backoff(func, *args, **call_kwargs)
    if func is not None and callable(func):
        if call_kwargs or len(call_kwargs) > 0:
            return run_with_retry(func, **call_kwargs)
        # Check if caller passed func and extra positional args were meant as decorator or immediate call
        return functools.wraps(func)(lambda *a, **k: run_with_retry(func, *a, **k))

    # Called as decorator factory: @retry_with_backoff(...)
    def decorator(target: Callable) -> Callable:
        @functools.wraps(target)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return run_with_retry(target, *args, **kwargs)

        return wrapper

    return decorator


def call_with_retry(
    func: Callable,
    *args: Any,
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    caller_name: str = "Model API",
    **kwargs: Any,
) -> Any:
    """
    Explicit direct execution helper for functions with arguments:
        call_with_retry(client.chat.completions.create, model="...", messages=messages)
    """
    decorator = retry_with_backoff(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        caller_name=caller_name,
    )
    return decorator(func)(*args, **kwargs)
