import os
import platform
import subprocess
import tempfile
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


def get_latest_screenshot():
    """Retrieve the most recently captured in-memory screenshot PIL Image."""
    global _LATEST_SCREENSHOT
    return _LATEST_SCREENSHOT


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

        # 1. Try saving directly to target_path
        try:
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            screenshot.save(target_path)
            return target_path
        except Exception:
            pass

        # 2. Try saving to a timestamped file in the same directory
        try:
            base, ext = os.path.splitext(target_path)
            alt_path = f"{base}_{int(time.time() * 1000)}{ext or '.png'}"
            screenshot.save(alt_path)
            return alt_path
        except Exception:
            pass

        # 3. If disk writes are blocked by Windows Security/ACLs, return in-memory flag
        return "IN_MEMORY_SCREENSHOT"

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
