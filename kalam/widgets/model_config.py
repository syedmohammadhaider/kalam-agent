from __future__ import annotations

import os

import httpx
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Select, Static

from kalam.agents.utils import MODEL_CONFIG, DEFAULT_MODEL

OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

NODES: list[tuple[str, str]] = [
    ("planner", "Planner"),
    ("designer", "Designer"),
    ("decomposer", "Decomposer"),
    ("context_retriever", "Context"),
    ("brain", "Brain"),
]


class ModelConfigPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("models", classes="panel-label")
        yield Label("loading...", id="model-loading")
        with VerticalScroll(id="model-config-rows"):
            pass

    def on_mount(self) -> None:
        self._populate()

    def _fetch_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return models if models else ["(no models found)"]
        except Exception:
            return [f"{DEFAULT_MODEL} (offline)"]

    def _populate(self) -> None:
        models = self._fetch_models()
        loading = self.query_one("#model-loading")
        loading.remove()
        container = self.query_one("#model-config-rows")

        for node_key, node_label in NODES:
            current = MODEL_CONFIG.get(node_key) or DEFAULT_MODEL
            value = current if current in models else models[0]
            select = Select(
                [(m, m) for m in models],
                value=value,
                id=f"select-{node_key}",
                allow_blank=False,
            )
            row = Horizontal(
                Label(node_label, classes="model-config-label"),
                select,
                classes="model-config-row",
            )
            container.mount(row)

    def on_select_changed(self, event: Select.Changed) -> None:
        if not event.select.id:
            return
        prefix = "select-"
        if event.select.id.startswith(prefix):
            node_key = event.select.id[len(prefix):]
            MODEL_CONFIG[node_key] = event.value
