from langchain_core.messages import HumanMessage, SystemMessage
from ollama._types import ResponseError
from kalam.agents.utils import get_llm, read_files
from kalam.agents.coder.schema.state import CoderState


CODE_GENERATOR_SYSTEM_PROMPT = """You are a code generator. Given a specific coding subtask and project context, generate a unified diff (git diff format) that implements the required change.

Rules:
- Output ONLY the diff, no explanation
- Use standard unified diff format with proper file headers
- Each hunk must reference line numbers correctly
- For new files, the diff header is: --- /dev/null\n+++ b/path/to/file
- Respect existing code style and conventions

Example:
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
 def hello():
-    print("Hello")
+    name = "World"
+    print(f"Hello, {name}!")
"""


def code_generator_node(state: CoderState) -> dict:
    llm = get_llm()
    diffs: list[str] = list(state.get("diffs", []))
    errors: list[str] = list(state.get("errors", []))

    for task_idx, task in enumerate(state.get("todo", [])):
        file_contents = read_files(state.get("files", []))

        files_section = "\n\n---\n".join(
            f"### {path}\n```\n{content}\n```"
            for path, content in file_contents.items()
        )

        messages = [
            SystemMessage(content=CODE_GENERATOR_SYSTEM_PROMPT),
            HumanMessage(content=f"## Subtask\n{task['task']}\n\n## Context\n{task.get('context', '')}\n\n## Current Files\n{files_section}"),
        ]

        try:
            response = llm.invoke(messages)
            diff = response.content
            diffs.append(diff)
        except ResponseError as e:
            errors.append(f"Ollama error in code_generator (subtask {task_idx}): {e}")
        except Exception as e:
            errors.append(f"LLM error in code_generator (subtask {task_idx}): {e}")

    return {"diffs": diffs, "errors": errors}
