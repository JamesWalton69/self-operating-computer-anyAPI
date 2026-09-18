import os
import platform
import queue
import subprocess
import tempfile
import threading
import time
import pyautogui
from PIL import Image, ImageDraw, ImageGrab

try:
    import Xlib.display
    import Xlib.X
    import Xlib.Xutil
except ImportError:
    Xlib = None


_LATEST_SCREENSHOT = None
_SAVE_QUEUE = queue.Queue()
_WORKER_THREAD = None
_WORKER_LOCK = threading.Lock()


def _ensure_worker():
    """Ensure the background disk save worker thread is running."""
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = threading.Thread(
                target=_disk_save_worker, name="ScreenshotSaveWorker", daemon=True
            )
            _WORKER_THREAD.start()


def _write_image_to_disk(img, target_path):
    """Write an image to disk safely, handling directories and atomic replaces."""
    try:
        if not os.path.isabs(target_path):
            target_path = os.path.abspath(target_path)

        dir_name = os.path.dirname(target_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        temp_path = f"{target_path}.tmp.{os.getpid()}_{int(time.time() * 1000)}"
        try:
            img.save(temp_path, format="PNG")
            try:
                os.replace(temp_path, target_path)
            except Exception:
                # If replace fails on Windows due to file lock, fallback to direct save
                img.save(target_path, format="PNG")
        except Exception:
            img.save(target_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
    except Exception:
        pass


def _disk_save_worker():
    """Background worker that continuously writes queued screenshots to disk."""
    while True:
        try:
            item = _SAVE_QUEUE.get()
            if item is None:
                _SAVE_QUEUE.task_done()
                break
            img, target_path = item
            _write_image_to_disk(img, target_path)
        except Exception:
            pass
        finally:
            _SAVE_QUEUE.task_done()


def _save_to_disk_async(img, file_path=None):
    """Background disk write — doesn't block the hot path.
    Enqueues the image to a background worker queue."""
    if img is None:
        return
    if file_path is None:
        file_path = os.path.join("screenshots", "screenshot.png")

    _ensure_worker()

    try:
        img_copy = img.copy()
    except Exception:
        img_copy = img

    try:
        _SAVE_QUEUE.put_nowait((img_copy, file_path))
    except Exception:
        try:
            threading.Thread(
                target=_write_image_to_disk,
                args=(img_copy, file_path),
                daemon=True,
            ).start()
        except Exception:
            pass


def flush_screenshot_queue(timeout=2.0):
    """Wait for all pending screenshot disk saves to complete."""
    try:
        deadline = time.time() + timeout
        while _SAVE_QUEUE.unfinished_tasks > 0 and time.time() < deadline:
            time.sleep(0.02)
    except Exception:
        pass


def get_latest_screenshot():
    """Retrieve the most recently captured in-memory screenshot PIL Image."""
    global _LATEST_SCREENSHOT
    return _LATEST_SCREENSHOT


def capture_screen_fast(file_path=None):
    """Capture screen directly to RAM. No disk I/O in the hot path.

    Returns the in-memory PIL Image immediately, and enqueues an asynchronous
    disk save for GUI thumbnail / caching purposes.
    """
    global _LATEST_SCREENSHOT
    img = None
    target_path = (
        file_path
        if file_path is not None
        else os.path.join("screenshots", "screenshot.png")
    )

    # Primary: use mss (fastest, direct memory access)
    try:
        import mss

        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception:
        pass

    # Fallback 1: pyautogui
    if img is None:
        try:
            img = pyautogui.screenshot()
        except Exception:
            pass

    # Fallback 2: PIL ImageGrab
    if img is None:
        try:
            img = ImageGrab.grab()
        except Exception:
            pass

    # Fallback 3: previous cached screenshot or existing file from disk
    if img is None:
        if _LATEST_SCREENSHOT is not None:
            img = _LATEST_SCREENSHOT
        else:
            for fallback_file in [
                target_path,
                os.path.join("screenshots", "screenshot.png"),
            ]:
                if fallback_file and os.path.exists(fallback_file):
                    try:
                        img = Image.open(fallback_file).convert("RGB")
                        break
                    except Exception:
                        pass

    # Fallback 4: blank fallback canvas
    if img is None:
        img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))

    _LATEST_SCREENSHOT = img

    # Save to disk in background (for GUI thumbnail only)
    _save_to_disk_async(img, target_path)

    return img


def capture_screen_with_cursor(file_path):
    global _LATEST_SCREENSHOT
    user_platform = platform.system()

    # Normalize to absolute path using cwd if relative
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)

    dir_name = os.path.dirname(file_path)
    try:
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
    except Exception:
        pass

    target_path = file_path

    if user_platform == "Windows":
        screenshot = None
        # Primary: use mss (faster, no GDI dependency)
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception:
            pass

        # Fallback: pyautogui (slower, GDI-based)
        if screenshot is None:
            try:
                screenshot = pyautogui.screenshot()
            except Exception:
                pass

        if screenshot is None:
            if os.path.exists(target_path):
                try:
                    screenshot = Image.open(target_path)
                except Exception:
                    pass
            if screenshot is None:
                screenshot = Image.new("RGB", (1920, 1080), color=(30, 30, 30))

        _LATEST_SCREENSHOT = screenshot

        # Non-blocking disk write: return immediately so the hot path never waits
        # on PNG serialization. The file appears atomically via the background
        # worker; pixel consumers use get_latest_screenshot() or the in-memory
        # fallback in _encode_image_fast, and callers that read the path
        # synchronously use flush_screenshot_queue() first.
        _save_to_disk_async(screenshot, target_path)
        return target_path

    elif user_platform == "Linux":
        # Use xdotool to get the cursor position and Xlib to get the cursor image
        display = Xlib.display.Display()
        root = display.screen().root
        pointer = root.query_pointer()
        cursor_x = pointer.root_x
        cursor_y = pointer.root_y

        # Get the cursor image using Xfixes extension
        cursor_image = Xlib.Xfixes.get_cursor_image(display)
        cursor_width = cursor_image.width
        cursor_height = cursor_image.height
        xhot = cursor_image.xhot
        yhot = cursor_image.yhot

        # Convert the cursor image data to a PIL Image
        cursor_data = cursor_image.cursor_image
        cursor_img = Image.frombytes(
            "RGBA", (cursor_width, cursor_height), b"".join(cursor_data)
        )

        # Capture the screen using scrot
        subprocess.run(["scrot", "-z", file_path])

        # Paste the cursor image onto the screenshot
        img = Image.open(file_path)
        img.paste(
            cursor_img, (cursor_x - xhot, cursor_y - yhot), cursor_img.split()[3]
        )
        img.save(file_path)

    elif user_platform == "Darwin":  # (Mac OS)
        # Use the screencapture utility to capture the screen with the cursor
        subprocess.run(["screencapture", "-C", file_path])

    else:
        print(f"The platform you're using ({user_platform}) is not currently supported")

    return file_path


def compress_screenshot(raw_screenshot_filename, screenshot_filename):
    """Compress the raw screenshot file by converting RGBA to RGB for JPEG format"""
    with Image.open(raw_screenshot_filename) as img:
        # Check if image has alpha channel (transparency)
        if img.mode in ("RGBA", "LA"):
            # Create a white background image
            background = Image.new("RGB", img.size, (255, 255, 255))
            # Paste the image on the background using the alpha channel as mask
            background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
            # Save the result as JPEG
            background.save(screenshot_filename, "JPEG", quality=85)
        else:
            # If no alpha channel, simply convert and save
            img.convert("RGB").save(screenshot_filename, "JPEG", quality=85)
