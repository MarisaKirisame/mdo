from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional, Tuple

WEEKDAY_MAP = {
    "monday": 0,
    "mon": 0,
    "mo": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "tu": 1,
    "wednesday": 2,
    "wed": 2,
    "we": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "th": 3,
    "friday": 4,
    "fri": 4,
    "fr": 4,
    "saturday": 5,
    "sat": 5,
    "sa": 5,
    "sunday": 6,
    "sun": 6,
    "su": 6,
}


@dataclass(frozen=True)
class TaskTime:
    day: date

    def to_json(self) -> Any:
        return self.day.isoformat()

    @staticmethod
    def from_json(raw: Any) -> "TaskTime":
        if isinstance(raw, TaskTime):
            return raw
        if isinstance(raw, str):
            return TaskTime(date.fromisoformat(raw))
        if isinstance(raw, dict) and "value" in raw:
            return TaskTime(date.fromisoformat(str(raw["value"])))
        raise TypeError("Unsupported time payload in store.")

    def __str__(self) -> str:
        return self.day.isoformat()


def parse_time_input(raw: str, today: date) -> Tuple[Optional[TaskTime], Optional[int]]:
        value = raw.strip()
        if not value:
            return None, None
        lowered = value.lower()

        if lowered in {"daily", "everyday", "every day"}:
            return TaskTime(today), 1

        if lowered == "today":
            return TaskTime(today), None

        if lowered == "tomorrow":
            return TaskTime(today + timedelta(days=1)), None

        if lowered.startswith("in "):
            remainder = lowered[3:].strip()
            if remainder.endswith(" days"):
                remainder = remainder[:-5].strip()
            elif remainder.endswith(" day"):
                remainder = remainder[:-4].strip()
            try:
                offset = int(remainder)
            except ValueError:
                return None, None
            if offset < 0:
                return None, None
            return TaskTime(today + timedelta(days=offset)), None

        if lowered.startswith("every "):
            remainder = lowered[6:].strip()
            if remainder in {"day", "daily", "day(s)"}:
                return TaskTime(today), 1
            weekday = _match_weekday(remainder)
            if weekday is not None:
                return TaskTime(_next_weekday(today, weekday)), 7
            if remainder.endswith(" days") or remainder.endswith(" day"):
                number = remainder.split()[0]
                try:
                    interval = int(number)
                except ValueError:
                    interval = None
                if interval is not None and interval > 0:
                    return TaskTime(today + timedelta(days=interval)), interval
            return None, None

        weekday = _match_weekday(lowered)
        if weekday is not None:
            return TaskTime(_next_weekday(today, weekday)), None

        try:
            return TaskTime(date.fromisoformat(value)), None
        except ValueError:
            pass

        if "-" in value:
            parts = value.split("-")
            if len(parts) == 2 and all(part.isdigit() for part in parts):
                month = int(parts[0])
                day = int(parts[1])
                try:
                    return TaskTime(date(today.year, month, day)), None
                except ValueError:
                    return None, None

        if value.isdigit():
            day = int(value)
            try:
                return TaskTime(date(today.year, today.month, day)), None
            except ValueError:
                return None, None

        return None, None


def _match_weekday(text: str) -> Optional[int]:
    return WEEKDAY_MAP.get(text.strip().lower())


def _next_weekday(current: date, target_weekday: int) -> date:
    current_weekday = current.weekday()
    delta = (target_weekday - current_weekday) % 7
    if delta <= 0:
        delta += 7
    return current + timedelta(days=delta)

__all__ = ["TaskTime", "parse_time_input"]