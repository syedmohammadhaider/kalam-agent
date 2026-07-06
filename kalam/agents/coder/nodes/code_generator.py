from langchain_core.messages import HumanMessage, SystemMessage
from kalam.agents.utils import get_llm, llm_call_with_retry, read_files
from kalam.agents.coder.schema.state import CoderState


CODE_GENERATOR_SYSTEM_PROMPT = """Generate a unified diff (git format) for the required change. Output ONLY the diff.

For new files:
--- /dev/null
+++ b/path/to/file
@@ -0,0 +1,N @@
+line1
+line2

For existing files:
--- a/path/to/file
+++ b/path/to/file
@@ -start,count +start,count @@
 context
-removed
+added

One file per diff. Keep changes minimal."""


def code_generator_node(state: CoderState) -> dict:
    llm = get_llm(node="code_generator")
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
            diff = llm_call_with_retry(llm, messages)
            diffs.append(diff)
        except RuntimeError as e:
            errors.append(str(e))

    return {"diffs": diffs, "errors": errors}
