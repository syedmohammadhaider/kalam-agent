from __future__ import annotations

import os

import httpx
from textual.app import ComposeResult
from textual.widgets import Static, ListView, ListItem, Label


OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


class ModelList(Static):
    """Display available Ollama models with the active one highlighted.

    STUB: The data source (self.load_models) is a placeholder — wire it up
    to the real Ollama API or inject model data from the parent app.
    """

    def compose(self) -> ComposeResult:
        yield ListView(id="model-items")

    def on_mount(self) -> None:
        self.load_models()

    def load_models(self) -> None:
        """Fetch models from Ollama and populate the list.

        STUB: Replace this implementation with a real API call or
        external data injection when connecting to the backend.
        """
        models = self._fetch_models()
        list_view = self.query_one("#model-items", ListView)
        list_view.clear()

        for m in models:
            label = m["name"]
            is_active = m.get("active", False)
            item = ListItem(Label(label))
            if is_active:
                item.classes = "active-model"
            list_view.append(item)

    def _fetch_models(self) -> list[dict]:
        """STUB: returns hardcoded data. Wire to Ollama API."""
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])

            active_model = os.environ.get("KALAM_LLM_MODEL", "qwen2.5-coder:7b")
            result = []
            for m in models:
                name = m["name"]
                result.append({"name": name, "active": name == active_model})
            if not result:
                result.append({"name": "(no models found)", "active": False})
            return result
        except Exception:
            return [{"name": "qwen2.5-coder:7b (offline)", "active": True}]
