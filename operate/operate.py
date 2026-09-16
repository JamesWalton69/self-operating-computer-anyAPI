import sys
import os
import time
import asyncio
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit import prompt
from operate.exceptions import ModelNotRecognizedException
import platform

# from operate.models.prompts import USER_QUESTION, get_system_prompt
from operate.models.prompts import (
    USER_QUESTION,
    get_system_prompt,
)
from operate.config import Config
from operate.utils.style import (
    ANSI_GREEN,
    ANSI_RESET,
    ANSI_YELLOW,
    ANSI_RED,
    ANSI_BRIGHT_MAGENTA,
    ANSI_BLUE,
    style,
)
from operate.utils.operating_system import OperatingSystem
from operate.models.apis import get_next_action

# Load configuration
config = Config()
operating_system = OperatingSystem()


def main(
    model,
    terminal_prompt,
    voice_mode=False,
    verbose_mode=False,
    step_callback=None,
    stop_event=None,
    max_steps=10,
):
    """
    Main function for the Self-Operating Computer.

    Parameters:
    - model: The model used for generating responses.
    - terminal_prompt: A string representing the prompt provided in the terminal.
    - voice_mode: A boolean indicating whether to enable voice mode.
    - step_callback: Optional callback(step_data) for GUI monitoring.
    - stop_event: Optional threading.Event to request early termination.
    - max_steps: Maximum iterations before stopping (default 10).

    Returns:
    None
    """

    mic = None
    # Initialize `WhisperMic`, if `voice_mode` is True

    config.verbose = verbose_mode
    config.validation(model, voice_mode)

    if voice_mode:
        try:
            from whisper_mic import WhisperMic

            # Initialize WhisperMic if import is successful
            mic = WhisperMic()
        except ImportError:
            print(
                "Voice mode requires the 'whisper_mic' module. Please install it using 'pip install -r requirements-audio.txt'"
            )
            sys.exit(1)

    # Skip message dialog if prompt was given directly
    if not terminal_prompt:
        message_dialog(
            title="Self-Operating Computer",
            text="An experimental framework to enable multimodal models to operate computers",
            style=style,
        ).run()

    else:
        print("Running direct prompt...")

    # # Clear the console
    if platform.system() == "Windows":
        os.system("cls")
    else:
        print("\033c", end="")

    if terminal_prompt:  # Skip objective prompt if it was given as an argument
        objective = terminal_prompt
    elif voice_mode:
        print(
            f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RESET} Listening for your command... (speak now)"
        )
        try:
            objective = mic.listen()
        except Exception as e:
            print(f"{ANSI_RED}Error in capturing voice input: {e}{ANSI_RESET}")
            return  # Exit if voice input fails
    else:
        print(
            f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]\n{USER_QUESTION}"
        )
        print(f"{ANSI_YELLOW}[User]{ANSI_RESET}")
        objective = prompt(style=style)

    system_prompt = get_system_prompt(model, objective)
    system_message = {"role": "system", "content": system_prompt}
    messages = [system_message]

    loop_count = 0

    session_id = None

    while True:
        if stop_event and stop_event.is_set():
            if config.verbose:
                print("[Self Operating Computer] Stop event requested, exiting loop.")
            break

        if config.verbose:
            print("[Self Operating Computer] loop_count", loop_count)
        try:
            if step_callback:
                step_callback({
                    "type": "status",
                    "status": "thinking",
                    "step": loop_count + 1,
                    "max_steps": max_steps,
                    "message": f"Analyzing screen for step {loop_count + 1}..."
                })

            operations, session_id = asyncio.run(
                get_next_action(model, messages, objective, session_id)
            )

            if stop_event and stop_event.is_set():
                break

            stop = operate(operations, model, step_callback=step_callback, stop_event=stop_event, current_step=loop_count + 1)
            if stop:
                break

            loop_count += 1
            # Allow the OS UI to settle and render changes before capturing the next screenshot
            time.sleep(1.0)
            if loop_count >= max_steps:
                print(f"{ANSI_YELLOW}[Self-Operating Computer] Reached maximum step limit ({max_steps}).{ANSI_RESET}")
                if step_callback:
                    step_callback({
                        "type": "done",
                        "status": "max_steps_reached",
                        "summary": f"Reached maximum steps ({max_steps})."
                    })
                break
        except ModelNotRecognizedException as e:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] -> {e} {ANSI_RESET}"
            )
            if step_callback:
                step_callback({"type": "error", "error": str(e)})
            break
        except Exception as e:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] -> {e} {ANSI_RESET}"
            )
            if step_callback:
                step_callback({"type": "error", "error": str(e)})
            break


def operate(operations, model, step_callback=None, stop_event=None, current_step=1):
    if config.verbose:
        print("[Self Operating Computer][operate]")

    # Check if this batch contains both active actions and 'done'
    active_op_types = [
        "click", "double_click", "right_click", "middle_click",
        "write", "paste", "launch", "press", "hotkey", "drag"
    ]
    has_active_action = any(
        op.get("operation", "").lower() in active_op_types
        for op in operations
    )
    has_done = any(op.get("operation", "").lower() == "done" for op in operations)
    # Defer 'done' if bundled with actions so the agent must inspect the screen to verify
    defer_done = has_active_action and has_done

    for operation in operations:
        if stop_event and stop_event.is_set():
            return True

        if config.verbose:
            print("[Self Operating Computer][operate] operation", operation)
        # wait one second
        time.sleep(1)
        operate_type = operation.get("operation", "").lower()
        operate_thought = operation.get("thought", "")
        operate_detail = ""
        if config.verbose:
            print("[Self Operating Computer][operate] operate_type", operate_type)

        if operate_type == "press" or operate_type == "hotkey":
            keys = operation.get("keys")
            operate_detail = keys
            operating_system.press(keys)
        elif operate_type == "write":
            content = operation.get("content")
            operate_detail = content
            operating_system.write(content)
        elif operate_type == "click":
            x = operation.get("x")
            y = operation.get("y")
            click_detail = {"x": x, "y": y}
            operate_detail = click_detail
            operating_system.mouse(click_detail)

        elif operate_type == "double_click":
            x = operation.get("x")
            y = operation.get("y")
            click_detail = {"x": x, "y": y}
            operate_detail = click_detail
            operating_system.double_click(click_detail)

        elif operate_type == "right_click":
            x = operation.get("x")
            y = operation.get("y")
            click_detail = {"x": x, "y": y}
            operate_detail = click_detail
            operating_system.right_click(click_detail)

        elif operate_type == "middle_click":
            x = operation.get("x")
            y = operation.get("y")
            click_detail = {"x": x, "y": y}
            operate_detail = click_detail
            operating_system.middle_click(click_detail)

        elif operate_type == "paste":
            content = operation.get("content", "")
            operate_detail = content[:50] + "..." if len(content) > 50 else content
            operating_system.paste(content)

        elif operate_type == "scroll":
            direction = operation.get("direction", "down")
            amount = operation.get("amount", 3)
            scroll_x = operation.get("x")
            scroll_y = operation.get("y")
            operate_detail = f"{direction} {amount}"
            operating_system.scroll(direction=direction, amount=amount, x=scroll_x, y=scroll_y)

        elif operate_type == "wait":
            seconds = operation.get("seconds", 1)
            operate_detail = f"{seconds}s"
            operating_system.wait(seconds)

        elif operate_type == "launch":
            target = operation.get("target", "")
            operate_detail = target
            operating_system.launch(target)

        elif operate_type == "drag":
            start_x = operation.get("start_x")
            start_y = operation.get("start_y")
            end_x = operation.get("end_x")
            end_y = operation.get("end_y")
            duration = operation.get("duration", 0.5)
            operate_detail = f"({start_x},{start_y}) -> ({end_x},{end_y})"
            operating_system.drag(start_x, start_y, end_x, end_y, duration)

        elif operate_type == "done":
            summary = str(operation.get("summary", ""))
            # Check if this done operation is actually an error indicator
            is_error_summary = any(kw in summary.lower() for kw in [
                "execution halted", "model error", "api error", "403 forbidden", "403", "unauthorized", "failed"
            ])
            if is_error_summary:
                print(f"{ANSI_RED}[Self-Operating Computer] Operation stopped with error: {summary}{ANSI_RESET}\n")
                if step_callback:
                    step_callback({
                        "type": "error",
                        "error": summary,
                        "step": current_step
                    })
                return True

            if defer_done:
                print(
                    f"[{ANSI_GREEN}Self-Operating Computer{ANSI_RESET}] "
                    f"Action completed. Verifying on-screen result in next step before finishing..."
                )
                if step_callback:
                    step_callback({
                        "type": "status",
                        "status": "verifying",
                        "step": current_step,
                        "message": "Action completed. Verifying on-screen result in next step..."
                    })
                continue

            print(
                f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]"
            )
            print(f"{ANSI_BLUE}Objective Complete: {ANSI_RESET}{summary}\n")
            if step_callback:
                step_callback({
                    "type": "done",
                    "status": "completed",
                    "summary": summary
                })
            return True

        else:
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] unknown operation response :({ANSI_RESET}"
            )
            print(
                f"{ANSI_GREEN}[Self-Operating Computer]{ANSI_RED}[Error] AI response {ANSI_RESET}{operation}"
            )
            if step_callback:
                step_callback({
                    "type": "error",
                    "error": f"Unknown operation: {operation}"
                })
            return True

        print(
            f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {model}{ANSI_RESET}]"
        )
        print(f"{operate_thought}")
        print(f"{ANSI_BLUE}Action: {ANSI_RESET}{operate_type} {operate_detail}\n")

        if step_callback:
            step_callback({
                "type": "action",
                "operation": operate_type,
                "detail": str(operate_detail),
                "thought": operate_thought,
                "step": current_step,
            })

    return False
