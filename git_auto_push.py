#!/usr/bin/env python3
"""
git_auto_push.py
================
Detects local git changes and unpushed commits, uses a local on-device LLM
(via LiteRTAgent & Gemma 4 on Apple Silicon) to generate concise, contextual
Conventional Commit messages, and pushes changes to the remote repository.

Usage:
    python3 git_auto_push.py [OPTIONS]

Options:
    --all, -a            Stage changes, generate commit via LiteRTAgent, and push
    --detect, -d         Only detect and display status & unpushed commits
    --commit, -c         Stage and commit changes
    --push, -p           Push unpushed commits to remote
    --message, -m MSG    Custom commit message (overrides local LLM)
    --no-llm             Use fast rule-based commit generator instead of local LiteRT LLM
    --model-path PATH    Path to local .litertlm model file
    --remote REMOTE      Remote name (default: origin)
    --dry-run            Simulate operations without modifying git or pushing
    --yes, -y            Skip confirmation prompts
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Terminal colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

DEFAULT_MODEL_PATH = os.path.expanduser("~/.litert-lm/models/gemma4-26b/model.litertlm")
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> Tuple[int, str, str]:
    """Execute a git command and return (exit_code, stdout, stderr) preserving line-leading spaces."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd or WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )
        # Note: rstrip only trailing whitespace to preserve porcelain indentation
        stdout = res.stdout.rstrip("\r\n") if res.stdout else ""
        stderr = res.stderr.rstrip("\r\n") if res.stderr else ""
        return res.returncode, stdout, stderr
    except subprocess.CalledProcessError as e:
        stdout = e.stdout.rstrip("\r\n") if e.stdout else ""
        stderr = e.stderr.rstrip("\r\n") if e.stderr else ""
        return e.returncode, stdout, stderr
    except FileNotFoundError:
        print(f"{RED}Error: 'git' executable not found in PATH.{RESET}")
        sys.exit(1)


def is_git_repository() -> bool:
    code, out, _ = run_git(["rev-parse", "--is-inside-work-tree"], check=False)
    return code == 0 and out.strip().lower() == "true"


def get_current_branch() -> str:
    code, out, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    return out.strip() if code == 0 else ""


def get_git_status() -> Dict[str, List[str]]:
    """Parse git status --porcelain accurately."""
    _, out, _ = run_git(["status", "--porcelain"], check=False)
    changes: Dict[str, List[str]] = {
        "staged": [],
        "modified": [],
        "untracked": [],
        "deleted": [],
    }

    if not out:
        return changes

    for line in out.splitlines():
        if len(line) < 3:
            continue

        index_status = line[0]
        worktree_status = line[1]
        filepath = line[3:].strip()

        # Untracked files
        if index_status == "?" and worktree_status == "?":
            changes["untracked"].append(filepath)
            continue

        # Staged changes (Index differs from HEAD)
        if index_status in ["M", "A", "R", "C", "D"]:
            changes["staged"].append(filepath)

        # Unstaged modifications in worktree
        if worktree_status == "M":
            changes["modified"].append(filepath)
        elif worktree_status == "D":
            changes["deleted"].append(filepath)

    return changes


def get_diff_summary(max_diff_lines: int = 150) -> str:
    """Fetch git diff summary and capped diff text for LLM context."""
    # Staged or unstaged diff stat
    _, stat_out, _ = run_git(["diff", "HEAD", "--stat"], check=False)
    if not stat_out:
        _, stat_out, _ = run_git(["diff", "--stat"], check=False)

    # Detailed patch, capped to avoid context overflow
    _, diff_out, _ = run_git(["diff", "HEAD"], check=False)
    if not diff_out:
        _, diff_out, _ = run_git(["diff"], check=False)

    diff_lines = diff_out.splitlines() if diff_out else []
    if len(diff_lines) > max_diff_lines:
        truncated_diff = "\n".join(diff_lines[:max_diff_lines]) + f"\n... [diff truncated, {len(diff_lines) - max_diff_lines} lines omitted]"
    else:
        truncated_diff = "\n".join(diff_lines)

    summary = ""
    if stat_out:
        summary += f"File Summary:\n{stat_out}\n\n"
    if truncated_diff:
        summary += f"Diff Content:\n{truncated_diff}"

    return summary


def get_unpushed_commits(remote: str, branch: str) -> List[Dict[str, str]]:
    """Detect local commits that are ahead of the remote."""
    _, upstream, _ = run_git(["rev-parse", "--abbrev-ref", "@{u}"], check=False)
    upstream = upstream.strip()

    target_ref = upstream if upstream else f"{remote}/{branch}"

    code, _, _ = run_git(["rev-parse", "--verify", target_ref], check=False)
    if code != 0:
        # Remote tracking branch does not exist yet; list commits on local branch
        code, log_out, _ = run_git(["log", branch, "--oneline", "-n", "25"], check=False)
    else:
        code, log_out, _ = run_git(["log", f"{target_ref}..HEAD", "--oneline"], check=False)

    commits = []
    if code == 0 and log_out:
        for line in log_out.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 1)
            commit_hash = parts[0]
            msg = parts[1] if len(parts) > 1 else ""
            commits.append({"hash": commit_hash, "message": msg})

    return commits


def fallback_rule_based_commit_message(changes: Dict[str, List[str]]) -> str:
    """Fast rule-based commit message generator when LLM is skipped."""
    all_files = set()
    for file_list in changes.values():
        all_files.update(file_list)

    if not all_files:
        return "chore: update local files"

    scopes = set()
    is_doc = True
    is_fix = False
    is_test = False

    for f in all_files:
        parts = Path(f).parts
        if len(parts) > 1:
            scopes.add(parts[0])
        else:
            scopes.add(parts[0].split(".")[0])

        lower = f.lower()
        if not (lower.endswith(".md") or "doc" in lower):
            is_doc = False
        if "test" in lower:
            is_test = True
        if any(keyword in lower for keyword in ["fix", "bug", "patch"]):
            is_fix = True

    if is_doc:
        commit_type = "docs"
    elif is_test and len(all_files) <= 2:
        commit_type = "test"
    elif is_fix:
        commit_type = "fix"
    else:
        if changes["untracked"] and not changes["modified"] and not changes["staged"]:
            commit_type = "feat"
        else:
            commit_type = "feat" if any("routes" in f or "api" in f or "app" in f for f in all_files) else "chore"

    scope_str = ""
    if len(scopes) == 1:
        scope_str = f"({list(scopes)[0]})"
    elif 1 < len(scopes) <= 2:
        scope_str = f"({','.join(sorted(scopes))})"

    file_count = len(all_files)
    sample_files = [Path(f).name for f in list(all_files)[:3]]
    sample_desc = ", ".join(sample_files)
    if file_count > 3:
        sample_desc += f" and {file_count - 3} other(s)"

    action = "update"
    if changes["untracked"] and not changes["modified"]:
        action = "add"
    elif changes["deleted"] and not changes["modified"] and not changes["untracked"]:
        action = "remove"

    return f"{commit_type}{scope_str}: {action} {sample_desc}"


async def generate_commit_with_local_llm(
    changes: Dict[str, List[str]],
    diff_context: str,
    model_path: str,
) -> Optional[str]:
    """
    Invokes the local LiteRTAgent (on-device Gemma 4 26B) to inspect changes
    and generate a high quality Conventional Commit message.
    """
    if not os.path.exists(model_path):
        print(f"{YELLOW}Warning: Local model not found at {model_path}. Using rule-based fallback.{RESET}")
        return None

    try:
        from google.antigravity import Agent, LiteRTAgentConfig
        from google.antigravity.hooks import policy
    except ImportError as e:
        print(f"{YELLOW}Warning: google.antigravity package not installed ({e}). Using rule-based fallback.{RESET}")
        return None

    print(f"{CYAN}Generating commit message with local LLM (LiteRTAgent on Apple Silicon)...{RESET}")

    files_list = []
    for category, filepaths in changes.items():
        if filepaths:
            files_list.append(f"{category.upper()}: " + ", ".join(filepaths))
    changed_files_str = "\n".join(files_list)

    prompt = (
        "You are an expert Git commit message generator.\n"
        "Analyze the following changed files and diff from the repository.\n"
        "Write a concise, standard Conventional Commit message in imperative mood.\n"
        "Format: <type>(<optional-scope>): <summary subject line under 72 chars>\n"
        "Examples:\n"
        "- feat(auth): add token refresh endpoint\n"
        "- fix(routes): resolve stock calculation discrepancy\n"
        "- chore: update deployment configuration\n\n"
        f"Changed files:\n{changed_files_str}\n\n"
        f"{diff_context}\n\n"
        "CRITICAL INSTRUCTION: Output ONLY the commit message itself on a single line. "
        "Do NOT include explanations, markdown code blocks, quotes, or preamble."
    )

    try:
        config = LiteRTAgentConfig(
            model_path=model_path,
            workspaces=[WORKSPACE_DIR],
            policies=[policy.allow_all()],
        ).lightweight()

        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            full_response = ""
            async for token in response:
                full_response += token

            raw = full_response.strip()
            # Clean up potential markdown formatting or quotes
            clean_msg = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            clean_msg = re.sub(r"\n?```$", "", clean_msg).strip()
            clean_msg = clean_msg.strip('"\'`')

            # Extract the first non-empty line as commit subject
            lines = [l.strip() for l in clean_msg.splitlines() if l.strip()]
            if lines:
                return lines[0]
            return clean_msg if clean_msg else None

    except Exception as ex:
        print(f"{YELLOW}Local LiteRTAgent error: {ex}. Falling back to rule-based generator.{RESET}")
        return None


def print_detection_report(
    branch: str,
    changes: Dict[str, List[str]],
    unpushed_commits: List[Dict[str, str]],
    remote: str,
):
    print(f"\n{BOLD}{CYAN}=== Git Local Status & Commit Detector ==={RESET}")
    print(f"Current Branch: {BOLD}{GREEN}{branch}{RESET}")
    print(f"Remote:         {CYAN}{remote}{RESET}\n")

    total_uncommitted = sum(len(v) for v in changes.values())
    if total_uncommitted == 0:
        print(f"{GREEN}✓ Working tree clean (no uncommitted changes).{RESET}")
    else:
        print(f"{YELLOW}● Uncommitted Changes ({total_uncommitted} file(s)):{RESET}")
        for filepath in changes["staged"]:
            print(f"  {GREEN}[staged]    {filepath}{RESET}")
        for filepath in changes["modified"]:
            print(f"  {YELLOW}[modified]  {filepath}{RESET}")
        for filepath in changes["untracked"]:
            print(f"  {CYAN}[untracked] {filepath}{RESET}")
        for filepath in changes["deleted"]:
            print(f"  {RED}[deleted]   {filepath}{RESET}")

    print()
    if not unpushed_commits:
        print(f"{GREEN}✓ No unpushed commits. Local branch is in sync with {remote}.{RESET}")
    else:
        print(f"{YELLOW}● Local Commits Ahead (Ready to Push - {len(unpushed_commits)} commit(s)):{RESET}")
        for c in unpushed_commits:
            print(f"  {BOLD}{CYAN}{c['hash']}{RESET} {c['message']}")

    print()


def ask_confirmation(prompt: str) -> bool:
    try:
        reply = input(f"{BOLD}{prompt} [y/N]: {RESET}").strip().lower()
        return reply in ["y", "yes"]
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Detect local git changes, generate commits via local LiteRTAgent, and push to remote.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Full workflow: auto-stage, commit with LiteRTAgent generated message, and push",
    )
    parser.add_argument(
        "--detect", "-d",
        action="store_true",
        help="Only detect and display status & commits (default)",
    )
    parser.add_argument(
        "--commit", "-c",
        action="store_true",
        help="Stage all changes and commit",
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="Push unpushed commits to remote",
    )
    parser.add_argument(
        "--message", "-m",
        type=str,
        default=None,
        help="Custom commit message (overrides local LLM generation)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip local LiteRTAgent LLM and use fast rule-based message generation",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to LiteRT model (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default="origin",
        help="Name of git remote (default: origin)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the operations without executing commit or push",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Automatic yes to confirmation prompts",
    )

    args = parser.parse_args()

    # Verify git repository
    if not is_git_repository():
        print(f"{RED}Error: Current directory '{WORKSPACE_DIR}' is not a git repository.{RESET}")
        sys.exit(1)

    branch = get_current_branch()
    if not branch:
        print(f"{RED}Error: Unable to determine current git branch (detached HEAD?).{RESET}")
        sys.exit(1)

    # 1. Detect Changes & Unpushed Commits
    changes = get_git_status()
    unpushed_commits = get_unpushed_commits(args.remote, branch)
    print_detection_report(branch, changes, unpushed_commits, args.remote)

    # If --detect was requested, we are done
    if args.detect:
        return

    do_commit = args.commit or args.all
    do_push = args.push or args.all

    total_uncommitted = sum(len(v) for v in changes.values())

    # Interactive prompt if no explicit execution flag was given
    if not (do_commit or do_push):
        if total_uncommitted == 0 and not unpushed_commits:
            print(f"{GREEN}Working tree is clean and up to date! Nothing to do.{RESET}")
            return

        if not args.yes:
            prompt_actions = []
            if total_uncommitted > 0:
                prompt_actions.append("commit changes")
            if unpushed_commits or total_uncommitted > 0:
                prompt_actions.append("push to remote")

            action_summary = " and ".join(prompt_actions)
            if ask_confirmation(f"Proceed to {action_summary}?"):
                do_commit = total_uncommitted > 0
                do_push = True
            else:
                return

    # 2. Stage and Commit
    if do_commit:
        if total_uncommitted == 0:
            print(f"{CYAN}No uncommitted changes to commit.{RESET}")
        else:
            commit_msg = args.message
            if not commit_msg:
                if not args.no_llm:
                    diff_ctx = get_diff_summary()
                    commit_msg = await generate_commit_with_local_llm(changes, diff_ctx, args.model_path)
                if not commit_msg:
                    commit_msg = fallback_rule_based_commit_message(changes)

            print(f"\n{BOLD}Commit Message:{RESET} {GREEN}'{commit_msg}'{RESET}")

            if args.dry_run:
                print(f"{YELLOW}[Dry-Run] Would run: git add -A && git commit -m \"{commit_msg}\"{RESET}")
            else:
                if not args.yes and not args.all:
                    if not ask_confirmation("Proceed with this commit message?"):
                        custom = input("Enter custom commit message (leave blank to abort): ").strip()
                        if not custom:
                            print("Commit aborted.")
                            return
                        commit_msg = custom

                # Stage all changes
                print(f"Staging changes: {CYAN}git add -A{RESET}")
                code, _, err = run_git(["add", "-A"], check=False)
                if code != 0:
                    print(f"{RED}Failed to stage changes: {err}{RESET}")
                    sys.exit(1)

                # Commit
                print(f"Committing changes: {CYAN}git commit -m \"{commit_msg}\"{RESET}")
                code, out, err = run_git(["commit", "-m", commit_msg], check=False)
                if code != 0:
                    print(f"{RED}Commit failed: {err}{RESET}")
                    sys.exit(1)

                print(f"{GREEN}✓ Successfully committed!{RESET}")
                unpushed_commits = get_unpushed_commits(args.remote, branch)

    # 3. Push to Remote
    if do_push:
        if not unpushed_commits:
            print(f"{CYAN}No unpushed commits detected. Nothing to push.{RESET}")
            return

        print(f"\n{BOLD}Ready to push {len(unpushed_commits)} commit(s) to '{args.remote}/{branch}'.{RESET}")

        if args.dry_run:
            print(f"{YELLOW}[Dry-Run] Would run: git push -u {args.remote} {branch}{RESET}")
            return

        if not args.yes:
            if not ask_confirmation(f"Push to {args.remote}/{branch}?"):
                print("Push aborted.")
                return

        print(f"Pushing to {args.remote}/{branch}...")
        _, upstream, _ = run_git(["rev-parse", "--abbrev-ref", "@{u}"], check=False)
        push_args = ["push"]
        if not upstream.strip():
            push_args.extend(["-u", args.remote, branch])

        code, out, err = run_git(push_args, check=False)
        if code != 0:
            print(f"{RED}Push failed:\n{err or out}{RESET}")
            sys.exit(1)

        print(f"{GREEN}✓ Successfully pushed changes to {args.remote}/{branch}!{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
