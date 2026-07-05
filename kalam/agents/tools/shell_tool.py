import os
import subprocess

from langchain_core.tools import tool


@tool
def run_shell(command: str) -> str:
    """Run a shell command and return its output.

    Use this to verify files exist, check directory contents, run tests,
    or execute any command-line operation.
    """
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
