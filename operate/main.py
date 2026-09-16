"""
Self-Operating Computer
"""
import os
import argparse
from dotenv import load_dotenv
from operate.utils.style import ANSI_BRIGHT_MAGENTA
from operate.operate import main

load_dotenv()


def main_entry():
    default_model = os.getenv("OPENAI_MODEL_NAME", "agy/gemini-3.7-flash-low")

    parser = argparse.ArgumentParser(
        description="Run the self-operating-computer with a specified model."
    )
    parser.add_argument(
        "-m",
        "--model",
        help="Specify the model to use (or any custom model name)",
        required=False,
        default=default_model,
    )

    # Add GUI flag
    parser.add_argument(
        "--gui",
        help="Launch the desktop Studio GUI",
        action="store_true",
    )

    # Add a voice flag
    parser.add_argument(
        "--voice",
        help="Use voice input mode",
        action="store_true",
    )
    
    # Add a flag for verbose mode
    parser.add_argument(
        "--verbose",
        help="Run operate in verbose mode",
        action="store_true",
    )
    
    # Allow for direct input of prompt
    parser.add_argument(
        "--prompt",
        help="Directly input the objective prompt",
        type=str,
        required=False,
    )

    try:
        args = parser.parse_args()

        if args.gui:
            from operate.gui.app import launch_gui
            launch_gui()
            return

        main(
            args.model,
            terminal_prompt=args.prompt,
            voice_mode=args.voice,
            verbose_mode=args.verbose
        )
    except KeyboardInterrupt:
        print(f"\n{ANSI_BRIGHT_MAGENTA}Exiting...")


if __name__ == "__main__":
    main_entry()
