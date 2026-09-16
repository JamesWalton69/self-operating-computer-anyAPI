import base64
import sys
from pathlib import Path
from openai import OpenAI
from operate.utils.retry import call_with_retry

import os

# ─── Setup ───────────────────────────────────────────────
client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "none",  # Get free key at https://aistudio.google.com
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

MODEL = "gemini-3.8-flash"  # or "gemini-2.5-flash"

# ─── OCR Function ────────────────────────────────────────
def ocr(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Read and encode
    mime = path.suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}
    mime = mime_map.get(mime, "png")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    print(f"📷 Image: {path.name} ({path.stat().st_size / 1024:.1f} KB)")
    print(f"🤖 Model: {MODEL}")
    print("-" * 40)

    resp = call_with_retry(
        client.chat.completions.create,
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract ALL text from this image exactly as it appears. Preserve formatting, line breaks, and layout. Return ONLY the extracted text, nothing else."},
                {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{b64}"}}
            ]
        }],
        max_tokens=4096,
        caller_name=f"OCR ({MODEL})"
    )

    return resp.choices[0].message.content


# ─── Video OCR (extract frames) ─────────────────────────
def ocr_video(video_path: str, num_frames: int = 5) -> str:
    """
    Extracts frames from a video and OCRs each one.
    Requires: pip install opencv-python
    """
    import cv2

    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = total // num_frames
    results = []

    for i in range(num_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * step)
        ret, frame = cap.read()
        if not ret:
            break
        _, buf = cv2.imencode(".jpg", frame)
        b64 = base64.b64encode(buf).decode()

        resp = call_with_retry(
            client.chat.completions.create,
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all visible text from this video frame."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }],
            max_tokens=2048,
            caller_name=f"Video OCR ({MODEL})"
        )
        text = resp.choices[0].message.content
        results.append(f"--- Frame {i+1}/{num_frames} ---\n{text}")
        print(f"  ✓ Frame {i+1} done")

    cap.release()
    return "\n\n".join(results)


# ─── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ocr_test.py image.jpg")
        print("  python ocr_test.py video.mp4 --video")
        sys.exit(1)

    filepath = sys.argv[1]

    if "--video" in sys.argv:
        result = ocr_video(filepath)
    else:
        result = ocr(filepath)

    print("\n" + "=" * 40)
    print("📝 EXTRACTED TEXT:")
    print("=" * 40)
    print(result)   