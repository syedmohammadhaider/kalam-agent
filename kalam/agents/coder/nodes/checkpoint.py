import os

from kalam.agents.coder.schema.state import CoderState


def _resolve(root: str, path: str) -> str:
    return os.path.join(root, path) if not os.path.isabs(path) else path


def checkpoint_node(state: CoderState) -> dict:
    project_path = state.get("project_path", os.getcwd())
    errors: list[str] = list(state.get("errors", []))
    generated_files: dict[str, str] = dict(state.get("generated_files", {}))

    for file_path in generated_files:
        abs_path = _resolve(project_path, file_path)

        if not os.path.exists(abs_path):
            errors.append(f"checkpoint failed: file not found on disk — {file_path}")
            parent = os.path.dirname(abs_path)
            if parent and os.path.isdir(parent):
                try:
                    entries = sorted(os.listdir(parent))
                    hint = f"  (directory {parent} contains: {entries[:15]})"
                    errors.append(hint)
                except PermissionError:
                    errors.append(f"  (cannot list directory {parent}: permission denied)")
        else:
            if file_path.endswith(".py"):
                try:
                    with open(abs_path) as f:
                        content = f.read()
                    if content != generated_files[file_path]:
                        errors.append(
                            f"checkpoint warning: {file_path} exists but content differs "
                            f"from what was generated ({len(generated_files[file_path])} vs {len(content)} bytes)"
                        )
                except OSError as e:
                    errors.append(f"checkpoint warning: cannot read {file_path}: {e}")

    return {"errors": errors, "generated_files": generated_files}
