from langchain_core.messages import HumanMessage, SystemMessage

from kalam.agents.utils import get_llm, llm_call_with_retry
from kalam.agents.master.schema.state import MasterState


DESIGNER_SYSTEM_PROMPT = """Check if the project needs a UI.
First line: YES or NO.
If YES, add design notes below.

Examples:
NO

YES
Minimal dashboard layout, dark theme, sidebar navigation"""


def _parse_design(text: str) -> tuple[bool, str]:
    lines = text.strip().splitlines()
    first = lines[0].strip().upper() if lines else "NO"
    if first.startswith("YES"):
        guidelines = "\n".join(l for l in lines[1:] if l.strip())
        return True, guidelines
    return False, ""


def designer_node(state: MasterState) -> dict:
    messages = [
        SystemMessage(content=DESIGNER_SYSTEM_PROMPT),
        HumanMessage(content=f"## User Request\n{state['prompt']}\n\n## Project Context\n{' '.join(state['context'][:5])}"),
    ]

    llm = get_llm(node="designer")
    text = llm_call_with_retry(llm, messages)
    needs, guidelines = _parse_design(text)

    if needs:
        return {"design_guidelines": guidelines, "errors": [], "status": "designing"}
    return {"design_guidelines": "", "errors": [], "status": "designing"}


def needs_design(state: MasterState) -> bool:
    keywords = ["frontend", "ui", "react", "vue", "angular", "html", "css", "dashboard", "web", "interface"]
    return any(kw in state["prompt"].lower() for kw in keywords)
