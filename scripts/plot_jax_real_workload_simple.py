#!/usr/bin/env python3
"""Render a simple JAX persistent-cache summary figure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


WORKLOADS = [
    ("torax-pulse-64", "Pulse transport"),
    ("torax-mlsurrogate-64", "Surrogate transport"),
]


def read_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render(results_dir: Path, out: Path) -> None:
    summary = read_summary(results_dir / "summary.json")
    labels = summary["labels"]

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "axes.edgecolor": "#d7dce5",
            "axes.labelcolor": "#202633",
            "xtick.color": "#5b6473",
            "ytick.color": "#202633",
            "text.color": "#111827",
            "grid.color": "#e7eaf0",
        }
    )

    fig, ax = plt.subplots(figsize=(10.5, 5.8), dpi=180)
    fig.subplots_adjust(left=0.19, right=0.97, top=0.78, bottom=0.18)
    y = list(range(len(WORKLOADS)))
    offset = 0.18
    baseline = [labels["baseline"][key]["compileOrLoadMsMedian"] for key, _name in WORKLOADS]
    cached = [labels["persistent-cache-reuse"][key]["compileOrLoadMsMedian"] for key, _name in WORKLOADS]

    ax.barh([pos + offset for pos in y], baseline, height=0.28, color="#ef4444", label="No cache")
    ax.barh([pos - offset for pos in y], cached, height=0.28, color="#16a34a", label="Restored cache")

    for pos, base, hit in zip(y, baseline, cached):
        speedup = base / hit
        ax.text(base + 5, pos + offset, f"{base:.0f} ms", va="center", fontsize=10, color="#7f1d1d")
        ax.text(hit + 5, pos - offset, f"{hit:.0f} ms", va="center", fontsize=10, color="#14532d")
        ax.text(
            max(base, hit) + 42,
            pos,
            f"{speedup:.1f}x",
            va="center",
            ha="center",
            fontsize=16,
            fontweight="bold",
            color="#111827",
        )

    fig.text(0.19, 0.93, "JAX Persistent Cache Cuts Compile Latency", fontsize=21, weight="bold")
    fig.text(
        0.19,
        0.885,
        "TORAX-style JAX workloads, 10 fresh-process trials, CPU backend",
        fontsize=10.5,
        color="#6b7280",
    )
    ax.set_yticks(y)
    ax.set_yticklabels([name for _key, name in WORKLOADS], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel("Compile/load p50 latency (ms)", fontsize=11)
    ax.set_xlim(0, max(baseline) * 1.55)
    ax.grid(True, axis="x", linewidth=0.9)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", frameon=False, fontsize=10)

    mismatch = labels["mismatch-control"]["torax-pulse-64-mismatch"]["compileOrLoadMsMedian"]
    import_ms = labels["persistent-cache-reuse"]["torax-pulse-64"]["artifactImportMsMedian"]
    archive_kb = labels["persistent-cache-reuse"]["torax-pulse-64"]["archiveBytesLast"] / 1024
    ax.text(
        0.0,
        -0.18,
        f"Changed-profile control misses: {mismatch:.0f} ms. Artifact: {archive_kb:.0f} KB compressed, {import_ms:.1f} ms import.",
        transform=ax.transAxes,
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
