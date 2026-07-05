import json

from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError

from kalam.agents.utils import get_llm, read_files
from kalam.agents.master.schema.state import MasterState


PLANNER_SYSTEM_PROMPT = """Break the user request into a list of coding tasks. Order by dependencies first.

Return JSON list. Each item has:
- "task": what to do
- "context": constraints or references

Example:
[{"task": "Add GET /api/items route", "context": "Use src/db.py"}, {"task": "Add Pydantic validation", "context": "Validate name and price"}]"""


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

    llm = get_llm()
    try:
        response = llm.invoke(messages)
    except ResponseError as e:
        return {
            "todo": [],
            "context": [],
            "errors": [f"Ollama model not found: {e}. Pull it with: ollama pull {get_llm().model}"],
        }
    except Exception as e:
        return {
            "todo": [],
            "context": [],
            "errors": [f"LLM error in planner: {e}"],
        }

    try:
        todo_list = json.loads(response.content)
        if isinstance(todo_list, dict):
            for key in ("tasks", "todo", "subtasks"):
                if key in todo_list:
                    todo_list = todo_list[key]
                    break
    except (json.JSONDecodeError, TypeError):
        todo_list = [{"task": state["prompt"], "context": ""}]

    if not isinstance(todo_list, list):
        todo_list = [{"task": str(todo_list), "context": ""}]

    context = [f"File: {path}\n{content[:2000]}" for path, content in file_contents.items()]

    return {
        "todo": todo_list,
        "context": context,
        "errors": [],
        "status": "planning",
    }
