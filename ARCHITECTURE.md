# Kalam Architecture

Kalam is a two-agent coding system — a **Master agent** that plans and delegates, and a **Coder agent** that implements. A Textual TUI frontend talks to a FastAPI/LangGraph backend over HTTP, with Ollama providing the local LLM inference.

---

## Project Structure

```
kalam/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── agents/
│   │   ├── utils.py               # LLM factory (ChatOllama), file reader
│   │   ├── master/
│   │   │   ├── graph.py           # Master StateGraph compilation
│   │   │   ├── schema/state.py    # MasterState, MasterTask TypedDicts
│   │   │   └── nodes/
│   │   │       ├── filesystem_explorer.py  # Discovers source files, skips ignored dirs
│   │   │       ├── planner.py              # planner_node — LLM breaks prompt into tasks
│   │   │       ├── designer.py             # designer_node + needs_design() router
│   │   │       └── executor.py             # executor_node — invokes Coder per task
│   │   └── coder/
│   │       ├── graph.py           # Coder StateGraph compilation
│   │       ├── schema/state.py    # CoderState, CoderTask TypedDicts
│   │       └── nodes/
│   │           ├── decomposer.py        # LLM breaks task into subtasks
│   │           ├── context_retriever.py # LLM extracts relevant context
│   │           ├── code_generator.py    # LLM produces diffs → stored in state
│   │           ├── file_writer.py      # Applies diffs from state to filesystem
│   │           └── verifier.py          # Syntax + existence checks
│   └── api/
│       └── routes.py             # POST /run, POST /run/stream (SSE), GET /health
└── frontend/
    └── tui/
        ├── main.py               # TUI entry point
        ├── app.py                # KalamApp (Textual), FileSelector
        ├── kalam.tcss            # Stylesheet (dark GitHub-inspired theme)
        └── widgets/
            ├── model_list.py     # ModelList — fetches Ollama models
            └── __init__.py
```

---

## Agent Graphs

### Master Graph

```
START ──► planner ──► [needs_design?] ──► designer ──► executor ──► shell_executor ──► END
                   │                                  ▲
                   └── (False) ───────────────────────┘
```

- **planner**: Reads project files from `state["files"]` (discovered by the TUI and sent as `POST` body), includes chat history from `state["history"]`, sends prompt + file contents + history to LLM, which returns a JSON list of `{task, context}`. Stores in `state["todo"]`.
- **designer** (conditional): If prompt contains frontend keywords (`react`, `html`, `ui`, `css`, `dashboard`, etc.), the LLM produces design guidelines. Otherwise skipped.
- **executor**: Iterates over each task from the plan. For each task, constructs a `CoderState` and invokes the **Coder graph**. Accumulates `generated_files` and `errors`.
- **shell_executor**: Runs shell commands to verify generated files. If `state["commands"]` is non-empty, runs those; otherwise auto-generates checkpoint commands — `test -f <path>` for each generated file and `python -c "compile(...)"` for `.py` files. Stores results in `state["shell_output"]` and reports any failures in `state["errors"]`.

### Coder Graph

```
START ──► decomposer ──► context_retriever ──► code_generator ──► file_writer ──► verifier ──► checkpoint ──► END
```

- **decomposer**: Breaks a single coding task into finer subtasks via LLM.
- **context_retriever**: Reads project files, asks LLM to extract only the context relevant to the current task. Overwrites `state["injected_context"]`.
- **code_generator**: Per-subtask: LLM produces a unified diff and stores it in `state["diffs"]`. No filesystem mutations.
- **file_writer**: Iterates over `state["diffs"]`, applies each via `patch -p1` (existing files) or parses new files from `+++ b/...` lines and writes them directly. Populates `state["generated_files"]`.
- **verifier**: Checks generated files exist on disk; for `.py` files, runs `ast.parse()` and `py_compile.compile()`.
- **checkpoint**: Last line of defence before the coder graph returns. Checks every file in `state["generated_files"]` actually exists on disk via `os.path.exists()`. For `.py` files, also verifies the on-disk content matches what was stored in state. Reports missing/mismatched files as errors with debug info (parent directory listing).

**State schemas** use `TypedDict`. Errors are accumulated in `state["errors"]` — every LLM call wraps `ResponseError` and `Exception`, so no node crash halts the graph. Each node sets `state["status"]` to describe its current phase (`exploring`, `planning`, `designing`, `generating`), which is streamed to the TUI via SSE and displayed in the status bar.

---

## API

| Method | Path | Input | Output |
|---|---|---|---|---|
| `POST` | `/run` | `{prompt: str, files: list[str]}` | `{todo, design_guidelines, generated_files, errors, status}` |
| `POST` | `/run/stream` | `{prompt: str, files: list[str]}` | SSE stream of status events, final `complete` event |
| `GET` | `/health` | — | `{status: "ok"}` |

The `/run` handler builds a `MasterState` with the request body, calls `master_graph.invoke(state)`, and returns the result. The `/run/stream` handler uses SSE (Server-Sent Events) to stream per-node status updates in real time — each event includes the current phase (`exploring`, `planning`, `designing`, `generating`) and intermediate data (todo, errors, etc.).

---

## Frontend (TUI)

Textual `App` laid out as:

- **Left column (2fr)**: Chat messages (`RichLog` with markup), text prompt input.
- **Right column (1fr)**: Process tabs (`TabbedContent` with Files, Plan, Design, Errors tabs), model list.

Communication with the backend uses SSE (Server-Sent Events) via `httpx.AsyncClient` streaming — the TUI opens a streaming `POST /run/stream` connection and processes per-node status events in real time. The TUI also queries Ollama directly for the model list.

**Key bindings**: `Ctrl+R` run, `Ctrl+L` clear, `Ctrl+Q` quit.

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `KALAM_LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model for all LLM calls |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `KALAM_BACKEND_URL` | `http://localhost:8000` | Backend URL (TUI → API) |

All nodes call `get_llm()` (from `utils.py`) with no arguments, defaulting to the model above at temperature 0.1.

---

## Data Flow (End-to-End)

1. User enters a prompt and selects files in the TUI, then clicks Run / `Ctrl+R`.
2. TUI sends `POST /run {prompt, files}` to the backend.
3. Backend invokes the Master graph, which:
   - Plans tasks from the prompt + file context.
   - Optionally generates design guidelines.
   - Invokes the Coder graph per task to implement code.
4. The Coder graph decomposes, retrieves context, generates diffs (applied to filesystem via `patch`), and verifies results.
5. The Master graph returns accumulated `generated_files`, `errors`, `todo`, and `design_guidelines`.
6. Backend serializes the response as JSON.
7. TUI displays the user message in the chat log, then streams status updates (exploring, planning, designing, generating) into the status bar and intermediate data into the sidebar tabs. On completion, an assistant response is appended to the chat and sidebar tabs are finalized.

---

## Key Design Decisions

- **Two-level graph** — Master plans and orchestrates; Coder implements. The executor invokes the coder graph as a sub-graph for each task.
- **Keyword-based routing** — `needs_design()` uses keyword matching (not an LLM call) for the fast path.
- **Filesystem mutations** — `code_generator` applies `patch -p1` directly to project files, bypassing a "preview-only" model.
- **SSE streaming** — The backend streams per-node status updates via `POST /run/stream` (SSE). The TUI displays real-time progress in the status bar and sidebar tabs.
- **Direct Ollama access** — The model list widget queries Ollama independently, not proxied through the backend.
- **Error resilience** — Every node catches LLM/parse errors into `state["errors"]`; no single failure aborts the graph.
