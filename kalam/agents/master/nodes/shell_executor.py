import os
import subprocess

from kalam.agents.master.schema.state import MasterState


def _make_checkpoint_commands(generated_files: dict[str, str]) -> list[str]:
    commands: list[str] = []
    for path in generated_files:
        abs_path = os.path.abspath(path) if not os.path.isabs(path) else path
        commands.append(f"test -f {abs_path}")
        if path.endswith(".py"):
            commands.append(f"python -c \"compile(open('{abs_path}').read(), '{abs_path}', 'exec')\"")
    return commands


def shell_executor_node(state: MasterState) -> dict:
    errors: list[str] = list(state.get("errors", []))
    shell_output: list[dict] = list(state.get("shell_output", []))

    commands: list[str] = list(state.get("commands", []))
    if not commands:
        commands = _make_checkpoint_commands(state.get("generated_files", {}))

    if not commands:
        return {"shell_output": shell_output, "errors": errors, "status": "verifying"}

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=os.getcwd(),
            )
            shell_output.append({
                "command": cmd,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            })
            if result.returncode != 0:
                stderr = result.stderr.strip()
                detail = f": {stderr}" if stderr else ""
                errors.append(f"checkpoint failed (exit {result.returncode}){detail}: {cmd}")
        except Exception as e:
            errors.append(f"command error: {cmd}: {e}")

    return {"shell_output": shell_output, "errors": errors, "status": "verifying"}
