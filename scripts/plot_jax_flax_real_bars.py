#!/usr/bin/env python3
"""Render bar-chart comparisons for the real-data Flax cache result."""

from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_rows(path: Path, scenario: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["scenario"] == scenario]
    for row in rows:
        for field in (
            "lower_ms",
            "compile_or_load_ms",
            "first_execute_ms",
            "startup_plus_first_request_ms",
        ):
            row[field] = float(row[field])
    return rows


def median(rows: list[dict[str, Any]], field: str) -> float:
    return statistics.median(row[field] for row in rows)


def render(results_dir: Path, scenario: str, out: Path) -> None:
    baseline = read_rows(results_dir / "baseline.csv", scenario)
    cache = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)
    if not baseline or not cache:
        raise ValueError(f"missing rows for {scenario} in {results_dir}")

    base_first = baseline[0]
    cache_first = cache[0]
    base_first_total = base_first["lower_ms"] + base_first["compile_or_load_ms"] + base_first["first_execute_ms"]
    cache_first_total = cache_first["lower_ms"] + cache_first["compile_or_load_ms"] + cache_first["first_execute_ms"]

    categories = [
        ("First request\np50", "startup_plus_first_request_ms"),
        ("Trace/lower\np50", "lower_ms"),
        ("Compile/load\np50", "compile_or_load_ms"),
        ("Execute\np50", "first_execute_ms"),
    ]
    baseline_values = [median(baseline, field) for _label, field in categories]
    cache_values = [median(cache, field) for _label, field in categories]

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

    fig = plt.figure(figsize=(15.4, 6.4), dpi=180)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1.0], wspace=0.24)
    cmp_ax = fig.add_subplot(gs[0, 0])
    phase_ax = fig.add_subplot(gs[0, 1])

    x = list(range(len(categories)))
    width = 0.34
    baseline_color = "#7ec8ff"
    cache_color = "#ffb86b"
    cmp_ax.bar([i - width / 2 for i in x], baseline_values, width=width, color=baseline_color, label="Baseline JIT")
    cmp_ax.bar([i + width / 2 for i in x], cache_values, width=width, color=cache_color, label="Persistent cache hit")

    for i, value in enumerate(baseline_values):
        cmp_ax.text(i - width / 2, value + 13, f"{value:.0f}", ha="center", va="bottom", fontsize=9.5, fontweight="bold")
    for i, value in enumerate(cache_values):
        label = f"{value:.1f}" if value < 10 else f"{value:.0f}"
        cmp_ax.text(i + width / 2, value + 13, label, ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    cmp_ax.set_title("Median Cold-Start Component Comparison", fontsize=14, pad=14)
    cmp_ax.set_ylabel("Milliseconds")
    cmp_ax.set_xticks(x, [label for label, _field in categories])
    cmp_ax.set_ylim(0, max(max(baseline_values), max(cache_values)) * 1.28)
    cmp_ax.grid(True, axis="y", linewidth=0.8)
    cmp_ax.legend(loc="upper right", frameon=True, facecolor="#0a2a50", edgecolor="#3b76ad", labelcolor="#edf6ff")

    cmp_ax.text(
        0.02,
        0.94,
        f"compile/load p50: {baseline_values[2]:.0f}ms -> {cache_values[2]:.1f}ms\n"
        f"first request p50: {baseline_values[0]:.0f}ms -> {cache_values[0]:.0f}ms",
        transform=cmp_ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#0a2a50", "edgecolor": "#3b76ad", "alpha": 0.95},
    )

    phases = [
        ("Trace/lower", "lower_ms", "#7ec8ff"),
        ("Compile/load", "compile_or_load_ms", "#ffb86b"),
        ("Execute", "first_execute_ms", "#90e0a6"),
    ]
    positions = [0, 1]
    labels = ["Baseline\n(no cache)", "Cache hit\n(persistent)"]
    rows = [base_first, cache_first]
    totals = [base_first_total, cache_first_total]
    min_visible_ms = 18.0
    bottoms = [0.0, 0.0]
    for phase_label, field, color in phases:
        actual_values = [row[field] for row in rows]
        display_values = [value if value >= min_visible_ms else min_visible_ms for value in actual_values]
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
        for pos, bottom, actual, shown in zip(positions, bottoms, actual_values, display_values):
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
        bottoms = [bottom + shown for bottom, shown in zip(bottoms, display_values)]

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

    phase_ax.set_title("Iteration 1 Phase Breakdown", fontsize=14, pad=14)
    phase_ax.set_ylabel("Milliseconds")
    phase_ax.set_xticks(positions, labels)
    phase_ax.set_ylim(0, max(bottoms) * 1.25)
    phase_ax.grid(True, axis="y", linewidth=0.8)
    phase_ax.legend(loc="upper right", frameon=True, facecolor="#0a2a50", edgecolor="#3b76ad", labelcolor="#edf6ff")

    fig.suptitle("Real Flax/MNIST Persistent Compilation Cache Results", fontsize=16, y=0.98)
    fig.text(
        0.5,
        0.02,
        "Real MNIST training images, Flax Linen CNN train_step, CPU backend. Values are measured from fresh Python processes.",
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
