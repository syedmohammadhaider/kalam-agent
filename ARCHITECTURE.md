# Kalam Architecture

Kalam is a two-agent coding system — a **Master agent** that plans and delegates, and a **Coder agent** that implements. A Textual TUI drives LangGraph state machines directly in a single process, with Ollama providing the local LLM inference.

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
    ├── app.py                   # KalamApp TUI (Textual), FileSelector, file discovery
    ├── kalam.tcss               # TUI stylesheet (dark GitHub-inspired theme)
    ├── agents/
    │   ├── utils.py             # LLM factory (ChatOllama), file reader
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   └── shell_tool.py    # run_shell LangChain @tool
    │   ├── master/
    │   │   ├── graph.py         # Master StateGraph compilation
    │   │   ├── schema/state.py  # MasterState, MasterTask TypedDicts
    │   │   └── nodes/
    │   │       ├── planner.py           # planner_node — LLM prompt → tasks
    │   │       ├── designer.py          # designer_node + needs_design() router
    │   │       ├── executor.py          # executor_node — invokes Coder per task
    │   │       └── ...
    │   └── coder/
    │       ├── graph.py         # Coder StateGraph compilation
    │       ├── schema/state.py  # CoderState, CoderTask TypedDicts
    │       └── nodes/
    │           ├── decomposer.py         # LLM task → subtasks
    │           ├── context_retriever.py  # LLM extracts relevant context
    │           ├── code_generator.py     # LLM produces unified diffs
    │           ├── file_writer.py        # Applies diffs to filesystem
    │           ├── verifier.py           # Syntax + existence checks
    │           └── checkpoint.py         # On-disk file verification
    └── widgets/
        ├── __init__.py
        └── model_list.py       # Ollama model list widget
```

---

## Agent Graphs

### Master Graph

```
START ──► planner ──► [needs_design?] ──► designer ──► executor ──► END
                   │                                  ▲
                   └── (False) ───────────────────────┘
```

- **planner**: Reads project files from `state["files"]` (discovered by the TUI), includes chat history from `state["history"]`, sends prompt + file contents + history to LLM, which returns a JSON list of `{task, context}`. Stores in `state["todo"]`.
- **designer** (conditional): If prompt contains frontend keywords (`react`, `html`, `ui`, `css`, `dashboard`, etc.), the LLM produces design guidelines. Otherwise skipped.
- **executor**: Iterates over each task from the plan. For each task, constructs a `CoderState` and invokes the **Coder graph**. Accumulates `generated_files` and `errors`.

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

**State schemas** use `TypedDict`. Errors are accumulated in `state["errors"]` — every LLM call wraps `ResponseError` and `Exception`, so no node crash halts the graph. Each node sets `state["status"]` to describe its current phase (`planning`, `designing`, `generating`).

---

## Frontend (TUI)

Textual `App` laid out as:

- **Left column (2fr)**: Chat messages (`RichLog` with markup), text prompt input, welcome ASCII art.
- **Right column (1fr)**: Process tabs (`TabbedContent` with Files, Plan, Design, Errors tabs), model list. Debug tab when `--debug` is passed.

The TUI calls `master_graph.astream(state)` directly — no HTTP layer. It processes LangGraph events per-node, updating the status bar and sidebar tabs in real time.

**Key bindings**: `Ctrl+R` run, `Ctrl+L` clear, `Ctrl+Q` quit.

---

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `KALAM_LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model for all LLM calls |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

All nodes call `get_llm()` (from `utils.py`) with no arguments, defaulting to the model above at temperature 0.1.

---

## Data Flow (End-to-End)

1. User enters a prompt and selects files in the TUI, then presses `Ctrl+R`.
2. TUI discovers source files in the project directory (up to 200, skipping ignored dirs), merges with manual selections.
3. TUI calls `master_graph.astream(state)` directly — no HTTP layer.
4. LangGraph runs the Master graph, which:
   - Plans tasks from the prompt + file context.
   - Optionally generates design guidelines.
   - Invokes the Coder graph per task to implement code.
5. The Coder graph decomposes, retrieves context, generates diffs (applied to filesystem via `patch`), and verifies results.
6. The checkpoint node confirms every generated file exists on disk.
7. Results stream to the TUI in real time — status bar updates per node, sidebar tabs populate with plan/design/errors as they arrive.
8. A `run_shell` tool (`@tool` decorated) is available for the LLM to run shell commands when needed.

---

## Key Design Decisions

- **Single process** — The agent graphs and TUI run in one Python process. No HTTP server, no SSE, no subprocess management.
- **Two-level graph** — Master plans and orchestrates; Coder implements. The executor invokes the coder graph as a sub-graph for each task.
- **Keyword-based routing** — `needs_design()` uses keyword matching (not an LLM call) for the fast path.
- **Direct Ollama access** — The model list widget queries Ollama independently with httpx.
- **Error resilience** — Every node catches LLM/parse errors into `state["errors"]`; no single failure aborts the graph.
- **Defence in depth** — Two layers verify generated files: `verifier` (syntax) and `checkpoint` (on-disk existence + content match).
- **Shell tool** — A `run_shell` LangChain `@tool` is available for the LLM to run arbitrary shell commands, including file verification.
