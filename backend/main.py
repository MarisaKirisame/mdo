from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .storage import TaskStore

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"
DATA_PATH = BASE_DIR / "data" / "tasks.json"

mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("application/json", ".map")
store = TaskStore(DATA_PATH)

app = FastAPI(title="Todo Backend")


class JSStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            media_type = response.media_type
            if media_type in (None, "application/octet-stream", "text/plain"):
                if path.endswith(".map"):
                    response.media_type = "application/json"
                else:
                    response.media_type = "text/javascript"
        return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskOut(BaseModel):
    id: str
    title: str
    position: int
    parent_id: Optional[str] = None
    created_at: float
    children: List["TaskOut"] = Field(default_factory=list)


class TaskList(BaseModel):
    tasks: List[TaskOut]


class TaskCreate(BaseModel):
    title: str
    parent_id: Optional[str] = None
    position: Optional[int] = None


class TaskReorder(BaseModel):
    order: List[str]


class TaskMove(BaseModel):
    task_id: str
    parent_id: Optional[str] = None
    position: int


try:  # Pydantic v2
    TaskOut.model_rebuild()
except AttributeError:  # pragma: no cover - fallback for Pydantic v1
    TaskOut.update_forward_refs()


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str) -> Response:
    try:
        store.delete_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/tasks", response_model=TaskList)
def list_tasks() -> TaskList:
    tasks = store.list_tasks()
    return TaskList(tasks=tasks)


@app.post("/api/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> TaskOut:
    try:
        task = store.create_task(
            payload.title,
            parent_id=payload.parent_id,
            position=payload.position,
        )
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TaskOut(**task)


@app.post("/api/tasks/reorder", response_model=TaskList)
def reorder_tasks(payload: TaskReorder) -> TaskList:
    try:
        tasks = store.reorder_tasks(payload.order)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TaskList(tasks=tasks)


@app.post("/api/tasks/move", response_model=TaskList)
def move_task(payload: TaskMove) -> TaskList:
    try:
        tasks = store.move_task(payload.task_id, payload.parent_id, payload.position)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TaskList(tasks=tasks)


if WEB_DIR.exists():
    app.mount("/", JSStaticFiles(directory=WEB_DIR, html=True), name="frontend")
else:  # pragma: no cover - fallback
    @app.get("/")
    def fallback_root() -> JSONResponse:
        return JSONResponse(
            {"message": "Frontend directory not found.", "expected": str(WEB_DIR)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
