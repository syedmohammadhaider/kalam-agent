import os
import re
import subprocess
import tempfile
from agents.coder.schema.state import CoderState


def _parse_new_file_content(diff: str, file_path: str) -> str | None:
    lines = []
    in_target = False
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            in_target = os.path.abspath(line[6:]) == os.path.abspath(file_path)
            continue
        if line.startswith("---"):
            continue
        if line.startswith("@@") and in_target:
            continue
        if in_target and line.startswith("+"):
            lines.append(line[1:])
    return "\n".join(lines) if lines else None


def _apply_diff(diff: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False) as f:
        f.write(diff)
        diff_path = f.name
    try:
        result = subprocess.run(
            ["patch", "-p1", "-i", diff_path],
            capture_output=True, text=True, cwd=os.getcwd(),
        )
        ok = result.returncode == 0
        details = result.stderr.strip() if result.stderr else ""
        return ok, details
    except FileNotFoundError:
        return False, "patch command not found — is it installed?"
    finally:
        os.unlink(diff_path)


def _extract_target_files(diff: str) -> list[str]:
    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
    return files


def file_writer_node(state: CoderState) -> dict:
    generated_files: dict[str, str] = dict(state.get("generated_files", {}))
    errors: list[str] = list(state.get("errors", []))

    for diff_idx, diff in enumerate(state.get("diffs", [])):
        target_files = _extract_target_files(diff)

        for file_path in target_files:
            abs_path = os.path.abspath(file_path)
            if os.path.exists(abs_path):
                success, details = _apply_diff(diff)
                if success:
                    with open(abs_path) as f:
                        generated_files[file_path] = f.read()
                else:
                    msg = f"Failed to apply diff for {file_path} (diff {diff_idx})"
                    if details:
                        msg += f": {details}"
                    errors.append(msg)
            else:
                os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
                content = _parse_new_file_content(diff, file_path)
                if content is not None:
                    with open(abs_path, "w") as f:
                        f.write(content)
                    generated_files[file_path] = content
                else:
                    errors.append(f"Failed to parse new file content for {file_path} (diff {diff_idx})")

    return {"generated_files": generated_files, "errors": errors}
