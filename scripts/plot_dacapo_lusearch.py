#!/usr/bin/env python3
"""Plot DaCapo lusearch CSV output as SVG."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--prefix", default="dacapo-lusearch-local")
    args = parser.parse_args()

    rows = read_rows(args.csv)
    if not rows:
        raise SystemExit(f"no rows in {args.csv}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize(rows)
    (args.out_dir / f"{args.prefix}-latency.svg").write_text(render_latency(rows), encoding="utf-8")
    (args.out_dir / f"{args.prefix}-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"latency: {args.out_dir / f'{args.prefix}-latency.svg'}")
    print(f"summary: {args.out_dir / f'{args.prefix}-summary.json'}")


def read_rows(path: Path) -> list[dict[str, float | int | str]]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "label": row.get("label") or row.get("phase") or "lusearch",
                    "iteration": int(row["iteration"]),
                    "wall_ms": float(row.get("wall_ms") or row.get("http_ms") or 0),
                    "dacapo_ms": float(row.get("dacapo_ms") or row.get("handler_ms") or 0),
                    "rc": int(row.get("rc") or 0),
                }
            )
    return rows


def summarize(rows: list[dict[str, float | int | str]]) -> dict[str, float | int]:
    walls = sorted(float(row["wall_ms"]) for row in rows)
    dacapo = sorted(float(row["dacapo_ms"]) for row in rows if float(row["dacapo_ms"]) > 0)
    return {
        "n": len(rows),
        "wall_mean_ms": sum(walls) / len(walls),
        "wall_p50_ms": percentile(walls, 0.50),
        "wall_p95_ms": percentile(walls, 0.95),
        "dacapo_mean_ms": sum(dacapo) / len(dacapo) if dacapo else 0,
        "dacapo_p50_ms": percentile(dacapo, 0.50) if dacapo else 0,
        "dacapo_p95_ms": percentile(dacapo, 0.95) if dacapo else 0,
    }


def render_latency(rows: list[dict[str, float | int | str]]) -> str:
    width, height = 960, 560
    left, right, top, bottom = 90, 40, 74, 82
    chart_w = width - left - right
    chart_h = height - top - bottom
    y_max = nice_max(max(float(row["wall_ms"]) for row in rows) * 1.15)
    max_iter = max(int(row["iteration"]) for row in rows)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="DaCapo lusearch latency">',
        "<title>DaCapo lusearch latency</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(width / 2, 32, "DaCapo lusearch Cold Invocation Latency", 22, "middle", "#0f172a", 700),
        text(width / 2, 56, "Each point is a fresh benchmark execution.", 13, "middle", "#475569"),
    ]
    for i in range(6):
        value = y_max * i / 5
        y = top + chart_h - (value / y_max) * chart_h
        parts.append(line(left, y, left + chart_w, y, "#e2e8f0", 1))
        parts.append(text(left - 12, y + 4, f"{value:.0f}", 11, "end", "#64748b"))
    parts.append(line(left, top, left, top + chart_h, "#64748b", 1.2))
    parts.append(line(left, top + chart_h, left + chart_w, top + chart_h, "#64748b", 1.2))
    parts.append(text(24, top + chart_h / 2, "Wall latency (ms)", 13, "middle", "#334155", 600, rotate=-90))
    points = []
    for row in rows:
        x = left + ((int(row["iteration"]) - 1) / max(max_iter - 1, 1)) * chart_w
        y = top + chart_h - (float(row["wall_ms"]) / y_max) * chart_h
        points.append((x, y))
    parts.append(polyline(points, "#0f766e"))
    for x, y in points:
        parts.append(circle(x, y, 4, "#0f766e"))
    for row, (x, y) in zip(rows, points):
        parts.append(text(x, y - 10, f"{float(row['wall_ms']):.0f}", 11, "middle", "#334155", 600))
        parts.append(text(x, top + chart_h + 24, str(row["iteration"]), 11, "middle", "#475569"))
    parts.append(text(left + chart_w / 2, height - 30, "Run number", 13, "middle", "#334155", 600))
    parts.append("</svg>")
    return "\n".join(parts)


def percentile(sorted_values: list[float], p: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = p * (len(sorted_values) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = pos - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def nice_max(value: float) -> float:
    magnitude = 10 ** math.floor(math.log10(max(value, 1)))
    normalized = value / magnitude
    if normalized <= 1.5:
        nice = 1.5
    elif normalized <= 2:
        nice = 2
    elif normalized <= 3:
        nice = 3
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def text(x: float, y: float, value: str, size: int, anchor: str, color: str, weight: int = 400, rotate: int | None = None) -> str:
    transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}"{transform}>{html.escape(value)}</text>'


def line(x1: float, y1: float, x2: float, y2: float, color: str, width: float) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"/>'


def polyline(points: list[tuple[float, float]], color: str) -> str:
    encoded = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{encoded}" fill="none" stroke="{color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'


def circle(x: float, y: float, radius: float, color: str) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" stroke="#ffffff" stroke-width="1"/>'


if __name__ == "__main__":
    main()
