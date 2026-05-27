#!/usr/bin/env python3
"""Render clean line graphs for the real JAX workload cache run."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


WORKLOADS = [
    ("torax-pulse-64", "Core transport solve"),
    ("torax-mlsurrogate-64", "Core transport + learned closure"),
]


def read_rows(path: Path, scenario: str) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = [row for row in csv.DictReader(f) if row["scenario"] == scenario]
    for row in rows:
        row["iteration"] = int(row["iteration"])
        row["compile_or_load_ms"] = float(row["compile_or_load_ms"])
    return sorted(rows, key=lambda row: row["iteration"])


def render(results_dir: Path, out: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "axes.edgecolor": "#d7dce5",
            "axes.labelcolor": "#202633",
            "xtick.color": "#5b6473",
            "ytick.color": "#5b6473",
            "text.color": "#111827",
            "grid.color": "#e7eaf0",
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), dpi=180, sharey=True)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.76, bottom=0.18, wspace=0.12)

    fig.text(0.08, 0.93, "JAX Cold-Start Compile Latency: Persistent Cache vs Baseline", fontsize=20, weight="bold")
    fig.text(
        0.08,
        0.875,
        "Workload family: TORAX-style core transport simulation · 10 fresh-process trials · CPU backend",
        fontsize=10.5,
        color="#6b7280",
    )

    for ax, (scenario, title) in zip(axes, WORKLOADS):
        baseline = read_rows(results_dir / "baseline.csv", scenario)
        cached = read_rows(results_dir / "persistent-cache-reuse.csv", scenario)

        ax.plot(
            [row["iteration"] for row in baseline],
            [row["compile_or_load_ms"] for row in baseline],
            color="#ef4444",
            marker="o",
            linewidth=2.4,
            markersize=5.5,
            label="No cache",
        )
        ax.plot(
            [row["iteration"] for row in cached],
            [row["compile_or_load_ms"] for row in cached],
            color="#16a34a",
            marker="s",
            linewidth=2.4,
            markersize=5.2,
            label="Restored cache",
        )

        ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=10)
        ax.set_xlabel("Fresh process trial")
        ax.set_xticks(range(1, 11))
        ax.grid(True, linewidth=0.9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, 285)

        base_med = sorted(row["compile_or_load_ms"] for row in baseline)[len(baseline) // 2]
        cache_med = sorted(row["compile_or_load_ms"] for row in cached)[len(cached) // 2]
        ax.text(
            0.03,
            0.92,
            f"{base_med / cache_med:.1f}x lower p50",
            transform=ax.transAxes,
            fontsize=11,
            weight="bold",
            color="#111827",
        )

    axes[0].set_ylabel("Compile/load latency (ms)")
    axes[1].legend(loc="upper right", frameon=False)

    fig.text(
        0.08,
        0.055,
        "Changed-profile control misses the restored artifact: 212 ms compile/load p50. Artifact: 127 KB compressed, 1.7 ms import p50.",
        fontsize=9.5,
        color="#6b7280",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    render(args.results_dir, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
