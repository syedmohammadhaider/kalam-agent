from typing import TypedDict


class MasterTask(TypedDict):
    task: str
    context: str


class ChatEntry(TypedDict):
    role: str
    content: str


class ShellOutput(TypedDict):
    command: str
    returncode: int
    stdout: str
    stderr: str


class MasterState(TypedDict):
    files: list[str]
    prompt: str
    todo: list[MasterTask]
    context: list[str]
    design_guidelines: str
    generated_files: dict[str, str]
    errors: list[str]
    history: list[ChatEntry]
    status: str
    commands: list[str]
    shell_output: list[ShellOutput]
