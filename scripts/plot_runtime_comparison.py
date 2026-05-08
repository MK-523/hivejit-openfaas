#!/usr/bin/env python3
"""Plot JVM/OpenFaaS latency against Go and .NET profile-cache prototypes."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


COLORS = [
    "#2563eb",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#dc2626",
    "#0891b2",
    "#4b5563",
    "#be123c",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((p / 100.0) * len(ordered))
    return ordered[min(index, len(ordered) - 1)]


def escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_java_csv(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    latencies = [float(row["latency_ms"]) for row in rows]
    statuses: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", ""))
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "label": "Java/OpenFaaS George JVM",
        "source": str(path),
        "kind": "http",
        "times_ms": latencies,
        "mean_ms": statistics.fmean(latencies),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "max_ms": max(latencies),
        "statuses": statuses,
    }


def load_json_result(label: str, path: Path, kind: str = "local-prototype") -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    times = data.get("invocationTimesMs") or data.get("InvocationTimesMs")
    if not times:
        p50 = data.get("invocationP50Ms", data.get("InvocationP50Ms", 0.0))
        times = [float(p50)]
    times = [float(value) for value in times]
    return {
        "label": label,
        "source": str(path),
        "kind": kind,
        "times_ms": times,
        "mean_ms": statistics.fmean(times),
        "p50_ms": percentile(times, 50),
        "p95_ms": percentile(times, 95),
        "max_ms": max(times),
    }


def line_svg(series: list[dict[str, Any]], path: Path) -> None:
    width = 1100
    height = 560
    margin_left = 76
    margin_right = 260
    margin_top = 58
    margin_bottom = 68
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    max_x = max(len(item["times_ms"]) for item in series)
    max_y = max(max(item["times_ms"]) for item in series)
    y_max = max(1.0, math.ceil(max_y / 10.0) * 10.0)

    def x_scale(index: int) -> float:
        if max_x <= 1:
            return margin_left
        return margin_left + (index / (max_x - 1)) * plot_w

    def y_scale(value: float) -> float:
        return margin_top + plot_h - (value / y_max) * plot_h

    grid = []
    for i in range(6):
        value = y_max * i / 5
        y = y_scale(value)
        grid.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" stroke="#e5e7eb" />')
        grid.append(f'<text x="{margin_left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#4b5563">{value:.0f}</text>')

    body = []
    legend = []
    for i, item in enumerate(series):
        color = COLORS[i % len(COLORS)]
        points = " ".join(f"{x_scale(j):.1f},{y_scale(value):.1f}" for j, value in enumerate(item["times_ms"]))
        body.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.4" />')
        for j, value in enumerate(item["times_ms"]):
            body.append(f'<circle cx="{x_scale(j):.1f}" cy="{y_scale(value):.1f}" r="3" fill="{color}" />')
        y = margin_top + i * 22
        legend.append(f'<line x1="{width - margin_right + 28}" y1="{y}" x2="{width - margin_right + 52}" y2="{y}" stroke="{color}" stroke-width="3" />')
        legend.append(f'<text x="{width - margin_right + 60}" y="{y + 4}" font-size="12" fill="#111827">{escape(item["label"])}</text>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{margin_left}" y="26" font-family="Arial, sans-serif" font-size="19" font-weight="700" fill="#111827">Invocation latency curves: JVM HTTP vs non-JVM profile-cache prototypes</text>
  <text x="{margin_left}" y="46" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">Java is the OpenFaaS/George JVM HTTP CSV; Go and .NET are local prototype handler loops after profile/AOT artifact import.</text>
  <g font-family="Arial, sans-serif">
    {''.join(grid)}
    <line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}" stroke="#9ca3af" />
    <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#9ca3af" />
    {''.join(body)}
    {''.join(legend)}
    <text x="{margin_left + plot_w / 2:.1f}" y="{height - 20}" text-anchor="middle" font-size="13" fill="#374151">Invocation number within run</text>
    <text x="20" y="{margin_top + plot_h / 2:.1f}" text-anchor="middle" font-size="13" fill="#374151" transform="rotate(-90 20 {margin_top + plot_h / 2:.1f})">Latency (ms)</text>
  </g>
</svg>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def bar_svg(series: list[dict[str, Any]], path: Path) -> None:
    width = 1180
    height = 560
    margin_left = 76
    margin_right = 24
    margin_top = 58
    margin_bottom = 140
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    y_max = max(max(item["p50_ms"], item["p95_ms"]) for item in series)
    y_max = max(1.0, math.ceil(y_max / 10.0) * 10.0)
    group_w = plot_w / len(series)
    bar_w = min(34, group_w * 0.28)

    def y_scale(value: float) -> float:
        return margin_top + plot_h - (value / y_max) * plot_h

    grid = []
    for i in range(6):
        value = y_max * i / 5
        y = y_scale(value)
        grid.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" stroke="#e5e7eb" />')
        grid.append(f'<text x="{margin_left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#4b5563">{value:.0f}</text>')

    bars = []
    for i, item in enumerate(series):
        center = margin_left + group_w * i + group_w / 2
        for offset, key, color in [(-bar_w / 1.7, "p50_ms", "#2563eb"), (bar_w / 1.7, "p95_ms", "#dc2626")]:
            value = float(item[key])
            x = center + offset - bar_w / 2
            y = y_scale(value)
            h = margin_top + plot_h - y
            bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="2" />')
            bars.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="10" fill="{color}">{value:.1f}</text>')
        label = escape(item["label"])
        bars.append(f'<text x="{center:.1f}" y="{height - 98}" text-anchor="end" font-size="11" fill="#111827" transform="rotate(-32 {center:.1f} {height - 98})">{label}</text>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{margin_left}" y="26" font-family="Arial, sans-serif" font-size="19" font-weight="700" fill="#111827">Latency percentile comparison</text>
  <text x="{margin_left}" y="46" font-family="Arial, sans-serif" font-size="12" fill="#4b5563">p50 and p95 across the Java/OpenFaaS JVM HTTP run and non-JVM profile-cache prototypes.</text>
  <g font-family="Arial, sans-serif">
    {''.join(grid)}
    <line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}" stroke="#9ca3af" />
    <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#9ca3af" />
    {''.join(bars)}
    <rect x="{width - 190}" y="18" width="12" height="12" fill="#2563eb" /><text x="{width - 172}" y="29" font-size="12" fill="#111827">p50</text>
    <rect x="{width - 130}" y="18" width="12" height="12" fill="#dc2626" /><text x="{width - 112}" y="29" font-size="12" fill="#111827">p95</text>
    <text x="20" y="{margin_top + plot_h / 2:.1f}" text-anchor="middle" font-size="13" fill="#374151" transform="rotate(-90 20 {margin_top + plot_h / 2:.1f})">Latency (ms)</text>
  </g>
</svg>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-csv", default="openfaas_lusearch.csv")
    parser.add_argument("--out-dir", default="docs/figures")
    args = parser.parse_args()

    root = Path.cwd()
    out_dir = root / args.out_dir
    series = [
        load_java_csv(root / args.java_csv),
        load_json_result("Go baseline hot", root / "prototypes/go-pgo-serverless/results/baseline-hot.json"),
        load_json_result("Go PGO hot", root / "prototypes/go-pgo-serverless/results/pgo-hot.json"),
        load_json_result(".NET IL hot", root / "prototypes/dotnet-readytorun-pgo/results/il-hot.json"),
        load_json_result(".NET ReadyToRun hot", root / "prototypes/dotnet-readytorun-pgo/results/r2r-hot.json"),
        load_json_result("Go baseline mixed", root / "prototypes/go-pgo-serverless/results/baseline-mixed.json"),
        load_json_result("Go PGO mixed", root / "prototypes/go-pgo-serverless/results/pgo-mixed.json"),
        load_json_result(".NET IL mixed", root / "prototypes/dotnet-readytorun-pgo/results/il-mixed.json"),
        load_json_result(".NET ReadyToRun mixed", root / "prototypes/dotnet-readytorun-pgo/results/r2r-mixed.json"),
    ]

    curve_series = series[:5]
    line_svg(curve_series, out_dir / "jvm-go-dotnet-invocation-curves.svg")
    bar_svg(series, out_dir / "jvm-go-dotnet-p50-p95.svg")
    (out_dir / "jvm-go-dotnet-comparison-summary.json").write_text(
        json.dumps(
            [
                {key: value for key, value in item.items() if key != "times_ms"}
                | {"times_ms": item["times_ms"]}
                for item in series
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_dir / 'jvm-go-dotnet-invocation-curves.svg'}")
    print(f"wrote {out_dir / 'jvm-go-dotnet-p50-p95.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
