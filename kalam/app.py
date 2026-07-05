from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    DirectoryTree,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from kalam.agents.master.graph import master_graph
from kalam.agents.master.schema.state import MasterState
from kalam.widgets import ModelList

STATUS_LABELS = {
    "planner": "planning tasks",
    "designer": "designing UI",
    "executor": "generating code",
}

IGNORED_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".next", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".tox", ".vscode", ".idea", ".egg-info", "target",
    ".ruff_cache", ".gitlab", ".svn", "coverage",
})

SOURCE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    ".scala", ".vue", ".svelte", ".css", ".scss", ".less",
    ".html", ".md", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".conf", ".txt", ".env", ".sh", ".bash", ".zsh",
    ".sql", ".graphql", ".proto", ".xml", ".svg",
})

MAX_FILES = 200


def discover_source_files(root: Path) -> list[str]:
    discovered: list[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if d not in IGNORED_DIRS and not (d.startswith(".") and d not in (".env", ".gitignore"))]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in SOURCE_EXTENSIONS:
                    discovered.append(os.path.join(dirpath, filename))
                    if len(discovered) >= MAX_FILES:
                        return discovered
    except (PermissionError, OSError):
        pass
    return discovered


KALAM_ASCII = """\
\u2580\u2592\u2584\u2593\u2580 \u2580\u2588\u2584\u2593\u2580   \u2584\u2593\u2588\u2593\u2592\u2591\u2584   \u2591\u2584\u2592        \u2584\u2593\u2588\u2593\u2592\u2591\u2584   \u2580\u2592\u2584\u2593\u2580\u2588\u2584\u2584\u2588\u2580\u2588\u2584\u2593\u2580
 \u2591\u2588\u2593   \u2591\u2588\u2593   \u2550\u2588\u2593\u255e \u2550\u2591\u2588\u255e  \u2592\u2588\u2592       \u2550\u2588\u2593\u255e \u2550\u2591\u2588\u255e   \u2591\u2588\u2593 \u2550\u2593\u2593\u255e \u2591\u2588\u2593
 \u2592\u2593\u2592  \u2584\u2591\u2593\u2580   \u2592\u2593\u2592   \u2591\u2593\u2591  \u2592\u2588\u2593       \u2592\u2593\u2592   \u2591\u2593\u2591   \u2592\u2593\u2592  \u2592\u2592  \u2591\u2593\u2591
 \u2592\u2588\u2592\u2584\u2592\u25a0\u2588\u2584    \u2592\u2588\u2592\u2591\u2588\u25a0\u2588\u2593\u2592  \u2591\u2593\u2593       \u2592\u2588\u2592\u2591\u2588\u25a0\u2588\u2593\u2592   \u2592\u2588\u2592  \u2591\u2591  \u2588\u2593\u2592
 \u2591\u2593\u2592\u2593\u2580 \u2591\u2593\u2593   \u2591\u2593\u2592   \u2591\u2593\u2593  \u2591\u2593\u2591       \u2591\u2593\u2592   \u2591\u2593\u2593   \u2591\u2593\u2592  \u2588\u2588  \u2591\u2593\u2593
 \u2591\u2593\u2592   \u2591\u2593\u2591   \u2591\u2593\u2592   \u2591\u2593\u2591  \u2591\u2592\u2591       \u2591\u2593\u2592   \u2591\u2593\u2591   \u2591\u2593\u2592      \u2591\u2593\u2591
 \u2591\u2593\u2593   \u2591\u2593\u2592   \u2591\u2593\u2593   \u2591\u2593\u2592  \u2591\u2591\u2592       \u2591\u2593\u2593   \u2591\u2593\u2592   \u2591\u2593\u2593      \u2591\u2593\u2592
 \u2592 \u2593   \u2591 \u2593   \u2592 \u2593   \u2591 \u2593  \u2591\u2591\u2592       \u2592 \u2593   \u2591 \u2593   \u2592 \u2593      \u2591 \u2593
 \u2591 \u2593   \u2591\u2591\u2593   \u2591 \u2593   \u2591\u2591\u2593  \u2591\u2591\u2593  \u2584\u2591\u2592  \u2591 \u2593   \u2591\u2591\u2593   \u2591 \u2593      \u2591\u2591\u2593
  \u2591\u2588\u255e \u2550 \u2591\u2588    \u2591\u2588\u255e \u2550 \u2591\u2588   \u2591\u2588  \u2591\u2593\u2591   \u2591\u2588\u255e \u2550 \u2591\u2588    \u2591\u2588\u255e    \u2550 \u2591\u2588
 \u2591\u2592\u2588\u2588  \u2591\u2592\u2593\u2588  \u2591\u2592\u2588\u2588  \u2591\u2592\u2593\u2588 \u2591\u2592\u2593\u2584\u2584\u2588\u2588\u2588  \u2591\u2592\u2588\u2588  \u2591\u2592\u2593\u2588  \u2591\u2592\u2588\u2588     \u2591\u2592\u2593\u2588"""


class FileSelector(DirectoryTree):
    FILE_MARK = "\u25cb "
    SELECTED_MARK = "\u25cf "

    def __init__(self, path: str, **kwargs):
        super().__init__(path, **kwargs)
        self.selected: set[str] = set()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        path = str(event.path)
        node = self._find_node(event.path)

        if path in self.selected:
            self.selected.remove(path)
            if node:
                lbl = str(node.label)
                if lbl.startswith(self.SELECTED_MARK):
                    node.label = lbl.replace(self.SELECTED_MARK, self.FILE_MARK, 1)
        else:
            self.selected.add(path)
            if node:
                lbl = str(node.label)
                if not lbl.startswith(self.SELECTED_MARK):
                    node.label = lbl.replace(self.FILE_MARK, self.SELECTED_MARK, 1) if lbl.startswith(self.FILE_MARK) else self.SELECTED_MARK + lbl

        self._notify_selection_count()

    @staticmethod
    def _node_path(node) -> str | None:
        data = node.data
        if isinstance(data, dict):
            p = data.get("path")
        else:
            p = getattr(data, "path", None) if data is not None else None
        return str(p) if p else None

    def on_tree_node_expanded(self, event: DirectoryTree.NodeExpanded):
        for child in event.node.children:
            p = self._node_path(child)
            if p and p in self.selected:
                lbl = str(child.label)
                if not lbl.startswith(self.SELECTED_MARK):
                    child.label = lbl.replace(self.FILE_MARK, self.SELECTED_MARK, 1) if lbl.startswith(self.FILE_MARK) else self.SELECTED_MARK + lbl

    def reset_marks(self):
        self.selected.clear()
        self._reset_node_marks(self.root)

    def _reset_node_marks(self, node):
        for child in node.children:
            if child.label:
                lbl = str(child.label)
                if lbl.startswith(self.SELECTED_MARK):
                    child.label = lbl.replace(self.SELECTED_MARK, self.FILE_MARK, 1)
            self._reset_node_marks(child)

    def _find_node(self, target: Path):
        return self._search_node(self.root, target)

    def _search_node(self, node, target: Path):
        for child in node.children:
            p = self._node_path(child)
            if p and Path(p) == target:
                return child
            found = self._search_node(child, target)
            if found:
                return found
        return None

    def _notify_selection_count(self):
        app = self.app
        if hasattr(app, "update_file_count"):
            app.update_file_count(len(self.selected))


class KalamApp(App):
    TITLE = "Kalam"
    SUB_TITLE = "AI Coding Agent"
    CSS_PATH = "kalam.tcss"

    BINDINGS = [
        ("ctrl+r", "run_agent", "Run"),
        ("ctrl+l", "clear_all", "Clear"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, project_path: str | None = None, debug: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.project_path = Path(project_path).resolve() if project_path else Path.cwd()
        self._messages: list[dict] = []
        self._debug_mode = debug

    def compose(self) -> ComposeResult:
        with Vertical(id="app-container"):
            yield Header(show_clock=True)

            with Horizontal(id="main-container"):
                with Vertical(id="left-column"):
                    with Vertical(id="chat-history"):
                        yield RichLog(id="chat-messages", highlight=True, markup=True)
                    with Vertical(id="chat-input-area"):
                        yield TextArea(id="prompt-input", placeholder="describe what you want to build...")

                with Vertical(id="right-column"):
                    with TabbedContent(id="process-tabs"):
                        with TabPane("files", id="files-tab"):
                            yield FileSelector(str(self.project_path), id="file-tree")
                        with TabPane("plan", id="plan-tab"):
                            yield RichLog(id="plan-output", highlight=True, markup=True)
                        with TabPane("design", id="design-tab"):
                            yield RichLog(id="design-output", highlight=True, markup=True)
                        with TabPane("errors", id="errors-tab"):
                            yield RichLog(id="errors-output", highlight=True, markup=True)

                    if self._debug_mode:
                        with TabPane("debug", id="debug-tab"):
                            yield RichLog(id="debug-output", highlight=True, markup=True)

                    with Vertical(id="models-panel"):
                        yield Label("models", classes="panel-label")
                        yield ModelList()

            yield Static("ready", id="status-bar")
            yield Footer()

    def on_mount(self):
        chat = self.query_one("#chat-messages", RichLog)
        art_lines = KALAM_ASCII.splitlines()
        art_w = max(len(l) for l in art_lines)
        left = self.query_one("#left-column")
        w = left.outer_size.width if hasattr(left, "outer_size") else self.size.width
        pad = " " * max(0, (w - art_w) // 2)
        centered = "\n".join(pad + l for l in art_lines)
        chat.write(f"[dim]{centered}[/]")
        chat.write("")
        self.query_one("#prompt-input", TextArea).focus()

    def _add_chat_message(self, role: str, content: str):
        chat = self.query_one("#chat-messages", RichLog)
        if role == "user":
            chat.write(f"[bold cyan]You:[/] {content}")
        else:
            chat.write(f"[bold green]Kalam:[/] {content}")
        chat.write("")
        self._messages.append({"role": role, "content": content})

    def update_file_count(self, count: int):
        pass

    def action_run_agent(self):
        self._run_agent()

    def action_clear_all(self):
        self._clear_all()

    def _clear_all(self):
        self.query_one("#prompt-input", TextArea).clear()
        file_selector = self.query_one("#file-tree", FileSelector)
        file_selector.reset_marks()

        clear_ids = ["plan-output", "design-output", "errors-output"]
        if self._debug_mode:
            clear_ids.append("debug-output")
        for wid in clear_ids:
            self.query_one(f"#{wid}", RichLog).clear()

        self._messages.clear()
        self.query_one("#chat-messages", RichLog).clear()
        self.query_one("#status-bar", Static).update("ready")
        self.query_one("#prompt-input", TextArea).focus()

    def _log(self, message: str):
        if not self._debug_mode:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        debug_out = self.query_one("#debug-output", RichLog)
        debug_out.write(f"[dim]{ts}[/] {message}")

    def _set_status(self, text: str):
        self.query_one("#status-bar", Static).update(text)

    @work(exclusive=True)
    async def _run_agent(self):
        prompt = self.query_one("#prompt-input", TextArea).text.strip()
        if not prompt:
            self._show_error("enter a prompt before running.")
            return

        file_selector = self.query_one("#file-tree", FileSelector)
        selected = set(file_selector.selected)

        discovered = discover_source_files(self.project_path)
        if discovered:
            files = list(selected | set(discovered))
        else:
            files = list(selected)

        self._add_chat_message("user", prompt)
        self.query_one("#prompt-input", TextArea).clear()
        n_files = len(files)
        self._set_status(f"[yellow]starting ({n_files} file{'s' if n_files != 1 else ''})...[/]")
        self._log(f"starting with {n_files} files, prompt: {prompt[:60]}...")

        state: MasterState = {
            "files": files,
            "prompt": prompt,
            "todo": [],
            "context": [],
            "design_guidelines": "",
            "generated_files": {},
            "errors": [],
            "history": [],
            "status": "",
        }

        try:
            async for event in master_graph.astream(state):
                for node_name, node_output in event.items():
                    if node_name == "__start__":
                        continue
                    self._log(f"node: [bold]{node_name}[/] {'started' if node_output is None else 'completed'}")
                    if node_output:
                        state.update(node_output)
                    self._handle_graph_event(node_name, node_output)
            self._log("[green]graph complete[/]")
            self._display_results(state)
        except Exception as e:
            self._log(f"[red]error[/]: {type(e).__name__}: {e}")
            self._show_error(f"{type(e).__name__}: {e}")

    def _handle_graph_event(self, node_name: str, node_output: dict | None):
        status_text = STATUS_LABELS.get(node_name, node_name)
        self._set_status(f"[yellow]{status_text}[/]")

        if not node_output:
            return

        n_errors = len(node_output.get("errors", []))
        n_todo = len(node_output.get("todo", []))
        n_files = len(node_output.get("generated_files", {}))
        parts = []
        if n_todo:
            parts.append(f"{n_todo} tasks")
        if n_files:
            parts.append(f"{n_files} files generated")
        if n_errors:
            parts.append(f"[red]{n_errors} errors[/]")
        if parts:
            self._log(f"  -> {', '.join(parts)}")

        errors = node_output.get("errors", [])
        if errors:
            err_out = self.query_one("#errors-output", RichLog)
            for e in errors:
                err_out.write(f"[red]{e}[/]")

        todo = node_output.get("todo", [])
        if todo:
            plan_out = self.query_one("#plan-output", RichLog)
            plan_out.clear()
            for i, t in enumerate(todo, 1):
                plan_out.write(f"[bold cyan]{i}.[/] {t.get('task', '')}")
                ctx = t.get("context", "")
                if ctx:
                    plan_out.write(f"  [dim]{ctx}[/]")

        guidelines = node_output.get("design_guidelines", "")
        if guidelines:
            design_out = self.query_one("#design-output", RichLog)
            design_out.clear()
            design_out.write(f"[green]{guidelines}[/]")

    def _show_error(self, message: str):
        self._set_status(f"[red]error: {message}[/]")
        self.notify(message, severity="error", timeout=8)
        self.query_one("#prompt-input", TextArea).focus()

    def _display_results(self, data: dict):
        generated = data.get("generated_files", {})
        errors = data.get("errors", [])
        todo = data.get("todo", [])
        guidelines = data.get("design_guidelines", "")

        # Build assistant response
        parts = []
        if generated:
            files_list = "\n".join(f"  \u2713 {f}" for f in generated)
            parts.append(f"generated files:\n{files_list}")
        if errors:
            parts.append(f"errors: {'; '.join(errors[:3])}")
        if not parts:
            parts.append("done")

        self._add_chat_message("assistant", "\n".join(parts))

        # Update sidebar tabs
        plan_out = self.query_one("#plan-output", RichLog)
        plan_out.clear()
        if todo:
            for i, t in enumerate(todo, 1):
                plan_out.write(f"[bold cyan]{i}.[/] {t.get('task', '')}")
                ctx = t.get("context", "")
                if ctx:
                    plan_out.write(f"  [dim]{ctx}[/]")
                plan_out.write("")
        else:
            plan_out.write("[yellow]no tasks were generated.[/]")

        design_out = self.query_one("#design-output", RichLog)
        design_out.clear()
        if guidelines:
            design_out.write(f"[green]{guidelines}[/]")
        else:
            design_out.write("[dim]no design guidelines[/]")

        err_out = self.query_one("#errors-output", RichLog)
        err_out.clear()
        if errors:
            for e in errors:
                err_out.write(f"[red]{e}[/]")
            self._set_status(f"[red]complete with {len(errors)} error(s)[/]")
        else:
            self._set_status("[green]complete[/]")

        n_gen = len(data.get("generated_files", {}))
        n_err = len(data.get("errors", []))
        self._log(f"done: {n_gen} files written, [{'red' if n_err else 'green'}]{n_err} errors[/]")

        self.query_one("#prompt-input", TextArea).focus()
