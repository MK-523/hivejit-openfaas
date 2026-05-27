#!/usr/bin/env python3
"""Render a distinct real-data Flax cache result figure."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def read_rows(path: Path, scenario: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["scenario"] == scenario]
    for row in rows:
        row["iteration"] = int(row["iteration"])
        for field in (
            "lower_ms",
            "compile_or_load_ms",
            "first_execute_ms",
            "artifact_import_ms",
            "startup_plus_first_request_ms",
        ):
            row[field] = float(row[field])
    return sorted(rows, key=lambda row: row["iteration"])


def warm_curve(rows: list[dict[str, Any]]) -> list[float]:
    values = [rows[0]["startup_plus_first_request_ms"] / 1000.0]
    values.extend(row["first_execute_ms"] / 1000.0 for row in rows[1:10])
    return values


def render(results_dir: Path, scenario: str, out: Path) -> None:
    baseline = read_rows(results_dir / "baseline.csv", scenario)
    cache = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)
    if len(baseline) < 10 or len(cache) < 10:
        raise ValueError(f"expected 10 rows for {scenario} in {results_dir}")

    x = list(range(1, 11))
    baseline_curve = warm_curve(baseline)
    cache_curve = warm_curve(cache)

    base_first = baseline[0]
    cache_first = cache[0]
    base_total = base_first["lower_ms"] + base_first["compile_or_load_ms"] + base_first["first_execute_ms"]
    cache_total = cache_first["lower_ms"] + cache_first["compile_or_load_ms"] + cache_first["first_execute_ms"]

    baseline_p50 = statistics.median(row["startup_plus_first_request_ms"] for row in baseline)
    cache_p50 = statistics.median(row["startup_plus_first_request_ms"] for row in cache)
    compile_p50 = statistics.median(row["compile_or_load_ms"] for row in baseline)
    cache_compile_p50 = statistics.median(row["compile_or_load_ms"] for row in cache)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": "#04152d",
            "axes.facecolor": "#082344",
            "savefig.facecolor": "#04152d",
            "text.color": "#edf6ff",
            "axes.labelcolor": "#cfe2f5",
            "xtick.color": "#9fb9d3",
            "ytick.color": "#9fb9d3",
            "axes.edgecolor": "#2b5f93",
            "grid.color": "#1e4b77",
        }
    )

    fig = plt.figure(figsize=(15.2, 6.5), dpi=180)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.25, 1.0], wspace=0.25)
    ax = fig.add_subplot(gs[0, 0])
    phase_ax = fig.add_subplot(gs[0, 1])

    ax.plot(
        x,
        baseline_curve,
        color="#7ec8ff",
        marker="o",
        linewidth=2.7,
        markersize=6,
        label="Baseline cold JIT",
    )
    ax.plot(
        x,
        cache_curve,
        color="#ffb86b",
        marker="s",
        linewidth=2.7,
        markersize=5.8,
        linestyle="--",
        label="Persistent cache hit",
    )
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xlabel("Invocation")
    ax.set_ylabel("Latency (seconds, log scale)")
    ax.set_title("Real Flax/MNIST Cold Start with JAX Persistent Cache", fontsize=15, pad=14)
    ax.grid(True, which="both", linewidth=0.8)
    ax.legend(loc="upper right", frameon=True, facecolor="#0a2a50", edgecolor="#3b76ad", labelcolor="#edf6ff")
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda value, _pos: f"{value:.2f}s" if value >= 0.1 else f"{value * 1000:.0f}ms")
    )

    ax.text(
        0.015,
        0.07,
        f"First-request p50: {baseline_p50:.0f}ms -> {cache_p50:.0f}ms\n"
        f"Compile/load p50: {compile_p50:.0f}ms -> {cache_compile_p50:.1f}ms",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.5,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#0a2a50", "edgecolor": "#3b76ad", "alpha": 0.95},
    )

    phases = [
        ("Trace/lower", "lower_ms", "#7ec8ff"),
        ("Compile/load", "compile_or_load_ms", "#ffb86b"),
        ("Execute", "first_execute_ms", "#90e0a6"),
    ]
    labels = ["Baseline\n(no cache)", "Cache hit\n(persistent)"]
    rows = [base_first, cache_first]
    totals = [base_total, cache_total]
    positions = [0, 1]
    min_visible_ms = 18.0
    bottoms = [0.0, 0.0]
    for phase_label, key, color in phases:
        values = [row[key] for row in rows]
        display_values = [value if value >= min_visible_ms else min_visible_ms for value in values]
        phase_ax.bar(
            positions,
            display_values,
            bottom=bottoms,
            width=0.58,
            color=color,
            edgecolor="#082344",
            linewidth=1.2,
            label=phase_label,
        )
        for pos, bottom, actual, shown in zip(positions, bottoms, values, display_values):
            label = f"{actual:.1f}" if actual < 10 else f"{actual:.0f}"
            phase_ax.text(
                pos,
                bottom + shown / 2,
                label,
                ha="center",
                va="center",
                fontsize=9.2,
                color="#061427",
                fontweight="bold",
            )
        bottoms = [bottom + value for bottom, value in zip(bottoms, display_values)]

    phase_ax.set_title("Iteration 1 Phase Breakdown", fontsize=13, pad=14)
    phase_ax.set_ylabel("Milliseconds")
    phase_ax.set_xticks(positions, labels)
    phase_ax.set_ylim(0, max(bottoms) * 1.25)
    phase_ax.grid(True, axis="y", linewidth=0.8)
    phase_ax.legend(
        loc="upper right",
        frameon=True,
        facecolor="#0a2a50",
        edgecolor="#3b76ad",
        labelcolor="#edf6ff",
        fontsize=8.8,
    )
    for pos, total, shown_total in zip(positions, totals, bottoms):
        phase_ax.text(
            pos,
            shown_total + max(bottoms) * 0.035,
            f"{total:.0f}ms",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    phase_ax.set_facecolor("#082344")

    fig.text(
        0.5,
        0.02,
        "Real MNIST training images, Flax Linen CNN train_step, CPU backend. "
        "Point 1 includes lower/compile/execute; later points are hot execution.",
        ha="center",
        va="bottom",
        fontsize=9.3,
        color="#9fb9d3",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--scenario", default="flax-mnist-cnn-train-real")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render(args.results_dir, args.scenario, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
