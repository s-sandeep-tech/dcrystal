import asyncio
import json
import os
import sys
from google.antigravity import Agent, LocalAgentConfig, LiteRTAgentConfig, CapabilitiesConfig
from google.antigravity.hooks import policy

# 1. Path to your locally imported Gemma 4 26B LiteRT model
MODEL_PATH = os.path.expanduser("~/.litert-lm/models/gemma4-26b/model.litertlm")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

async def run_hybrid_workflow(high_level_task: str, file_list: list[str]):
    """
    Hybrid Orchestration Pattern:
    1. Cloud Architect (Gemini Flash): High-level planner.
       - Takes only the task description and file names (NO file contents uploaded).
       - Generates a concise, structured task list.
    2. Local Worker (Gemma 4 on LiteRT): On-device execution.
       - Takes each task, reads local file contents, generates code, and runs tests.
       - 100% private: source code stays completely on-device.
    """
    print("\n" + "=" * 65)
    print("  HYBRID ORCHESTRATION: CLOUD ARCHITECT + LOCAL WORKER")
    print("=" * 65)

    # -------------------------------------------------------------
    # PHASE 1: Cloud Architect (Planner)
    # -------------------------------------------------------------
    print("\n[Phase 1: Cloud Architect Planning]")
    print(f"Objective: {high_level_task}")
    print(f"Target files: {', '.join(file_list)} (Metadata only, no code uploaded)")

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        print("Connecting to Cloud Architect (Gemini)...")
        planner_config = LocalAgentConfig(
            model="gemini-2.5-flash",
            api_key=api_key,
            system_instructions=(
                "You are an AI Software Architect. Given an objective and a list of target file names, "
                "decompose the work into an ordered list of concrete, actionable tasks for a local code worker. "
                "Return ONLY a raw JSON array of strings, without markdown backticks."
            )
        )
        async with Agent(planner_config) as architect:
            prompt = f"Objective: {high_level_task}\nFiles: {file_list}\nDecompose into 2-3 execution tasks:"
            response = await architect.chat(prompt)
            plan_text = ""
            async for token in response:
                plan_text += token
            
            try:
                tasks = json.loads(plan_text.strip().removeprefix("```json").removesuffix("```").strip())
            except Exception:
                tasks = [plan_text.strip()]
    else:
        # Fallback plan if GEMINI_API_KEY is not set in shell environment
        print("Note: GEMINI_API_KEY not set in shell. Using pre-decomposed plan.")
        tasks = [
            f"Inspect {file_list[0]} and locate key functions or data structures.",
            f"Review logic in {file_list[0]} and draft recommended improvements or test assertions."
        ]

    print("\n[Architect's Plan]:")
    for i, t in enumerate(tasks, 1):
        print(f"  Step {i}: {t}")

    # -------------------------------------------------------------
    # PHASE 2: Local Worker (Gemma 4 26B on LiteRT)
    # -------------------------------------------------------------
    print("\n" + "-" * 65)
    print("[Phase 2: Local Worker Execution on Local GPU]")
    print(f"Model: {MODEL_PATH}")
    print("All code inspection and editing runs strictly on-device.")
    print("-" * 65)

    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model not found at {MODEL_PATH}")
        return

    worker_config = LiteRTAgentConfig(
        model_path=MODEL_PATH,
        workspaces=[WORKSPACE_DIR],
        capabilities=CapabilitiesConfig(),
        policies=[policy.allow_all()], # Grants permission to read/write files and execute commands locally
    ).lightweight()

    async with Agent(worker_config) as worker:
        for idx, task_step in enumerate(tasks, 1):
            print(f"\n>>> Executing Step {idx}: {task_step}\n")
            worker_response = await worker.chat(f"Workspace directory: {WORKSPACE_DIR}\nExecute this task: {task_step}")
            async for token in worker_response:
                sys.stdout.write(token)
                sys.stdout.flush()
            print()

    print("\n" + "=" * 65)
    print("Hybrid Orchestration Complete: Plan created in Cloud, executed On-Device.")
    print("=" * 65)

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Audit security and validate error handling"
    files = sys.argv[2:] if len(sys.argv) > 2 else ["server/tests/test_auth_security.py"]
    asyncio.run(run_hybrid_workflow(task, files))
