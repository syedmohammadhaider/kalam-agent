import json
import os
import re

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from ollama._types import ResponseError

DEFAULT_MODEL = os.environ.get("KALAM_LLM_MODEL", "qwen2.5-coder:7b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Per-node model overrides.  Populated by the UI (ModelConfigPanel).
# Keys: planner, designer, decomposer, context_retriever, brain.
MODEL_CONFIG: dict[str, str] = {}


def get_llm(model: str | None = None, temperature: float = 0.1, node: str | None = None) -> ChatOllama:
    if model is None and node is not None:
        model = MODEL_CONFIG.get(node)
    return ChatOllama(model=model or DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=temperature)


def read_files(file_paths: list[str]) -> dict[str, str]:
    contents: dict[str, str] = {}
    for path in file_paths:
        try:
            with open(path) as f:
                contents[path] = f.read()
        except Exception as e:
            contents[path] = ""
    return contents


def _extract_json(text: str) -> str:
    stripped = text.strip()
    m = re.search(r"```(?:json)?\s*\n(.+?)\n```", stripped, re.DOTALL)
    if m:
        stripped = m.group(1).strip()
    start = stripped.find("{")
    if start < 0:
        start = stripped.find("[")
    if start > 0:
        stripped = stripped[start:]
    return stripped


def llm_call_with_retry(llm, messages, max_retries: int = 3, parse_json: bool = False):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = llm.invoke(messages)
        except ResponseError as e:
            last_error = f"Ollama error: {e}"
            continue
        except Exception as e:
            last_error = f"LLM error: {e}"
            continue

        if not parse_json:
            return response.content

        try:
            candidate = _extract_json(response.content)
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError) as e:
            last_error = f"Invalid JSON: {e}"
            messages.append(HumanMessage(
                content=(
                    f"ERROR: Your previous response was not valid JSON.\n"
                    f"---\n{response.content[:2000]}\n---\n\n"
                    f"Parse error: {e}\n\n"
                    f"Respond with valid JSON only, no markdown."
                )
            ))

    raise RuntimeError(
        f"LLM call failed after {max_retries} attempts. Last error: {last_error}"
    )
