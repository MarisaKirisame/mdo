
#!/usr/bin/env python
from __future__ import annotations

import argparse
import shlex
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

# Ensure the project root is importable when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mdo import App

FIXED_TODAY = date(2025, 4, 20)


@dataclass
class GoldenCase:
    name: str
    input_path: Path
    output_path: Path

    def load_commands(self) -> List[List[str]]:
        text = self.input_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        commands: List[List[str]] = []
        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            commands.append(shlex.split(raw_line, posix=True))
        if not commands:
            commands.append([])
        return commands

    def load_expected_output(self) -> str:
        return self.output_path.read_text(encoding="utf-8").strip()

class GoldenRunner:
    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    def discover(self) -> List[GoldenCase]:
        cases = []
        for input_path in sorted(self.fixtures_dir.glob("*.in.txt")):
            base = input_path.stem[:-3] if input_path.stem.endswith(".in") else input_path.stem
            output_path = self.fixtures_dir / f"{base}.out.txt"
            if output_path.exists():
                cases.append(GoldenCase(name=base, input_path=input_path, output_path=output_path))
        return cases

    def run_all(self, store_dir: Path) -> int:
        failures = 0
        for case in self.discover():
            output = capture_output(case, store_dir)
            expected = case.load_expected_output()
            if output.strip() != expected:
                failures += 1
                print(f"CASE {case.name} FAILED")
                print("--- expected")
                print(expected)
                print("--- got")
                print(output.strip())
                print("======")
        return failures


def capture_output(case: GoldenCase, store_dir: Path) -> str:
    store_file = store_dir / f"{case.name}.json"
    if store_file.exists():
        store_file.unlink()
    commands = case.load_commands()
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    try:
        from io import StringIO

        buffer = StringIO()
        sys.stdout = buffer
        sys.stderr = buffer
        for args in commands:
            app = App(store_path=store_file, today=FIXED_TODAY)
            try:
                app.run(args)
            except SystemExit:
                pass
        return buffer.getvalue()
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run golden CLI cases")
    default_fixtures = Path(__file__).resolve().parent / "fixtures" / "time"
    parser.add_argument("fixtures", nargs="?", default=default_fixtures, type=Path)
    parser.add_argument("--store", default=Path.cwd() / ".golden-store", type=Path)
    args = parser.parse_args(argv)
    runner = GoldenRunner(args.fixtures)
    args.store.mkdir(parents=True, exist_ok=True)
    failures = runner.run_all(args.store)
    if failures:
        print(f"{failures} case(s) failed")
        return 1
    print("all golden cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
