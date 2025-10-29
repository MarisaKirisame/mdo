from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

TaskDict = Dict[str, Any]


class TaskStore:
    """JSON-backed hierarchical task storage with basic locking."""

    def __init__(self, data_path: Path) -> None:
        self._path = data_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    def _read_no_lock(self) -> List[TaskDict]:
        raw_text = self._path.read_text(encoding="utf-8-sig")
        raw = json.loads(raw_text or "[]")
        if not isinstance(raw, list):
            raise ValueError("Task store file is corrupted: expected a list.")
        return raw

    def _write_no_lock(self, tasks: List[TaskDict]) -> None:
        self._path.write_text(
            json.dumps(tasks, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _reindex(self, tasks: List[TaskDict]) -> None:
        by_parent: Dict[Optional[str], List[TaskDict]] = {}
        for task in tasks:
            parent_id = task.get("parent_id")
            if parent_id in ("", None):
                parent_id = None
            task["parent_id"] = parent_id
            by_parent.setdefault(parent_id, []).append(task)

        for siblings in by_parent.values():
            siblings.sort(key=lambda item: item.get("position", 0))
            for position, task in enumerate(siblings):
                task["position"] = position

    def _normalise(self, tasks: List[TaskDict]) -> List[TaskDict]:
        valid_ids = {task.get("id") for task in tasks if "id" in task}
        for task in tasks:
            parent_id = task.get("parent_id")
            if parent_id not in valid_ids:
                task["parent_id"] = None
            else:
                task["parent_id"] = parent_id
        self._reindex(tasks)
        return tasks

    def _build_tree(self, tasks: List[TaskDict]) -> List[TaskDict]:
        by_parent: Dict[Optional[str], List[TaskDict]] = {}
        for task in tasks:
            by_parent.setdefault(task.get("parent_id"), []).append(task)

        for siblings in by_parent.values():
            siblings.sort(key=lambda item: item.get("position", 0))

        def build(parent_id: Optional[str]) -> List[TaskDict]:
            nodes: List[TaskDict] = []
            for item in by_parent.get(parent_id, []):
                node = {
                    "id": item["id"],
                    "title": item["title"],
                    "position": item["position"],
                    "created_at": item["created_at"],
                    "parent_id": item.get("parent_id"),
                    "children": build(item["id"]),
                }
                nodes.append(node)
            return nodes

        return build(None)

    def list_tasks(self) -> List[TaskDict]:
        with self._lock:
            tasks = self._normalise(self._read_no_lock())
            tree = self._build_tree(tasks)
        return tree

    def _ensure_parent(self, tasks: List[TaskDict], parent_id: Optional[str]) -> None:
        if parent_id is None:
            return
        if not any(task["id"] == parent_id for task in tasks):
            raise ValueError("Parent task not found.")

    def _collect_descendants(self, tasks: List[TaskDict], root_id: str) -> Set[str]:
        descendants: Set[str] = set()
        frontier = [root_id]
        while frontier:
            current = frontier.pop()
            for task in tasks:
                if task.get("parent_id") == current:
                    child_id = task["id"]
                    if child_id not in descendants:
                        descendants.add(child_id)
                        frontier.append(child_id)
        return descendants

    def create_task(
        self,
        title: str,
        parent_id: Optional[str] = None,
        position: Optional[int] = None,
    ) -> TaskDict:
        normalised_title = title.strip()
        if not normalised_title:
            raise ValueError("Task title must not be empty.")

        with self._lock:
            tasks = self._normalise(self._read_no_lock())
            self._ensure_parent(tasks, parent_id)

            siblings = [task for task in tasks if task.get("parent_id") == parent_id]
            insert_position = len(siblings) if position is None else max(0, min(position, len(siblings)))

            for task in siblings:
                if task["position"] >= insert_position:
                    task["position"] += 1

            new_task = {
                "id": uuid.uuid4().hex,
                "title": normalised_title,
                "created_at": time.time(),
                "position": insert_position,
                "parent_id": parent_id,
            }

            tasks.append(new_task)
            self._reindex(tasks)
            self._write_no_lock(tasks)

        return new_task

    def delete_task(self, task_id: str) -> None:
        with self._lock:
            tasks = self._normalise(self._read_no_lock())
            if not any(task["id"] == task_id for task in tasks):
                raise ValueError("Task not found.")

            ids_to_remove = {task_id} | self._collect_descendants(tasks, task_id)
            remaining = [task for task in tasks if task["id"] not in ids_to_remove]

            self._reindex(remaining)
            self._write_no_lock(remaining)

    def reorder_tasks(self, task_ids_in_order: List[str]) -> List[TaskDict]:
        with self._lock:
            tasks = self._normalise(self._read_no_lock())
            top_level = [task for task in tasks if task.get("parent_id") is None]
            top_level_ids = {task["id"] for task in top_level}

            requested_ids = list(task_ids_in_order)
            if set(requested_ids) != top_level_ids or len(requested_ids) != len(top_level_ids):
                raise ValueError("Reorder request must include each top-level task exactly once.")

            ordering = {task_id: position for position, task_id in enumerate(requested_ids)}
            for task in top_level:
                task["position"] = ordering[task["id"]]

            self._reindex(tasks)
            self._write_no_lock(tasks)
            tree = self._build_tree(tasks)

        return tree

    def move_task(self, task_id: str, parent_id: Optional[str], position: int) -> List[TaskDict]:
        with self._lock:
            tasks = self._normalise(self._read_no_lock())
            index = {task["id"]: task for task in tasks}

            if task_id not in index:
                raise ValueError("Task not found.")
            if parent_id is not None and parent_id not in index:
                raise ValueError("Parent task not found.")
            if parent_id == task_id:
                raise ValueError("Task cannot be its own parent.")

            if parent_id is not None:
                descendants = self._collect_descendants(tasks, task_id)
                if parent_id in descendants:
                    raise ValueError("Cannot move a task inside its own subtree.")

            target = index[task_id]
            old_parent = target.get("parent_id")
            old_position = target.get("position", 0)

            for task in tasks:
                if task.get("parent_id") == old_parent and task["position"] > old_position:
                    task["position"] -= 1

            target["parent_id"] = parent_id

            siblings = [task for task in tasks if task.get("parent_id") == parent_id and task["id"] != task_id]
            insert_position = max(0, min(position, len(siblings)))

            for task in siblings:
                if task["position"] >= insert_position:
                    task["position"] += 1

            target["position"] = insert_position

            self._reindex(tasks)
            self._write_no_lock(tasks)
            tree = self._build_tree(tasks)

        return tree
