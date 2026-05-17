#!/usr/bin/env python3
"""Overlaid baseline vs redis comparison plots — JVM-reference style.

Each workload gets one figure with four lines:
  baseline raw     thin blue,   alpha=0.45  (jagged raw data)
  baseline EWMA    thick red,   alpha=0.95  (smoothed warmup curve)
  redis raw        thin green,  alpha=0.45
  redis EWMA       thick blue,  alpha=0.95

Fill-between the two EWMA curves shades the improvement region.
EWMA alpha=0.16 matches the JVM plot_churn.py default so the warmup
decay shape is directly comparable.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np


EWMA_ALPHA = 0.16


def read_csv(path: Path) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "invocation": int(row["invocation"]),
                    "latency_ms": float(row.get("http_latency_ms") or 0),
                    "status": int(row.get("status") or 0),
                    "churn": row.get("churn") == "1",
                })
            except (ValueError, TypeError):
                continue
    return rows


def ok_xy(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    ok = [r for r in rows if 200 <= r["status"] < 400]
    return (np.array([r["invocation"] for r in ok]),
            np.array([r["latency_ms"] for r in ok]))


def ewma(values: np.ndarray, alpha: float = EWMA_ALPHA) -> np.ndarray:
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


MODES = [
    ("baseline",    "#d62728", "baseline (cold JIT)",          1.2, 0.85),
    ("redis",       "#1f77b4", "redis precompile cache",       1.2, 0.85),
    ("sysimage5",   "#2ca02c", "AOT sysimage (5 profiles)",   1.4, 0.90),
    ("sysimage10",  "#9467bd", "AOT sysimage (10 profiles)",  1.4, 0.90),
]


def main() -> None:
    if len(sys.argv) < 2:
        results_dir = Path(__file__).parent / "results-fix4"
    else:
        results_dir = Path(sys.argv[1])

    known = ["lusearch", "h2", "eclipse", "matrix", "regex", "sort"]
    workloads = [w for w in known
                 if (results_dir / f"{w}-baseline.csv").exists()]

    for wl in workloads:
        fig, ax = plt.subplots(figsize=(14, 5))

        all_rows: list = []
        all_y:    list = []
        b_peak = 0.0

        for mode, color, label, lw, alpha in MODES:
            csv_path = results_dir / f"{wl}-{mode}.csv"
            if not csv_path.exists():
                continue
            rows = read_csv(csv_path)
            x, y = ok_xy(rows)
            if len(x) == 0:
                continue
            ax.plot(x, y, color=color, linewidth=lw, alpha=alpha,
                    label=label, zorder=3)
            all_rows.extend(rows)
            all_y.append(y)
            if mode == "baseline":
                bx_ref, by_ref = x, y
                b_peak = float(y.max())

        # Fill between baseline and best cached mode where available
        for mode, color, *_ in MODES[1:]:
            csv_path = results_dir / f"{wl}-{mode}.csv"
            if not csv_path.exists():
                continue
            rows = read_csv(csv_path)
            rx, ry = ok_xy(rows)
            n = min(len(bx_ref), len(rx))
            if n == 0:
                continue
            ax.fill_between(
                bx_ref[:n], by_ref[:n], ry[:n],
                where=(by_ref[:n] > ry[:n]),
                interpolate=True,
                color=color, alpha=0.08, label="_nolegend_", zorder=2,
            )
            break  # shade only against the first available non-baseline mode

        # Pod-restart markers
        churn_x = sorted({r["invocation"] for r in all_rows if r["churn"]})
        first = True
        for cx in churn_x:
            ax.axvline(cx, color="#888888", linestyle="--", linewidth=1.2,
                       alpha=0.65, zorder=1,
                       label="pod restart (churn)" if first else "_nolegend_")
            first = False

        # Y-axis cap at warm-state p99 × 2.5
        if all_y:
            warm_all = np.concatenate([yy[yy < b_peak * 0.5] for yy in all_y if len(yy)])
            p99 = float(np.percentile(warm_all, 99)) if len(warm_all) else b_peak
            ax.set_ylim(bottom=0, top=max(p99 * 2.5, 50))

        ax.set_xlim(left=0)
        ax.set_xlabel("Request index", fontsize=12)
        ax.set_ylabel("End-to-end latency (ms)", fontsize=12)
        ax.set_title(
            f"Julia {wl} on OpenFaaS — baseline vs cache modes"
            f"  (raw latency, container churn + JIT warmup)",
            fontsize=13, fontweight="bold",
        )
        ax.legend(loc="upper right", fontsize=10, framealpha=0.92)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True, nbins=12))
        ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)

        plt.tight_layout()
        out = results_dir / f"{wl}-comparison.png"
        fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
