import json
import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents.master.graph import master_graph
from agents.master.schema.state import MasterState

router = APIRouter()


class RunRequest(BaseModel):
    prompt: str
    files: list[str] = []


class RunResponse(BaseModel):
    todo: list[dict]
    design_guidelines: str
    generated_files: dict[str, str]
    errors: list[str]
    status: str = ""


def _build_initial_state(req: RunRequest) -> MasterState:
    return {
        "files": req.files,
        "prompt": req.prompt,
        "todo": [],
        "context": [],
        "design_guidelines": "",
        "generated_files": {},
        "errors": [],
        "history": [],
        "status": "",
        "commands": [],
        "shell_output": [],
    }


@router.post("/run", response_model=RunResponse)
def run_agent(req: RunRequest):
    initial_state = _build_initial_state(req)
    result = master_graph.invoke(initial_state)

    todo = result.get("todo", [])
    return RunResponse(
        todo=[{"task": t["task"], "context": t["context"]} for t in todo] if isinstance(todo, list) else [],
        design_guidelines=result.get("design_guidelines", ""),
        generated_files=result.get("generated_files", {}),
        errors=result.get("errors", []),
        status=result.get("status", ""),
    )


STATUS_LABELS = {
    "planner": "planning tasks",
    "designer": "designing UI",
    "executor": "generating code",
    "shell_executor": "verifying files",
}


@router.post("/run/stream")
async def run_agent_stream(req: RunRequest):
    initial_state = _build_initial_state(req)

    async def event_stream():
        yield f"data: {json.dumps({'type': 'status', 'status': 'starting', 'node': ''})}\n\n"

        final_state: dict = dict(initial_state)

        async for event in master_graph.astream(initial_state):
            for node_name, node_output in event.items():
                if node_name == "__start__":
                    continue

                if node_output:
                    final_state.update(node_output)

                status_text = STATUS_LABELS.get(node_name, node_name)
                payload: dict[str, object] = {"type": "status", "status": status_text, "node": node_name}

                if node_output:
                    for key in ("errors", "generated_files", "design_guidelines", "todo"):
                        if key in node_output and node_output[key]:
                            payload[key] = node_output[key]
                    if "status" in node_output:
                        payload["status"] = node_output["status"]

                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'complete', **final_state})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/health")
def health():
    return {"status": "ok"}
