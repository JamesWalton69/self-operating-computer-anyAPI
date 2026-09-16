import asyncio
import os
import sys

# Ensure root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from operate.config import Config
from operate.models.apis import get_next_action
from operate.models.prompts import get_system_prompt

async def run_test():
    print("=" * 60)
    print("TESTING OMNIROUTE WITH AGY/GEMINI-3.7-FLASH-LOW")
    print("=" * 60)

    config = Config()
    base_url = os.getenv("OPENAI_API_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL_NAME", "agy/gemini-3.7-flash-low")
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")

    objective = "Open Google Chrome"
    system_prompt = get_system_prompt(model_name, objective)
    messages = [{"role": "system", "content": system_prompt}]

    print("\nInvoking get_next_action with objective:", objective)
    try:
        operations, session_id = await get_next_action(
            model=model_name,
            messages=messages,
            objective=objective,
            session_id=None,
        )
        print("\n--- MODEL RESPONSE OPERATIONS ---")
        import json
        print(json.dumps(operations, indent=2))
        print("---------------------------------")
        assert isinstance(operations, list), "Operations should be a list"
        assert len(operations) > 0, "Operations list should not be empty"
        print("\nSUCCESS: OmniRoute successfully processed multimodal input and returned valid operations!")
        return True
    except Exception as e:
        print(f"\nERROR running get_next_action: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
