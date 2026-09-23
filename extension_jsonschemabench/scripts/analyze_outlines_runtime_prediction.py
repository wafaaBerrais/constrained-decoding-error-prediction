#!/usr/bin/env python3
"""Analyze runtime-only coverage-prediction signals and errors."""

from __future__ import annotations

import argparse
import csv
import html
import math
from collections import Counter
from pathlib import Path
from typing import Any

import joblib

from build_outlines_coverage_prediction import CATEGORICAL_FEATURES, make_feature_matrix


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction" / "modeles_predictifs" / "outlines"

PALETTE = {
    "blue": "#2F6BFF",
    "red": "#C43C39",
    "orange": "#D96C06",
    "grid": "#D9DEE5",
    "text": "#1F2933",
    "bg": "#FFFFFF",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--framework-label", default=None)
    return parser.parse_args()


def framework_label(output_root: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    name = output_root.name.lower()
    if name == "xgr":
        return "XGR"
    if name == "guidance":
        return "Guidance"
    if name == "outlines":
        return "Outlines"
    return output_root.name


def as_float(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    text = str(value).strip().lower()
    if text == "true":
        return 1.0
    if text == "false":
        return 0.0
    if text == "":
        return 0.0
    try:
        number = float(text)
    except ValueError:
        return 0.0
    return number if math.isfinite(number) else 0.0


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def feature_kind(rows: list[dict[str, Any]], feature: str) -> str:
    if feature in CATEGORICAL_FEATURES:
        return "categorical"
    values = {str(row.get(feature, "")).lower() for row in rows if str(row.get(feature, "")) != ""}
    if values and values <= {"true", "false"}:
        return "boolean"
    for value in values:
        try:
            float(value)
        except ValueError:
            return "categorical"
    return "numeric"


def mean(rows: list[dict[str, Any]], feature: str) -> float:
    return sum(as_float(row.get(feature, "")) for row in rows) / len(rows) if rows else 0.0


def true_rate(rows: list[dict[str, Any]], feature: str) -> float:
    return sum(str(row.get(feature, "")).lower() == "true" for row in rows) / len(rows) if rows else 0.0


def numeric_boolean_differences(
    rows: list[dict[str, Any]],
    features: list[str],
    positive_group: str,
    negative_group: str,
) -> list[dict[str, Any]]:
    positive = [row for row in rows if row["_analysis_group"] == positive_group]
    negative = [row for row in rows if row["_analysis_group"] == negative_group]
    out: list[dict[str, Any]] = []
    for feature in features:
        kind = feature_kind(rows, feature)
        if kind == "categorical":
            continue
        if kind == "boolean":
            positive_value = true_rate(positive, feature)
            negative_value = true_rate(negative, feature)
            unit = "true_rate"
        else:
            positive_value = mean(positive, feature)
            negative_value = mean(negative, feature)
            unit = "mean"
        out.append(
            {
                "feature": feature,
                "kind": kind,
                "unit": unit,
                f"{positive_group}_value": positive_value,
                f"{negative_group}_value": negative_value,
                "difference": positive_value - negative_value,
                "abs_difference": abs(positive_value - negative_value),
            }
        )
    return sorted(out, key=lambda row: float(row["abs_difference"]), reverse=True)


def categorical_profiles(rows: list[dict[str, Any]], features: list[str], groups: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for feature in features:
        if feature_kind(rows, feature) != "categorical":
            continue
        for group in groups:
            members = [row for row in rows if row["_analysis_group"] == group]
            counts = Counter(str(row.get(feature, "")) if str(row.get(feature, "")) else "absent" for row in members)
            for value, count in counts.most_common(12):
                out.append(
                    {
                        "feature": feature,
                        "group": group,
                        "value": value,
                        "count": count,
                        "share": count / len(members) if members else 0.0,
                    }
                )
    return out


def svg_text(x: float, y: float, text: Any, size: int = 12, anchor: str = "start", weight: str = "400") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" fill="{PALETTE["text"]}" text-anchor="{anchor}" font-weight="{weight}">'
        f"{html.escape(str(text))}</text>"
    )


def svg_doc(width: int, height: int, title: str, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
        f'<rect width="100%" height="100%" fill="{PALETTE["bg"]}"/>'
        f"{svg_text(24, 30, title, 17, weight='700')}"
        + "".join(body)
        + "</svg>\n"
    )


def nice_max(value: float) -> float:
    if value <= 0 or not math.isfinite(value):
        return 1.0
    exponent = math.floor(math.log10(value))
    base = 10**exponent
    for step in (1, 2, 5, 10):
        if value <= step * base:
            return step * base
    return value


def bar_svg(path: Path, title: str, rows: list[tuple[str, float]], x_label: str, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows[:25]
    width, height = 1060, max(260, 84 + 34 * len(rows))
    left, right, top, bottom = 430, 42, 54, 44
    plot_w = width - left - right
    max_v = nice_max(max((abs(value) for _, value in rows), default=1))
    zero_x = left + plot_w / 2
    body: list[str] = []
    for i in range(6):
        x = left + plot_w * i / 5
        value = -max_v + 2 * max_v * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, height - 18, f"{value:.2g}", 10, "middle"))
    body.append(f'<line x1="{zero_x:.2f}" y1="{top}" x2="{zero_x:.2f}" y2="{height-bottom}" stroke="{PALETTE["text"]}" stroke-width="1"/>')
    for idx, (label, value) in enumerate(rows):
        y = top + idx * 34 + 8
        w = (plot_w / 2) * abs(value) / max_v if max_v else 0
        x = zero_x if value >= 0 else zero_x - w
        body.append(svg_text(left - 10, y + 15, str(label)[:62], 11, "end"))
        body.append(f'<rect x="{x:.2f}" y="{y}" width="{max(w, 1):.2f}" height="20" rx="3" fill="{PALETTE[color]}"/>')
        value_x = x + w + 7 if value >= 0 else x - 7
        anchor = "start" if value >= 0 else "end"
        body.append(svg_text(value_x, y + 15, f"{value:.3g}", 11, anchor))
    body.append(svg_text(left + plot_w / 2, height - 4, x_label, 11, "middle"))
    path.write_text(svg_doc(width, height, title, body), encoding="utf-8")


def add_predictions(rows: list[dict[str, Any]], output_root: Path, target: str) -> tuple[str, float]:
    label = f"y_{target}"
    model = joblib.load(output_root / "models" / f"{target}_model.pkl")
    threshold = float(model["threshold"])
    split_ids = set(str(schema_id) for schema_id in model["split_schema_ids"]["test"])
    test_rows = [row for row in rows if str(row["schema_id"]) in split_ids]
    scores = model["pipeline"].predict_proba(make_feature_matrix(test_rows, model["selected_features"]))[:, 1]
    by_key = {(row["schema_id"], row["test_id"]): row for row in test_rows}
    for row, score in zip(test_rows, scores):
        y_true = int(row[label])
        y_pred = int(score >= threshold)
        row["predicted_probability"] = score
        row["predicted_class"] = y_pred
        row["_prediction_bucket"] = "TP" if y_true and y_pred else "FN" if y_true else "FP" if y_pred else "TN"
    for row in rows:
        key = (row["schema_id"], row["test_id"])
        if key in by_key:
            row["_analysis_group"] = by_key[key]["_prediction_bucket"]
        else:
            row["_analysis_group"] = "not_test_split"
    return str(model["model_name"]), threshold


def analyze_target(output_root: Path, analysis_root: Path, target: str, label_text: str) -> dict[str, Any]:
    target_root = analysis_root / target
    plots_root = target_root / "plots"
    rows = read_csv(output_root / "modeling" / f"{target}_dataset.csv")
    rows = [row for row in rows if row.get("actual_result") in {"passed", "failed"}]
    label = f"y_{target}"
    for row in rows:
        row["_analysis_group"] = "positive" if row[label] == "1" else "negative"
    metadata = {
        "dataset",
        "schema_id",
        "test_id",
        "test_index",
        "failure_type",
        "expected_validity",
        label,
        "outlines_result",
        "actual_result",
    }
    features = [feature for feature in rows[0] if feature not in metadata]
    class_diffs = numeric_boolean_differences(rows, features, "positive", "negative")
    write_csv(target_root / "class_numeric_boolean_differences.csv", class_diffs)
    write_csv(target_root / "class_categorical_profiles.csv", categorical_profiles(rows, features, ["positive", "negative"]))
    bar_svg(
        plots_root / "top_class_differences.svg",
        f"{label_text} {target.upper()} runtime: positive minus negative",
        [(str(row["feature"]), float(row["difference"])) for row in class_diffs],
        "positive - negative",
        "orange",
    )

    model_name, threshold = add_predictions(rows, output_root, target)
    test_rows = [row for row in rows if row["_analysis_group"] in {"TP", "FN", "FP", "TN"}]
    error_diffs: list[dict[str, Any]] = []
    error_diffs.extend({**row, "comparison": "FN_vs_TP"} for row in numeric_boolean_differences(test_rows, features, "FN", "TP"))
    error_diffs.extend({**row, "comparison": "FP_vs_TN"} for row in numeric_boolean_differences(test_rows, features, "FP", "TN"))
    write_csv(target_root / "prediction_error_numeric_boolean_differences.csv", error_diffs)
    write_csv(target_root / "prediction_error_categorical_profiles.csv", categorical_profiles(test_rows, features, ["FN", "TP", "FP", "TN"]))
    fn_rows = [row for row in error_diffs if row["comparison"] == "FN_vs_TP"]
    fp_rows = [row for row in error_diffs if row["comparison"] == "FP_vs_TN"]
    bar_svg(
        plots_root / "top_fn_vs_tp_differences.svg",
        f"{label_text} {target.upper()}: false negatives minus true positives",
        [(str(row["feature"]), float(row["difference"])) for row in fn_rows],
        "FN - TP",
        "red",
    )
    bar_svg(
        plots_root / "top_fp_vs_tn_differences.svg",
        f"{label_text} {target.upper()}: false positives minus true negatives",
        [(str(row["feature"]), float(row["difference"])) for row in fp_rows],
        "FP - TN",
        "blue",
    )
    return {
        "target": target,
        "rows": len(rows),
        "class_counts": dict(Counter("positive" if row[label] == "1" else "negative" for row in rows)),
        "model_name": model_name,
        "threshold": threshold,
        "test_buckets": dict(Counter(row["_analysis_group"] for row in test_rows)),
        "top_class_diffs": class_diffs[:10],
    }


def write_report(path: Path, summaries: list[dict[str, Any]], label_text: str) -> None:
    lines = [
        f"# {label_text} Runtime Prediction Analysis",
        "",
        "This analysis excludes `compile_error` rows and focuses on runtime `passed` / `failed` results.",
        "",
    ]
    for summary in summaries:
        lines.extend(
            [
                f"## {summary['target'].upper()}",
                "",
                f"- Runtime rows: {summary['rows']}",
                f"- Class counts: {summary['class_counts']}",
                f"- Selected model: `{summary['model_name']}`",
                f"- Decision threshold: `{summary['threshold']:.4g}`",
                f"- Test prediction buckets: {summary['test_buckets']}",
                "",
                "Strongest class separators:",
                "",
            ]
        )
        for row in summary["top_class_diffs"]:
            lines.append(
                f"- `{row['feature']}` ({row['unit']}): "
                f"positive={float(row['positive_value']):.3g}, "
                f"negative={float(row['negative_value']):.3g}, "
                f"diff={float(row['difference']):.3g}."
            )
        lines.append("")
        lines.extend(
            [
                "Files:",
                "",
                f"- `{summary['target']}/class_numeric_boolean_differences.csv`",
                f"- `{summary['target']}/class_categorical_profiles.csv`",
                f"- `{summary['target']}/prediction_error_numeric_boolean_differences.csv`",
                f"- `{summary['target']}/prediction_error_categorical_profiles.csv`",
                f"- `{summary['target']}/plots/top_class_differences.svg`",
                f"- `{summary['target']}/plots/top_fn_vs_tp_differences.svg`",
                f"- `{summary['target']}/plots/top_fp_vs_tn_differences.svg`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    label_text = framework_label(output_root, args.framework_label)
    analysis_root = output_root / "analyse"
    analysis_root.mkdir(parents=True, exist_ok=True)
    summaries = [analyze_target(output_root, analysis_root, target, label_text) for target in ("over", "under")]
    write_report(analysis_root / "README.md", summaries, label_text)
    print(f"[runtime-analysis] done: {analysis_root}")


if __name__ == "__main__":
    main()
