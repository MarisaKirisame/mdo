from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from mdo_time import TaskTime, parse_time_input

DEFAULT_STORE_PATH = Path(__file__).with_name("items.json")

class Task:
    id: int
    title: str
    parent_id: Optional[int]
    children: Set[int]
    time: Optional[TaskTime]
    recurrence: Optional[int]

    def __init__(
        self,
        id: int,
        title: str,
        parent_id: Optional[int] = None,
        time: Optional[TaskTime] = None,
        recurrence: Optional[int] = None,
    ) -> None:
        assert isinstance(id, int)
        assert isinstance(title, str)
        assert parent_id is None or isinstance(parent_id, int)
        assert time is None or isinstance(time, TaskTime)
        assert recurrence is None or isinstance(recurrence, int)
        if recurrence is not None:
            assert recurrence > 0
        self.id = id
        self.title = title
        self.parent_id = parent_id
        self.children = set()
        self.time = time
        self.recurrence = recurrence

    def is_subtask(self) -> bool:
        return self.parent_id is not None
    
    def have_subtask(self) -> bool:
        return len(self.children) > 0
    
    def to_json(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "time": self.time.to_json() if self.time is not None else None,
            "recurrence": self.recurrence,
        }
    
    @staticmethod
    def from_json(json) -> Task:
        id = int(json["id"])
        title = str(json["title"])
        parent_id = json.get("parent_id", None)
        raw_time = json.get("time")
        time = None if raw_time is None else TaskTime.from_json(raw_time)
        raw_recurrence = json.get("recurrence")
        recurrence: Optional[int] = None
        if raw_recurrence is not None:
            if isinstance(raw_recurrence, int):
                recurrence = raw_recurrence if raw_recurrence > 0 else None
            elif isinstance(raw_recurrence, str):
                alias = raw_recurrence.strip().lower()
                legacy = {
                    "daily": 1,
                    "day": 1,
                    "everyday": 1,
                    "every day": 1,
                }
                if alias in legacy:
                    recurrence = legacy[alias]
                else:
                    try:
                        parsed = int(alias)
                        if parsed > 0:
                            recurrence = parsed
                    except ValueError:
                        recurrence = None
        return Task(id=id, title=title, parent_id=parent_id, time=time, recurrence=recurrence)

    def __str__(self) -> str:
        label = f"{self.id}: {self.title}"
        if self.time:
            label = f"{label} [{self.time}]"
        if self.recurrence:
            label = f"{label} (repeat every {self.recurrence} day(s))"
        if self.have_subtask():
            return f"{label} (has {len(self.children)} subtasks)"
        else:
            return label
    
class AppData:
    tasks: Dict[int, Task]
    fresh_id: int
    store_path: Path
    _today: Optional[date]

    def __init__(self, store_path: Path, today: Optional[date] = None) -> None:
        self.store_path = store_path
        self.tasks = {}
        self.fresh_id = 0
        self._today = today

    def to_json(self) -> Dict[str, Any]:
        return {"tasks": [self.tasks[task_id].to_json() for task_id in self.tasks]}
    
    def from_json(self, json) -> None:
        lines = json.get("tasks", [])
        for entry in lines:
            task = Task.from_json(entry)
            self.tasks[task.id] = task
    
    def save(self) -> None:
        payload = self.to_json()
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.store_path.exists():
            return

        raw_text = self.store_path.read_text(encoding="utf-8")
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
            for child_id in list(task.children):
                if child_id not in self.tasks:
                    task.children.remove(child_id)
            self.fresh_id = max(self.fresh_id, task_id + 1)

    def get_id(self) -> int:
        ret = self.fresh_id
        self.fresh_id += 1
        return ret

    def clear(self) -> None:
        self.tasks = {}
        self.fresh_id = 0

    def _task_title_stack(self, task: Task) -> List[str]:
        titles: List[str] = []
        current: Optional[Task] = task
        visited: Set[int] = set()
        while current is not None and current.id not in visited:
            titles.append(current.title)
            visited.add(current.id)
            if current.parent_id is None:
                break
            current = self.tasks.get(current.parent_id)
        return list(reversed(titles))

    def _format_stack_path(self, task: Task) -> str:
        return " > ".join(self._task_title_stack(task))

    def _format_task_display(self, task: Task) -> str:
        stack = self._format_stack_path(task)
        if task.time:
            stack = f"{stack} [{task.time}]"
        if task.recurrence:
            stack = f"{stack} (repeat every {task.recurrence} day(s))"
        if task.have_subtask():
            return f"{task.id}: {stack} (has {len(task.children)} subtasks)"
        return f"{task.id}: {stack}"

    def list(self, at:Optional[int]=None) -> None:
        if at is None:
            tasks = [task for task in self.tasks.values() if not task.is_subtask()]
            context_label = "root"
        else:
            parent = self.tasks.get(at)
            if parent is None:
                print(f"Task {at} not found.")
                return
            tasks = [self.tasks[child_id] for child_id in parent.children if child_id in self.tasks]
            context_label = self._format_stack_path(parent)
        tasks.sort(key=lambda task: task.id)
        if not tasks:
            print(f"{context_label} (no tasks)")
            return
        print(f"{context_label}, tasks count: {len(tasks)}")
        for task in tasks:
            print(self._format_task_display(task))
    
    def list_today(self) -> None:
        today = self._today or date.today()
        tasks = [task for task in self.tasks.values() if task.time is not None and task.time.day <= today]
        tasks.sort(key=lambda task: (task.time.day, task.id))
        if not tasks:
            print("today (no tasks)")
            return
        print(f"today, tasks count: {len(tasks)}")
        for task in tasks:
            print(self._format_task_display(task))

    def move(self, task_id: int, new_parent_id: Optional[int]) -> bool:
        task = self.tasks.get(task_id)
        if task is None:
            print(f"Task {task_id} not found.")
            return False

        if new_parent_id is not None:
            parent = self.tasks.get(new_parent_id)
            if parent is None:
                print(f"Task {new_parent_id} not found.")
                return False
            if new_parent_id == task_id:
                print("Cannot move a task under itself.")
                return False
            ancestor = parent
            while ancestor is not None:
                if ancestor.id == task_id:
                    print("Cannot move a task into its own subtask hierarchy.")
                    return False
                ancestor = self.tasks.get(ancestor.parent_id)

        if task.parent_id == new_parent_id:
            print("Task already under the requested parent.")
            return False

        old_parent_id = task.parent_id
        if old_parent_id is not None and old_parent_id in self.tasks:
            self.tasks[old_parent_id].children.discard(task_id)

        task.parent_id = new_parent_id
        if new_parent_id is not None:
            self.tasks[new_parent_id].children.add(task_id)

        print(f"Moved {task}.")
        if old_parent_id is not None and old_parent_id != new_parent_id:
            self.list(old_parent_id)
        if new_parent_id is not None:
            self.list(new_parent_id)
        else:
            self.list()
        return True

    def set_time(self, task_id: int, time_value: Optional[str]) -> bool:
        task = self.tasks.get(task_id)
        if task is None:
            print(f"Task {task_id} not found.")
            return False
        if time_value is None:
            if task.time is None:
                print(f"Task {task_id} already has no time set.")
                return False
            task.time = None
            print(f"Cleared time for {task}.")
        else:
            base_day = self._today or date.today()
            parsed_time, recurrence = parse_time_input(time_value, base_day)
            if parsed_time is None:
                print("Invalid date. Please use YYYY-MM-DD, MM-DD, DD, weekday names, or recurrence phrases.")
                return False
            task.time = parsed_time
            if recurrence is not None:
                task.recurrence = recurrence
            print(f"Set time for {task}.")
        return True

    def set_recurrence(self, task_id: int, interval: Optional[int]) -> bool:
        task = self.tasks.get(task_id)
        if task is None:
            print(f"Task {task_id} not found.")
            return False
        if interval is None:
            if task.recurrence is None:
                print(f"Task {task_id} already has no recurrence.")
                return False
            task.recurrence = None
            print(f"Cleared recurrence for Task {task_id}.")
            return True
        if interval <= 0:
            print("Recurrence must be a positive integer number of days.")
            return False
        if task.recurrence == interval:
            print(f"Task {task_id} already set to every {interval} day(s).")
            return False
        task.recurrence = interval
        print(f"Set recurrence for Task {task_id} to every {interval} day(s).")
        return True

    def do(self, id: int) -> Tuple[bool, Optional[int]]:
        task = self.tasks.get(id)
        if task is None:
            print(f"Task {id} not found.")
            return False, None
        if task.have_subtask():
            print("cannot do task with subtasks. Please do subtasks first.")
            self.list(at=id)
            return False, None

        if task.recurrence is not None:
            before_display = str(task)
            base_day = task.time.day if task.time else (self._today or date.today())
            next_day = base_day + timedelta(days=task.recurrence)
            task.time = TaskTime(next_day)
            print(f"Done {before_display}.")
            print(f"Rescheduled for {task.time}.")
            return True, task.parent_id

        parent_id = task.parent_id
        if task.is_subtask() and parent_id in self.tasks:
            self.tasks[parent_id].children.discard(id)
        del self.tasks[id]
        print(f"Done {task}.")
        return True, parent_id

class App:
    def __init__(self, store_path: Optional[Path] = None, today: Optional[date] = None) -> None:
        resolved_path = Path(store_path) if store_path is not None else DEFAULT_STORE_PATH
        self.data = AppData(resolved_path, today=today)
        self.data.load()

    def cmd_add(self, title: str, parent_id: Optional[int]) -> None:
        task_id = self.data.get_id()
        task = Task(id=task_id, title=title, parent_id=parent_id)
        self.data.tasks[task_id] = task
        if parent_id is not None and parent_id in self.data.tasks:
            self.data.tasks[parent_id].children.add(task_id)
        self.data.save()
        print(f"Added {task}.")

    def cmd_list(self, at: Optional[int]) -> None:
        self.data.list(at)

    def cmd_today(self) -> None:
        self.data.list_today()

    def cmd_clear(self) -> None:
        self.data.clear()
        self.data.save()
        print("Cleared all items.")

    def cmd_do(self, id: int) -> None:
        success, parent_id = self.data.do(id)
        if success:
            self.data.save()
            self.data.list(parent_id)
        # When the operation fails, AppData.do already printed additional context.

    def cmd_move(self, id: int, parent: Optional[int]) -> None:
        if self.data.move(id, parent):
            self.data.save()

    def cmd_settime(self, id: int, time_value: Optional[str]) -> None:
        if self.data.set_time(id, time_value):
            self.data.save()

    def cmd_repeat(self, id: int, interval: Optional[int]) -> None:
        if self.data.set_recurrence(id, interval):
            self.data.save()

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="mdo", description="Simple list manager.")
        subparsers = parser.add_subparsers(dest="command", required=True)

        add_parser = subparsers.add_parser("add", help="Append a string to the list.")
        add_parser.add_argument("text", help="Text to store.")
        add_parser.add_argument("parent", nargs="?", help="parent id", default=None, type=int)
        add_parser.set_defaults(func=lambda args: self.cmd_add(args.text, args.parent))

        clear_parser = subparsers.add_parser("clear", help="Clear all stored items.")
        clear_parser.set_defaults(func=lambda args: self.cmd_clear())

        list_parser = subparsers.add_parser("list", help="Show all stored items.")
        list_parser.add_argument("at", nargs="?", help="list subtasks from id:", default=None, type=int)
        list_parser.set_defaults(func=lambda args: self.cmd_list(args.at))

        today_parser = subparsers.add_parser("today", help="Show tasks due today or overdue.")
        today_parser.set_defaults(func=lambda args: self.cmd_today())

        do_parser = subparsers.add_parser("do", help="do task")
        do_parser.add_argument("id", help="task id to do", type=int)
        do_parser.set_defaults(func=lambda args: self.cmd_do(args.id))

        move_parser = subparsers.add_parser("move", help="Move a task under a new parent (or root).")
        move_parser.add_argument("id", help="task id to move", type=int)
        move_parser.add_argument("parent", nargs="?", help="new parent id (omit for root)", default=None, type=int)
        move_parser.set_defaults(func=lambda args: self.cmd_move(args.id, args.parent))

        settime_parser = subparsers.add_parser("settime", help="Set or clear the due date for a task.")
        settime_parser.add_argument("id", help="task id to update", type=int)
        settime_parser.add_argument(
            "time",
            nargs="?",
            help="date value (YYYY-MM-DD, MM-DD, or DD; omit to clear)",
            default=None,
        )
        settime_parser.set_defaults(func=lambda args: self.cmd_settime(args.id, args.time))
        repeat_parser = subparsers.add_parser("repeat", help="Set or clear recurrence for a task.")
        repeat_parser.add_argument("id", help="task id to update", type=int)
        repeat_parser.add_argument(
            "interval",
            nargs="?",
            type=int,
            help="number of days between occurrences (omit to clear)",
            default=None,
        )
        repeat_parser.set_defaults(func=lambda args: self.cmd_repeat(args.id, args.interval))
        return parser

    def run(self, argv: Optional[List[str]] = None) -> int:
        parser = self.build_parser()
        args = parser.parse_args(argv)
        args.func(args)
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    app = App()
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main())

