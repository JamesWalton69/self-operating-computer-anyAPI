import unittest
from operate.models.apis import reset_prompt_context, _INITIALIZED_SESSIONS
from operate.gui.studio import PROVIDER_CONFIGS, OMNIROUTE_MODELS


class TestStudioLogic(unittest.TestCase):
    def test_reset_prompt_context(self):
        # Add dummy session
        _INITIALIZED_SESSIONS.add(("test-model", "test-objective"))
        self.assertGreater(len(_INITIALIZED_SESSIONS), 0)

        # Reset
        reset_prompt_context()
        self.assertEqual(len(_INITIALIZED_SESSIONS), 0)

    def test_provider_configs(self):
        expected_presets = [
            "Google Account (Direct Antigravity)",
            "Local OmniRoute (localhost:20128)",
            "Custom (OpenAI-compatible)",
            "Local Ollama (localhost:11434)",
            "Local LM Studio (localhost:1234)",
            "Local vLLM (localhost:8000)",
            "OpenRouter",
            "OpenAI Official",
            "Anthropic Claude",
            "Google Gemini (API Key)",
            "Alibaba Qwen",
        ]
        for preset in expected_presets:
            self.assertIn(preset, PROVIDER_CONFIGS)
            cfg = PROVIDER_CONFIGS[preset]
            self.assertIn("env_key", cfg)
            self.assertIn("default_url", cfg)
            self.assertIn("default_model", cfg)
            self.assertIn("models", cfg)
            self.assertIsInstance(cfg["models"], list)

    def test_omniroute_defaults(self):
        omni = PROVIDER_CONFIGS["Local OmniRoute (localhost:20128)"]
        self.assertEqual(omni["default_url"], "http://localhost:20128/v1")
        self.assertEqual(omni["default_key"], "sk-b6fe217dd1fbeeda-18f222-7107776b")
        self.assertEqual(omni["models"], OMNIROUTE_MODELS)


if __name__ == "__main__":
    unittest.main()
