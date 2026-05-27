#!/usr/bin/env python3
"""Render a compact summary figure for the real JAX workload cache run."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


WORKLOAD_LABELS = {
    "torax-pulse-64": "Pulse transport",
    "torax-mlsurrogate-64": "Surrogate transport",
    "torax-pulse-64-mismatch": "Changed profile",
}


def read_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_trial_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["iteration"] = int(row["iteration"])
        for field in (
            "startup_plus_first_request_ms",
            "lower_ms",
            "compile_or_load_ms",
            "first_execute_ms",
            "artifact_import_ms",
        ):
            row[field] = float(row[field])
    return rows


def scenario_rows(rows: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["scenario"] == scenario]


def median(values: list[float]) -> float:
    return float(statistics.median(values))


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": "#f7f8fb",
            "savefig.facecolor": "#f7f8fb",
            "axes.facecolor": "#ffffff",
            "axes.edgecolor": "#d7dbe5",
            "axes.labelcolor": "#202633",
            "xtick.color": "#5b6473",
            "ytick.color": "#5b6473",
            "text.color": "#171923",
            "grid.color": "#e6e9f0",
        }
    )


def add_card(fig: plt.Figure, x: float, y: float, w: float, h: float, title: str, value: str, note: str) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        transform=fig.transFigure,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.0,
        facecolor="#ffffff",
        edgecolor="#dfe3ec",
        zorder=0,
    )
    fig.add_artist(box)
    fig.text(x + 0.018, y + h - 0.030, title, fontsize=10, color="#687386", weight="bold")
    fig.text(x + 0.018, y + 0.045, value, fontsize=22, color="#111827", weight="bold")
    fig.text(x + 0.018, y + 0.018, note, fontsize=9.5, color="#6b7280")


def plot_speedup(ax: plt.Axes, summary: dict[str, Any]) -> None:
    labels = summary["labels"]
    scenarios = ["torax-pulse-64", "torax-mlsurrogate-64"]
    y_positions = list(range(len(scenarios)))
    baseline_vals = [labels["baseline"][s]["compileOrLoadMsMedian"] for s in scenarios]
    cache_vals = [labels["persistent-cache-reuse"][s]["compileOrLoadMsMedian"] for s in scenarios]

    ax.set_title("XLA compile/load drops on matching profiles", loc="left", fontsize=13, weight="bold", pad=10)
    for y, scenario, base, cached in zip(y_positions, scenarios, baseline_vals, cache_vals):
        ax.hlines(y, cached, base, color="#cfd6e3", linewidth=7, zorder=1)
        ax.scatter([base], [y], s=140, color="#ef4444", edgecolor="white", linewidth=1.5, zorder=3)
        ax.scatter([cached], [y], s=140, color="#16a34a", edgecolor="white", linewidth=1.5, zorder=3)
        speedup = base / cached
        ax.text(base + 8, y, f"{base:.0f} ms", va="center", fontsize=10, color="#7f1d1d")
        ax.text(cached - 8, y, f"{cached:.0f} ms", va="center", ha="right", fontsize=10, color="#14532d")
        ax.text((base + cached) / 2, y + 0.23, f"{speedup:.1f}x", va="center", ha="center", fontsize=11, weight="bold")

    mismatch = labels["mismatch-control"]["torax-pulse-64-mismatch"]["compileOrLoadMsMedian"]
    ax.scatter([mismatch], [len(scenarios) + 0.15], s=115, color="#f59e0b", edgecolor="white", linewidth=1.5)
    ax.text(mismatch + 8, len(scenarios) + 0.15, f"changed profile: {mismatch:.0f} ms miss", va="center", fontsize=10, color="#92400e")

    ax.set_yticks(y_positions + [len(scenarios) + 0.15])
    ax.set_yticklabels([WORKLOAD_LABELS[s] for s in scenarios] + ["Mismatch control"])
    ax.set_xlabel("Compile/load latency p50 (ms)")
    ax.set_xlim(0, max(max(baseline_vals), mismatch) * 1.22)
    ax.grid(True, axis="x", linewidth=0.9)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)


def plot_phase_breakdown(ax: plt.Axes, summary: dict[str, Any]) -> None:
    labels = summary["labels"]
    scenarios = ["torax-pulse-64", "torax-mlsurrogate-64"]
    bars: list[tuple[str, dict[str, float]]] = []
    for scenario in scenarios:
        bars.append((f"{WORKLOAD_LABELS[scenario]}\nbase", labels["baseline"][scenario]))
        bars.append((f"{WORKLOAD_LABELS[scenario]}\ncache", labels["persistent-cache-reuse"][scenario]))

    phases = [
        ("artifactImportMsMedian", "Import", "#f5c04f"),
        ("lowerMsMedian", "Trace/lower", "#3b82f6"),
        ("compileOrLoadMsMedian", "Compile/load", "#ef4444"),
        ("firstExecuteMsMedian", "Execute", "#22c55e"),
    ]
    xs = list(range(len(bars)))
    bottoms = [0.0] * len(bars)
    for key, name, color in phases:
        values = [float(data.get(key, 0.0)) for _label, data in bars]
        ax.bar(xs, values, bottom=bottoms, width=0.64, label=name, color=color)
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    for x, total in zip(xs, bottoms):
        ax.text(x, total + 8, f"{total:.0f}", ha="center", va="bottom", fontsize=9.5, weight="bold")

    ax.set_title("First request phase breakdown", loc="left", fontsize=13, weight="bold", pad=10)
    ax.set_ylabel("Median latency (ms)")
    ax.set_xticks(xs)
    ax.set_xticklabels([label for label, _data in bars], fontsize=9)
    ax.grid(True, axis="y", linewidth=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", frameon=False, fontsize=9)


def plot_trials(ax: plt.Axes, results_dir: Path) -> None:
    baseline = read_trial_rows(results_dir / "baseline.csv")
    cache = read_trial_rows(results_dir / "persistent-cache-reuse.csv")
    styles = {
        ("torax-pulse-64", "baseline"): ("#ef4444", "-", "o"),
        ("torax-pulse-64", "cache"): ("#16a34a", "-", "o"),
        ("torax-mlsurrogate-64", "baseline"): ("#fb7185", "--", "s"),
        ("torax-mlsurrogate-64", "cache"): ("#22c55e", "--", "s"),
    }
    for scenario in ("torax-pulse-64", "torax-mlsurrogate-64"):
        for mode, rows in (("baseline", baseline), ("cache", cache)):
            selected = scenario_rows(rows, scenario)
            selected.sort(key=lambda row: row["iteration"])
            color, line_style, marker = styles[(scenario, mode)]
            label = f"{WORKLOAD_LABELS[scenario]} {'baseline' if mode == 'baseline' else 'cache'}"
            ax.plot(
                [row["iteration"] for row in selected],
                [row["startup_plus_first_request_ms"] for row in selected],
                color=color,
                linestyle=line_style,
                marker=marker,
                linewidth=2.0,
                markersize=4.8,
                label=label,
            )

    ax.set_title("Fresh-process trials", loc="left", fontsize=13, weight="bold", pad=10)
    ax.set_xlabel("Trial")
    ax.set_ylabel("First-request latency (ms)")
    ax.set_xticks(range(1, 11))
    ax.grid(True, linewidth=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", ncol=2, frameon=False, fontsize=8.5)


def render(results_dir: Path, out: Path) -> None:
    summary = read_summary(results_dir / "summary.json")
    configure_style()

    fig = plt.figure(figsize=(16, 9), dpi=170)
    fig.text(0.045, 0.955, "JAX Profile-Artifact Cache: Real-Workload Summary", fontsize=23, weight="bold")
    fig.text(
        0.045,
        0.925,
        "TORAX-style scenario profiles reuse a compact JAX/XLA persistent compilation artifact across fresh Python processes.",
        fontsize=11.5,
        color="#5b6473",
    )

    comps = summary["comparisons"]
    avg_compile_speedup = median([float(comps[s]["compileLoadSpeedup"]) for s in comps])
    avg_request_speedup = median([float(comps[s]["firstRequestSpeedup"]) for s in comps])
    artifact = summary["labels"]["persistent-cache-reuse"]["torax-pulse-64"]
    add_card(
        fig,
        0.045,
        0.785,
        0.265,
        0.105,
        "COMPILE/LOAD SPEEDUP",
        f"{avg_compile_speedup:.1f}x",
        "median across both matching profiles",
    )
    add_card(
        fig,
        0.335,
        0.785,
        0.265,
        0.105,
        "FIRST REQUEST SPEEDUP",
        f"{avg_request_speedup:.1f}x",
        "includes import + lower + execute",
    )
    add_card(
        fig,
        0.625,
        0.785,
        0.330,
        0.105,
        "ARTIFACT OVERHEAD",
        f"{artifact['archiveBytesLast'] / 1024:.0f} KB / {artifact['artifactImportMsMedian']:.1f} ms",
        "compressed cache artifact / p50 import",
    )

    gs = fig.add_gridspec(
        2,
        2,
        left=0.055,
        right=0.965,
        bottom=0.085,
        top=0.735,
        width_ratios=[0.48, 0.52],
        height_ratios=[0.55, 0.45],
        hspace=0.34,
        wspace=0.22,
    )
    speed_ax = fig.add_subplot(gs[0, 0])
    phase_ax = fig.add_subplot(gs[0, 1])
    trial_ax = fig.add_subplot(gs[1, :])

    plot_speedup(speed_ax, summary)
    plot_phase_breakdown(phase_ax, summary)
    plot_trials(trial_ax, results_dir)

    fig.text(
        0.055,
        0.030,
        "Run: prototypes/jax-real-workload-cache/results/20260526-171937. "
        "Cache restored at the same mount path used during population; changed-profile control misses and creates a new cache entry.",
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
