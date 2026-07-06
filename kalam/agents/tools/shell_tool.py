import os
import subprocess

from langchain_core.tools import tool


@tool
def view_file(path: str) -> str:
    """Read a file from disk and return its contents. Use this to inspect existing code before making changes."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found at {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


@tool
def code_writer(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed. Use this to create new files or overwrite existing ones."""
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing to {path}: {e}"


# Module-level state for shell command confirmation
_pending_command: str | None = None
_approved_commands: set[str] = set()


def approve_shell(command: str) -> None:
    """Mark a shell command as approved by the user."""
    _approved_commands.add(command)
    global _pending_command
    if _pending_command == command:
        _pending_command = None


def clear_approvals() -> None:
    _approved_commands.clear()
    global _pending_command
    _pending_command = None


@tool
def run_shell(command: str) -> str:
    """Run a shell command and return its output. Use for testing, installing deps, running linters, or verification. Requires user approval."""
    global _pending_command
    if command not in _approved_commands:
        _pending_command = command
        return f"APPROVAL_REQUIRED: run `{command}`"

    _pending_command = None
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=os.getcwd(),
        )
        parts = []
        if result.stdout.strip():
            parts.append(result.stdout.strip())
        if result.stderr.strip():
            parts.append(f"stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            parts.append(f"(exit code {result.returncode})")
        return "\n".join(parts) if parts else f"(exit code {result.returncode})"
    except Exception as e:
        return f"error: {e}"
