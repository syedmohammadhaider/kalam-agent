import os

from langchain_ollama import ChatOllama

DEFAULT_MODEL = os.environ.get("KALAM_LLM_MODEL", "qwen2.5-coder:7b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def get_llm(model: str | None = None, temperature: float = 0.1) -> ChatOllama:
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
