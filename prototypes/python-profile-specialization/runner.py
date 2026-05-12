#!/usr/bin/env python3
"""Run cold process invocations for the Python specialization prototype."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handler", type=Path, default=Path(__file__).with_name("handler.py"))
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--requests", type=int, required=True)
    parser.add_argument("--iterations", type=int, default=16)
    parser.add_argument("--label", required=True)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "label",
                "benchmark",
                "iteration",
                "wall_ms",
                "work_ms",
                "checksum",
                "used_artifact",
            ],
        )
        writer.writeheader()
        for iteration in range(1, args.iterations + 1):
            cmd = [
                sys.executable,
                str(args.handler),
                "--benchmark",
                args.benchmark,
                "--requests",
                str(args.requests),
                "--seed",
                str(iteration),
                "--json",
            ]
            if args.artifact:
                cmd.extend(["--artifact", str(args.artifact)])
            start = time.perf_counter()
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
            wall_ms = (time.perf_counter() - start) * 1000.0
            data = json.loads(completed.stdout)
            writer.writerow(
                {
                    "label": args.label,
                    "benchmark": args.benchmark,
                    "iteration": iteration,
                    "wall_ms": f"{wall_ms:.6f}",
                    "work_ms": f"{float(data['workMs']):.6f}",
                    "checksum": data["checksum"],
                    "used_artifact": str(bool(data["usedArtifact"])).lower(),
                }
            )
            print(
                f"{args.label} {args.benchmark} iteration={iteration} "
                f"wall_ms={wall_ms:.3f} work_ms={float(data['workMs']):.3f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
