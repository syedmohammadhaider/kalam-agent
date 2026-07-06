from langchain_core.messages import HumanMessage, SystemMessage

from kalam.agents.utils import get_llm, llm_call_with_retry, read_files
from kalam.agents.master.schema.state import MasterState


PLANNER_SYSTEM_PROMPT = """Break the user request into as few coding tasks as possible. Prefer ONE task.

Rules:
- Combine tightly coupled changes (model + route + schema) into ONE task
- Split only when changes are completely independent across unrelated files
- If the request is straightforward, output the original request as a single task
- Do not number tasks; one task per line, dependencies first

Examples — single task (preferred):
Add Item model with CRUD routes, schema, and database migration
Add user authentication with JWT and login endpoint
Fix input validation across all forms

Examples — split (only when truly independent):
Add user authentication with JWT
Add logging middleware"""


def _parse_todo(text: str, prompt: str) -> list[dict]:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return [{"task": prompt, "context": ""}]
    return [{"task": l, "context": ""} for l in lines]


def planner_node(state: MasterState) -> dict:
    file_contents = read_files(state["files"])

    files_section = "\n\n---\n".join(
        f"### {path}\n```\n{content}\n```"
        for path, content in file_contents.items()
    )

    history_section = ""
    history = state.get("history", [])
    if history:
        history_lines = []
        for entry in history:
            role = entry.get("role", "unknown")
            content = entry.get("content", "")
            if len(content) > 500:
                content = content[:500] + "..."
            history_lines.append(f"[{role}]\n{content}")
        history_section = "\n\n---\n".join(history_lines)

    user_message = f"## User Request\n{state['prompt']}\n\n## Project Files\n{files_section}"
    if history_section:
        user_message += f"\n\n## Conversation History\n{history_section}"

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    llm = get_llm(node="planner")
    text = llm_call_with_retry(llm, messages)
    todo_list = _parse_todo(text, state["prompt"])

    context = [f"File: {path}\n{content[:2000]}" for path, content in file_contents.items()]

    return {
        "todo": todo_list,
        "context": context,
        "errors": [],
        "status": "planning",
    }
