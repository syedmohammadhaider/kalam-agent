import json

from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError

from kalam.agents.utils import get_llm
from kalam.agents.coder.schema.state import CoderState


DECOMPOSER_SYSTEM_PROMPT = """Split a coding task into smaller subtasks. One file per subtask. Order by dependency.

Return JSON list. Each item:
- "task": what to implement
- "context": constraints
- "files": list of file paths

Example:
[{"task": "Add Item model", "context": "fields: name, description", "files": ["src/models.py"]}]"""


def decomposer_node(state: CoderState) -> dict:
    messages = [
        SystemMessage(content=DECOMPOSER_SYSTEM_PROMPT),
        HumanMessage(content=f"## Task\n{state['prompt']}\n\n## Context\n{state['injected_context']}\n\n## Files\n{', '.join(state['files'])}"),
    ]

    llm = get_llm()
    try:
        response = llm.invoke(messages)
    except ResponseError as e:
        return {"todo": [{"task": state["prompt"], "context": state.get("injected_context", ""), "files": state.get("files", [])}], "errors": [f"Ollama error in decomposer: {e}"]}
    except Exception as e:
        return {"todo": [{"task": state["prompt"], "context": state.get("injected_context", ""), "files": state.get("files", [])}], "errors": [f"LLM error in decomposer: {e}"]}

    try:
        subtasks = json.loads(response.content)
        if isinstance(subtasks, dict):
            for key in ("subtasks", "tasks", "todo"):
                if key in subtasks:
                    subtasks = subtasks[key]
                    break
        if not isinstance(subtasks, list):
            subtasks = [{"task": state["prompt"], "context": state.get("injected_context", ""), "files": state.get("files", [])}]
    except (json.JSONDecodeError, TypeError):
        subtasks = [{"task": state["prompt"], "context": state.get("injected_context", ""), "files": state.get("files", [])}]

    for st in subtasks:
        st.setdefault("files", state.get("files", []))
        st.setdefault("context", state.get("injected_context", ""))

    return {"todo": subtasks}
