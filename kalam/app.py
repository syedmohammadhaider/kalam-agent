from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, Binding, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from kalam.agents.coder.graph import coder_graph
from kalam.agents.coder.schema.state import CoderState
from kalam.agents.master.nodes.designer import designer_node, needs_design
from kalam.agents.master.nodes.planner import planner_node
from kalam.agents.master.schema.state import MasterState
from kalam.agents.tools import approve_shell, clear_approvals
from kalam.widgets import ModelConfigPanel

STATUS_LABELS = {
    "planner": "planning tasks",
    "designer": "designing UI",
    "executor": "generating code",
}

CODER_STATUS_LABELS = {
    "decomposer": "decomposing",
    "context_retriever": "gathering context",
    "brain": "executing tasks",
    "verifier": "verifying",
    "checkpoint": "checkpointing",
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
 █████   ████   █████████   █████         █████████   ██████   ██████
░░███   ███░   ███░░░░░███ ░░███         ███░░░░░███ ░░██████ ██████ 
 ░███  ███    ░███    ░███  ░███        ░███    ░███  ░███░█████░███ 
 ░███████     ░███████████  ░███        ░███████████  ░███░░███ ░███ 
 ░███░░███    ░███░░░░░███  ░███        ░███░░░░░███  ░███ ░░░  ░███ 
 ░███ ░░███   ░███    ░███  ░███      █ ░███    ░███  ░███      ░███ 
 █████ ░░████ █████   █████ ███████████ █████   █████ █████     █████
░░░░░   ░░░░ ░░░░░   ░░░░░ ░░░░░░░░░░░ ░░░░░   ░░░░░ ░░░░░     ░░░░░"""


class KalamApp(App):
    TITLE = "Kalam"
    SUB_TITLE = "AI Coding Agent"
    CSS_PATH = "kalam.tcss"

    BINDINGS = [
        Binding("ctrl+r", "run_agent", "Run"),
        Binding("ctrl+l", "clear_all", "Clear"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+y", "approve_shell", "Approve", priority=True),
        Binding("ctrl+g", "approve_shell", "Approve", priority=True),
    ]

    def __init__(self, project_path: str | None = None, debug: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.project_path = Path(project_path).resolve() if project_path else Path.cwd()
        self._messages: list[dict] = []
        self._debug_mode = debug
        self._run_start_time: float | None = None
        self._timer_handle = None
        self._status_text = "ready"
        self._state: MasterState | None = None
        self._source_files: list[str] = []
        self._autocomplete_active = False
        self._autocomplete_index = 0
        self._autocomplete_matches: list[str] = []
        self._autocomplete_at_pos = -1
        self._approval_event: asyncio.Event | None = None
        self._kalam_buffer = ""
        self._kalam_index = -1

    def compose(self) -> ComposeResult:
        with Vertical(id="app-container"):
            yield Header(show_clock=True)

            with Horizontal(id="main-container"):
                with Vertical(id="left-column"):
                    with Vertical(id="chat-history"):
                        yield RichLog(id="chat-messages", highlight=True, markup=True)
                    with Vertical(id="chat-input-area"):
                        yield ListView(id="file-autocomplete")
                        yield TextArea(id="prompt-input", placeholder="describe what you want to build... (type @ to attach files)")
                        yield Button("Approve Shell", id="approve-btn", variant="primary")

                with Vertical(id="right-column"):
                    with TabbedContent(id="process-tabs"):
                        with TabPane("errors", id="errors-tab"):
                            yield RichLog(id="errors-output", highlight=True, markup=True)
                        with TabPane("state", id="state-tab"):
                            yield RichLog(id="state-output", highlight=True, markup=True)

                    yield ModelConfigPanel(id="models-panel")

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
        self._source_files = discover_source_files(self.project_path)
        self.query_one("#prompt-input", TextArea).focus()

    def _add_chat_message(self, role: str, content: str):
        self._messages.append({"role": role, "content": content})
        self._rerender_chat()

    def _append_kalam_step(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[dim]{ts}[/] {text}"
        if not self._kalam_buffer:
            self._kalam_buffer = line
            self._messages.append({"role": "assistant", "content": self._kalam_buffer})
            self._kalam_index = len(self._messages) - 1
        else:
            self._kalam_buffer += f"\n{line}"
            self._messages[self._kalam_index]["content"] = self._kalam_buffer
        self._rerender_chat()

    def _rerender_chat(self):
        chat = self.query_one("#chat-messages", RichLog)
        chat.clear()
        for msg in self._messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                chat.write(f"[bold cyan]You:[/] {content}")
            else:
                chat.write(f"[bold green]Kalam:[/] {content}")
            chat.write("")

    def action_run_agent(self):
        self._run_agent()

    def action_approve_shell(self):
        if self._approval_event:
            self._approval_event.set()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "approve-btn":
            self.action_approve_shell()

    def action_clear_all(self):
        self._clear_all()

    def _clear_all(self):
        self._stop_timer()
        self._state = None
        self._hide_autocomplete()
        self._approval_event = None
        self._kalam_buffer = ""
        self._kalam_index = -1
        clear_approvals()
        self.query_one("#approve-btn", Button).display = False
        self.query_one("#prompt-input", TextArea).clear()

        clear_ids = ["errors-output", "state-output"]
        for wid in clear_ids:
            self.query_one(f"#{wid}", RichLog).clear()

        self._messages.clear()
        self.query_one("#chat-messages", RichLog).clear()
        self._status_text = "ready"
        self._update_status_bar()
        self.query_one("#prompt-input", TextArea).focus()

    def _log(self, message: str):
        if not self._debug_mode:
            return
        self._append_kalam_step(f"[dim][debug][/] {message}")

    def _set_status(self, text: str):
        self._status_text = text
        self._update_status_bar()

    def _update_status_bar(self):
        base = self._status_text
        if self._run_start_time is not None:
            elapsed = time.monotonic() - self._run_start_time
            mins, secs = divmod(int(elapsed), 60)
            timer = f"[bold cyan][{mins:02d}:{secs:02d}][/]"
            self.query_one("#status-bar", Static).update(f"{timer} {base}")
        else:
            self.query_one("#status-bar", Static).update(base)

    # ---- @ file autocomplete ----

    def on_text_area_changed(self, event: TextArea.Changed):
        if event.text_area.id == "prompt-input":
            self._check_autocomplete(event.text_area)

    def on_list_view_selected(self, event: ListView.Selected):
        list_view = self.query_one("#file-autocomplete", ListView)
        if list_view.display and event.list_view.id == "file-autocomplete":
            self._autocomplete_index = list_view.index
            self._select_autocomplete_item()

    def on_key(self, event):
        if event.key == "escape" and self._autocomplete_active:
            self._hide_autocomplete()
            self.query_one("#prompt-input", TextArea).focus()

    def _check_autocomplete(self, textarea: TextArea):
        text = textarea.text
        row, col = textarea.cursor_location
        lines = text.split('\n')
        line = lines[row]

        before_cursor = line[:col]
        at_pos = before_cursor.rfind('@')

        if at_pos >= 0:
            fragment = before_cursor[at_pos + 1:]
            if ' ' not in fragment and '\t' not in fragment:
                self._autocomplete_at_pos = at_pos
                self._autocomplete_matches = self._find_matching_files(fragment)
                self._autocomplete_index = 0
                self._autocomplete_active = bool(self._autocomplete_matches)
                self._render_autocomplete()
                return

        self._hide_autocomplete()

    def _find_matching_files(self, fragment: str) -> list[str]:
        if not fragment:
            return self._source_files[:30]
        fragment_lower = fragment.lower()
        return [f for f in self._source_files if fragment_lower in f.lower()][:30]

    def _render_autocomplete(self):
        list_view = self.query_one("#file-autocomplete", ListView)
        list_view.clear()
        for path in self._autocomplete_matches:
            rel = os.path.relpath(path, self.project_path)
            list_view.append(ListItem(Label(rel)))
        list_view.index = 0
        list_view.display = True
        list_view.focus()

    def _hide_autocomplete(self):
        self._autocomplete_active = False
        self._autocomplete_matches = []
        self._autocomplete_index = 0
        self._autocomplete_at_pos = -1
        try:
            list_view = self.query_one("#file-autocomplete", ListView)
            list_view.display = False
            list_view.clear()
        except Exception:
            pass

    def _select_autocomplete_item(self):
        if not self._autocomplete_matches:
            return
        selected = self._autocomplete_matches[self._autocomplete_index]
        rel_path = os.path.relpath(selected, self.project_path)
        textarea = self.query_one("#prompt-input", TextArea)
        text = textarea.text
        row, col = textarea.cursor_location

        lines = text.split('\n')
        line = lines[row]
        new_line = line[:self._autocomplete_at_pos] + "@" + rel_path + line[col:]
        lines[row] = new_line
        textarea.text = '\n'.join(lines)

        new_col = self._autocomplete_at_pos + 1 + len(rel_path)
        textarea.move_cursor((row, new_col))

        self._hide_autocomplete()
        textarea.focus()

    def _resolve_file_references(self, text: str) -> list[str]:
        """Parse @file/path references from the prompt and resolve to absolute paths."""
        files: list[str] = []
        for match in re.finditer(r'(?<!\w)@(\S+)', text):
            ref = match.group(1)
            abs_path = self.project_path / ref
            if abs_path.exists() and abs_path.is_file():
                files.append(str(abs_path))
            else:
                ref_lower = ref.lower()
                matches = [f for f in self._source_files if ref_lower in f.lower()]
                files.extend(matches)
        return list(set(files))

    def _format_state(self) -> str:
        if self._state is None:
            return "[dim]no state[/]"
        lines = []
        for k, v in self._state.items():
            if k == "history":
                lines.append(f"[bold]{k}:[/] {len(v)} entries")
            elif k == "generated_files" and v:
                for f in v:
                    lines.append(f"[bold]{k}:[/] {f}")
            elif k == "context" and v:
                for i, c in enumerate(v, 1):
                    preview = c[:80] + "..." if len(c) > 80 else c
                    lines.append(f"[bold]{k}:[/] [{i}] {preview}")
            elif k == "injected_context" and v:
                preview = v[:80] + "..." if len(v) > 80 else v
                lines.append(f"[bold]{k}:[/] {preview}")
            elif k == "diffs" and v:
                lines.append(f"[bold]{k}:[/] {len(v)} diff(s)")
            elif k == "todo" and v:
                for i, t in enumerate(v, 1):
                    task_text = t.get("task", "")[:60]
                    lines.append(f"[bold]{k}:[/] [{i}] {task_text}")
            elif isinstance(v, list):
                if v:
                    for item in v:
                        item_s = str(item)[:80]
                        lines.append(f"[bold]{k}:[/] {item_s}")
                else:
                    lines.append(f"[bold]{k}:[/] [dim]empty[/]")
            elif isinstance(v, dict):
                if v:
                    lines.append(f"[bold]{k}:[/] {len(v)} item(s)")
                else:
                    lines.append(f"[bold]{k}:[/] [dim]empty[/]")
            else:
                text = str(v)[:120]
                lines.append(f"[bold]{k}:[/] {text}" if v else f"[bold]{k}:[/] [dim]{text}[/]")
        return "\n".join(lines)

    def _update_state_display(self):
        out = self.query_one("#state-output", RichLog)
        out.clear()
        out.write(self._format_state())

    def _stop_timer(self):
        self._run_start_time = None
        if self._timer_handle:
            self._timer_handle.stop()
            self._timer_handle = None

    @work(exclusive=True)
    async def _run_agent(self):
        prompt = self.query_one("#prompt-input", TextArea).text.strip()
        if not prompt:
            self._show_error("enter a prompt before running.")
            return

        self._source_files = discover_source_files(self.project_path)
        files = self._resolve_file_references(prompt) or self._source_files

        self._add_chat_message("user", prompt)
        self._kalam_buffer = ""
        self._kalam_index = -1
        self._append_kalam_step("starting...")
        self.query_one("#prompt-input", TextArea).clear()
        n_files = len(files)
        self._run_start_time = time.monotonic()
        self._timer_handle = self.set_interval(1, self._update_status_bar)
        self._set_status(f"starting ({n_files} files)")
        self._log(f"starting with {n_files} files, prompt: {prompt[:60]}...")

        # Include recent conversation history from previous runs
        history: list[dict] = []
        for msg in self._messages[-20:-1]:
            history.append({"role": msg["role"], "content": msg["content"]})

        state: MasterState = {
            "files": files,
            "prompt": prompt,
            "todo": [],
            "context": [],
            "design_guidelines": "",
            "generated_files": {},
            "errors": [],
            "history": history,
            "status": "",
        }
        self._state = state
        self._update_state_display()

        try:
            # Phase 1: Planning (run in thread to avoid blocking the event loop)
            self._append_kalam_step("planning tasks")
            self._set_status("planning tasks")
            self._log("phase: master/planner")
            plan_result = await asyncio.to_thread(planner_node, state)
            state.update(plan_result)
            n_planned = len(state.get("todo", []))
            self._append_kalam_step(f"planned {n_planned} task{'s' if n_planned != 1 else ''}")
            self._handle_graph_event("planner", plan_result)
            self._update_state_display()

            # Phase 1.5: Design (conditional, also blocking)
            if needs_design(state):
                self._append_kalam_step("designing UI")
                self._set_status("designing UI")
                self._log("phase: master/designer")
                design_result = await asyncio.to_thread(designer_node, state)
                state.update(design_result)
                self._handle_graph_event("designer", design_result)
                self._update_state_display()

            # Phase 2: Execute each task via coder graph with streaming
            todo = state.get("todo", [])
            n_tasks = len(todo)
            if n_tasks == 0:
                self._log("[yellow]no tasks to execute[/]")
            else:
                for i, task in enumerate(todo, 1):
                    task_label = task.get("task", "")[:60]
                    self._append_kalam_step(f"task {i}/{n_tasks}: {task_label}")
                    coder_state: CoderState = {
                        "todo": [],
                        "prompt": task["task"],
                        "context": state.get("context", []),
                        "files": state.get("files", []),
                        "injected_context": task.get("context", ""),
                        "diffs": [],
                        "generated_files": {},
                        "errors": [],
                        "skip_decompose": False,
                        "project_path": str(self.project_path),
                        "brain_subtask_idx": 0,
                        "brain_messages": [],
                        "pending_shell": "",
                        "shell_approved": False,
                        "chat_messages": [],
                    }

                    self._log(f"coder: task {i}/{n_tasks} ('{task_label}')")

                    # Task loop — may re-enter for shell approval
                    while True:
                        async for coder_event in coder_graph.astream(coder_state):
                            for node_name, node_output in coder_event.items():
                                if node_name == "__start__":
                                    continue
                                coder_label = CODER_STATUS_LABELS.get(node_name, node_name)
                                self._set_status(f"task {i}/{n_tasks}: {coder_label}")
                                self._log(f"  coder/{node_name}")
                                if node_output:
                                    coder_state.update(node_output)
                                    # Coder transparency — log node outputs to chat
                                    if node_name == "decomposer":
                                        n_sub = len(node_output.get("todo", []))
                                        skip = node_output.get("skip_decompose", False)
                                        if skip:
                                            self._append_kalam_step(f"  \u21b3 no split needed ({n_sub} subtask)")
                                        elif n_sub > 1:
                                            self._append_kalam_step(f"  \u21b3 split into {n_sub} subtasks")
                                    elif node_name == "context_retriever":
                                        ctx = node_output.get("injected_context", "")
                                        if ctx:
                                            preview = ctx[:100] + "..." if len(ctx) > 100 else ctx
                                            self._append_kalam_step(f"  \u21b3 context: {preview}")
                                    elif node_name == "verifier":
                                        v_errors = node_output.get("errors", [])
                                        v_files = node_output.get("generated_files", {})
                                        if v_errors:
                                            self._append_kalam_step(f"  \u21b3 verification: {len(v_errors)} error(s)")
                                        elif v_files:
                                            self._append_kalam_step(f"  \u21b3 verification: {len(v_files)} file(s) OK")

                        if coder_state.get("pending_shell"):
                            cmd = coder_state["pending_shell"]
                            self._append_kalam_step(
                                f"\u26a0\ufe0f Shell needs approval: `{cmd}`",
                            )
                            self._approval_event = asyncio.Event()
                            self._set_status("[yellow]awaiting shell approval \u2014 press Ctrl+Y or click Approve[/]")
                            self.query_one("#prompt-input", TextArea).blur()
                            self.query_one("#approve-btn", Button).display = True
                            self.query_one("#approve-btn", Button).focus()
                            await self._approval_event.wait()
                            self._approval_event = None
                            approve_shell(cmd)
                            coder_state["shell_approved"] = True
                            coder_state["pending_shell"] = cmd
                            self.query_one("#approve-btn", Button).display = False
                            self.query_one("#prompt-input", TextArea).focus()
                            continue

                        # Display brain chat messages as Kalam steps
                        for chat_msg in coder_state.get("chat_messages", []):
                            self._append_kalam_step(chat_msg.get("content", ""))
                        coder_state["chat_messages"] = []

                        break  # task done

                    # Collect per-task results
                    task_errors = coder_state.get("errors", [])
                    if task_errors:
                        full_msg = f"Task {i} ('{task['task'][:60]}'): {'; '.join(task_errors)}"
                        state["errors"].append(full_msg)
                        err_out = self.query_one("#errors-output", RichLog)
                        err_out.write(f"[red]{full_msg}[/]")

                    state["generated_files"].update(coder_state.get("generated_files", {}))
                    self._update_state_display()

                    # Refresh file list so subsequent tasks can see newly created files
                    self._source_files = discover_source_files(self.project_path)
                    state["files"] = list(set(state.get("files", [])) | set(self._source_files))

            # Record history
            todo_for_history = [t["task"][:80] for t in todo]
            summary = f"todo: {todo_for_history}"
            if state["generated_files"]:
                summary += f"\ngenerated: {list(state['generated_files'].keys())}"
            if state["errors"]:
                summary += f"\nerrors: {state['errors']}"
            state["history"].append({"role": "user", "content": prompt})
            state["history"].append({"role": "assistant", "content": summary})

            self._log("[green]graph complete[/]")
            self._display_results(state)
        except Exception as e:
            self._log(f"[red]error[/]: {type(e).__name__}: {e}")
            self._show_error(f"{type(e).__name__}: {e}")
        finally:
            self._stop_timer()

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
            lines = [f"  {i}. {t.get('task', '')}" for i, t in enumerate(todo, 1)]
            self._append_kalam_step("plan:\n" + "\n".join(lines))

        guidelines = node_output.get("design_guidelines", "")
        if guidelines:
            preview = guidelines[:200] + "..." if len(guidelines) > 200 else guidelines
            self._append_kalam_step(f"design: {preview}")

    def _finalize_kalam_run(self):
        self._kalam_buffer = ""
        self._kalam_index = -1

    def _show_error(self, message: str):
        self._stop_timer()
        self._finalize_kalam_run()
        self._set_status(f"[red]error: {message}[/]")
        self.notify(message, severity="error", timeout=8)
        self.query_one("#prompt-input", TextArea).focus()

    def _display_results(self, data: dict):
        self._stop_timer()
        self._finalize_kalam_run()
        generated = data.get("generated_files", {})
        errors = data.get("errors", [])
        todo = data.get("todo", [])
        guidelines = data.get("design_guidelines", "")

        # Build assistant response
        parts = []
        if todo:
            plan_lines = "\n".join(f"  {i}. {t.get('task', '')}" for i, t in enumerate(todo, 1))
            parts.append(f"plan:\n{plan_lines}")
        if generated:
            files_list = "\n".join(f"  \u2713 {f}" for f in generated)
            parts.append(f"generated files:\n{files_list}")
        if errors:
            parts.append(f"errors: {'; '.join(errors[:3])}")
        if not parts:
            parts.append("done")

        self._add_chat_message("assistant", "\n".join(parts))

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
