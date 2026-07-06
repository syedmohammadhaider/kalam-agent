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
    skip_decompose: bool
    project_path: str
    # brain node state
    brain_subtask_idx: int
    brain_messages: list
    pending_shell: str
    shell_approved: bool
    chat_messages: list[dict]
