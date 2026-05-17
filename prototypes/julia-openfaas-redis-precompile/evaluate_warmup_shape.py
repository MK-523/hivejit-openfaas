#!/usr/bin/env python3
"""Evaluate whether a churn trace has the OpenWhisk-style warmup shape.

This is intentionally separate from the benchmark runner. The runner measures
requests; this script checks the shape the user cares about: long raw latency
decay after churn, not just one cold spike followed by flat steady state.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def pct(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100.0
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append(
                    {
                        "invocation": int(row["invocation"]),
                        "segment": int(row["segment"]),
                        "invocation_in_segment": int(row["invocation_in_segment"]),
                        "churn": row.get("churn") == "1",
                        "status": int(row.get("status") or 0),
                        "http_latency_ms": float(row.get("http_latency_ms") or 0.0),
                        "handler_elapsed_ms": float(row.get("handler_elapsed_ms") or 0.0),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def consecutive_tail_length(rows: list[dict[str, Any]], threshold: float) -> int:
    length = 0
    for row in rows:
        if row["http_latency_ms"] > threshold:
            length += 1
        else:
            break
    return length


def segment_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_segment: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if 200 <= row["status"] < 400:
            by_segment[row["segment"]].append(row)

    metrics = []
    for segment in sorted(by_segment):
        seg_rows = sorted(by_segment[segment], key=lambda row: row["invocation_in_segment"])
        if not seg_rows:
            continue
        latencies = [row["http_latency_ms"] for row in seg_rows]
        tail_window = latencies[-min(30, len(latencies)) :]
        steady = statistics.median(tail_window)
        first = latencies[0]
        peak_first_5 = max(latencies[: min(5, len(latencies))])
        half_threshold = steady + max(0.0, first - steady) / 2.0
        warm_threshold = steady + 10.0

        half_life = None
        warm_life = None
        for row in seg_rows:
            if half_life is None and row["http_latency_ms"] <= half_threshold:
                half_life = row["invocation_in_segment"]
            if warm_life is None and row["http_latency_ms"] <= warm_threshold:
                warm_life = row["invocation_in_segment"]
            if half_life is not None and warm_life is not None:
                break

        metrics.append(
            {
                "segment": segment,
                "churn_invocation": seg_rows[0]["invocation"],
                "requests": len(seg_rows),
                "first_ms": first,
                "peak_first_5_ms": peak_first_5,
                "steady_tail_median_ms": steady,
                "half_life_requests": half_life or len(seg_rows),
                "warm_life_requests": warm_life or len(seg_rows),
                "initial_tail_gt_steady_plus_10_requests": consecutive_tail_length(seg_rows, warm_threshold),
                "peak_to_steady_ratio": peak_first_5 / steady if steady else 0.0,
            }
        )
    return metrics


def summarize(path: Path, label: str) -> dict[str, Any]:
    rows = read_rows(path)
    ok_rows = [row for row in rows if 200 <= row["status"] < 400]
    latencies = [row["http_latency_ms"] for row in ok_rows]
    segs = segment_metrics(rows)
    tail_lengths = [seg["initial_tail_gt_steady_plus_10_requests"] for seg in segs]
    half_lives = [seg["half_life_requests"] for seg in segs]
    ratios = [seg["peak_to_steady_ratio"] for seg in segs]

    trace_scale_openwhisk_level = len(rows) >= 1000 and len(segs) >= 6
    median_tail = statistics.median(tail_lengths) if tail_lengths else 0.0
    median_half_life = statistics.median(half_lives) if half_lives else 0.0
    median_ratio = statistics.median(ratios) if ratios else 0.0
    warmup_decay_present = median_tail >= 20 and median_ratio >= 2.0

    return {
        "label": label,
        "csv": str(path),
        "requests": len(rows),
        "ok": len(ok_rows),
        "churn_points": [seg["churn_invocation"] for seg in segs],
        "segments": len(segs),
        "http_latency_ms": {
            "p50": pct(latencies, 50),
            "p95": pct(latencies, 95),
            "p99": pct(latencies, 99),
            "max": max(latencies) if latencies else 0.0,
        },
        "shape": {
            "median_initial_tail_requests": median_tail,
            "median_half_life_requests": median_half_life,
            "median_peak_to_steady_ratio": median_ratio,
            "trace_scale_openwhisk_level": trace_scale_openwhisk_level,
            "warmup_decay_present": warmup_decay_present,
            "openwhisk_level": trace_scale_openwhisk_level and warmup_decay_present,
        },
        "segment_metrics": segs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", nargs="+", required=True, type=Path)
    parser.add_argument("--labels", nargs="*", default=None)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    labels = args.labels or [path.stem for path in args.csv]
    if len(labels) != len(args.csv):
        raise SystemExit("--labels must match --csv count")

    summaries = [summarize(path, label) for path, label in zip(args.csv, labels)]

    by_label = {item["label"]: item for item in summaries}
    comparisons: dict[str, Any] = {}
    baseline = by_label.get("baseline")
    if baseline:
        base_p95 = baseline["http_latency_ms"]["p95"]
        base_tail = baseline["shape"]["median_initial_tail_requests"]
        for label, item in by_label.items():
            if label == "baseline":
                continue
            comparisons[f"{label}_vs_baseline"] = {
                "p95_ratio": item["http_latency_ms"]["p95"] / base_p95 if base_p95 else 0.0,
                "tail_ratio": item["shape"]["median_initial_tail_requests"] / base_tail if base_tail else 0.0,
            }

    result = {"series": summaries, "comparisons": comparisons}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
