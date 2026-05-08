#!/usr/bin/env python3
"""Rank profile export overhead buckets from CSV or JSONL instrumentation logs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any


DEFAULT_BUCKETS = [
    "safepoint_entry_ms",
    "enumerate_classes_ms",
    "enumerate_methods_ms",
    "find_method_data_ms",
    "serialize_counters_ms",
    "serialize_type_profiles_ms",
    "bytecode_hash_ms",
    "symbolize_ms",
    "compress_ms",
    "write_ms",
    "upload_ms",
]


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return data["records"]
        return [data]
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((p / 100.0) * len(ordered))
    return ordered[min(index, len(ordered) - 1)]


def discover_buckets(rows: list[dict[str, Any]]) -> list[str]:
    keys = set(DEFAULT_BUCKETS)
    for row in rows:
        keys.update(key for key in row if key.endswith("_ms") and key != "total_export_ms")
    return sorted(keys)


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, float | int | str]]:
    buckets = discover_buckets(rows)
    totals = [value for row in rows if (value := as_float(row.get("total_export_ms"))) is not None]
    total_mean = statistics.fmean(totals) if totals else 0.0
    summaries: list[dict[str, float | int | str]] = []

    for bucket in buckets:
        values = [value for row in rows if (value := as_float(row.get(bucket))) is not None]
        if not values:
            continue
        mean = statistics.fmean(values)
        summaries.append(
            {
                "bucket": bucket,
                "count": len(values),
                "mean_ms": mean,
                "p50_ms": percentile(values, 50),
                "p95_ms": percentile(values, 95),
                "max_ms": max(values),
                "mean_pct_total": (mean / total_mean * 100.0) if total_mean > 0 else 0.0,
            }
        )

    summaries.sort(key=lambda item: float(item["mean_ms"]), reverse=True)
    return summaries


def print_markdown(summaries: list[dict[str, float | int | str]]) -> None:
    print("| bucket | count | mean ms | p50 ms | p95 ms | max ms | mean % total |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for item in summaries:
        print(
            f"| {item['bucket']} | {item['count']} | "
            f"{float(item['mean_ms']):.3f} | {float(item['p50_ms']):.3f} | "
            f"{float(item['p95_ms']):.3f} | {float(item['max_ms']):.3f} | "
            f"{float(item['mean_pct_total']):.1f}% |"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="CSV, JSON, or JSONL export timing log")
    args = parser.parse_args()

    rows = load_rows(Path(args.path))
    if not rows:
        raise SystemExit("no rows found")

    print_markdown(summarize(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
