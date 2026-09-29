import asyncio
import os
import sys
from google.antigravity import Agent, LiteRTAgentConfig
from google.antigravity.hooks import policy

# Model path where litert-lm saves imported models
MODEL_PATH = os.path.expanduser("~/.litert-lm/models/gemma4-26b/model.litertlm")
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))

async def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}.")
        print("Please wait for 'litert-lm import' to finish downloading.")
        sys.exit(1)

    print(f"Loading local LiteRT model: {MODEL_PATH}")
    print("Initializing agent on-device. Please allow some time for initial load...")

    config = LiteRTAgentConfig(
        model_path=MODEL_PATH,
        workspaces=[WORKING_DIR],
        policies=[policy.allow_all()],
    ).lightweight()

    async with Agent(config) as agent:
        prompt = sys.argv[1] if len(sys.argv) > 1 else "List the top-level files in this repository and describe what this project does."
        print(f"\nPrompt: {prompt}\n")
        print("--- Response ---")
        
        response = await agent.chat(prompt)
        async for token in response:
            sys.stdout.write(token)
            sys.stdout.flush()
        print("\n----------------")

if __name__ == "__main__":
    asyncio.run(main())
