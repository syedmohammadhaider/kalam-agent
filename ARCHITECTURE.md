# Kalām Architecture

Kalām is a two-agent coding system — a **Master agent** that plans and delegates, and a **Coder agent** that implements via tool-calling. A Textual TUI drives LangGraph state machines directly in a single process, with Ollama providing local LLM inference.

---

## Project Structure

```
kalam/
├── pyproject.toml              # Package metadata, CLI entry point
├── README.md
├── ARCHITECTURE.md
└── kalam/
    ├── __init__.py
    ├── __main__.py              # CLI entry point (argparse → KalamApp)
    ├── app.py                   # KalamApp TUI — chat, @ file attachment, shell approval
    ├── kalam.tcss               # TUI stylesheet (dark GitHub-inspired theme)
    ├── agents/
    │   ├── utils.py             # LLM factory (ChatOllama), file reader, retry wrapper
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   └── shell_tool.py    # code_writer, view_file, run_shell LangChain @tools
    │   ├── master/
    │   │   ├── graph.py         # Master StateGraph compilation
    │   │   ├── schema/state.py  # MasterState, MasterTask TypedDicts
    │   │   └── nodes/
    │   │       ├── planner.py   # planner_node — LLM prompt → tasks
    │   │       └── designer.py  # designer_node + needs_design() router
    │   └── coder/
    │       ├── graph.py         # Coder StateGraph compilation
    │       ├── schema/state.py  # CoderState, CoderTask TypedDicts
    │       └── nodes/
    │           ├── decomposer.py         # LLM task → subtasks
    │           ├── context_retriever.py  # LLM extracts relevant context
    │           ├── brain.py              # Tool-calling LLM (code_writer/view_file/run_shell)
    │           ├── verifier.py           # Syntax + existence checks
    │           └── checkpoint.py         # On-disk file verification
    └── widgets/
        ├── __init__.py
        ├── model_config.py  # Per-node model selector panel
        └── model_list.py    # Ollama model list widget
```

---

## Agent Graphs

### Master Graph

```
START ──► planner ──► [needs_design?] ──► designer ──► (TUI loops per task)
                    │                                  ▲
                    └── (False) ───────────────────────┘
```

- **planner**: Reads project files from `state["files"]` (discovered by the TUI), includes chat history from `state["history"]`, sends prompt + file contents + history to LLM, which returns a JSON list of `{task, context}` tasks. Stores in `state["todo"]`. Prefers returning a single task — splits only when subtasks target unrelated files.
- **designer** (conditional): If prompt contains frontend keywords (`react`, `html`, `ui`, `css`, `dashboard`, etc.), the LLM produces design guidelines. Otherwise skipped.
- **TUI execution loop**: Instead of a traditional executor node, the TUI's `_run_agent` method iterates over `state["todo"]` directly. For each task it builds a `CoderState` and invokes the **Coder graph** via `astream`. Accumulates `generated_files` and `errors` back into the master state.

### Coder Graph

```
START ──► decomposer ──► context_retriever ──► brain ──► verifier ──► checkpoint ──► END
```

- **decomposer**: Breaks a single coding task into finer subtasks via LLM. Prefers no split (single subtask); only splits when subtasks touch different files and the prompt is complex enough. Output stored in `state["todo"]` as a list of `CoderTask` dicts.
- **context_retriever**: Reads project files, asks LLM to extract only the context relevant to the current subtask. Overwrites `state["injected_context"]`.
- **brain**: The core implementation node. Uses `bind_tools([view_file, code_writer, run_shell])` so the LLM decides which tool to call for each subtask. Loops over subtasks, calling the LLM repeatedly until all are complete. Supports shell approval HITL — when `run_shell` is invoked, the node returns early with `pending_shell` set, the TUI pauses for user approval, then re-invokes the node with `shell_approved=True`.
- **verifier**: Checks generated files exist on disk; for `.py` files, runs `ast.parse()` and `py_compile.compile()`.
- **checkpoint**: Last line of defence. Checks every file in `state["generated_files"]` actually exists on disk via `os.path.exists()`. For `.py` files, also verifies on-disk content matches what was stored in state. Reports missing/mismatched files as errors.

**State** uses `TypedDict`. Errors accumulate in `state["errors"]` — every LLM call wraps exceptions, so no node crash halts the graph. Per-node model selection is supported via `get_llm(node="node_name")`.

---

## Frontend (TUI)

Textual `App` laid out as:

- **Left column (2fr)**: Chat messages (`RichLog` with markup) — a single growing assistant message accumulates all agent steps with `[HH:MM:SS]` timestamps. Prompt input with `@` file attachment autocomplete.
- **Right column (1fr)**: Sidebar with Errors and State tabs, plus a per-node model configuration panel.

**Key bindings**: `Ctrl+R` run, `Ctrl+L` clear, `Ctrl+Q` quit, `Ctrl+Y`/`Ctrl+G` approve shell, `Esc` close autocomplete.

**Shell approval HITL**: When the brain node invokes `run_shell`, the coder graph pauses. The TUI shows an "Approve Shell" button below the prompt input and the status bar indicates approval is needed. The user can click the button or press `Ctrl+Y`/`Ctrl+G` (both `priority=True` to override widget-level bindings). Approved shell commands are tracked in a module-level `_approved_commands: set[str]` so they don't require re-approval within the same run.

**File attachment**: Typing `@` in the prompt opens a `ListView` popup of matching project files. Selecting one inserts the relative path. On submit, `@references` are resolved to absolute paths and included in `state["files"]`.

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `KALAM_LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model for all LLM calls |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

Each graph node can use a different model. The model config panel in the TUI sidebar exposes per-node model selection. The `get_llm()` function in `utils.py` defaults to `KALAM_LLM_MODEL` at temperature 0.1 unless overridden.

---

## Data Flow (End-to-End)

1. User enters a prompt (optionally attaching files with `@`) and presses `Ctrl+R`.
2. TUI discovers source files in the project directory (up to 200, skipping ignored dirs like `node_modules`, `.git`), merges with `@`-attached files.
3. TUI seeds `state["history"]` with recent messages from the current session for conversation continuity.
4. TUI calls `planner_node` in a thread — LLM returns a task list.
5. If `needs_design()` matches frontend keywords, `designer_node` runs in a thread.
6. TUI loops over each planned task, building a `CoderState` and running it through `coder_graph.astream()`.
7. The Coder graph decomposes the task (if needed), retrieves relevant context, then the brain node iterates subtasks calling tools:
   - `view_file` — reads existing files (no approval needed)
   - `code_writer` — writes/overwrites files (no approval needed)
   - `run_shell` — runs shell commands (requires user approval)
8. If `run_shell` is called, the brain returns early; the TUI shows the Approve button and waits; after approval the brain is re-invoked.
9. After all subtasks complete, the verifier and checkpoint nodes validate generated files.
10. Results stream to the TUI in real time — all step descriptions accumulate in the chat panel; errors appear in the Errors tab; generated files are summarized.

---

## Key Design Decisions

- **Single process** — The agent graphs and TUI run in one Python process. No HTTP server, no SSE, no subprocess management.
- **Two-level graph** — Master plans and orchestrates; Coder implements. The TUI itself acts as the executor, invoking the coder graph per task.
- **Tool-calling brain** — Instead of separate code_generator + file_writer nodes, a single brain node uses `bind_tools()` so the LLM decides which tool to call (view_file, code_writer, run_shell) per subtask.
- **Shell approval HITL** — `run_shell` tool uses an `asyncio.Event` for approval. The brain returns early when shell is needed; the TUI awaits the event; approval re-invokes the brain. Avoids complicating the graph with LangGraph interrupt mechanics.
- **Single growing chat message** — All agent step descriptions are appended to one assistant message with timestamps, keeping the chat panel clean rather than creating separate messages per action.
- **Keyword-based design routing** — `needs_design()` uses keyword matching (not an LLM call) for the fast path.
- **Direct Ollama access** — The model list widget queries Ollama independently with httpx.
- **Error resilience** — Every node catches LLM/parse errors into `state["errors"]`; no single failure aborts the graph.
- **Defence in depth** — Two layers verify generated files: `verifier` (syntax) and `checkpoint` (on-disk existence + content match).
- **File attachment via @** — Rather than a sidebar file tree, files are attached by typing `@` in the prompt, which triggers an autocomplete popup. This keeps the UI focused on the chat interaction.
- **Conversation history** — The planner receives recent messages from the current TUI session as context, enabling it to understand follow-up requests.
