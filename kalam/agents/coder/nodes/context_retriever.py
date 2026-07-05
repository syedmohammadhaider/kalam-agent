from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError

from kalam.agents.utils import get_llm, read_files
from kalam.agents.coder.schema.state import CoderState


CONTEXT_RETRIEVAL_SYSTEM_PROMPT = """Extract only the parts of the project context that are needed for the task. Skip anything unrelated.

Focus on: relevant classes, functions, imports, patterns, config.
Return a brief paragraph."""


def context_retriever_node(state: CoderState) -> dict:
    file_contents = read_files(state.get("files", []))

    files_section = "\n\n---\n".join(
        f"### {path}\n```\n{content[:3000]}\n```"
        for path, content in file_contents.items()
    )

    context_list = "\n".join(state.get("context", []))

    messages = [
        SystemMessage(content=CONTEXT_RETRIEVAL_SYSTEM_PROMPT),
        HumanMessage(content=f"## Task\n{state['prompt']}\n\n## Injected Context\n{state.get('injected_context', '')}\n\n## Available Context\n{context_list[:3000]}\n\n## Files\n{files_section}"),
    ]

    llm = get_llm()
    try:
        response = llm.invoke(messages)
    except ResponseError as e:
        return {"injected_context": "", "errors": [f"Ollama error in context_retriever: {e}"]}
    except Exception as e:
        return {"injected_context": "", "errors": [f"LLM error in context_retriever: {e}"]}

    return {"injected_context": response.content}
