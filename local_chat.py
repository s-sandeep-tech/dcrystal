import asyncio
import os
import sys
from google.antigravity import Agent, LiteRTAgentConfig, CapabilitiesConfig
from google.antigravity.hooks import policy
from google.antigravity.utils.interactive import run_interactive_loop

# Path to the imported local Gemma 4 26B model
MODEL_PATH = os.path.expanduser("~/.litert-lm/models/gemma4-26b/model.litertlm")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

async def main():
    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model file not found at {MODEL_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("  ANTIGRAVITY LOCAL AGENT (Gemma 4 26B on LiteRT)")
    print("=" * 60)
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Model:     {MODEL_PATH}")
    print("Running 100% locally on your Apple Metal GPU / Neural Engine.")
    print("Type your questions or tasks below. Type 'exit' to quit.\n")

    # Configure local agent with write & command capabilities in this workspace
    config = LiteRTAgentConfig(
        model_path=MODEL_PATH,
        workspaces=[WORKSPACE_DIR],
        capabilities=CapabilitiesConfig(),
        policies=[policy.allow_all()],
    ).lightweight()

    async with Agent(config) as agent:
        await run_interactive_loop(agent)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting local agent session.")
