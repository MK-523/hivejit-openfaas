#!/usr/bin/env python3
"""Render a Discord-style JAX persistent-cache figure."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def read_rows(path: Path, scenario: str) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["scenario"] != scenario:
                continue
            rows.append(
                {
                    "iteration": int(row["iteration"]),
                    "lower_ms": float(row["lower_ms"]),
                    "compile_or_load_ms": float(row["compile_or_load_ms"]),
                    "first_execute_ms": float(row["first_execute_ms"]),
                    "artifact_import_ms": float(row["artifact_import_ms"]),
                    "total_ms": float(row["startup_plus_first_request_ms"]),
                }
            )
    return sorted(rows, key=lambda row: int(row["iteration"]))


def ms_label(value: float) -> str:
    return f"{value:.0f}ms"


def render(results_dir: Path, scenario: str, out: Path) -> None:
    baseline = read_rows(results_dir / "baseline.csv", scenario)
    cache = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)
    if not baseline or not cache:
        raise ValueError(f"missing baseline/cache rows for scenario {scenario!r} in {results_dir}")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.facecolor": "#191c26",
            "figure.facecolor": "#0f1118",
            "savefig.facecolor": "#0f1118",
            "text.color": "#e8eaf0",
            "axes.labelcolor": "#d1d5db",
            "xtick.color": "#aeb4c0",
            "ytick.color": "#aeb4c0",
            "axes.edgecolor": "#3a4050",
            "grid.color": "#2c3240",
        }
    )

    fig = plt.figure(figsize=(18, 7.2), dpi=160)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.25, 0.95], wspace=0.22)
    ax = fig.add_subplot(gs[0, 0])
    bar_ax = fig.add_subplot(gs[0, 1])

    x = [int(row["iteration"]) for row in baseline]
    baseline_total = [float(row["total_ms"]) / 1000.0 for row in baseline]
    cache_total = [float(row["total_ms"]) / 1000.0 for row in cache]

    ax.plot(
        x,
        baseline_total,
        color="#e74c3c",
        marker="o",
        linewidth=2.8,
        markersize=6,
        label="Baseline JIT  (no persistent cache)",
    )
    ax.plot(
        x,
        cache_total,
        color="#2dbd68",
        marker="s",
        linestyle="--",
        linewidth=2.8,
        markersize=6,
        label="AOT Cache  (disk cache hit)",
    )

    ax.fill_between(
        [x[0] - 0.3, x[0] + 0.3],
        [cache_total[0], cache_total[0]],
        [baseline_total[0], baseline_total[0]],
        color="#c4c92f",
        alpha=0.18,
        linewidth=0,
    )
    ax.set_yscale("log")
    ax.set_xlabel("Iteration Number", fontsize=13)
    ax.set_ylabel("Total latency  (seconds, log scale)", fontsize=13)
    ax.set_title(
        "JAX Cold-Start Latency: Persistent Compilation Cache vs Baseline\n"
        f"Workload: TORAX-style transport ({scenario})  ·  CPU backend",
        fontsize=14,
        pad=14,
    )
    ax.grid(True, which="both", linewidth=0.8, alpha=0.72)
    ax.set_xticks(x)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _pos: f"{value:.3f}s"))
    ax.legend(loc="lower right", facecolor="#202433", edgecolor="#3c4358", framealpha=0.88, fontsize=11)

    source = (
        "Source: prototypes/jax-real-workload-cache "
        "· artifact restored at same cache mount path "
        "· compile/load saved by JAX persistent cache."
    )
    ax.text(
        0.995,
        -0.15,
        source,
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=9,
        color="#7d83a8",
        style="italic",
    )

    baseline_one = baseline[0]
    cache_one = cache[0]
    stacks = [
        ("Artifact import", "artifact_import_ms", "#f6c85f"),
        ("Tracing/lowering", "lower_ms", "#3498db"),
        ("Compilation/load", "compile_or_load_ms", "#e74c3c"),
        ("Execution", "first_execute_ms", "#2ecc71"),
    ]
    labels = ["Baseline\n(no cache)", "AOT Cache\n(disk hit)"]
    rows = [baseline_one, cache_one]
    bottoms = [0.0, 0.0]
    positions = [0, 1]
    for label, key, color in stacks:
        values = [float(row[key]) / 1000.0 for row in rows]
        bar_ax.bar(positions, values, bottom=bottoms, color=color, edgecolor="none", width=0.55, label=label)
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    for pos, total in zip(positions, bottoms):
        bar_ax.text(
            pos,
            total + max(bottoms) * 0.035,
            ms_label(total * 1000.0),
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color="#f2f4f8",
        )

    bar_ax.set_title("Iteration 1: Phase Breakdown", fontsize=14, pad=14)
    bar_ax.set_ylabel("Time (seconds)", fontsize=12)
    bar_ax.set_xticks(positions, labels, fontsize=11)
    bar_ax.grid(True, axis="y", linewidth=0.8, alpha=0.72)
    bar_ax.legend(loc="upper right", facecolor="#202433", edgecolor="#3c4358", framealpha=0.88, fontsize=10)
    bar_ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _pos: f"{value:.3f}s"))

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--scenario", default="torax-pulse-64")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render(args.results_dir, args.scenario, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
