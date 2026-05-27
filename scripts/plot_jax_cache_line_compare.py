#!/usr/bin/env python3
"""Render a clean baseline-vs-cache line graph from JAX cache measurements."""

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


WORKLOAD_TITLES = {
    "flax-transformer-train-128": "Flax Transformer train_step",
    "flax-transformer-infer-128": "Flax Transformer inference",
    "flax-mnist-cnn-train-real": "Flax CNN train_step on MNIST",
    "pyhpc-teos10-gsw-dhdt": "PyHPC Equation of State / TEOS-10 gsw_dHdT",
    "pyhpc-isoneutral-mixing": "PyHPC Isoneutral Mixing",
}

WORKLOAD_DETAILS = {
    "flax-transformer-train-128": "synthetic tokens, batch=4, seq=128, hidden=192, layers=4",
    "flax-transformer-infer-128": "synthetic tokens, batch=4, seq=128, hidden=192, layers=4",
    "flax-mnist-cnn-train-real": "real MNIST images, batch=128",
    "pyhpc-teos10-gsw-dhdt": "PyHPC-style TEOS-10 EOS polynomial, 512x512 synthetic inputs",
    "pyhpc-isoneutral-mixing": "PyHPC-style isoneutral mixing stencil, 384x384 synthetic inputs",
}


def read_rows(path: Path, scenario: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["scenario"] == scenario]
    for row in rows:
        row["iteration"] = int(row["iteration"])
        row["startup_plus_first_request_ms"] = float(row["startup_plus_first_request_ms"])
        row["compile_or_load_ms"] = float(row["compile_or_load_ms"])
    return sorted(rows, key=lambda row: row["iteration"])


def render(results_dir: Path, scenario: str, out: Path) -> None:
    baseline = read_rows(results_dir / "baseline.csv", scenario)
    cache = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)
    if not baseline or not cache:
        raise ValueError(f"missing baseline/cache rows for {scenario} in {results_dir}")

    count = min(len(baseline), len(cache))
    baseline = baseline[:count]
    cache = cache[:count]
    x = [row["iteration"] for row in baseline]
    baseline_seconds = [row["startup_plus_first_request_ms"] / 1000.0 for row in baseline]
    cache_seconds = [row["startup_plus_first_request_ms"] / 1000.0 for row in cache]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.facecolor": "#171b24",
            "figure.facecolor": "#0f1218",
            "savefig.facecolor": "#0f1218",
            "text.color": "#eef1f6",
            "axes.labelcolor": "#d7dbe4",
            "xtick.color": "#aeb6c4",
            "ytick.color": "#aeb6c4",
            "axes.edgecolor": "#333a4a",
            "grid.color": "#2a3040",
        }
    )

    fig, ax = plt.subplots(figsize=(12.5, 6.2), dpi=180)
    ax.plot(
        x,
        baseline_seconds,
        color="#ef5147",
        marker="o",
        linewidth=2.7,
        markersize=6,
        label="Baseline JIT (no persistent cache)",
    )
    ax.plot(
        x,
        cache_seconds,
        color="#29b765",
        marker="s",
        linewidth=2.7,
        markersize=6,
        linestyle="--",
        label="Persistent cache restored",
    )

    ax.set_title(
        "JAX/Flax Cold-Start Latency: Persistent Compilation Cache vs Baseline\n"
        f"Workload: {WORKLOAD_TITLES.get(scenario, scenario)} · CPU backend",
        fontsize=14,
        pad=14,
    )
    ax.set_xlabel("Fresh Process Trial", fontsize=12)
    ax.set_ylabel("Startup + First Request Latency (seconds)", fontsize=12)
    ax.set_xticks(x)
    ax.grid(True, which="major", linewidth=0.8, alpha=0.8)
    ax.legend(loc="upper right", facecolor="#202536", edgecolor="#42495d", framealpha=0.92, fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda value, _pos: f"{value:.2f}s"))

    baseline_p50 = statistics.median(baseline_seconds)
    cache_p50 = statistics.median(cache_seconds)
    speedup = baseline_p50 / cache_p50 if cache_p50 else 0.0
    ax.text(
        0.015,
        0.94,
        f"p50 cold-start: {baseline_p50:.2f}s -> {cache_p50:.2f}s ({speedup:.1f}x)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10.5,
        color="#dfe4f0",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#202536", "edgecolor": "#42495d", "alpha": 0.86},
    )
    ax.text(
        0.5,
        -0.16,
        f"Source: {WORKLOAD_DETAILS.get(scenario, 'JAX workload')} · each point is a fresh Python process.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color="#8289a8",
        style="italic",
    )

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
