import base64
import concurrent.futures
import io
import json
import os
import time
import traceback

easyocr = None

try:
    import ollama
except ImportError:
    ollama = None

try:
    import pkg_resources
except ImportError:
    pkg_resources = None

from PIL import Image

YOLO = None

from operate.config import Config
from operate.exceptions import ModelNotRecognizedException
from operate.models.prompts import (
    get_system_prompt,
    get_user_first_message_prompt,
    get_user_prompt,
)
from operate.utils.label import (
    add_labels,
    get_click_position_in_percent,
    get_label_coordinates,
)
from operate.utils.ocr import get_text_coordinates, get_text_element
from operate.utils.retry import call_with_retry
from operate.utils.screenshot import (
    capture_screen_with_cursor,
    capture_screen_fast,
    compress_screenshot,
    flush_screenshot_queue,
)
from operate.utils.style import ANSI_BRIGHT_MAGENTA, ANSI_GREEN, ANSI_RED, ANSI_RESET

# Load configuration
config = Config()

_OCR_READER = None


def get_ocr_reader():
    global _OCR_READER, easyocr
    if _OCR_READER is None:
        if easyocr is None:
            try:
                import easyocr
            except ImportError:
                raise ImportError("Please install easyocr using 'pip install easyocr'")
        _OCR_READER = easyocr.Reader(["en"])
    return _OCR_READER


_OCR_EXECUTOR = None


def _readtext_safe(screenshot_filename):
    """Run EasyOCR readtext, never raising into the hot path."""
    try:
        return get_ocr_reader().readtext(screenshot_filename)
    except Exception:
        return None


def start_ocr_readtext(screenshot_filename):
    """Kick off OCR immediately so it runs in parallel with the LLM call.

    Returns a zero-arg callable that yields the OCR result when needed. Calling it
    blocks until OCR finishes; since the LLM network call is the bottleneck, the
    OCR cost is hidden behind it.
    """
    global _OCR_EXECUTOR
    try:
        if _OCR_EXECUTOR is None:
            _OCR_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = _OCR_EXECUTOR.submit(_readtext_safe, screenshot_filename)
        return lambda: future.result()
    except Exception:
        result = _readtext_safe(screenshot_filename)
        return lambda: result


_YOLO_MODEL = None


def get_yolo_model():
    """Load the SoM YOLO label model once and cache it (saves 0.5-1.5s per step)."""
    global _YOLO_MODEL, YOLO
    if _YOLO_MODEL is None:
        if YOLO is None:
            try:
                from ultralytics import YOLO
            except ImportError:
                raise ImportError(
                    "Please install ultralytics using 'pip install ultralytics'"
                )
        _YOLO_MODEL = YOLO(
            pkg_resources.resource_filename("operate.models.weights", "best.pt")
        )
    return _YOLO_MODEL


_INITIALIZED_SESSIONS = set()


def reset_prompt_context():
    """Clear session cache so that next execution restarts prompt schema afresh."""
    _INITIALIZED_SESSIONS.clear()


async def get_next_action(model, messages, objective, session_id):
    if config.verbose:
        print("[Self-Operating Computer][get_next_action]")
        print("[Self-Operating Computer][get_next_action] model", model)
    if model == "gpt-4":
        return call_gpt_4o(messages), None
    if model == "qwen-vl":
        operation = await call_qwen_vl_with_ocr(messages, objective, model)
        return operation, None
    if model == "gpt-4-with-som":
        operation = await call_gpt_4o_labeled(messages, objective, model)
        return operation, None
    if model == "gpt-4-with-ocr":
        operation = await call_gpt_4o_with_ocr(messages, objective, model)
        return operation, None
    if model == "gpt-4.1-with-ocr":
        operation = await call_gpt_4_1_with_ocr(messages, objective, model)
        return operation, None
    if model == "o1-with-ocr":
        operation = await call_o1_with_ocr(messages, objective, model)
        return operation, None
    if model == "agent-1":
        return "coming soon"
    if model == "gemini-pro-vision":
        return call_gemini_pro_vision(messages, objective), None
    if model == "llava":
        operation = call_ollama_llava(messages)
        return operation, None
    if model == "claude-3":
        operation = await call_claude_3_with_ocr(messages, objective, model)
        return operation, None

    # --- Gemini OAuth route (Direct Google Antigravity / Cloud Code) ---
    if os.getenv("GEMINI_OAUTH") == "1":
        from operate.auth_gemini import gemini_generate_operations

        confirm_system_prompt(messages, objective, model)

        screenshot_img = capture_screen_fast()

        session_key = (model, objective)
        if len(messages) == 1 or session_key not in _INITIALIZED_SESSIONS:
            user_prompt = get_user_first_message_prompt()
            system_prompt = messages[0]["content"]
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            _INITIALIZED_SESSIONS.add(session_key)
        else:
            user_prompt = get_user_prompt()
            # On subsequent steps, do NOT send the massive 150-line system prompt again!
            full_prompt = (
                f"Objective: {objective}\n\n"
                f"{user_prompt}\n\n"
                f"Reminder: Respond ONLY with a valid JSON array of action objects matching the required schema."
            )

        # Pass PIL Image directly — gemini_generate() handles compression via _encode_image_fast
        images = [screenshot_img] if screenshot_img else None

        # Strip grounding suffix and routing prefixes for Google API
        raw_model = model
        for suffix in ["-direct", "-with-som", "-som", "-with-ocr", "-ocr"]:
            raw_model = raw_model.replace(suffix, "")
        if "/" in raw_model:
            raw_model = raw_model.split("/")[-1]

        operations = gemini_generate_operations(
            prompt=full_prompt,
            images=images,
            model=raw_model or "gemini-2.5-pro",
        )

        # Record in message history for context tracking
        assistant_message = {"role": "assistant", "content": json.dumps(operations)}
        messages.append(assistant_message)
        return operations, None

    # Custom model handling for any arbitrary model name or custom OpenAI-compatible endpoint
    raw_model = model
    targeting_mode = "direct"  # Default to fast, native multimodal direct vision
    if model.endswith("-with-som") or model.endswith("-som"):
        targeting_mode = "som"
        raw_model = model.replace("-with-som", "").replace("-som", "")
    elif model.endswith("-direct"):
        targeting_mode = "direct"
        raw_model = model.replace("-direct", "")
    elif model.endswith("-with-ocr") or model.endswith("-ocr"):
        targeting_mode = "ocr"
        raw_model = model.replace("-with-ocr", "").replace("-ocr", "")

    # If raw_model is empty (e.g. user just passed -m with-ocr), fallback to config custom model or gpt-4o
    if not raw_model:
        raw_model = getattr(config, "custom_model_name", None) or os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

    if targeting_mode == "som":
        operation = await call_custom_model_with_som(messages, objective, model, raw_model)
        return operation, None
    elif targeting_mode == "direct":
        operation = await call_custom_model_direct(messages, objective, model, raw_model)
        return operation, None
    else:
        operation = await call_custom_model_with_ocr(messages, objective, model, raw_model)
        return operation, None


def call_gpt_4o(messages):
    if config.verbose:
        print("[call_gpt_4_v]")
    client = config.initialize_openai()
    try:
        screenshot_img = capture_screen_fast()
        flush_screenshot_queue()

        img_base64 = _encode_image_fast(screenshot_img)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        if config.verbose:
            print(
                "[call_gpt_4_v] user_prompt",
                user_prompt,
            )

        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model="gpt-4o",
            messages=api_messages,
            presence_penalty=1,
            frequency_penalty=1,
            caller_name="gpt-4o",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        assistant_message = {"role": "assistant", "content": content}
        if config.verbose:
            print(
                "[call_gpt_4_v] content",
                content,
            )
        content = json.loads(content)

        messages.append(assistant_message)

        return content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[Operate] That did not work. Trying again {ANSI_RESET}",
            e,
        )
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] AI response was {ANSI_RESET}",
            content,
        )
        if config.verbose:
            traceback.print_exc()
        return call_gpt_4o(messages)


async def call_qwen_vl_with_ocr(messages, objective, model):
    if config.verbose:
        print("[call_qwen_vl_with_ocr]")

    # Construct the path to the file within the package
    try:
        client = config.initialize_qwen()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        # Capture directly to RAM and compress for the API
        screenshot_img = capture_screen_fast()
        flush_screenshot_queue()

        get_ocr_result = start_ocr_readtext("IN_MEMORY_SCREENSHOT")
        img_base64 = _encode_image_fast(screenshot_img)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text",
                 "text": f"{user_prompt}**REMEMBER** Only output json format, do not append any other text."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                },
            ],
        }
        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model="qwen2.5-vl-72b-instruct",
            messages=api_messages,
            caller_name="qwen-vl",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        # used later for the messages
        content_str = content

        content = json.loads(content)

        processed_content = []

        for operation in content:
            if operation.get("operation") == "click":
                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        "[call_qwen_vl_with_ocr][click] text_to_click",
                        text_to_click,
                    )
                # Initialize EasyOCR Reader
                # OCR ran concurrently with the LLM call; result is ready
                result = get_ocr_result()

                text_element_index = get_text_element(
                    result, text_to_click, screenshot_filename
                )
                coordinates = get_text_coordinates(
                    result, text_element_index, screenshot_filename
                )

                # add `coordinates`` to `content`
                operation["x"] = coordinates["x"]
                operation["y"] = coordinates["y"]

                if config.verbose:
                    print(
                        "[call_qwen_vl_with_ocr][click] text_element_index",
                        text_element_index,
                    )
                    print(
                        "[call_qwen_vl_with_ocr][click] coordinates",
                        coordinates,
                    )
                    print(
                        "[call_qwen_vl_with_ocr][click] final operation",
                        operation,
                    )
                processed_content.append(operation)

            else:
                processed_content.append(operation)

        # wait to append the assistant message so that if the `processed_content` step fails we don't append a message and mess up message history
        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return gpt_4_fallback(messages, objective, model)

def call_gemini_pro_vision(messages, objective):
    """
    Get the next action for Self-Operating Computer using Gemini Pro Vision
    """
    if config.verbose:
        print(
            "[Self Operating Computer][call_gemini_pro_vision]",
        )
    try:
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        # Call the function to capture the screen with the cursor
        capture_screen_with_cursor(screenshot_filename)
        prompt = get_system_prompt("gemini-pro-vision", objective)

        model = config.initialize_google()
        if config.verbose:
            print("[call_gemini_pro_vision] model", model)

        flush_screenshot_queue()
        response = call_with_retry(
            model.generate_content,
            [prompt, Image.open(screenshot_filename)],
            caller_name="gemini-pro-vision (Google)",
        )

        content = response.text[1:]
        if config.verbose:
            print("[call_gemini_pro_vision] response", response)
            print("[call_gemini_pro_vision] content", content)

        content = json.loads(content)
        if config.verbose:
            print(
                "[get_next_action][call_gemini_pro_vision] content",
                content,
            )

        return content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[Operate] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return call_gpt_4o(messages)


async def call_gpt_4o_with_ocr(messages, objective, model):
    if config.verbose:
        print("[call_gpt_4o_with_ocr]")

    # Construct the path to the file within the package
    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        get_ocr_result = start_ocr_readtext(screenshot_filename)

        img_base64 = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model="gpt-4o",
            messages=api_messages,
            caller_name="gpt-4o",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        # used later for the messages
        content_str = content

        content = json.loads(content)

        processed_content = []

        for operation in content:
            if operation.get("operation") == "click":
                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        "[call_gpt_4o_with_ocr][click] text_to_click",
                        text_to_click,
                    )
                # Initialize EasyOCR Reader
                # OCR ran concurrently with the LLM call; result is ready
                result = get_ocr_result()

                text_element_index = get_text_element(
                    result, text_to_click, screenshot_filename
                )
                coordinates = get_text_coordinates(
                    result, text_element_index, screenshot_filename
                )

                # add `coordinates`` to `content`
                operation["x"] = coordinates["x"]
                operation["y"] = coordinates["y"]

                if config.verbose:
                    print(
                        "[call_gpt_4o_with_ocr][click] text_element_index",
                        text_element_index,
                    )
                    print(
                        "[call_gpt_4o_with_ocr][click] coordinates",
                        coordinates,
                    )
                    print(
                        "[call_gpt_4o_with_ocr][click] final operation",
                        operation,
                    )
                processed_content.append(operation)

            else:
                processed_content.append(operation)

        # wait to append the assistant message so that if the `processed_content` step fails we don't append a message and mess up message history
        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return gpt_4_fallback(messages, objective, model)


async def call_gpt_4_1_with_ocr(messages, objective, model):
    if config.verbose:
        print("[call_gpt_4_1_with_ocr]")

    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        get_ocr_result = start_ocr_readtext(screenshot_filename)

        img_base64 = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                },
            ],
        }
        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model="gpt-4.1",
            messages=api_messages,
            caller_name="gpt-4.1",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        content_str = content

        content = json.loads(content)

        processed_content = []

        for operation in content:
            if operation.get("operation") == "click":
                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        "[call_gpt_4_1_with_ocr][click] text_to_click",
                        text_to_click,
                    )
                # OCR ran concurrently with the LLM call; result is ready
                result = get_ocr_result()

                text_element_index = get_text_element(
                    result, text_to_click, screenshot_filename
                )
                coordinates = get_text_coordinates(
                    result, text_element_index, screenshot_filename
                )

                operation["x"] = coordinates["x"]
                operation["y"] = coordinates["y"]

                if config.verbose:
                    print(
                        "[call_gpt_4_1_with_ocr][click] text_element_index",
                        text_element_index,
                    )
                    print(
                        "[call_gpt_4_1_with_ocr][click] coordinates",
                        coordinates,
                    )
                    print(
                        "[call_gpt_4_1_with_ocr][click] final operation",
                        operation,
                    )
                processed_content.append(operation)

            else:
                processed_content.append(operation)

        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return gpt_4_fallback(messages, objective, model)


async def call_o1_with_ocr(messages, objective, model):
    if config.verbose:
        print("[call_o1_with_ocr]")

    # Construct the path to the file within the package
    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        get_ocr_result = start_ocr_readtext(screenshot_filename)

        img_base64 = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                },
            ],
        }
        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model="o1",
            messages=api_messages,
            caller_name="o1",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        # used later for the messages
        content_str = content

        content = json.loads(content)

        processed_content = []

        for operation in content:
            if operation.get("operation") == "click":
                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        "[call_o1_with_ocr][click] text_to_click",
                        text_to_click,
                    )
                # Initialize EasyOCR Reader
                # OCR ran concurrently with the LLM call; result is ready
                result = get_ocr_result()

                text_element_index = get_text_element(
                    result, text_to_click, screenshot_filename
                )
                coordinates = get_text_coordinates(
                    result, text_element_index, screenshot_filename
                )

                # add `coordinates`` to `content`
                operation["x"] = coordinates["x"]
                operation["y"] = coordinates["y"]

                if config.verbose:
                    print(
                        "[call_o1_with_ocr][click] text_element_index",
                        text_element_index,
                    )
                    print(
                        "[call_o1_with_ocr][click] coordinates",
                        coordinates,
                    )
                    print(
                        "[call_o1_with_ocr][click] final operation",
                        operation,
                    )
                processed_content.append(operation)

            else:
                processed_content.append(operation)

        # wait to append the assistant message so that if the `processed_content` step fails we don't append a message and mess up message history
        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return gpt_4_fallback(messages, objective, model)


async def call_gpt_4o_labeled(messages, objective, model):
    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        file_path = pkg_resources.resource_filename("operate.models.weights", "best.pt")
        yolo_model = get_yolo_model()
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        with open(screenshot_filename, "rb") as img_file:
            img_base64 = base64.b64encode(img_file.read()).decode("utf-8")

        img_base64_labeled, label_coordinates = add_labels(img_base64, yolo_model)

        # Compress only the labeled OUTPUT for upload; YOLO keeps full resolution
        img_base64_labeled = _encode_image_from_base64(img_base64_labeled)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        if config.verbose:
            print(
                "[call_gpt_4_vision_preview_labeled] user_prompt",
                user_prompt,
            )

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64_labeled}"
                    },
                },
            ],
        }
        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64_labeled)

        response = call_with_retry(
            client.chat.completions.create,
            model="gpt-4o",
            messages=api_messages,
            presence_penalty=1,
            frequency_penalty=1,
            caller_name="gpt-4o",
        )

        content = response.choices[0].message.content

        content = clean_json(content)

        assistant_message = {"role": "assistant", "content": content}

        messages.append(assistant_message)

        content = json.loads(content)
        if config.verbose:
            print(
                "[call_gpt_4_vision_preview_labeled] content",
                content,
            )

        processed_content = []

        for operation in content:
            print(
                "[call_gpt_4_vision_preview_labeled] for operation in content",
                operation,
            )
            if operation.get("operation") == "click":
                label = operation.get("label")
                if config.verbose:
                    print(
                        "[Self Operating Computer][call_gpt_4_vision_preview_labeled] label",
                        label,
                    )

                coordinates = get_label_coordinates(label, label_coordinates)
                if config.verbose:
                    print(
                        "[Self Operating Computer][call_gpt_4_vision_preview_labeled] coordinates",
                        coordinates,
                    )
                image = Image.open(
                    io.BytesIO(base64.b64decode(img_base64))
                )  # Load the image to get its size
                image_size = image.size  # Get the size of the image (width, height)
                click_position_percent = get_click_position_in_percent(
                    coordinates, image_size
                )
                if config.verbose:
                    print(
                        "[Self Operating Computer][call_gpt_4_vision_preview_labeled] click_position_percent",
                        click_position_percent,
                    )
                if not click_position_percent:
                    print(
                        f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] Failed to get click position in percent. Trying another method {ANSI_RESET}"
                    )
                    return call_gpt_4o(messages)

                x_percent = f"{click_position_percent[0]:.2f}"
                y_percent = f"{click_position_percent[1]:.2f}"
                operation["x"] = x_percent
                operation["y"] = y_percent
                if config.verbose:
                    print(
                        "[Self Operating Computer][call_gpt_4_vision_preview_labeled] new click operation",
                        operation,
                    )
                processed_content.append(operation)
            else:
                if config.verbose:
                    print(
                        "[Self Operating Computer][call_gpt_4_vision_preview_labeled] .append none click operation",
                        operation,
                    )

                processed_content.append(operation)

            if config.verbose:
                print(
                    "[Self Operating Computer][call_gpt_4_vision_preview_labeled] new processed_content",
                    processed_content,
                )
            return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
        return call_gpt_4o(messages)


def call_ollama_llava(messages):
    if config.verbose:
        print("[call_ollama_llava]")
    try:
        model = config.initialize_ollama()
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        if config.verbose:
            print(
                "[call_ollama_llava] user_prompt",
                user_prompt,
            )

        vision_message = {
            "role": "user",
            "content": user_prompt,
            "images": [screenshot_filename],
        }
        messages.append(vision_message)

        response = model.chat(
            model="llava",
            messages=messages,
        )

        # Important: Remove the image path from the message history.
        # Ollama will attempt to load each image reference and will
        # eventually timeout.
        messages[-1]["images"] = None

        content = response["message"]["content"].strip()

        content = clean_json(content)

        assistant_message = {"role": "assistant", "content": content}
        if config.verbose:
            print(
                "[call_ollama_llava] content",
                content,
            )
        content = json.loads(content)

        messages.append(assistant_message)

        return content

    except ollama.ResponseError as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Operate] Couldn't connect to Ollama. With Ollama installed, run `ollama pull llava` then `ollama serve`{ANSI_RESET}",
            e,
        )

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[llava] That did not work. Trying again {ANSI_RESET}",
            e,
        )
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] AI response was {ANSI_RESET}",
            content,
        )
        if config.verbose:
            traceback.print_exc()
        return call_ollama_llava(messages)


async def call_claude_3_with_ocr(messages, objective, model):
    if config.verbose:
        print("[call_claude_3_with_ocr]")

    try:
        client = config.initialize_anthropic()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        get_ocr_result = start_ocr_readtext(screenshot_filename)

        # compress once; keeps payload small on every step
        img_data = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        vision_message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_data,
                    },
                },
                {
                    "type": "text",
                    "text": user_prompt
                    + "**REMEMBER** Only output json format, do not append any other text.",
                },
            ],
        }
        api_messages = _prepare_anthropic_messages_with_single_latest_image(messages, vision_message)

        # anthropic api expect system prompt as an separate argument
        response = call_with_retry(
            client.messages.create,
            model="claude-3-opus-20240229",
            max_tokens=3000,
            system=messages[0]["content"],
            messages=api_messages[1:],
            caller_name="claude-3",
        )

        content = response.content[0].text
        content = clean_json(content)
        content_str = content
        try:
            content = json.loads(content)
        # rework for json mode output
        except json.JSONDecodeError as e:
            if config.verbose:
                print(
                    f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] JSONDecodeError: {e} {ANSI_RESET}"
                )
            response = client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=3000,
                system=f"This json string is not valid, when using with json.loads(content) \
                it throws the following error: {e}, return correct json string. \
                **REMEMBER** Only output json format, do not append any other text.",
                messages=[{"role": "user", "content": content}],
            )
            content = response.content[0].text
            content = clean_json(content)
            content_str = content
            content = json.loads(content)

        if config.verbose:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] content: {content} {ANSI_RESET}"
            )
        processed_content = []

        for operation in content:
            if operation.get("operation") == "click":
                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        "[call_claude_3_ocr][click] text_to_click",
                        text_to_click,
                    )
                # Initialize EasyOCR Reader
                # OCR ran concurrently with the LLM call; result is ready
                result = get_ocr_result()

                # limit the text to extract has a higher success rate
                text_element_index = get_text_element(
                    result, text_to_click[:3], screenshot_filename
                )
                coordinates = get_text_coordinates(
                    result, text_element_index, screenshot_filename
                )

                # add `coordinates`` to `content`
                operation["x"] = coordinates["x"]
                operation["y"] = coordinates["y"]

                if config.verbose:
                    print(
                        "[call_claude_3_ocr][click] text_element_index",
                        text_element_index,
                    )
                    print(
                        "[call_claude_3_ocr][click] coordinates",
                        coordinates,
                    )
                    print(
                        "[call_claude_3_ocr][click] final operation",
                        operation,
                    )
                processed_content.append(operation)

            else:
                processed_content.append(operation)

        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{model}] That did not work. Trying another method {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][Operate] error", e)
            traceback.print_exc()
            print("message before convertion ", messages)

        # Convert the messages to the GPT-4 format
        gpt4_messages = [messages[0]]  # Include the system message
        for message in messages[1:]:
            if message["role"] == "user":
                # Update the image type format from "source" to "url"
                updated_content = []
                for item in message["content"]:
                    if isinstance(item, dict) and "type" in item:
                        if item["type"] == "image":
                            updated_content.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{item['source']['data']}"
                                    },
                                }
                            )
                        else:
                            updated_content.append(item)

                gpt4_messages.append({"role": "user", "content": updated_content})
            elif message["role"] == "assistant":
                gpt4_messages.append(
                    {"role": "assistant", "content": message["content"]}
                )

        return gpt_4_fallback(gpt4_messages, objective, model)


def get_last_assistant_message(messages):
    """
    Retrieve the last message from the assistant in the messages array.
    If the last assistant message is the first message in the array, return None.
    """
    for index in reversed(range(len(messages))):
        if messages[index]["role"] == "assistant":
            if index == 0:  # Check if the assistant message is the first in the array
                return None
            else:
                return messages[index]
    return None  # Return None if no assistant message is found


def gpt_4_fallback(messages, objective, model):
    if config.verbose:
        print("[gpt_4_fallback]")
    system_prompt = get_system_prompt("gpt-4o", objective)
    new_system_message = {"role": "system", "content": system_prompt}
    # remove and replace the first message in `messages` with `new_system_message`

    messages[0] = new_system_message

    if config.verbose:
        print("[gpt_4_fallback][updated]")
        print("[gpt_4_fallback][updated] len(messages)", len(messages))

    return call_gpt_4o(messages)


def confirm_system_prompt(messages, objective, model):
    """
    Ensure the first message in messages is the system prompt.
    Only computes and assigns if not already present, avoiding redundant string formatting.
    """
    if not messages:
        system_prompt = get_system_prompt(model, objective)
        messages.append({"role": "system", "content": system_prompt})
    elif messages[0].get("role") != "system":
        system_prompt = get_system_prompt(model, objective)
        messages.insert(0, {"role": "system", "content": system_prompt})

    if config.verbose:
        print("[confirm_system_prompt]")
        print("[confirm_system_prompt] len(messages)", len(messages))
        for m in messages:
            if m["role"] != "user":
                print("--------------------[message]--------------------")
                print("[confirm_system_prompt][message] role", m["role"])
                print("[confirm_system_prompt][message] content", m["content"])
                print("------------------[end message]------------------")


def clean_json(content):
    if not content:
        return "[]"
    if config.verbose:
        print("\n\n[clean_json] content before cleaning", content)

    # Use regex to extract ```json ... ``` or ``` ... ```
    import re
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if match:
        content = match.group(1).strip()
    elif content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content).strip()

    # If it's wrapped in square brackets or curly braces somewhere in text
    if not (content.startswith("[") or content.startswith("{")):
        match_bracket = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', content)
        if match_bracket:
            content = match_bracket.group(1).strip()

    # Normalize line breaks
    content = "\n".join(line.strip() for line in content.splitlines())

    if config.verbose:
        print("\n\n[clean_json] content after cleaning", content)

    return content


def _encode_image_fast(screenshot_or_image, max_dim=1280, quality=70):
    """Load, downscale to max_dim, and encode as a small optimized JPEG.
    Accepts either a file path (str) or a PIL.Image. Aggressive settings keep
    UI screenshots readable while cutting upload size ~30x."""
    from operate.utils.screenshot import get_latest_screenshot
    if isinstance(screenshot_or_image, Image.Image):
        img = screenshot_or_image
    elif screenshot_or_image == "IN_MEMORY_SCREENSHOT" or not os.path.exists(screenshot_or_image):
        img = get_latest_screenshot()
    else:
        try:
            img = Image.open(screenshot_or_image)
        except Exception:
            img = get_latest_screenshot()

    if img is None:
        img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, subsampling="4:2:0")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _encode_image_from_base64(img_base64):
    """Re-encode a base64 image (e.g. a labeled SoM PNG) as a compressed JPEG base64."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(img_base64)))
        return _encode_image_fast(img)
    except Exception:
        return img_base64


def _prepare_anthropic_messages_with_single_latest_image(messages, vision_message):
    """
    Anthropic-format prune: keep only the LATEST image, replacing older images in
    conversation history with text placeholders to prevent payload explosion.
    """
    clean_messages = []
    for m in messages:
        m_copy = dict(m)
        if isinstance(m_copy.get("content"), list):
            new_content = []
            for item in m_copy["content"]:
                if isinstance(item, dict) and item.get("type") == "image":
                    new_content.append(
                        {"type": "text", "text": "[Previous desktop screenshot - action taken]"}
                    )
                else:
                    new_content.append(item)
            m_copy["content"] = new_content
        clean_messages.append(m_copy)
    clean_messages.append(vision_message)
    messages.append(vision_message)
    return clean_messages


def _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64):
    """
    Construct API messages payload keeping only the LATEST image.
    Replaces older images in conversation history with text placeholders to prevent token explosion and vision confusion.
    """
    clean_messages = []
    for m in messages:
        m_copy = dict(m)
        if m_copy.get("role") == "user" and isinstance(m_copy.get("content"), list):
            new_content = []
            for item in m_copy["content"]:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    new_content.append({"type": "text", "text": "[Previous desktop screenshot - action taken]"})
                else:
                    new_content.append(item)
            m_copy["content"] = new_content
        clean_messages.append(m_copy)

    vision_message = {
        "role": "user",
        "content": [
            {"type": "text", "text": user_prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
            },
        ],
    }
    clean_messages.append(vision_message)
    # Also record in original messages list for session tracking
    messages.append(vision_message)
    return clean_messages


async def call_custom_model_with_ocr(messages, objective, model, raw_model):
    if config.verbose:
        print(f"[call_custom_model_with_ocr] model: {model}, raw_model: {raw_model}")

    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        img_base64 = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model=raw_model,
            messages=api_messages,
            caller_name=f"{raw_model} (Google/Custom)",
        )

        content = response.choices[0].message.content
        content = clean_json(content)
        content_str = content
        content = json.loads(content)
        if isinstance(content, dict):
            content = [content]

        processed_content = []

        for operation in content:
            op_type = operation.get("operation", "").lower()
            if op_type in ["click", "double_click", "right_click", "middle_click"]:
                # If model already provided coordinates, use them directly
                if "x" in operation and "y" in operation and operation["x"] is not None and operation["y"] is not None:
                    processed_content.append(operation)
                    continue

                text_to_click = operation.get("text")
                if config.verbose:
                    print(
                        f"[call_custom_model_with_ocr][{op_type}] text_to_click",
                        text_to_click,
                    )
                if not text_to_click:
                    print(
                        f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Warn] {op_type} operation missing text and coordinates: {operation}{ANSI_RESET}"
                    )
                    continue

                reader = get_ocr_reader()
                if screenshot_filename != "IN_MEMORY_SCREENSHOT" and os.path.exists(screenshot_filename):
                    ocr_target = screenshot_filename
                else:
                    import numpy as np
                    ocr_target = np.array(get_latest_screenshot())

                try:
                    result = reader.readtext(ocr_target)
                    text_element_index = get_text_element(
                        result, text_to_click, ocr_target
                    )
                    coordinates = get_text_coordinates(
                        result, text_element_index, ocr_target
                    )

                    operation["x"] = coordinates["x"]
                    operation["y"] = coordinates["y"]

                    if config.verbose:
                        print(
                            f"[call_custom_model_with_ocr][{op_type}] coordinates",
                            coordinates,
                        )
                    processed_content.append(operation)
                except Exception as ocr_err:
                    print(
                        f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_YELLOW}[OCR] Could not locate text '{text_to_click}': {ocr_err}{ANSI_RESET}"
                    )
            else:
                processed_content.append(operation)

        assistant_message = {"role": "assistant", "content": content_str}
        messages.append(assistant_message)
        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{raw_model}] That did not work: {e} {ANSI_RESET}"
        )
        if config.verbose:
            print("[Self-Operating Computer][call_custom_model_with_ocr] error", e)
            traceback.print_exc()
        return [{"operation": "done", "summary": f"Execution halted due to model error: {e}"}]


async def call_custom_model_direct(messages, objective, model, raw_model):
    if config.verbose:
        print(f"[call_custom_model_direct] model: {model}, raw_model: {raw_model}")

    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        img_base64 = _encode_image_fast(screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64)

        response = call_with_retry(
            client.chat.completions.create,
            model=raw_model,
            messages=api_messages,
            caller_name=f"{raw_model} (Google/Custom)",
        )

        content = response.choices[0].message.content
        content = clean_json(content)
        assistant_message = {"role": "assistant", "content": content}
        messages.append(assistant_message)
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{raw_model}] Error: {e} {ANSI_RESET}"
        )
        if config.verbose:
            traceback.print_exc()
        return [{"operation": "done", "summary": f"Execution halted due to error: {e}"}]


async def call_custom_model_with_som(messages, objective, model, raw_model):
    if config.verbose:
        print(f"[call_custom_model_with_som] model: {model}, raw_model: {raw_model}")

    try:
        client = config.initialize_openai()

        confirm_system_prompt(messages, objective, model)
        screenshots_dir = "screenshots"
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)

        screenshot_filename = os.path.join(screenshots_dir, "screenshot.png")
        screenshot_filename = capture_screen_with_cursor(screenshot_filename)

        yolo_model = get_yolo_model()
        flush_screenshot_queue()
        result = yolo_model(screenshot_filename)
        labeled_screenshot_filename = os.path.join(
            screenshots_dir, "labeled_screenshot.png"
        )
        label_coordinates = add_labels(
            result, screenshot_filename, labeled_screenshot_filename
        )

        # Compress only the labeled OUTPUT for upload; YOLO keeps full resolution
        img_base64_labeled = _encode_image_fast(labeled_screenshot_filename)

        if len(messages) == 1:
            user_prompt = get_user_first_message_prompt()
        else:
            user_prompt = get_user_prompt()

        vision_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64_labeled}"
                    },
                },
            ],
        }
        api_messages = _prepare_messages_with_single_latest_image(messages, user_prompt, img_base64_labeled)

        response = call_with_retry(
            client.chat.completions.create,
            model=raw_model,
            messages=api_messages,
            caller_name=f"{raw_model} (Google/Custom)",
        )

        content = response.choices[0].message.content
        content = clean_json(content)
        assistant_message = {"role": "assistant", "content": content}
        messages.append(assistant_message)
        content = json.loads(content)

        processed_content = []
        for operation in content:
            op_type = operation.get("operation", "").lower()
            if op_type in ["click", "double_click", "right_click", "middle_click"]:
                label = operation.get("label")
                coordinates = get_label_coordinates(label, label_coordinates)
                # Size from the on-disk screenshot matches the full-resolution
                # coordinates YOLO produced
                image_size = Image.open(screenshot_filename).size
                click_position_percent = get_click_position_in_percent(
                    coordinates, image_size
                )
                if not click_position_percent:
                    print(
                        f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] Failed to get {op_type} position for {label}.{ANSI_RESET}"
                    )
                    break
                operation["x"] = click_position_percent[0]
                operation["y"] = click_position_percent[1]
                processed_content.append(operation)
            else:
                processed_content.append(operation)

        return processed_content

    except Exception as e:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_BRIGHT_MAGENTA}[{raw_model}] Error: {e} {ANSI_RESET}"
        )
        if config.verbose:
            traceback.print_exc()
        return [{"operation": "done", "summary": f"Execution halted due to error: {e}"}]
