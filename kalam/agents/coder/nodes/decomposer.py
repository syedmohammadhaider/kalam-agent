from langchain_core.messages import HumanMessage, SystemMessage

from kalam.agents.utils import get_llm, llm_call_with_retry
from kalam.agents.coder.schema.state import CoderState


DECOMPOSER_SYSTEM_PROMPT = """The following tools are available:
- code_writer(path, content) — write a file
- view_file(path) — read a file
- run_shell(command) — run shell commands

Split the task ONLY when it truly requires multiple unrelated steps that use different tools on different files. Prefer ONE subtask.

Format: <task> | <file1.py, file2.py>

Examples — single subtask (preferred):
Add Item model with CRUD endpoints | src/models.py, src/routes.py
Add unit tests for the API | tests/test_api.py

Examples — split only when truly independent:
Add Item model | src/models.py
Add GET /items route | src/routes.py"""


def _is_simple_task(prompt: str, subtasks: list) -> bool:
    if len(subtasks) <= 1:
        return True
    all_files: set[str] = set()
    for st in subtasks:
        for f in st.get("files", []):
            all_files.add(f)
    if len(all_files) <= 1:
        return True
    if len(subtasks) <= 2 and len(prompt.strip().split()) <= 15:
        return True
    return False


def _parse_tasks(text: str, prompt: str, injected_context: str, files: list[str]) -> list[dict]:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return [{"task": prompt, "context": injected_context, "files": files}]
    result = []
    for l in lines:
        parts = l.split("|", 1)
        task = parts[0].strip()
        task_files = [f.strip() for f in parts[1].split(",")] if len(parts) > 1 else list(files)
        result.append({"task": task, "context": injected_context, "files": task_files})
    return result


def decomposer_node(state: CoderState) -> dict:
    messages = [
        SystemMessage(content=DECOMPOSER_SYSTEM_PROMPT),
        HumanMessage(content=f"## Task\n{state['prompt']}\n\n## Context\n{state['injected_context']}\n\n## Files\n{', '.join(state['files'])}"),
    ]

    llm = get_llm(node="decomposer")
    text = llm_call_with_retry(llm, messages)
    subtasks = _parse_tasks(text, state["prompt"], state.get("injected_context", ""), state.get("files", []))
    skip_decompose = _is_simple_task(state["prompt"], subtasks)

    return {"todo": subtasks, "skip_decompose": skip_decompose}
