#!/usr/bin/env python3
"""Render paper-style JAX cold-start plots for PyHPC-style workloads."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


WORKLOAD_TITLES = {
    "pyhpc-teos10-gsw-dhdt": "PyHPC Equation of State / TEOS-10 gsw_dHdT",
    "pyhpc-isoneutral-mixing": "PyHPC Isoneutral Mixing",
    "flax-transformer-train-128": "Flax Transformer train_step",
    "flax-transformer-infer-128": "Flax Transformer inference",
    "flax-mnist-cnn-train-real": "Flax CNN train_step on MNIST",
}

WORKLOAD_SOURCES = {
    "pyhpc-teos10-gsw-dhdt": "PyHPC-style TEOS-10 EOS polynomial; 512x512 synthetic inputs",
    "pyhpc-isoneutral-mixing": "PyHPC-style isoneutral mixing stencil; 384x384 synthetic inputs",
    "flax-transformer-train-128": "Flax Linen Transformer; batch=4, seq=128, hidden=192, layers=4, synthetic tokens",
    "flax-transformer-infer-128": "Flax Linen Transformer; batch=4, seq=128, hidden=192, layers=4, synthetic tokens",
    "flax-mnist-cnn-train-real": "Flax Linen CNN; real MNIST images, batch=128",
}


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
    if not rows:
        return []
    values = [float(rows[0]["startup_plus_first_request_ms"]) / 1000.0]
    # Later points represent the hot executable in the same worker: execution
    # only, using the per-trial execution samples from the measured run.
    values.extend(float(row["first_execute_ms"]) / 1000.0 for row in rows[1:10])
    return values


def render(results_dir: Path, scenario: str, out: Path) -> None:
    baseline = read_rows(results_dir / "baseline.csv", scenario)
    cache = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)
    if len(baseline) < 2 or len(cache) < 2:
        raise ValueError(f"not enough rows for {scenario} in {results_dir}")

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.facecolor": "#1b1e28",
            "figure.facecolor": "#10131a",
            "savefig.facecolor": "#10131a",
            "text.color": "#e7e9ee",
            "axes.labelcolor": "#d3d7df",
            "xtick.color": "#aeb4c0",
            "ytick.color": "#aeb4c0",
            "axes.edgecolor": "#3a4152",
            "grid.color": "#2b3140",
        }
    )

    fig = plt.figure(figsize=(16.2, 6.3), dpi=170)
    gs = fig.add_gridspec(1, 2, width_ratios=[2.35, 1.0], wspace=0.22)
    ax = fig.add_subplot(gs[0, 0])
    phase_ax = fig.add_subplot(gs[0, 1])

    x = list(range(1, 11))
    baseline_curve = warm_curve(baseline)
    cache_curve = warm_curve(cache)

    ax.plot(
        x,
        baseline_curve,
        color="#e74c3c",
        marker="o",
        linewidth=2.8,
        markersize=6,
        label="Baseline JIT  (no persistent cache)",
    )
    ax.plot(
        x,
        cache_curve,
        color="#2fbd68",
        marker="s",
        linestyle="--",
        linewidth=2.8,
        markersize=6,
        label="AOT Cache  (disk cache hit)",
    )
    ax.fill_between(
        [0.72, 1.28],
        [cache_curve[0], cache_curve[0]],
        [baseline_curve[0], baseline_curve[0]],
        color="#c7ca2f",
        alpha=0.16,
        linewidth=0,
    )

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xlabel("Iteration Number", fontsize=12)
    ax.set_ylabel("Total Latency  (seconds, log scale)", fontsize=12)
    title_prefix = "JAX/Flax" if scenario.startswith("flax-") else "JAX"
    ax.set_title(
        f"{title_prefix} Cold-Start Latency: Persistent Compilation Cache vs Baseline\n"
        f"Workload: {WORKLOAD_TITLES.get(scenario, scenario)}  ·  CPU backend",
        fontsize=13,
        pad=12,
    )
    ax.grid(True, which="both", linewidth=0.8, alpha=0.75)
    ax.legend(loc="lower right", facecolor="#202433", edgecolor="#444b61", framealpha=0.88, fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _pos: f"{value:.3f}s" if value >= 0.1 else f"{value * 1000:.2f}ms"))

    source = (
        f"Source: {WORKLOAD_SOURCES.get(scenario, 'JAX synthetic workload')} "
        "· first point includes lower/compile; later points are hot execution."
    )
    ax.text(
        0.5,
        -0.15,
        source,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.5,
        color="#8186a8",
        style="italic",
    )

    first_rows = [baseline[0], cache[0]]
    labels = ["Baseline\n(no cache)", "AOT Cache\n(disk hit)"]
    phases = [
        ("Tracing/lowering\n(Python->jaxpr)", "lower_ms", "#3498db"),
        ("Compilation/load\n(jaxpr->XLA binary)", "compile_or_load_ms", "#e74c3c"),
        ("Execution", "first_execute_ms", "#28a85a"),
    ]
    bottoms = [0.0, 0.0]
    positions = [0, 1]
    for phase_label, key, color in phases:
        values = [float(row[key]) / 1000.0 for row in first_rows]
        phase_ax.bar(positions, values, bottom=bottoms, color=color, edgecolor="none", width=0.55, label=phase_label)
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    phase_ax.set_ylim(0, max(bottoms) * 1.22)
    for pos, total in zip(positions, bottoms):
        phase_ax.text(
            pos,
            total + max(bottoms) * 0.035,
            f"{total * 1000:.0f}ms",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color="#f4f6fb",
        )

    phase_ax.set_title("Iteration 1: Phase Breakdown", fontsize=13, pad=12)
    phase_ax.set_ylabel("Time (seconds)", fontsize=11)
    phase_ax.set_xticks(positions, labels, fontsize=10)
    phase_ax.grid(True, axis="y", linewidth=0.8, alpha=0.75)
    phase_ax.legend(loc="upper right", facecolor="#202433", edgecolor="#444b61", framealpha=0.88, fontsize=8.8)
    phase_ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _pos: f"{value:.3f}s"))

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render(args.results_dir, args.scenario, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
