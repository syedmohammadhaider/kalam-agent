import os

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from kalam.agents.tools import code_writer, view_file, run_shell, approve_shell
from kalam.agents.utils import get_llm, read_files
from kalam.agents.coder.schema.state import CoderState


BRAIN_SYSTEM_PROMPT = """You are a coding agent. For each subtask, use the available tools to make the change.

Available tools:
- view_file(path) — read a file to inspect existing code
- code_writer(path, content) — create or overwrite a file with complete code
- run_shell(command) — run shell commands (testing, linting, installs)

Rules:
1. First view relevant files to understand existing code before writing
2. Write complete, working code — not partial diffs
3. After writing, use run_shell to verify (e.g., syntax check, test)
4. One file change per code_writer call
5. Keep changes minimal and focused on the subtask"""


def _resolve(path: str, project_path: str) -> str:
    return os.path.join(project_path, path) if not os.path.isabs(path) else path


def _read_tool_result(tool_name: str, args: dict, project_path: str) -> str:
    if tool_name == "view_file":
        return view_file.invoke({"path": _resolve(args["path"], project_path)})
    if tool_name == "code_writer":
        return code_writer.invoke({
            "path": _resolve(args["path"], project_path),
            "content": args["content"],
        })
    if tool_name == "run_shell":
        return run_shell.invoke({"command": args["command"]})
    return f"Unknown tool: {tool_name}"


def brain_node(state: CoderState) -> dict:
    project_path = state.get("project_path", os.getcwd())
    subtasks = list(state.get("todo", []))
    subtask_idx = state.get("brain_subtask_idx", 0)
    messages = list(state.get("brain_messages", []))
    generated_files = dict(state.get("generated_files", {}))
    errors = list(state.get("errors", []))
    chat_messages = list(state.get("chat_messages", []))
    pending_shell = state.get("pending_shell", "")

    # --- Handle shell approval from previous invocation ---
    if pending_shell and state.get("shell_approved"):
        approve_shell(pending_shell)
        result = _read_tool_result("run_shell", {"command": pending_shell}, project_path)
        messages.append(ToolMessage(content=result[:2000], tool_call_id=f"shell_{subtask_idx}"))
        chat_messages.append({
            "role": "assistant",
            "content": f"\u26a1 Ran: {pending_shell[:80]}",
        })
        pending_shell = ""
        state = {**state, "pending_shell": "", "shell_approved": False}

    llm = get_llm(node="brain").bind_tools([view_file, code_writer, run_shell])

    file_contents = read_files(state.get("files", []))
    files_section = "\n\n---\n".join(
        f"### {path}\n```\n{content[:3000]}\n```"
        for path, content in file_contents.items()
    )

    while subtask_idx < len(subtasks):
        task = subtasks[subtask_idx]
        task_label = task.get("task", "")[:80]

        if not messages:
            sys_msg = SystemMessage(content=BRAIN_SYSTEM_PROMPT)
            context_str = state.get("injected_context", "") or "\n".join(state.get("context", []))
            user_msg = HumanMessage(
                content=f"## Subtask\n{task['task']}\n\n## Context\n{context_str}\n\n## Current Files\n{files_section}"
            )
            messages = [sys_msg, user_msg]

        response = llm.invoke(messages)
        messages.append(response)

        if response.content and response.content.strip():
            chat_messages.append({
                "role": "assistant",
                "content": f"\U0001f9e0 {task_label}: {response.content.strip()[:120]}",
            })

        # Process tool calls
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", f"{tool_name}_{subtask_idx}")

                if tool_name == "run_shell":
                    cmd = args.get("command", "")
                    if cmd not in _get_approved():
                        return {
                            "pending_shell": cmd,
                            "shell_approved": False,
                            "brain_subtask_idx": subtask_idx,
                            "brain_messages": messages,
                            "generated_files": generated_files,
                            "errors": errors,
                            "chat_messages": chat_messages,
                            "diffs": [],
                        }

                result = _read_tool_result(tool_name, args, project_path)
                messages.append(ToolMessage(content=result[:2000], tool_call_id=tc_id))

                if tool_name == "code_writer":
                    path = args.get("path", "")
                    abs_path = _resolve(path, project_path)
                    if result.startswith("Successfully"):
                        chat_messages.append({
                            "role": "assistant",
                            "content": f"\u270f\ufe0f Wrote {path}",
                        })
                        try:
                            with open(abs_path) as f:
                                generated_files[path] = f.read()
                        except Exception:
                            pass
                    else:
                        chat_messages.append({
                            "role": "assistant",
                            "content": f"\u274c Error writing {path}: {result}",
                        })
                        errors.append(f"code_writer failed for {path}: {result}")
                elif tool_name == "view_file":
                    chat_messages.append({
                        "role": "assistant",
                        "content": f"\ud83d\udd0d Viewed {args.get('path', '')}",
                    })
                elif tool_name == "run_shell":
                    chat_messages.append({
                        "role": "assistant",
                        "content": f"\u26a1 Ran: {args.get('command', '')[:80]}",
                    })
        else:
            subtask_idx += 1
            messages = []

    return {
        "generated_files": generated_files,
        "errors": errors,
        "diffs": [],
        "pending_shell": "",
        "brain_subtask_idx": subtask_idx,
        "brain_messages": [],
        "chat_messages": chat_messages,
    }


def _get_approved():
    from kalam.agents.tools.shell_tool import _approved_commands
    return _approved_commands
