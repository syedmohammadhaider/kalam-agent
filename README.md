```
 █████   ████   █████████   █████         █████████   ██████   ██████
░░███   ███░   ███░░░░░███ ░░███         ███░░░░░███ ░░██████ ██████ 
 ░███  ███    ░███    ░███  ░███        ░███    ░███  ░███░█████░███ 
 ░███████     ░███████████  ░███        ░███████████  ░███░░███ ░███ 
 ░███░░███    ░███░░░░░███  ░███        ░███░░░░░███  ░███ ░░░  ░███ 
 ░███ ░░███   ░███    ░███  ░███      █ ░███    ░███  ░███      ░███ 
 █████ ░░████ █████   █████ ███████████ █████   █████ █████     █████
░░░░░   ░░░░ ░░░░░   ░░░░░ ░░░░░░░░░░░ ░░░░░   ░░░░░ ░░░░░     ░░░░░
```

**Kalām** (کلام) is a local AI coding agent that runs entirely on your machine. A Textual TUI drives LangGraph state machines directly — a **Master** agent plans and delegates, and a **Coder** agent implements via tool-calling, with Ollama providing local LLM inference.

## Installation

```bash
pip install git+https://github.com/syedmohammadhaider/kalam.git
```

Or from source:

```bash
git clone https://github.com/syedmohammadhaider/kalam.git
cd kalam
pip install -e .
```

### Dependencies

- Python >= 3.12
- [Ollama](https://ollama.ai) running locally (default: `http://localhost:11434`)
- A compatible model pulled, e.g. `ollama pull qwen2.5-coder:7b`

## Usage

```bash
# Open the TUI in the current directory
kalam

# Point to a specific project
kalam -p ~/projects/myapp
```

### Key Bindings

| Binding | Action |
|---|---|
| `Ctrl+R` | Run the agent with the current prompt |
| `Ctrl+L` | Clear chat history and output |
| `Ctrl+Q` | Quit |
| `Ctrl+Y` / `Ctrl+G` | Approve shell command execution |
| `Esc` | Close file autocomplete popup |

### Workflow

1. Type a prompt describing what you want to build
2. Type `@` to attach relevant project files (autocomplete popup appears)
3. Press `Ctrl+R` — Kalām plans tasks, generates code, writes files, and verifies them
4. All agent steps stream into the chat panel with timestamps: plan, design, subtasks, tool calls, verification
5. If a shell command is needed, the agent pauses — press `Ctrl+Y`/`Ctrl+G` or click the **Approve** button to allow it
6. Results are summarized in the chat; errors appear in the Errors sidebar tab

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KALAM_LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model for all LLM calls |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

Each node in the graph can use a different model via the model config panel in the sidebar.

## Architecture

Kalām runs as a single CLI process with two LangGraph state machines:

### Master Graph

```
START ──► planner ──► [needs_design?] ──► designer ──► (TUI loops per task)
                    │                                  ▲
                    └── (False) ───────────────────────┘
```

- **planner** — LLM reads project files + chat history, breaks the prompt into tasks
- **designer** — (conditional) generates UI design guidelines for frontend prompts
- The TUI itself loops over the planned tasks and runs each through the Coder graph

### Coder Graph

```
START ──► decomposer ──► context_retriever ──► brain ──► verifier ──► checkpoint ──► END
```

- **decomposer** — LLM splits a task into subtasks (prefers single subtask)
- **context_retriever** — LLM extracts relevant file context from the project
- **brain** — Tool-calling LLM node with `code_writer`, `view_file`, and `run_shell` tools. Invokes tools per subtask, supports shell approval HITL
- **verifier** — checks syntax (`ast.parse`, `py_compile`) and file existence
- **checkpoint** — confirms files exist on disk and content matches

### Frontend

A [Textual](https://textual.textualize.io) TUI with a chat-style interface (left column) and a process sidebar (right column: Errors, State tabs). File attachment via `@` mentions in the prompt. All agent steps stream into a single growing chat message with `[HH:MM:SS]` timestamps.

## Project Structure

```
kalam/
├── pyproject.toml              # Package metadata and CLI entry point
├── README.md
├── ARCHITECTURE.md
└── kalam/
    ├── __init__.py
    ├── __main__.py              # CLI entry point (argparse → KalamApp)
    ├── app.py                   # KalamApp TUI (Textual), @ file attachment
    ├── kalam.tcss               # TUI stylesheet (dark GitHub-inspired theme)
    ├── agents/
    │   ├── utils.py             # LLM factory (ChatOllama), file reader
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   └── shell_tool.py    # code_writer, view_file, run_shell LangChain tools
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
        ├── model_config.py  # Model configuration panel
        └── model_list.py    # Ollama model list widget
```

## License

MIT
