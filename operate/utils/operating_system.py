import os
import sys
import shutil
import pyautogui
import platform
import subprocess
import time
import math

# Ensure failsafe is globally disabled so mouse in corners doesn't crash automation
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

try:
    import pyperclip
except ImportError:
    pyperclip = None

# Enable DPI awareness on Windows so screen resolution matches physical pixels
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from operate.utils.misc import convert_percent_to_decimal


class OperatingSystem:
    def __init__(self):
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.05

    def _resolve_click_position(self, click_detail):
        """Convert percentage-based coordinates to pixel coordinates."""
        x = convert_percent_to_decimal(click_detail.get("x"))
        y = convert_percent_to_decimal(click_detail.get("y"))
        if x is not None and y is not None:
            screen_width, screen_height = pyautogui.size()
            x_pixel = int(screen_width * float(x))
            y_pixel = int(screen_height * float(y))
            return x_pixel, y_pixel
        return None, None

    # --- Click Actions ---
    def mouse(self, click_detail):
        """Standard left click at percentage coordinates with window-activating smooth move."""
        try:
            x_pixel, y_pixel = self._resolve_click_position(click_detail)
            if x_pixel is not None:
                pyautogui.moveTo(x_pixel, y_pixel, duration=0.12)
                time.sleep(0.05)
                pyautogui.click(x_pixel, y_pixel)
        except Exception as e:
            print(f"[OperatingSystem][mouse] error: {e}")

    def click_at_percentage(self, x_percentage, y_percentage, duration=0.15):
        """Click at percentage coordinates with smooth move."""
        try:
            screen_width, screen_height = pyautogui.size()
            x_pixel = int(screen_width * float(x_percentage))
            y_pixel = int(screen_height * float(y_percentage))
            pyautogui.moveTo(x_pixel, y_pixel, duration=duration)
            time.sleep(0.05)
            pyautogui.click(x_pixel, y_pixel)
        except Exception as e:
            print(f"[OperatingSystem][click_at_percentage] error: {e}")

    def double_click(self, click_detail):
        """Double-click at percentage coordinates (for opening files, desktop icons)."""
        try:
            x_pixel, y_pixel = self._resolve_click_position(click_detail)
            if x_pixel is not None:
                pyautogui.moveTo(x_pixel, y_pixel, duration=0.12)
                time.sleep(0.05)
                pyautogui.doubleClick(x_pixel, y_pixel)
        except Exception as e:
            print(f"[OperatingSystem][double_click] error: {e}")

    def right_click(self, click_detail):
        """Right-click at percentage coordinates (for context menus)."""
        try:
            x_pixel, y_pixel = self._resolve_click_position(click_detail)
            if x_pixel is not None:
                pyautogui.moveTo(x_pixel, y_pixel, duration=0.12)
                time.sleep(0.05)
                pyautogui.rightClick(x_pixel, y_pixel)
        except Exception as e:
            print(f"[OperatingSystem][right_click] error: {e}")

    def middle_click(self, click_detail):
        """Middle-click at percentage coordinates."""
        try:
            x_pixel, y_pixel = self._resolve_click_position(click_detail)
            if x_pixel is not None:
                pyautogui.moveTo(x_pixel, y_pixel, duration=0.12)
                time.sleep(0.05)
                pyautogui.middleClick(x_pixel, y_pixel)
        except Exception as e:
            print(f"[OperatingSystem][middle_click] error: {e}")

    # --- Keyboard Actions ---
    def _type_character_by_character(self, content, interval=0.01):
        """Type text character by character using keyboard events."""
        if not content:
            return
        content = str(content).replace("\\n", "\n")
        for char in content:
            if char == "\n":
                pyautogui.press("enter")
            elif char == "\t":
                pyautogui.press("tab")
            else:
                pyautogui.write(char, interval=0)
            if interval > 0:
                time.sleep(interval)

    def write(self, content, interval=0.01):
        """Type text. For long text (>25 chars) or multi-line strings, attempts fast paste with fallback to direct typing."""
        try:
            if not content:
                return
            content = str(content).replace("\\n", "\n")
            if len(content) > 25 or "\n" in content:
                # Attempt fast clipboard paste; paste() handles its own fallback to typing if clipboard is locked
                self.paste(content)
            else:
                self._type_character_by_character(content, interval=interval)
        except Exception as e:
            print(f"[OperatingSystem][write] error: {e}")
            # Final fallback: direct typing
            try:
                self._type_character_by_character(content, interval=interval)
            except Exception:
                pass

    def paste(self, content):
        """Instantly paste text via clipboard with graceful fallback to character typing."""
        try:
            if not content:
                return
            content = str(content).replace("\\n", "\n")
            success = False

            # Method 1: Try pyperclip with retries (in case clipboard was briefly locked)
            if pyperclip:
                for _ in range(3):
                    try:
                        pyperclip.copy(content)
                        success = True
                        break
                    except Exception:
                        time.sleep(0.05)

            # Method 2: Try tkinter clipboard if pyperclip failed
            if not success:
                try:
                    import tkinter as tk
                    root = tk.Tk()
                    root.withdraw()
                    root.clipboard_clear()
                    root.clipboard_append(content)
                    root.update()
                    root.destroy()
                    success = True
                except Exception:
                    pass

            if success:
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.1)
            else:
                # If all clipboard methods fail (e.g. Windows error 5 access denied or lock), fall back to direct keyboard typing
                print("[OperatingSystem][paste] Notice: Clipboard unavailable, falling back to direct keyboard typing")
                self._type_character_by_character(content, interval=0.005)
        except Exception as e:
            print(f"[OperatingSystem][paste] error: {e}, falling back to keyboard typing")
            self._type_character_by_character(content, interval=0.005)

    def press(self, keys):
        """Press a key combination (hotkey). Supports modifier sequences like ['ctrl', 'l']."""
        try:
            if not keys:
                return
            clean_keys = [str(k).strip().lower() for k in keys if k]
            if not clean_keys:
                return
            if len(clean_keys) == 1:
                pyautogui.press(clean_keys[0])
            else:
                pyautogui.hotkey(*clean_keys)
        except Exception as e:
            print(f"[OperatingSystem][press] error: {e}")

    # --- Scrolling ---
    def scroll(self, direction="down", amount=3, x=None, y=None):
        """Scroll the mouse wheel. direction: 'up' or 'down'. amount: number of scroll clicks."""
        try:
            scroll_amount = int(amount)
            if direction == "up":
                scroll_amount = abs(scroll_amount)
            else:
                scroll_amount = -abs(scroll_amount)

            if x is not None and y is not None:
                x_dec = convert_percent_to_decimal(x)
                y_dec = convert_percent_to_decimal(y)
                if x_dec is not None and y_dec is not None:
                    screen_width, screen_height = pyautogui.size()
                    px = int(screen_width * float(x_dec))
                    py = int(screen_height * float(y_dec))
                    pyautogui.moveTo(px, py, duration=0.1)

            pyautogui.scroll(scroll_amount)
        except Exception as e:
            print(f"[OperatingSystem][scroll] error: {e}")

    # --- Wait / Pacing ---
    def wait(self, seconds=1.0):
        """Explicit pause for UI transitions, app loading, animations."""
        try:
            time.sleep(max(0.1, float(seconds)))
        except Exception as e:
            print(f"[OperatingSystem][wait] error: {e}")

    # --- App Launch Helper ---
    def _resolve_windows_app(self, target):
        """Resolve application target on Windows to executable path or protocol."""
        try:
            import winreg
        except ImportError:
            winreg = None

        target_clean = target.strip().lower()
        alias_map = {
            "word": "winword",
            "msword": "winword",
            "microsoft word": "winword",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "excel": "excel",
            "powerpoint": "powerpnt",
            "ppt": "powerpnt",
            "google chrome": "chrome",
            "browser": "msedge",
            "calculator": "calc",
            "terminal": "wt",
        }
        clean_base = alias_map.get(target_clean, target.strip())
        if clean_base.endswith(".exe"):
            clean_base = clean_base[:-4]

        # Protocols or URLs
        if "://" in target or target.endswith(":"):
            return target

        # If user or model requested Chrome, verify if Chrome is installed.
        # If not, seamlessly route to Microsoft Edge (installed by default on Windows).
        if clean_base in ("chrome", "google chrome"):
            chrome_found = False
            if winreg:
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as k:
                            cp, _ = winreg.QueryValueEx(k, "")
                            if cp and os.path.exists(cp):
                                chrome_found = True
                                return cp
                    except OSError:
                        pass
            if not chrome_found:
                print("[OperatingSystem][launch] Notice: Chrome not detected on machine, routing to Microsoft Edge.")
                clean_base = "msedge"

        # Check Windows App Paths in Registry
        if winreg:
            for exe_cand in (f"{clean_base}.exe", clean_base):
                for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_cand}") as k:
                            app_p, _ = winreg.QueryValueEx(k, "")
                            if app_p and os.path.exists(app_p):
                                return app_p
                    except OSError:
                        pass

        # Check system PATH
        which_path = shutil.which(clean_base) or shutil.which(f"{clean_base}.exe")
        if which_path:
            return which_path

        # Known standard fallback paths
        known_fallbacks = {
            "msedge": [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ],
            "notepad": [
                r"C:\Windows\System32\notepad.exe",
                r"C:\Windows\notepad.exe",
            ],
            "calc": [
                r"C:\Windows\System32\calc.exe",
            ],
            "explorer": [
                r"C:\Windows\explorer.exe",
            ],
        }
        for candidate in known_fallbacks.get(clean_base, []):
            if os.path.exists(candidate):
                return candidate

        return clean_base

    def launch(self, target):
        """Launch an application directly via OS shell. Examples: 'winword', 'msedge', 'chrome', 'notepad', 'calc'."""
        try:
            if not target:
                return
            system = platform.system()
            if system == "Windows":
                resolved = self._resolve_windows_app(target)
                print(f"[OperatingSystem][launch] Starting application: {resolved}")
                try:
                    os.startfile(resolved)
                except Exception as start_err:
                    print(f"[OperatingSystem][launch] os.startfile failed ({start_err}), using cmd start fallback")
                    subprocess.Popen(["cmd", "/c", "start", "", resolved], shell=False)
            elif system == "Darwin":
                subprocess.Popen(["open", "-a", target])
            else:
                subprocess.Popen([target])
            # Give app time to paint and gain window focus
            time.sleep(2.0)
        except Exception as e:
            print(f"[OperatingSystem][launch] error: {e}")

    # --- Drag ---
    def drag(self, start_x, start_y, end_x, end_y, duration=0.5):
        """Drag from one percentage coordinate to another."""
        try:
            screen_width, screen_height = pyautogui.size()
            sx = convert_percent_to_decimal(start_x)
            sy = convert_percent_to_decimal(start_y)
            ex = convert_percent_to_decimal(end_x)
            ey = convert_percent_to_decimal(end_y)
            if all(v is not None for v in [sx, sy, ex, ey]):
                sx_px = int(screen_width * float(sx))
                sy_px = int(screen_height * float(sy))
                ex_px = int(screen_width * float(ex))
                ey_px = int(screen_height * float(ey))
                pyautogui.moveTo(sx_px, sy_px, duration=0.15)
                pyautogui.drag(
                    ex_px - sx_px, ey_px - sy_px,
                    duration=max(0.2, float(duration)),
                    button="left"
                )
        except Exception as e:
            print(f"[OperatingSystem][drag] error: {e}")
