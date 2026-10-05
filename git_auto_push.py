#!/usr/bin/env python3
"""
git_auto_push.py
================
Detects local git changes and unpushed commits, uses a lightweight local on-device
Gemma model via LiteRT-LM (e.g. gemma-4b / gemma2-9b on Apple Silicon) to generate
concise, contextual Conventional Commit messages, and pushes changes to the remote repository.

Usage:
    python3 git_auto_push.py [OPTIONS]

Options:
    --all, -a            Stage changes, generate commit via local Gemma, and push
    --detect, -d         Only detect and display status & unpushed commits
    --commit, -c         Stage and commit changes
    --push, -p           Push unpushed commits to remote
    --message, -m MSG    Custom commit message (overrides local LLM)
    --model MODEL        Name of LiteRT model to use (default: auto-detected, e.g. gemma-4b or gemma2-9b)
    --no-llm             Skip local LLM and use fast rule-based message generator
    --remote REMOTE      Remote name (default: origin)
    --dry-run            Simulate operations without modifying git or pushing
    --yes, -y            Skip confirmation prompts
"""

import argparse
import os
import re
import shutil
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

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
LITERT_MODELS_DIR = os.path.expanduser("~/.litert-lm/models")


def run_git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> Tuple[int, str, str]:
    """Execute a git command and return (exit_code, stdout, stderr) preserving output formatting."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd or WORKSPACE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=check,
        )
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


def get_diff_summary(max_diff_lines: int = 80) -> str:
    """Fetch git diff summary and capped diff text for LLM context."""
    _, stat_out, _ = run_git(["diff", "HEAD", "--stat"], check=False)
    if not stat_out:
        _, stat_out, _ = run_git(["diff", "--stat"], check=False)

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


def resolve_local_model(requested_model: Optional[str] = None) -> Optional[str]:
    """Find the best matching local LiteRT-LM model."""
    if requested_model:
        # Check direct model directory or file
        if os.path.exists(os.path.join(LITERT_MODELS_DIR, requested_model)) or os.path.exists(requested_model):
            return requested_model

    # Check preferred lightweight models
    candidates = ["gemma2-9b", "gemma-4b", "gemma-12b", "gemma-e4b"]
    for c in candidates:
        if os.path.exists(os.path.join(LITERT_MODELS_DIR, c)):
            return c

    # Fallback to any directory in models dir that is not the heavy 26b
    if os.path.exists(LITERT_MODELS_DIR):
        for entry in os.listdir(LITERT_MODELS_DIR):
            if "26b" not in entry.lower() and os.path.isdir(os.path.join(LITERT_MODELS_DIR, entry)):
                return entry

    return requested_model


def generate_commit_with_local_llm(
    changes: Dict[str, List[str]],
    diff_context: str,
    model_name: str,
) -> Optional[str]:
    """
    Invokes the local LiteRT-LM CLI (e.g. gemma-4b / gemma2-9b)
    to generate a concise Conventional Commit message.
    """
    litert_bin = shutil.which("litert-lm")
    if not litert_bin:
        # Check standard user paths
        candidate_paths = [
            os.path.expanduser("~/.pyenv/shims/litert-lm"),
            os.path.expanduser("~/.local/bin/litert-lm"),
            "/usr/local/bin/litert-lm",
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                litert_bin = p
                break

    if not litert_bin:
        print(f"{YELLOW}Warning: 'litert-lm' CLI not found. Falling back to rule-based generator.{RESET}")
        return None

    files_list = []
    for category, filepaths in changes.items():
        if filepaths:
            files_list.append(f"{category.upper()}: " + ", ".join(filepaths))
    changed_files_str = "\n".join(files_list)

    prompt = (
        "You are an expert Git commit message generator.\n"
        "Analyze the following changed files and diff.\n"
        "Write a single concise Conventional Commit message in imperative mood (under 72 chars).\n"
        "Format: <type>(<scope>): <summary>\n"
        "Types: feat, fix, refactor, style, docs, chore, test.\n"
        f"Changed files:\n{changed_files_str}\n\n"
        f"{diff_context}\n\n"
        "CRITICAL: Output ONLY the commit message itself on one line. No markdown, no quotes, no explanation."
    )

    print(f"{CYAN}Generating commit message with local Gemma ({model_name})...{RESET}")
    try:
        res = subprocess.run(
            [litert_bin, "run", model_name, "--prompt", prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        if res.returncode != 0:
            print(f"{YELLOW}Local model inference returned non-zero code: {res.stderr.strip()}{RESET}")
            return None

        output = res.stdout.strip()
        lines = [line.strip() for line in output.splitlines() if line.strip()]

        # Filter out informational engine lines (e.g. "Using model's default backend: gpu")
        filtered_lines = [
            l for l in lines
            if not l.lower().startswith("using model")
            and not l.lower().startswith("[enter]")
            and not l.startswith(">")
        ]

        if not filtered_lines:
            return None

        raw = filtered_lines[0]
        # Clean up markdown quotes or code fences
        clean = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        clean = re.sub(r"\n?```$", "", clean).strip()
        clean = clean.strip('"\'`')

        return clean if clean else None

    except subprocess.TimeoutExpired:
        print(f"{YELLOW}Local model inference timed out. Using fallback generator.{RESET}")
        return None
    except Exception as ex:
        print(f"{YELLOW}Local LLM error: {ex}. Using fallback generator.{RESET}")
        return None


def generate_fallback_commit_message(changes: Dict[str, List[str]]) -> str:
    """Fast rule-based commit message generator when LLM is unavailable."""
    all_files = []
    for file_list in changes.values():
        all_files.extend(file_list)

    if not all_files:
        return "chore: update project files"

    scopes = set()
    for fp in all_files:
        p = Path(fp)
        name = p.stem.lower()
        if "party_order" in name or "party_order" in fp:
            scopes.add("party-order")
        elif "settings" in name:
            scopes.add("settings")
        elif "user" in name or "rbac" in fp:
            scopes.add("users")
        elif len(p.parts) > 1:
            scopes.add(p.parts[0].lower().replace("_", "-"))
        else:
            scopes.add(name.replace("_", "-"))

    scope_str = f"({list(scopes)[0]})" if scopes else ""

    if all(f.endswith(".md") for f in all_files):
        commit_type = "docs"
        desc = "update documentation"
    elif all("test" in f.lower() for f in all_files):
        commit_type = "test"
        desc = "update tests"
    elif changes["untracked"] and not changes["modified"]:
        commit_type = "feat"
        desc = f"add {Path(all_files[0]).name}"
    else:
        commit_type = "feat" if any("template" in f or "api" in f for f in all_files) else "refactor"
        desc = f"update {Path(all_files[0]).name}"
        if len(all_files) > 1:
            desc += f" and {len(all_files) - 1} other file(s)"

    return f"{commit_type}{scope_str}: {desc}"


def print_detection_report(
    branch: str,
    changes: Dict[str, List[str]],
    unpushed_commits: List[Dict[str, str]],
    remote: str,
):
    print(f"\n{BOLD}{CYAN}=== Git Status & Local LLM Commit Helper ==={RESET}")
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


def main():
    parser = argparse.ArgumentParser(
        description="Local git helper: detect changes, auto-generate commit messages via local Gemma, and push.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Full workflow: auto-stage, commit with local Gemma generated message, and push",
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
        help="Custom commit message (overrides local LLM)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LiteRT-LM model identifier (e.g. gemma2-9b, gemma-4b)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip local Gemma model and use fast rule-based message generator",
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
        help="Simulate operations without executing commit or push",
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
                    model_to_use = resolve_local_model(args.model)
                    if model_to_use:
                        diff_ctx = get_diff_summary()
                        commit_msg = generate_commit_with_local_llm(changes, diff_ctx, model_to_use)

                if not commit_msg:
                    commit_msg = generate_fallback_commit_message(changes)

            print(f"\n{BOLD}Commit Message:{RESET} {GREEN}'{commit_msg}'{RESET}")

            if args.dry_run:
                print(f"{YELLOW}[Dry-Run] Would run: git add -A && git commit -m \"{commit_msg}\"{RESET}")
            else:
                if not args.yes and not args.all and not args.message:
                    if not ask_confirmation("Proceed with this commit message?"):
                        custom = input("Enter custom commit message (leave blank to abort): ").strip()
                        if not custom:
                            print("Commit aborted.")
                            return
                        commit_msg = custom

                # Stage all changes
                print("Staging all changes...")
                code, out, err = run_git(["add", "-A"], check=False)
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
        simulated_commit_pending = args.dry_run and do_commit and (total_uncommitted > 0)

        if not unpushed_commits and not simulated_commit_pending:
            print(f"{CYAN}No unpushed commits detected. Nothing to push.{RESET}")
            return

        commit_count = len(unpushed_commits) + (1 if simulated_commit_pending else 0)
        print(f"\n{BOLD}Ready to push {commit_count} commit(s) to '{args.remote}/{branch}'.{RESET}")

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
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
