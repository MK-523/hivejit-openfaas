#!/usr/bin/env python3
"""Serverless-style Python handler with profile-guided specialization support."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import time
from pathlib import Path
from types import ModuleType
from typing import Callable


MASK = (1 << 64) - 1

LUSEARCH_ROUTES = [
    {"name": "term", "threshold": 78, "rounds": 7, "salt": 0x9E3779B97F4A7C15},
    {"name": "phrase", "threshold": 91, "rounds": 11, "salt": 0xC2B2AE3D27D4EB4F},
    {"name": "wildcard", "threshold": 97, "rounds": 13, "salt": 0x165667B19E3779F9},
    {"name": "rank", "threshold": 100, "rounds": 17, "salt": 0x85EBCA77C2B2AE63},
]

H2_ROUTES = [
    {"name": "index_probe", "threshold": 70, "rounds": 6, "salt": 0xD6E8FEB86659FD93},
    {"name": "range_scan", "threshold": 88, "rounds": 10, "salt": 0xA5A3564E27F8866F},
    {"name": "join", "threshold": 97, "rounds": 14, "salt": 0x27D4EB2F165667C5},
    {"name": "aggregate", "threshold": 100, "rounds": 16, "salt": 0x94D049BB133111EB},
]

ECLIPSE_ROUTES = [
    {"name": "parse_unit", "threshold": 58, "rounds": 8, "salt": 0xBF58476D1CE4E5B9},
    {"name": "resolve_symbols", "threshold": 80, "rounds": 12, "salt": 0x94D049BB133111EB},
    {"name": "index_workspace", "threshold": 94, "rounds": 15, "salt": 0xD6E8FEB86659FD93},
    {"name": "refactor_plan", "threshold": 100, "rounds": 18, "salt": 0xA5A3564E27F8866F},
]

ROUTES = {
    "dacapo-lusearch": LUSEARCH_ROUTES,
    "dacapo-h2": H2_ROUTES,
    "dacapo-eclipse": ECLIPSE_ROUTES,
}


def mix64(value: int) -> int:
    value &= MASK
    value ^= value >> 33
    value = (value * 0xFF51AFD7ED558CCD) & MASK
    value ^= value >> 33
    value = (value * 0xC4CEB9FE1A85EC53) & MASK
    value ^= value >> 33
    return value & MASK


def choose_route(routes: list[dict[str, int | str]], index: int, state: int) -> dict[str, int | str]:
    ticket = mix64(index ^ state) % 100
    for route in routes:
        if ticket < int(route["threshold"]):
            return route
    return routes[-1]


def normalize_route(benchmark: str, route: dict[str, int | str]) -> dict[str, object]:
    """Normalize a dynamic route/query config as a generic framework would."""
    route_name = str(route["name"])
    normalized: dict[str, object] = {
        "name": route_name,
        "threshold": int(str(route["threshold"])),
        "rounds": int(str(route["rounds"])),
        "salt": int(str(route["salt"])),
    }
    if benchmark == "dacapo-lusearch":
        operations: dict[str, tuple[str, str, str]] = {
            "term": ("tokenize", "score", "rank"),
            "phrase": ("tokenize", "window", "score"),
            "wildcard": ("expand", "tokenize", "rank"),
            "rank": ("score", "boost", "rank"),
        }
        normalized["operations"] = tuple(str(step) for step in operations[route_name])
    elif benchmark == "dacapo-h2":
        query_plan: dict[str, tuple[tuple[str, int], ...]] = {
            "index_probe": (("eq_region", 2), ("amount_gt", 120)),
            "range_scan": (("amount_gt", 260), ("account_lt", 20)),
            "join": (("eq_region", 3), ("join_account", 7)),
            "aggregate": (("amount_gt", 80), ("group_region", 5)),
        }
        normalized["predicates"] = tuple((str(op), int(operand)) for op, operand in query_plan[route_name])
    elif benchmark == "dacapo-eclipse":
        phase_ops: dict[str, tuple[str, ...]] = {
            "parse_unit": ("scan", "parse", "fold"),
            "resolve_symbols": ("scan", "resolve", "fold"),
            "index_workspace": ("scan", "index", "resolve", "fold"),
            "refactor_plan": ("scan", "resolve", "rewrite", "fold"),
        }
        normalized["phases"] = tuple(str(phase) for phase in phase_ops[route_name])
    else:
        raise ValueError(f"unknown benchmark {benchmark}")
    return normalized


def interpreted_lusearch(route: dict[str, int | str], state: int, index: int) -> int:
    route_name = str(route["name"])
    rounds = int(route["rounds"])
    salt = int(route["salt"])
    acc = state ^ ((index + 1) * salt)

    # Intentionally generic: each operation goes through the same interpreter
    # shape so the generated artifact has real dispatch and constant work to remove.
    operations = route.get("operations")
    if not operations:
        operations = {
            "term": ("tokenize", "score", "rank"),
            "phrase": ("tokenize", "window", "score"),
            "wildcard": ("expand", "tokenize", "rank"),
            "rank": ("score", "boost", "rank"),
        }[route_name]
    for step in operations:
        for round_index in range(rounds):
            probe = mix64(acc + salt + round_index + (index << 1))
            if step == "tokenize":
                acc ^= (probe >> 7) | (probe << 3)
            elif step == "window":
                acc = (acc + ((probe & 0xFFFF) * 17)) & MASK
            elif step == "expand":
                acc ^= mix64(probe ^ 0xABC98388FB8FAC03)
            elif step == "boost":
                acc = (acc * 3 + (probe & 0xFFF)) & MASK
            else:
                acc = (acc + mix64(probe ^ acc)) & MASK
    return acc & MASK


def interpreted_h2(route: dict[str, int | str], state: int, index: int) -> int:
    route_name = str(route["name"])
    rounds = int(route["rounds"])
    salt = int(route["salt"])
    rows = [
        {"account": (index + i) & 31, "region": i % 5, "amount": ((state >> (i % 11)) + i * 17) & 0x3FF}
        for i in range(24)
    ]
    predicates = route.get("predicates")
    if not predicates:
        predicates = {
            "index_probe": (("eq_region", 2), ("amount_gt", 120)),
            "range_scan": (("amount_gt", 260), ("account_lt", 20)),
            "join": (("eq_region", 3), ("join_account", 7)),
            "aggregate": (("amount_gt", 80), ("group_region", 5)),
        }[route_name]
    acc = state ^ salt
    for row in rows:
        amount = int(row["amount"])
        account = int(row["account"])
        region = int(row["region"])
        matched = True
        for op, operand in predicates:
            if op == "eq_region":
                matched = matched and region == operand
            elif op == "amount_gt":
                matched = matched and amount > operand
            elif op == "account_lt":
                matched = matched and account < operand
            elif op == "join_account":
                matched = matched and ((account ^ operand) & 7) == (index & 7)
            elif op == "group_region":
                matched = matched and ((region + operand + index) % 3) == 0
            else:
                matched = matched and True
            if not matched:
                break
        if matched:
            for round_index in range(rounds):
                acc ^= mix64(amount + account * 131 + region * 17 + salt + round_index)
                acc = ((acc << 5) | (acc >> 59)) & MASK
    return acc & MASK


def interpreted_eclipse(route: dict[str, int | str], state: int, index: int) -> int:
    route_name = str(route["name"])
    rounds = int(route["rounds"])
    salt = int(route["salt"])
    phases = route.get("phases")
    if not phases:
        phases = {
            "parse_unit": ("scan", "parse", "fold"),
            "resolve_symbols": ("scan", "resolve", "fold"),
            "index_workspace": ("scan", "index", "resolve", "fold"),
            "refactor_plan": ("scan", "resolve", "rewrite", "fold"),
        }[route_name]
    acc = state ^ salt ^ index
    for phase in phases:
        for round_index in range(rounds):
            value = mix64(acc + salt + round_index * 0x100000001B3)
            if phase == "scan":
                acc = (acc + (value & 0xFFFF)) & MASK
            elif phase == "parse":
                acc ^= (value << 11) & MASK
            elif phase == "resolve":
                acc = (acc ^ (value >> 9) ^ mix64(index + round_index)) & MASK
            elif phase == "index":
                acc = (acc * 5 + (value & 0x7FFF)) & MASK
            elif phase == "rewrite":
                acc ^= mix64(value ^ 0xD1B54A32D192ED03)
            else:
                acc = (acc + mix64(value ^ acc)) & MASK
    return acc & MASK


INTERPRETERS: dict[str, Callable[[dict[str, int | str], int, int], int]] = {
    "dacapo-lusearch": interpreted_lusearch,
    "dacapo-h2": interpreted_h2,
    "dacapo-eclipse": interpreted_eclipse,
}


def run_generic(benchmark: str, requests: int, seed: int) -> tuple[int, dict[str, int]]:
    routes = ROUTES[benchmark]
    interpret = INTERPRETERS[benchmark]
    counts = {str(route["name"]): 0 for route in routes}
    state = (0x123456789ABCDEF0 ^ seed) & MASK
    for index in range(requests):
        route = choose_route(routes, index, state)
        route_name = str(route["name"])
        counts[route_name] += 1
        route = normalize_route(benchmark, route)
        state ^= interpret(route, state, index)
        state &= MASK
    return state, counts


def load_artifact(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("python_profile_specialized_artifact", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load specialization artifact: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_profile(path: Path, benchmark: str, requests: int, seed: int, checksum: int, route_counts: dict[str, int]) -> None:
    total = sum(route_counts.values()) or 1
    profile = {
        "schema": "python-profile-specialization.v1",
        "benchmark": benchmark,
        "requests": requests,
        "seed": seed,
        "checksum": checksum,
        "runtime": platform.python_version(),
        "generatedAtUnix": time.time(),
        "routeCounts": route_counts,
        "routeFractions": {route: count / total for route, count in route_counts.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=sorted(ROUTES), default="dacapo-lusearch")
    parser.add_argument("--requests", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--profile-out", type=Path)
    parser.add_argument("--artifact", type=Path, help="generated specialization module to import")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.requests <= 0:
        raise SystemExit("--requests must be positive")

    start = time.perf_counter()
    used_artifact = False
    route_counts: dict[str, int] = {}
    if args.artifact:
        artifact = load_artifact(args.artifact)
        artifact_benchmark = getattr(artifact, "BENCHMARK", None)
        if artifact_benchmark != args.benchmark:
            raise SystemExit(f"artifact benchmark {artifact_benchmark!r} does not match {args.benchmark!r}")
        checksum = int(artifact.run(args.requests, args.seed))
        used_artifact = True
    else:
        checksum, route_counts = run_generic(args.benchmark, args.requests, args.seed)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    if args.profile_out:
        if used_artifact:
            checksum_for_profile, route_counts = run_generic(args.benchmark, args.requests, args.seed)
            if checksum_for_profile != checksum:
                raise SystemExit("specialized checksum differs from generic checksum during profile export")
        write_profile(args.profile_out, args.benchmark, args.requests, args.seed, checksum, route_counts)

    result = {
        "domain": "python-profile-specialization",
        "benchmark": args.benchmark,
        "requests": args.requests,
        "seed": args.seed,
        "usedArtifact": used_artifact,
        "workMs": elapsed_ms,
        "checksum": checksum,
    }
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        mode = "specialized" if used_artifact else "generic"
        print(f"{mode} benchmark={args.benchmark} requests={args.requests} work_ms={elapsed_ms:.3f} checksum={checksum}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
