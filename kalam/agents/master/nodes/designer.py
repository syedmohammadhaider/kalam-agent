import json

from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError

from kalam.agents.utils import get_llm
from kalam.agents.master.schema.state import MasterState


DESIGNER_SYSTEM_PROMPT = """Check if the project needs a UI. If yes, give short design notes. If no, say false.

Return JSON:
{"needs_design": false}
or
{"needs_design": true, "guidelines": "color: ..., layout: ..."}"""


def designer_node(state: MasterState) -> dict:
    messages = [
        SystemMessage(content=DESIGNER_SYSTEM_PROMPT),
        HumanMessage(content=f"## User Request\n{state['prompt']}\n\n## Project Context\n{' '.join(state['context'][:5])}"),
    ]

    llm = get_llm()
    try:
        response = llm.invoke(messages)
    except ResponseError as e:
        return {"design_guidelines": "", "errors": [f"Ollama error in designer: {e}"]}
    except Exception as e:
        return {"design_guidelines": "", "errors": [f"LLM error in designer: {e}"]}

    try:
        result = json.loads(response.content)
        if result.get("needs_design"):
            return {"design_guidelines": result.get("guidelines", response.content), "errors": [], "status": "designing"}
    except (json.JSONDecodeError, TypeError):
        pass

    return {"design_guidelines": response.content, "errors": [], "status": "designing"}


def needs_design(state: MasterState) -> bool:
    keywords = ["frontend", "ui", "react", "vue", "angular", "html", "css", "dashboard", "web", "interface"]
    return any(kw in state["prompt"].lower() for kw in keywords)
