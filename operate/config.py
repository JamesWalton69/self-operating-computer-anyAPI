import os
import sys

genai = None

try:
    from ollama import Client as OllamaClient
except ImportError:
    OllamaClient = None

try:
    import anthropic
except ImportError:
    anthropic = None

from dotenv import load_dotenv
from openai import OpenAI
from prompt_toolkit.shortcuts import input_dialog


class Config:
    """
    Configuration class for managing settings.

    Attributes:
        verbose (bool): Flag indicating whether verbose mode is enabled.
        openai_api_key (str): API key for OpenAI.
        google_api_key (str): API key for Google.
        ollama_host (str): url to ollama running remotely.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            # Put any initialization here
        return cls._instance

    def __init__(self):
        load_dotenv()
        self.verbose = False
        self.openai_api_key = (
            None  # instance variables are backups in case saving to a `.env` fails
        )
        self.google_api_key = (
            None  # instance variables are backups in case saving to a `.env` fails
        )
        self.ollama_host = (
            None  # instance variables are backups in case savint to a `.env` fails
        )
        self.anthropic_api_key = (
            None  # instance variables are backups in case saving to a `.env` fails
        )
        self.qwen_api_key = (
            None  # instance variables are backups in case saving to a `.env` fails
        )
        self.custom_model_name = os.getenv("OPENAI_MODEL_NAME", "gemini-3.1-flash-lite")
        self._google_oauth = None

    @property
    def google_oauth(self):
        """Lazy-initialized Google OAuth manager singleton."""
        if self._google_oauth is None:
            try:
                from operate.utils.google_auth import GoogleOAuthManager
                self._google_oauth = GoogleOAuthManager()
            except Exception as e:
                print(f"[Config] Google OAuth init failed: {e}")
                return None
        return self._google_oauth

    def initialize_openai(self):
        if self.verbose:
            print("[Config][initialize_openai]")

        base_url = os.getenv("OPENAI_API_BASE_URL", None)
        is_local = base_url and ("localhost" in base_url or "127.0.0.1" in base_url)

        if self.openai_api_key:
            if self.verbose:
                print("[Config][initialize_openai] using cached openai_api_key")
            api_key = self.openai_api_key
        else:
            if self.verbose:
                print(
                    "[Config][initialize_openai] no cached openai_api_key, try to get from env."
                )
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key and is_local:
                api_key = "none"

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url.strip()

        client = OpenAI(**client_kwargs)
        return client

    def initialize_qwen(self):
        if self.verbose:
            print("[Config][initialize_qwen]")

        if self.qwen_api_key:
            if self.verbose:
                print("[Config][initialize_qwen] using cached qwen_api_key")
            api_key = self.qwen_api_key
        else:
            if self.verbose:
                print(
                    "[Config][initialize_qwen] no cached qwen_api_key, try to get from env."
                )
            api_key = os.getenv("QWEN_API_KEY")

        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        client.api_key = api_key
        client.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        return client

    def initialize_google(self):
        global genai
        if genai is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("Please install google-generativeai using 'pip install google-generativeai'")

        if self.google_api_key:
            if self.verbose:
                print("[Config][initialize_google] using cached google_api_key")
            api_key = self.google_api_key
        else:
            if self.verbose:
                print(
                    "[Config][initialize_google] no cached google_api_key, try to get from env."
                )
            api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key, transport="rest")
        model = genai.GenerativeModel("gemini-pro-vision")

        return model

    def initialize_ollama(self):
        if self.ollama_host:
            if self.verbose:
                print("[Config][initialize_ollama] using cached ollama host")
        else:
            if self.verbose:
                print(
                    "[Config][initialize_ollama] no cached ollama host. Assuming ollama running locally."
                )
            self.ollama_host = os.getenv("OLLAMA_HOST", None)
        if OllamaClient is None:
            raise ImportError("Please install ollama using 'pip install ollama'")
        model = OllamaClient(host=self.ollama_host)
        return model

    def initialize_anthropic(self):
        if self.anthropic_api_key:
            api_key = self.anthropic_api_key
        else:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        return anthropic.Anthropic(api_key=api_key)

    def validation(self, model, voice_mode):
        """
        Validate the input parameters for the dialog operation.
        """
        base_url = os.getenv("OPENAI_API_BASE_URL", "")
        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        if is_local and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = "none"
            self.openai_api_key = "none"

        is_builtin_non_openai = model in [
            "gemini-pro-vision",
            "claude-3",
            "qwen-vl",
            "llava",
        ]

        # Require OpenAI API key for OpenAI models and any custom models unless local
        is_openai_or_custom = not is_builtin_non_openai or voice_mode

        self.require_api_key(
            "OPENAI_API_KEY",
            "OpenAI (or custom OpenAI-compatible) API key",
            is_openai_or_custom,
        )
        self.require_api_key(
            "GOOGLE_API_KEY", "Google API key", model == "gemini-pro-vision"
        )
        self.require_api_key(
            "ANTHROPIC_API_KEY", "Anthropic API key", model == "claude-3"
        )
        self.require_api_key("QWEN_API_KEY", "Qwen API key", model == "qwen-vl")

    def require_api_key(self, key_name, key_description, is_required):
        key_exists = bool(os.environ.get(key_name))
        if self.verbose:
            print("[Config] require_api_key")
            print("[Config] key_name", key_name)
            print("[Config] key_description", key_description)
            print("[Config] key_exists", key_exists)
        if is_required and not key_exists:
            self.prompt_and_save_api_key(key_name, key_description)

    def prompt_and_save_api_key(self, key_name, key_description):
        key_value = input_dialog(
            title="API Key Required", text=f"Please enter your {key_description}:"
        ).run()

        if key_value is None:  # User pressed cancel or closed the dialog
            sys.exit("Operation cancelled by user.")

        if key_value:
            if key_name == "OPENAI_API_KEY":
                self.openai_api_key = key_value
            elif key_name == "GOOGLE_API_KEY":
                self.google_api_key = key_value
            elif key_name == "ANTHROPIC_API_KEY":
                self.anthropic_api_key = key_value
            elif key_name == "QWEN_API_KEY":
                self.qwen_api_key = key_value
            self.save_api_key_to_env(key_name, key_value)
            load_dotenv()  # Reload environment variables
            # Update the instance attribute with the new key

    @staticmethod
    def save_api_key_to_env(key_name, key_value):
        with open(".env", "a") as file:
            file.write(f"\n{key_name}='{key_value}'")
