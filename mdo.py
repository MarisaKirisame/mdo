from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

STORE_PATH = Path(__file__).with_name("items.json")

class Task:
    id: int
    title: str
    parent_id: Optional[int]
    children: Set[int]

    def __init__(self, id: int, title: str, parent_id: Optional[int] = None) -> None:
        assert isinstance(id, int)
        assert isinstance(title, str)
        assert parent_id is None or isinstance(parent_id, int)
        self.id = id
        self.title = title
        self.parent_id = parent_id
        self.children = set()

    def is_subtask(self) -> bool:
        return self.parent_id is not None
    
    def have_subtask(self) -> bool:
        return len(self.children) > 0
    
    def to_json(self) -> dict:
        return {"id": self.id, "title": self.title, "parent_id": self.parent_id}
    
    @staticmethod
    def from_json(json) -> Task:
        id = int(json["id"])
        title = str(json["title"])
        parent_id = json.get("parent_id", None)
        return Task(id=id, title=title, parent_id=parent_id)

    def __str__(self) -> str:
        if self.have_subtask():
            return f"{self.id}: {self.title} (has {len(self.children)} subtasks)"
        else:
            return f"{self.id}: {self.title}"
    
class AppData:
    tasks: Dict[int, Task]
    fresh_id: int

    def __init__(self) -> None:
        self.tasks = {}
        self.fresh_id = 0

    def to_json(self) -> Dict[str, Any]:
        return {"tasks": [self.tasks[task_id].to_json() for task_id in self.tasks]}
    
    def from_json(self, json) -> None:
        lines = json.get("tasks", [])
        for entry in lines:
            task = Task.from_json(entry)
            self.tasks[task.id] = task
    
    def save(self) -> None:
        payload = self.to_json()
        STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not STORE_PATH.exists():
            return

        raw_text = STORE_PATH.read_text(encoding="utf-8")
        if not raw_text.strip():
            return
    
        data = json.loads(raw_text)
        self.from_json(data)
        self.fix()
    
    def fix(self) -> None:
        for task_id, task in list(self.tasks.items()):
            if task.parent_id is not None:
                if task.parent_id not in self.tasks:
                    del self.tasks[task_id]
                else:
                    self.tasks[task.parent_id].children.add(task.id)
            for child_id in task.children:
                if child_id not in self.tasks:
                    task.children.remove(child_id)
            self.fresh_id = max(self.fresh_id, task_id + 1)

    def get_id(self) -> int:
        ret = self.fresh_id
        self.fresh_id += 1
        return ret
    
    def clear(self) -> None:
        self.tasks = []
        self.fresh_id = 0

    def list(self, at:Optional[int]=None) -> str:
        if at is None:
            tasks = list([task for task in self.tasks.values() if not task.is_subtask()])
        else:
            tasks = list([self.tasks[id] for id in self.tasks[at].children])
        if len(self.tasks) == 0:
            print("(no items)")
        else:
            print(f"{self.tasks[at] if at in self.tasks else "root"}, tasks count(including subtasks): {len(tasks)}")
            for task in tasks:
                print(task)

    def do(self, id: int) -> None:
        task = self.tasks[id]
        if task.have_subtask():
            print("cannot do task with subtasks. Please do subtasks first.")
            self.list(at=id)
        else:
            if task.is_subtask():
                parent = self.tasks[task.parent_id]
                parent.children.remove(id)
            del self.tasks[id]
            print(f"Done {task}.")
            data.list(task.parent_id)

data = AppData()
data.load()

def cmd_add(title: str, parent_id) -> None:
    task_id = data.get_id()
    task = Task(id=task_id, title=title, parent_id=parent_id)
    data.tasks[task_id] = task
    data.save()
    print(f"Added {task}.")

def cmd_list(at:Optional[int]) -> None:
    data.list(at)

def cmd_clear() -> None:
    data.clear()
    data.save()
    print("Cleared all items.")

def cmd_do(id: int) -> None:
    data.do(id)
    data.save()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mdo", description="Simple list manager.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Append a string to the list.")
    add_parser.add_argument("text", help="Text to store.")
    add_parser.add_argument("parent", nargs="?", help="parent id", default=None, type=int)
    add_parser.set_defaults(func=lambda args: cmd_add(args.text, args.parent))

    clear_parser = subparsers.add_parser("clear", help="Clear all stored items.")
    clear_parser.set_defaults(func=lambda args: cmd_clear())

    list_parser = subparsers.add_parser("list", help="Show all stored items.")
    list_parser.add_argument("at", nargs="?", help="list subtasks from id:", default=None, type=int)
    list_parser.set_defaults(func=lambda args: cmd_list(args.at))

    do_parser = subparsers.add_parser("do", help="do task")
    do_parser.add_argument("id", help="task id to do", type=int)
    do_parser.set_defaults(func=lambda args: cmd_do(args.id))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
