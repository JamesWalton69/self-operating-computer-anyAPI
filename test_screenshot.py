import os
import platform
import pyautogui
from PIL import Image

def test():
    file_path = r"E:\Coding\Projects\self-operating-computer-anyAPI\screenshots\screenshot.png"
    target_path = file_path
    
    screenshot = pyautogui.screenshot()
    print("Screenshot taken.")
    
    try:
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                print("Removed old file")
            except Exception as e:
                print(f"Error removing: {e}")
        screenshot.save(target_path)
        print("Saved to 1")
    except Exception as e:
        print(f"Exception 1: {e}")
        import time
        base, ext = os.path.splitext(target_path)
        alt_path = f"{base}_{int(time.time() * 1000)}{ext or '.png'}"
        try:
            screenshot.save(alt_path)
            print("Saved to 2")
        except Exception as e2:
            print(f"Exception 2: {e2}")
            try:
                root_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "..", f"screenshot_{int(time.time() * 1000)}.png")
                )
                print(f"root_path is {root_path}")
                screenshot.save(root_path)
                print("Saved to 3")
            except Exception as e3:
                print(f"Exception 3: {e3}")
    
test()
