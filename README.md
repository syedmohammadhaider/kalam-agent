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

**Kalam** is a local AI coding agent that runs entirely on your machine. It uses a two-agent LangGraph pipeline — a **Master** agent that plans and delegates, and a **Coder** agent that generates, writes, and verifies code — all driven by Ollama for local LLM inference.

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

### Workflow

1. Type a prompt describing what you want to build
2. Select relevant files in the file tree (right sidebar)
3. Press `Ctrl+R` — Kalam plans tasks, generates code, writes files, and verifies them
4. Progress streams in real time: status bar shows `planning tasks` → `generating code` → `verifying files`
5. Generated files appear in the chat response; errors show in the Errors tab

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `KALAM_LLM_MODEL` | `qwen2.5-coder:7b` | Ollama model for all LLM calls |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |

## Architecture

Kalam runs as a single CLI process with two LangGraph state machines:

### Master Graph

```
START ──► planner ──► [needs_design?] ──► designer ──► executor ──► END
                   │                                  ▲
                   └── (False) ───────────────────────┘
```

- **planner** — LLM reads project files + chat history, breaks the prompt into tasks
- **designer** — (conditional) generates UI design guidelines for frontend prompts
- **executor** — runs each task through the Coder graph

### Coder Graph

```
START ──► decomposer ──► context_retriever ──► code_generator ──► file_writer ──► verifier ──► checkpoint ──► END
```

- **decomposer** — LLM splits a task into subtasks
- **context_retriever** — LLM extracts relevant file context
- **code_generator** — LLM produces unified diffs
- **file_writer** — applies diffs to the filesystem via `patch -p1`
- **verifier** — checks syntax (`ast.parse`, `py_compile`)
- **checkpoint** — confirms files exist on disk and content matches

### Frontend

A [Textual](https://textual.textualize.io) TUI with a chat-style interface (left column) and process sidebar (right column: Files, Plan, Design, Errors tabs). The status bar shows the current phase and results.

## How It Works

1. Kalam discovers source files in your project directory (up to 200, skipping `node_modules`, `.git`, `.venv`, etc.)
2. The planner LLM reads your prompt, the project files, and conversation history to produce a task list
3. Each task is executed by the Coder graph: decompose, gather context, generate diffs, write files, verify, checkpoint
4. The checkpoint node in the Coder graph confirms every file exists on disk and content matches
5. Results stream to the TUI in real time with status updates and output in the sidebar tabs

## Project Structure

```
kalam/
├── pyproject.toml           # Package metadata and CLI entry point
├── ARCHITECTURE.md          # Detailed architecture documentation
└── kalam/
    ├── __init__.py
    ├── __main__.py           # CLI entry point (argparse → KalamApp)
    ├── app.py                # KalamApp TUI (Textual), FileSelector, file discovery
    ├── kalam.tcss            # TUI stylesheet (dark GitHub-inspired theme)
    ├── agents/
    │   ├── utils.py          # LLM factory (ChatOllama), file reader
    │   ├── tools/
    │   │   ├── __init__.py
    │   │   └── shell_tool.py # run_shell LangChain @tool
    │   ├── master/
    │   │   ├── graph.py      # Master StateGraph compilation
    │   │   ├── schema/state.py  # MasterState, MasterTask, ShellOutput TypedDicts
    │   │   └── nodes/
    │   │       ├── planner.py          # planner_node — LLM prompt → tasks
    │   │       ├── designer.py         # designer_node + needs_design() router
    │   │       ├── executor.py          # executor_node — invokes Coder per task
    │   │       └── ...
    │   └── coder/
    │       ├── graph.py      # Coder StateGraph compilation
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
        └── model_list.py    # Ollama model list widget
```

## License

MIT
