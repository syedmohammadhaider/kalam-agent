from kalam.agents.master.schema.state import MasterState
from kalam.agents.coder.graph import coder_graph
from kalam.agents.coder.schema.state import CoderState


def executor_node(state: MasterState) -> dict:
    generated_files: dict[str, str] = {}
    all_errors: list[str] = []
    status = "executing"

    for task_idx, task in enumerate(state.get("todo", [])):
        coder_state: CoderState = {
            "todo": [],
            "prompt": task["task"],
            "context": state.get("context", []),
            "files": state.get("files", []),
            "injected_context": task.get("context", ""),
            "diffs": [],
            "generated_files": {},
            "errors": [],
        }

        result = coder_graph.invoke(coder_state)
        task_errors = result.get("errors", [])
        if task_errors:
            all_errors.append(f"Task {task_idx + 1} ('{task['task'][:60]}'): {'; '.join(task_errors)}")

        generated_files.update(result.get("generated_files", {}))

    history: list[dict] = list(state.get("history", []))
    summary = f"todo: {[t['task'][:80] for t in state.get('todo', [])]}"
    if generated_files:
        summary += f"\ngenerated: {list(generated_files.keys())}"
    if all_errors:
        summary += f"\nerrors: {all_errors}"
    history.append({"role": "user", "content": state.get("prompt", "")})
    history.append({"role": "assistant", "content": summary})

    return {"generated_files": generated_files, "errors": all_errors, "history": history, "status": "generating"}
