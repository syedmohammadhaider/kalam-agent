import os
import ast
import subprocess
from kalam.agents.coder.schema.state import CoderState


def _check_python_syntax(file_path: str) -> str | None:
    try:
        with open(file_path) as f:
            ast.parse(f.read())
        return None
    except SyntaxError as e:
        return f"Syntax error in {file_path}: {e}"


def _check_file_exists(file_path: str) -> str | None:
    if not os.path.exists(file_path):
        return f"File does not exist: {file_path}"
    return None


def verifier_node(state: CoderState) -> dict:
    errors: list[str] = list(state.get("errors", []))

    for file_path in state.get("generated_files", {}):
        err = _check_file_exists(file_path)
        if err:
            errors.append(err)
            continue

        if file_path.endswith(".py"):
            err = _check_python_syntax(file_path)
            if err:
                errors.append(err)
                continue

        try:
            result = subprocess.run(
                ["python", "-c", f"import py_compile; py_compile.compile('{file_path}', doraise=True)"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(f"Compile error in {file_path}: {result.stderr.strip()}")
        except Exception:
            pass

    return {"errors": errors, "generated_files": state.get("generated_files", {})}
