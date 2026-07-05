import json

from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError

from kalam.agents.utils import get_llm, read_files
from kalam.agents.master.schema.state import MasterState


PLANNER_SYSTEM_PROMPT = """You are a software engineering planner. Given a user request, a set of project files, and prior conversation history, break down the work into a sequence of specific, actionable tasks.

Each task must be:
- Self-contained and focused on one concern
- Ordered logically (dependencies first)
- Described with enough context for execution

Return your response as a JSON list of objects, each with:
- "task": a clear description of what to do
- "context": any additional context or constraints for this task

Example:
[
  {"task": "Create a FastAPI route GET /api/items", "context": "Use the existing database module from src/db.py"},
  {"task": "Add input validation using Pydantic", "context": "Validate name and price fields"}
]
"""


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
