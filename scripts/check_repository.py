#!/usr/bin/env python3
"""Dependency-free structural checks for the research workspace."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


IGNORED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "obj",
    "profiles",
    "results",
}


@dataclass(frozen=True)
class CheckResult:
    python_files: int
    shell_files: int
    json_files: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def is_source(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return not any(part in IGNORED_PARTS or part.startswith("results-") for part in relative.parts)


def source_files(root: Path, suffix: str) -> list[Path]:
    return sorted(path for path in root.rglob(f"*{suffix}") if path.is_file() and is_source(path, root))


def run_checks(root: Path) -> CheckResult:
    errors: list[str] = []
    python_files = source_files(root, ".py")
    shell_files = source_files(root, ".sh")
    json_files = source_files(root, ".json")

    for path in python_files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"python:{path.relative_to(root)}:{exc}")

    for path in shell_files:
        completed = subprocess.run(
            ["bash", "-n", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or f"exit {completed.returncode}"
            errors.append(f"shell:{path.relative_to(root)}:{detail}")

    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"json:{path.relative_to(root)}:{exc}")

    required = (
        root / "README.md",
        root / "scripts" / "run_profile_cache_matrix.py",
        root / "docs" / "research-map.md",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"required:{path.relative_to(root)}:missing")

    return CheckResult(
        python_files=len(python_files),
        shell_files=len(shell_files),
        json_files=len(json_files),
        errors=tuple(errors),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()

    result = run_checks(args.root.resolve())
    payload = {**asdict(result), "ok": result.ok}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"checked {result.python_files} Python, {result.shell_files} shell, "
            f"and {result.json_files} JSON files"
        )
        for error in result.errors:
            print(error, file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
