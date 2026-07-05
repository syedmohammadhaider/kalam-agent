from typing import TypedDict


class CoderTask(TypedDict):
    task: str
    context: str
    files: list[str]


class CoderState(TypedDict):
    todo: list[CoderTask]
    prompt: str
    context: list[str]
    files: list[str]
    injected_context: str
    diffs: list[str]
    generated_files: dict[str, str]
    errors: list[str]
