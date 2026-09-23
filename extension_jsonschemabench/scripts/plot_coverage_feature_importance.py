#!/usr/bin/env python3
"""Plot coverage prediction feature importances as SVG bar charts."""

from __future__ import annotations

import argparse
import csv
import html
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction" / "modeles_predictifs" / "outlines"

PALETTE = {
    "under": "#2F6BFF",
    "over": "#D96C06",
    "grid": "#D9DEE5",
    "text": "#1F2933",
    "muted": "#5C6670",
    "bg": "#FFFFFF",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--top-n", type=int, default=25)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_feature_list(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def original_feature_name(transformed_feature: str, selected_features: list[str]) -> str:
    for feature in sorted(selected_features, key=len, reverse=True):
        if transformed_feature == feature:
            return feature
        if transformed_feature.startswith(f"{feature}_") or transformed_feature.startswith(f"{feature}="):
            return feature
    return transformed_feature


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    total = sum(to_float(row.get("importance")) for row in rows)
    for row in rows:
        importance = to_float(row.get("importance"))
        out.append(
            {
                "model": row.get("model", ""),
                "feature": row.get("feature", ""),
                "importance": importance,
                "importance_share": importance / total if total else 0.0,
                "importance_type": row.get("importance_type", ""),
            }
        )
    return sorted(out, key=lambda row: row["importance"], reverse=True)


def grouped_rows(rows: list[dict[str, Any]], selected_features: list[str]) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    top_component: dict[str, tuple[str, float]] = {}
    total_importance = sum(row["importance"] for row in rows)
    for row in rows:
        feature = original_feature_name(str(row["feature"]), selected_features)
        importance = float(row["importance"])
        totals[feature] += importance
        if feature not in top_component or importance > top_component[feature][1]:
            top_component[feature] = (str(row["feature"]), importance)
    out = []
    for feature, importance in totals.items():
        component, component_importance = top_component[feature]
        out.append(
            {
                "feature": feature,
                "importance": importance,
                "importance_share": importance / total_importance if total_importance else 0.0,
                "top_transformed_feature": component,
                "top_transformed_importance": component_importance,
            }
        )
    return sorted(out, key=lambda row: row["importance"], reverse=True)


def svg_text(x: float, y: float, text: Any, size: int = 12, anchor: str = "start", weight: str = "400", color: str = "text") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" fill="{PALETTE[color]}" text-anchor="{anchor}" font-weight="{weight}">'
        f"{html.escape(str(text))}</text>"
    )


def truncate(text: str, limit: int = 58) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "..."


def bar_svg(path: Path, title: str, rows: list[dict[str, Any]], color: str, top_n: int) -> None:
    rows = rows[:top_n]
    width = 1180
    height = max(320, 100 + 31 * len(rows))
    left = 385
    right = 115
    top = 70
    bottom = 45
    plot_w = width - left - right
    max_share = max((float(row["importance_share"]) for row in rows), default=1.0)
    max_share = max_share if max_share > 0 else 1.0
    body: list[str] = []
    body.append(f'<rect width="100%" height="100%" fill="{PALETTE["bg"]}"/>')
    body.append(svg_text(28, 34, title, 18, weight="700"))
    body.append(svg_text(28, 54, "Bars show share of total model importance.", 11, color="muted"))
    for i in range(6):
        x = left + plot_w * i / 5
        share = max_share * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, height - 16, f"{100 * share:.1f}%", 10, "middle", color="muted"))
    for idx, row in enumerate(rows):
        y = top + idx * 31 + 7
        share = float(row["importance_share"])
        raw = float(row["importance"])
        bar_w = plot_w * share / max_share
        label = truncate(str(row["feature"]))
        body.append(svg_text(left - 12, y + 15, label, 11, "end"))
        body.append(f'<rect x="{left}" y="{y}" width="{max(bar_w, 1):.2f}" height="19" rx="3" fill="{PALETTE[color]}"/>')
        body.append(svg_text(left + bar_w + 7, y + 15, f"{100 * share:.2f}% ({raw:.4g})", 10))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
        + "".join(body)
        + "</svg>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def write_index(path: Path, generated: list[tuple[str, Path]]) -> None:
    lines = [
        "<!doctype html>",
        '<meta charset="utf-8">',
        "<title>Coverage Prediction Feature Importance</title>",
        '<body style="font-family: Inter, Arial, sans-serif; margin: 24px; color: #1F2933;">',
        "<h1>Coverage Prediction Feature Importance</h1>",
    ]
    for title, svg_path in generated:
        rel = svg_path.name
        lines.append(f"<h2>{html.escape(title)}</h2>")
        lines.append(f'<img src="{html.escape(rel)}" style="max-width: 100%; height: auto;">')
    lines.append("</body>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    plot_dir = output_root / "plots" / "feature_importance"
    generated: list[tuple[str, Path]] = []
    for target in ("under", "over"):
        rows = normalize_rows(read_csv(output_root / "metrics" / f"{target}_feature_importance.csv"))
        selected_features = read_feature_list(output_root / "modeling" / f"selected_{target}_features.txt")
        grouped = grouped_rows(rows, selected_features)
        write_csv(
            plot_dir / f"{target}_grouped_feature_importance.csv",
            grouped,
            ["feature", "importance", "importance_share", "top_transformed_feature", "top_transformed_importance"],
        )
        color = "under" if target == "under" else "over"
        detailed_path = plot_dir / f"{target}_top{args.top_n}_feature_importance.svg"
        grouped_path = plot_dir / f"{target}_top{args.top_n}_grouped_feature_importance.svg"
        model = rows[0]["model"] if rows else "model"
        bar_svg(detailed_path, f"{target.upper()} feature importance - {model}", rows, color, args.top_n)
        bar_svg(grouped_path, f"{target.upper()} grouped feature importance - {model}", grouped, color, args.top_n)
        generated.extend(
            [
                (f"{target.upper()} detailed", detailed_path),
                (f"{target.upper()} grouped", grouped_path),
            ]
        )
    write_index(plot_dir / "feature_importance_index.html", generated)
    print(f"Wrote feature-importance plots to {plot_dir}")


if __name__ == "__main__":
    main()
