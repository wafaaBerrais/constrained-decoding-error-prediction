#!/usr/bin/env python3
"""Build v2 conditional analyses from refined feature tables."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = ROOT / "maskbench" / "data"

MIN_SUPPORT_TESTS = 20
MIN_SUPPORT_SCHEMAS = 10

COOCCURRENCE_KEYWORDS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "patternProperties",
    "additionalProperties",
    "properties",
    "required",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "enum",
    "const",
)

CONTEXTS = {
    "numeric": [
        "numeric_boundary_case",
        "numeric_target_type",
        "numeric_parent_keyword",
        "numeric_is_in_properties",
        "numeric_property_required",
        "numeric_has_default",
        "numeric_has_min_and_max",
    ],
    "patternProperties": [
        "additionalProperties_value",
        "patternProperties_with_properties",
        "patternProperties_has_additionalProperties",
        "patternProperties_regex_has_anchor",
        "patternProperties_regex_has_dotstar",
        "patternProperties_regex_has_alternation",
        "patternProperties_regex_has_charclass",
        "instance_has_unmatched_keys",
        "instance_matching_pattern_keys_count",
    ],
    "combinators": [
        "combinator_type",
        "combinator_branch_count_bucket",
        "allOf_satisfied_branch_ratio",
        "allOf_satisfied_branch_count_bucket",
        "anyOf_satisfied_branch_count",
        "anyOf_satisfied_branch_count_bucket",
        "oneOf_satisfied_branch_count",
        "oneOf_satisfied_branch_count_bucket",
        "branches_have_properties",
        "branches_have_required",
        "branches_have_not",
        "branches_have_enum",
        "branches_overlapping_properties",
        "branches_conflicting_types",
    ],
    "not": [
        "not_parent_keyword",
        "not_target_type",
        "not_contains_enum",
        "not_contains_const",
        "not_contains_pattern",
        "not_contains_properties",
        "not_contains_required",
        "instance_satisfies_not_subschema",
    ],
}

PALETTE = {
    "blue": "#2F6BFF",
    "teal": "#008C7D",
    "orange": "#D96C06",
    "red": "#C43C39",
    "purple": "#7557B8",
    "gray": "#5C6670",
    "grid": "#D9DEE5",
    "text": "#1F2933",
    "bg": "#FFFFFF",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="Github_medium")
    parser.add_argument("--input-dir", default=None, help="Default: data/<dataset>/refined_feature_analysis.")
    parser.add_argument("--output-data-dir", default=None, help="Default: data/<dataset>/refined_feature_analysis_v2.")
    parser.add_argument("--output-plot-dir", default=None, help="Default: plots/<dataset>/refined_feature_analysis_v2.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
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
            writer.writerow({key: format_value(row.get(key, "")) for key in fieldnames})


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.6g}"
    if value is None:
        return ""
    return str(value)


def pct(part: float, total: float) -> float:
    return part / total if total else 0.0


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def context_value(row: dict[str, str], feature: str) -> str:
    value = row.get(feature, "")
    return value if value != "" else "absent"


def is_invalid(row: dict[str, str]) -> bool:
    return row.get("expected_validity") == "invalid"


def is_valid(row: dict[str, str]) -> bool:
    return row.get("expected_validity") == "valid"


def is_low_support(schema_count: int, test_count: int) -> bool:
    return schema_count < MIN_SUPPORT_SCHEMAS or test_count < MIN_SUPPORT_TESTS


def conditional_under_risk(test_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    invalid_rows = [row for row in test_rows if is_invalid(row)]
    baseline = pct(sum(1 for row in invalid_rows if row.get("failure_type") == "UNDER"), len(invalid_rows))
    out: list[dict[str, Any]] = []
    for family, features in CONTEXTS.items():
        for feature in features:
            groups: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in invalid_rows:
                groups[context_value(row, feature)].append(row)
            for value, members in sorted(groups.items()):
                support_schemas = len({row["schema_id"] for row in members})
                under_count = sum(1 for row in members if row.get("failure_type") == "UNDER")
                rate = pct(under_count, len(members))
                out.append(
                    {
                        "context_family": family,
                        "context_feature": feature,
                        "context_value": value,
                        "support_invalid_tests": len(members),
                        "support_schemas": support_schemas,
                        "under_count": under_count,
                        "under_rate_invalid_only": rate,
                        "baseline_under_rate_invalid_only": baseline,
                        "under_lift_invalid_only": rate / baseline if baseline else 0.0,
                        "low_support": is_low_support(support_schemas, len(members)),
                    }
                )
    return sorted(out, key=lambda row: (row["context_family"], row["context_feature"], row["context_value"]))


def conditional_over_risk(test_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    valid_rows = [row for row in test_rows if is_valid(row)]
    baseline = pct(sum(1 for row in valid_rows if row.get("failure_type") == "OVER"), len(valid_rows))
    out: list[dict[str, Any]] = []
    for family, features in CONTEXTS.items():
        for feature in features:
            groups: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in valid_rows:
                groups[context_value(row, feature)].append(row)
            for value, members in sorted(groups.items()):
                support_schemas = len({row["schema_id"] for row in members})
                over_count = sum(1 for row in members if row.get("failure_type") == "OVER")
                rate = pct(over_count, len(members))
                out.append(
                    {
                        "context_family": family,
                        "context_feature": feature,
                        "context_value": value,
                        "support_valid_tests": len(members),
                        "support_schemas": support_schemas,
                        "over_count": over_count,
                        "over_rate_valid_only": rate,
                        "baseline_over_rate_valid_only": baseline,
                        "over_lift_valid_only": rate / baseline if baseline else 0.0,
                        "low_support": is_low_support(support_schemas, len(members)),
                    }
                )
    return sorted(out, key=lambda row: (row["context_family"], row["context_feature"], row["context_value"]))


def schema_level_risk(schema_rows: list[dict[str, str]], test_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    schema_status = {
        row["schema_id"]: {
            "has_under": row.get("has_under") == "true",
            "has_over": row.get("has_over") == "true",
        }
        for row in schema_rows
    }
    baseline_under = pct(sum(1 for status in schema_status.values() if status["has_under"]), len(schema_status))
    baseline_over = pct(sum(1 for status in schema_status.values() if status["has_over"]), len(schema_status))
    out: list[dict[str, Any]] = []
    for family, features in CONTEXTS.items():
        for feature in features:
            values_by_schema: dict[str, set[str]] = defaultdict(set)
            source_rows = schema_rows if feature in schema_rows[0] and not feature.startswith("instance_") and "satisfied_branch" not in feature else test_rows
            for row in source_rows:
                values_by_schema[row["schema_id"]].add(context_value(row, feature))
            groups: dict[str, set[str]] = defaultdict(set)
            for schema_id, values in values_by_schema.items():
                for value in values:
                    groups[value].add(schema_id)
            for value, schema_ids in sorted(groups.items()):
                under_schemas = sum(1 for schema_id in schema_ids if schema_status.get(schema_id, {}).get("has_under"))
                over_schemas = sum(1 for schema_id in schema_ids if schema_status.get(schema_id, {}).get("has_over"))
                under_rate = pct(under_schemas, len(schema_ids))
                over_rate = pct(over_schemas, len(schema_ids))
                out.append(
                    {
                        "context_family": family,
                        "context_feature": feature,
                        "context_value": value,
                        "support_schemas": len(schema_ids),
                        "schemas_with_under": under_schemas,
                        "schemas_with_over": over_schemas,
                        "schema_under_rate": under_rate,
                        "schema_over_rate": over_rate,
                        "baseline_schema_under_rate": baseline_under,
                        "baseline_schema_over_rate": baseline_over,
                        "schema_under_lift": under_rate / baseline_under if baseline_under else 0.0,
                        "schema_over_lift": over_rate / baseline_over if baseline_over else 0.0,
                    }
                )
    return sorted(out, key=lambda row: (row["context_family"], row["context_feature"], row["context_value"]))


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


def bar_svg(path: Path, title: str, rows: list[tuple[str, float, int, int]], x_label: str, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows[:40]
    width, height = 1060, max(280, 86 + 36 * len(rows))
    left, right, top, bottom = 330, 48, 56, 46
    plot_w = width - left - right
    max_v = nice_max(max((value for _, value, _, _ in rows), default=1))
    body: list[str] = []
    for i in range(6):
        x = left + plot_w * i / 5
        val = max_v * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, height - 18, f"{val:.2g}", 10, "middle"))
    for idx, (label, value, tests, schemas) in enumerate(rows):
        y = top + idx * 36 + 8
        w = plot_w * value / max_v if max_v else 0
        body.append(svg_text(left - 10, y + 15, str(label)[:45], 11, "end"))
        body.append(f'<rect x="{left}" y="{y}" width="{max(w, 1):.2f}" height="21" rx="3" fill="{PALETTE[color]}"/>')
        body.append(svg_text(left + w + 7, y + 15, f"{value:.3g}  n={tests}, s={schemas}", 11))
    body.append(svg_text(left + plot_w / 2, height - 4, x_label, 11, "middle"))
    path.write_text(svg_doc(width, height, title, body), encoding="utf-8")


def heatmap_svg(path: Path, title: str, rows: list[dict[str, Any]], x_key: str, y_key: str, value_key: str, support_key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xs = sorted({str(row[x_key]) for row in rows})
    ys = sorted({str(row[y_key]) for row in rows})
    width = max(680, 190 + 84 * len(xs))
    height = max(420, 140 + 52 * len(ys))
    left, top, cell_w, cell_h = 170, 72, 80, 48
    max_v = max((to_float(row[value_key]) for row in rows), default=1.0)
    by_pair = {(str(row[x_key]), str(row[y_key])): row for row in rows}
    body: list[str] = []
    for i, label in enumerate(xs):
        body.append(svg_text(left + i * cell_w + cell_w / 2, top - 12, label[:12], 10, "middle"))
    for j, label in enumerate(ys):
        body.append(svg_text(left - 10, top + j * cell_h + 29, label[:20], 10, "end"))
    for j, y_label in enumerate(ys):
        for i, x_label in enumerate(xs):
            row = by_pair.get((x_label, y_label))
            value = to_float(row[value_key]) if row else 0.0
            support = int(to_float(row[support_key])) if row else 0
            opacity = 0.08 + 0.82 * (value / max_v if max_v else 0)
            body.append(f'<rect x="{left + i * cell_w}" y="{top + j * cell_h}" width="{cell_w-2}" height="{cell_h-2}" fill="{PALETTE["blue"]}" opacity="{opacity:.3f}"/>')
            body.append(svg_text(left + i * cell_w + cell_w / 2, top + j * cell_h + 21, f"{value:.2f}", 10, "middle", "700"))
            body.append(svg_text(left + i * cell_w + cell_w / 2, top + j * cell_h + 37, f"n={support}", 9, "middle"))
    path.write_text(svg_doc(width, height, title, body), encoding="utf-8")


def scatter_svg(path: Path, title: str, rows: list[tuple[str, float, float]], x_label: str, y_label: str, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 900, 560
    left, right, top, bottom = 82, 34, 58, 68
    plot_w, plot_h = width - left - right, height - top - bottom
    points = [(label, max(x, 1.0), y) for label, x, y in rows if y > 0]
    max_x = max((math.log10(x) for _, x, _ in points), default=1.0)
    min_x = min((math.log10(x) for _, x, _ in points), default=0.0)
    max_y = nice_max(max((y for _, _, y in points), default=1.0))
    body: list[str] = []
    for i in range(6):
        y = top + plot_h - plot_h * i / 5
        val = max_y * i / 5
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(left - 10, y + 4, f"{val:.2g}", 10, "end"))
    for label, x, y in points:
        lx = math.log10(x)
        px = left + (lx - min_x) / (max_x - min_x or 1) * plot_w
        py = top + plot_h - (y / max_y if max_y else 0) * plot_h
        body.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{PALETTE[color]}" opacity="0.72"><title>{html.escape(label)}</title></circle>')
    body.append(svg_text(left + plot_w / 2, height - 18, x_label + " (log10)", 11, "middle"))
    body.append(svg_text(20, top + plot_h / 2, y_label, 11))
    path.write_text(svg_doc(width, height, title, body), encoding="utf-8")


def conditional_rows_2d(rows: list[dict[str, str]], x_feature: str, y_feature: str, target: str) -> list[dict[str, Any]]:
    if target == "under":
        base = [row for row in rows if is_invalid(row)]
        failure = "UNDER"
        value_key = "under_rate_invalid_only"
        support_key = "support_invalid_tests"
    else:
        base = [row for row in rows if is_valid(row)]
        failure = "OVER"
        value_key = "over_rate_valid_only"
        support_key = "support_valid_tests"
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in base:
        groups[(context_value(row, x_feature), context_value(row, y_feature))].append(row)
    out = []
    for (x_value, y_value), members in sorted(groups.items()):
        out.append(
            {
                x_feature: x_value,
                y_feature: y_value,
                value_key: pct(sum(1 for row in members if row.get("failure_type") == failure), len(members)),
                support_key: len(members),
            }
        )
    return out


def controlled_numeric_default_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    base = [row for row in rows if is_invalid(row)]
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in base:
        control_context = (
            f"{context_value(row, 'numeric_boundary_case')} | "
            f"in_properties={context_value(row, 'numeric_is_in_properties')} | "
            f"required={context_value(row, 'numeric_property_required')}"
        )
        groups[(context_value(row, "numeric_has_default"), control_context)].append(row)
    out = []
    for (default_value, control_context), members in sorted(groups.items()):
        out.append(
            {
                "numeric_has_default": default_value,
                "numeric_control_context": control_context,
                "under_rate_invalid_only": pct(sum(1 for row in members if row.get("failure_type") == "UNDER"), len(members)),
                "support_invalid_tests": len(members),
            }
        )
    return out


def rows_for_bar(risk_rows: list[dict[str, Any]], feature: str, value_key: str, support_key: str) -> list[tuple[str, float, int, int]]:
    selected = [row for row in risk_rows if row["context_feature"] == feature]
    selected = sorted(selected, key=lambda row: row[value_key], reverse=True)
    return [(row["context_value"], row[value_key], int(row[support_key]), int(row["support_schemas"])) for row in selected]


def write_numeric_plots(plot_dir: Path, test_rows: list[dict[str, str]], under_rows: list[dict[str, Any]]) -> None:
    numeric_dir = plot_dir / "numeric"

    bar_svg(numeric_dir / "under_invalid_only_by_numeric_boundary_case.svg", "UNDER among invalid tests by numeric_boundary_case", rows_for_bar(under_rows, "numeric_boundary_case", "under_rate_invalid_only", "support_invalid_tests"), "under_rate_invalid_only", "red")
    heatmap_svg(numeric_dir / "under_invalid_only_boundary_case_by_target_type.svg", "UNDER invalid-only: boundary_case x target_type", conditional_rows_2d(test_rows, "numeric_target_type", "numeric_boundary_case", "under"), "numeric_target_type", "numeric_boundary_case", "under_rate_invalid_only", "support_invalid_tests")
    heatmap_svg(numeric_dir / "under_invalid_only_boundary_case_by_parent_keyword.svg", "UNDER invalid-only: boundary_case x parent_keyword", conditional_rows_2d(test_rows, "numeric_parent_keyword", "numeric_boundary_case", "under"), "numeric_parent_keyword", "numeric_boundary_case", "under_rate_invalid_only", "support_invalid_tests")
    heatmap_svg(numeric_dir / "under_invalid_only_in_properties_by_property_required.svg", "UNDER invalid-only: in_properties x property_required", conditional_rows_2d(test_rows, "numeric_property_required", "numeric_is_in_properties", "under"), "numeric_property_required", "numeric_is_in_properties", "under_rate_invalid_only", "support_invalid_tests")
    heatmap_svg(numeric_dir / "under_invalid_only_default_by_boundary_properties_required.svg", "UNDER invalid-only: default controlled by boundary/properties/required", controlled_numeric_default_rows(test_rows), "numeric_has_default", "numeric_control_context", "under_rate_invalid_only", "support_invalid_tests")
    for feature in ("numeric_is_in_properties", "numeric_property_required", "numeric_has_default", "numeric_has_min_and_max"):
        bar_svg(numeric_dir / f"under_invalid_only_by_{feature}.svg", f"UNDER invalid-only by {feature}", rows_for_bar(under_rows, feature, "under_rate_invalid_only", "support_invalid_tests"), "under_rate_invalid_only", "red")
    numeric_dist = []
    for failure_type in ("CORRECT_INVALID", "UNDER", "CORRECT_VALID", "OVER"):
        members = [row for row in test_rows if row.get("failure_type") == failure_type]
        avg = sum(to_float(row.get("numeric_keyword_count")) for row in members) / len(members) if members else 0.0
        numeric_dist.append((failure_type, avg, len(members), len({row["schema_id"] for row in members})))
    bar_svg(numeric_dir / "numeric_keyword_count_by_failure_type.svg", "Average numeric_keyword_count by failure_type", numeric_dist, "average numeric_keyword_count", "blue")


def write_under_family_plots(
    plot_dir: Path,
    family: str,
    under_rows: list[dict[str, Any]],
    features: tuple[str, ...],
) -> None:
    family_dir = plot_dir / family
    for feature in features:
        bar_svg(
            family_dir / f"under_invalid_only_by_{feature}.svg",
            f"UNDER invalid-only by {feature}",
            rows_for_bar(under_rows, feature, "under_rate_invalid_only", "support_invalid_tests"),
            "under_rate_invalid_only",
            "red",
        )
    points = [
        (f"{row['context_feature']}={row['context_value']}", float(row["support_invalid_tests"]), float(row["under_lift_invalid_only"]))
        for row in under_rows
        if row["context_family"] == family and not row["low_support"]
    ]
    scatter_svg(
        family_dir / f"support_vs_under_lift_{family}.svg",
        f"{family} support vs UNDER lift",
        points,
        "support_invalid_tests",
        "under_lift_invalid_only",
        "red",
    )


def write_pattern_properties_plots(plot_dir: Path, test_rows: list[dict[str, str]], over_rows: list[dict[str, Any]]) -> None:
    pattern_dir = plot_dir / "patternProperties"

    bar_svg(pattern_dir / "over_valid_only_by_additionalProperties_value.svg", "OVER among valid tests by additionalProperties_value", rows_for_bar(over_rows, "additionalProperties_value", "over_rate_valid_only", "support_valid_tests"), "over_rate_valid_only", "orange")
    bar_svg(pattern_dir / "over_valid_only_by_matching_pattern_keys_count.svg", "OVER among valid tests by matching pattern key count", rows_for_bar(over_rows, "instance_matching_pattern_keys_count", "over_rate_valid_only", "support_valid_tests"), "over_rate_valid_only", "orange")
    heatmap_svg(pattern_dir / "over_valid_only_additionalProperties_by_unmatched_keys.svg", "OVER valid-only: additionalProperties x unmatched keys", conditional_rows_2d(test_rows, "additionalProperties_value", "instance_has_unmatched_keys", "over"), "additionalProperties_value", "instance_has_unmatched_keys", "over_rate_valid_only", "support_valid_tests")
    heatmap_svg(pattern_dir / "over_valid_only_additionalProperties_by_matching_pattern_keys.svg", "OVER valid-only: additionalProperties x matching key count", conditional_rows_2d(test_rows, "additionalProperties_value", "instance_matching_pattern_keys_count", "over"), "additionalProperties_value", "instance_matching_pattern_keys_count", "over_rate_valid_only", "support_valid_tests")
    for feature in ("patternProperties_regex_has_anchor", "patternProperties_regex_has_dotstar", "patternProperties_regex_has_alternation", "patternProperties_regex_has_charclass"):
        bar_svg(pattern_dir / f"over_valid_only_by_{feature}.svg", f"OVER valid-only by {feature}", rows_for_bar(over_rows, feature, "over_rate_valid_only", "support_valid_tests"), "over_rate_valid_only", "orange")
    pattern_points = [
        (f"{row['context_feature']}={row['context_value']}", float(row["support_valid_tests"]), float(row["over_lift_valid_only"]))
        for row in over_rows
        if row["context_family"] == "patternProperties" and not row["low_support"]
    ]
    scatter_svg(pattern_dir / "support_vs_over_lift_patternProperties.svg", "PatternProperties support vs OVER lift", pattern_points, "support_valid_tests", "over_lift_valid_only", "orange")


def write_not_plots(plot_dir: Path, over_rows: list[dict[str, Any]]) -> None:
    not_dir = plot_dir / "not"
    for feature in (
        "not_contains_properties",
        "not_contains_anyOf",
        "not_contains_enum",
        "not_target_type",
        "not_sibling_keyword_count_bucket",
        "not_parent_keyword",
    ):
        bar_svg(
            not_dir / f"over_valid_only_by_{feature}.svg",
            f"OVER valid-only by {feature}",
            rows_for_bar(over_rows, feature, "over_rate_valid_only", "support_valid_tests"),
            "over_rate_valid_only",
            "orange",
        )


def write_combinator_plots(
    plot_dir: Path,
    test_rows: list[dict[str, str]],
    over_rows: list[dict[str, Any]],
) -> None:
    comb_dir = plot_dir / "combinators"

    for feature in (
        "combinator_type",
        "combinator_branch_count_bucket",
        "branches_overlapping_properties",
        "branches_have_properties",
        "branches_have_not",
        "branches_have_enum",
        "branches_have_required",
        "allOf_satisfied_branch_ratio",
        "oneOf_satisfied_branch_count",
        "anyOf_satisfied_branch_count",
    ):
        bar_svg(
            comb_dir / f"over_valid_only_by_{feature}.svg",
            f"OVER valid-only by {feature}",
            rows_for_bar(over_rows, feature, "over_rate_valid_only", "support_valid_tests"),
            "over_rate_valid_only",
            "orange",
        )

    heatmap_svg(
        comb_dir / "over_valid_only_combinator_type_by_branch_count.svg",
        "OVER valid-only: combinator_type x branch_count",
        conditional_rows_2d(test_rows, "combinator_type", "combinator_branch_count_bucket", "over"),
        "combinator_type",
        "combinator_branch_count_bucket",
        "over_rate_valid_only",
        "support_valid_tests",
    )
    for feature in (
        "allOf_satisfied_branch_count_bucket",
        "anyOf_satisfied_branch_count_bucket",
        "oneOf_satisfied_branch_count_bucket",
    ):
        heatmap_svg(
            comb_dir / f"over_valid_only_combinator_type_by_{feature}.svg",
            f"OVER valid-only: combinator_type x {feature}",
            conditional_rows_2d(test_rows, "combinator_type", feature, "over"),
            "combinator_type",
            feature,
            "over_rate_valid_only",
            "support_valid_tests",
        )


def write_plots(plot_dir: Path, test_rows: list[dict[str, str]], under_rows: list[dict[str, Any]], over_rows: list[dict[str, Any]]) -> None:
    summary_dir = plot_dir / "summary"

    write_numeric_plots(plot_dir, test_rows, under_rows)
    write_pattern_properties_plots(plot_dir, test_rows, over_rows)
    write_not_plots(plot_dir, over_rows)
    write_combinator_plots(plot_dir, test_rows, over_rows)

    top_under = sorted([row for row in under_rows if not row["low_support"]], key=lambda row: row["under_lift_invalid_only"], reverse=True)[:20]
    top_over = sorted([row for row in over_rows if not row["low_support"]], key=lambda row: row["over_lift_valid_only"], reverse=True)[:20]
    bar_svg(summary_dir / "top20_under_lift_invalid_only.svg", "Top UNDER contexts by invalid-only lift", [(f"{r['context_feature']}={r['context_value']}", r["under_lift_invalid_only"], r["support_invalid_tests"], r["support_schemas"]) for r in top_under], "under_lift_invalid_only", "red")
    bar_svg(summary_dir / "top20_over_lift_valid_only.svg", "Top OVER contexts by valid-only lift", [(f"{r['context_feature']}={r['context_value']}", r["over_lift_valid_only"], r["support_valid_tests"], r["support_schemas"]) for r in top_over], "over_lift_valid_only", "orange")
    scatter_svg(summary_dir / "support_vs_under_lift_invalid_only.svg", "UNDER support vs invalid-only lift", [(f"{r['context_feature']}={r['context_value']}", r["support_invalid_tests"], r["under_lift_invalid_only"]) for r in under_rows if not r["low_support"]], "support_invalid_tests", "under_lift_invalid_only", "red")
    scatter_svg(summary_dir / "support_vs_over_lift_valid_only.svg", "OVER support vs valid-only lift", [(f"{r['context_feature']}={r['context_value']}", r["support_valid_tests"], r["over_lift_valid_only"]) for r in over_rows if not r["low_support"]], "support_valid_tests", "over_lift_valid_only", "orange")


def schema_keywords(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in COOCCURRENCE_KEYWORDS:
                found.add(key)
            found.update(schema_keywords(value))
    elif isinstance(node, list):
        for item in node:
            found.update(schema_keywords(item))
    return found


def cooccurrence_rows(schema_rows: list[dict[str, str]], data_root: Path, target: str) -> list[tuple[str, str, float]]:
    counts: Counter[tuple[str, str]] = Counter()
    selected = [row for row in schema_rows if row.get("has_under" if target == "under" else "has_over") == "true"]
    for row in selected:
        path = data_root / row["schema_id"]
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        keywords = sorted(schema_keywords(doc.get("schema", doc)).intersection(COOCCURRENCE_KEYWORDS))
        for i, left in enumerate(keywords):
            for right in keywords[i + 1 :]:
                counts[(left, right)] += 1
    return [(left, right, float(count)) for (left, right), count in counts.items()]


def cooccurrence_heatmap(path: Path, title: str, rows: list[tuple[str, str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = list(COOCCURRENCE_KEYWORDS)
    width = 980
    height = 930
    left, top, cell = 190, 76, 48
    max_v = max((value for _, _, value in rows), default=1.0)
    values = {(left, right): value for left, right, value in rows}
    body: list[str] = []
    for i, label in enumerate(labels):
        body.append(svg_text(left + i * cell + cell / 2, top - 10, label[:10], 9, "middle"))
        body.append(svg_text(left - 10, top + i * cell + 29, label, 9, "end"))
    for y, left_label in enumerate(labels):
        for x, right_label in enumerate(labels):
            value = values.get((left_label, right_label), values.get((right_label, left_label), 0.0))
            opacity = 0.06 + 0.84 * (value / max_v if max_v else 0)
            body.append(f'<rect x="{left + x * cell}" y="{top + y * cell}" width="{cell-2}" height="{cell-2}" fill="{PALETTE["blue"]}" opacity="{opacity:.3f}"/>')
            if value:
                body.append(svg_text(left + x * cell + cell / 2, top + y * cell + 28, f"{value:.0f}", 8, "middle"))
    path.write_text(svg_doc(width, height, title, body), encoding="utf-8")


def load_instance(data_root: Path, schema_id: str, test_index: int) -> Any:
    path = data_root / schema_id
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    tests = doc.get("tests", [])
    if 0 <= test_index < len(tests):
        return tests[test_index].get("data")
    return None


def preview_instance(instance: Any, limit: int = 260) -> str:
    text = json.dumps(instance, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def important_values(row: dict[str, str], feature: str) -> str:
    keys = [
        feature,
        "numeric_boundary_case",
        "numeric_target_type",
        "numeric_parent_keyword",
        "additionalProperties_value",
        "instance_has_unmatched_keys",
        "instance_matching_pattern_keys_count",
        "combinator_type",
        "combinator_branch_count_bucket",
        "oneOf_satisfied_branch_count_bucket",
        "anyOf_satisfied_branch_count_bucket",
    ]
    seen: set[str] = set()
    parts = []
    for key in keys:
        if key not in seen and key in row:
            seen.add(key)
            parts.append(f"{key}={row.get(key, '')}")
    return "; ".join(parts)


def top_examples(test_rows: list[dict[str, str]], under_rows: list[dict[str, Any]], over_rows: list[dict[str, Any]], data_root: Path) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    contexts: list[tuple[str, dict[str, Any], str, str]] = []
    contexts.extend(("UNDER", row, "UNDER", "CORRECT_INVALID") for row in sorted([r for r in under_rows if not r["low_support"]], key=lambda r: r["under_lift_invalid_only"], reverse=True)[:10])
    contexts.extend(("OVER", row, "OVER", "CORRECT_VALID") for row in sorted([r for r in over_rows if not r["low_support"]], key=lambda r: r["over_lift_valid_only"], reverse=True)[:10])
    for target, context, problem_type, correct_type in contexts:
        feature = str(context["context_feature"])
        value = str(context["context_value"])
        matching = [row for row in test_rows if context_value(row, feature) == value]
        selected = [row for row in matching if row.get("failure_type") == problem_type][:3]
        selected += [row for row in matching if row.get("failure_type") == correct_type][:3]
        for row in selected:
            test_index = int(float(row.get("test_index", 0) or 0))
            instance = load_instance(data_root, row["schema_id"], test_index)
            examples.append(
                {
                    "context_family": context["context_family"],
                    "context_feature": feature,
                    "context_value": value,
                    "schema_id": row["schema_id"],
                    "test_id": row["test_id"],
                    "test_index": test_index,
                    "expected_validity": row["expected_validity"],
                    "outlines_result": row["outlines_result"],
                    "failure_type": row["failure_type"],
                    "important_feature_values": important_values(row, feature),
                    "schema_path": str(data_root / row["schema_id"]),
                    "instance_preview": preview_instance(instance),
                }
            )
    return examples


def compare_schema_level(top_test_rows: list[dict[str, Any]], schema_rows: list[dict[str, Any]], metric: str) -> list[str]:
    schema_index = {
        (row["context_feature"], row["context_value"]): row
        for row in schema_rows
    }
    lines = []
    for row in top_test_rows[:8]:
        key = (row["context_feature"], row["context_value"])
        schema_row = schema_index.get(key)
        if not schema_row:
            continue
        if metric == "under":
            lines.append(
                f"- `{key[0]}={key[1]}`: test lift {row['under_lift_invalid_only']:.2f}; "
                f"schema lift {schema_row['schema_under_lift']:.2f}; schemas {schema_row['support_schemas']}."
            )
        else:
            lines.append(
                f"- `{key[0]}={key[1]}`: test lift {row['over_lift_valid_only']:.2f}; "
                f"schema lift {schema_row['schema_over_lift']:.2f}; schemas {schema_row['support_schemas']}."
            )
    return lines


def write_report(path: Path, test_rows: list[dict[str, str]], under_rows: list[dict[str, Any]], over_rows: list[dict[str, Any]], schema_risk: list[dict[str, Any]]) -> None:
    valid_rows = [row for row in test_rows if is_valid(row)]
    invalid_rows = [row for row in test_rows if is_invalid(row)]
    under_baseline = pct(sum(1 for row in invalid_rows if row["failure_type"] == "UNDER"), len(invalid_rows))
    over_baseline = pct(sum(1 for row in valid_rows if row["failure_type"] == "OVER"), len(valid_rows))
    top_under = sorted([row for row in under_rows if not row["low_support"]], key=lambda row: row["under_lift_invalid_only"], reverse=True)
    top_over = sorted([row for row in over_rows if not row["low_support"]], key=lambda row: row["over_lift_valid_only"], reverse=True)
    top_pattern = [row for row in top_over if row["context_family"] == "patternProperties"]
    top_comb = [row for row in top_over if row["context_family"] == "combinators"]

    def bullet_under(rows: list[dict[str, Any]], n: int = 8) -> list[str]:
        return [
            f"- `{row['context_feature']}={row['context_value']}`: rate={row['under_rate_invalid_only']:.3f}, "
            f"lift={row['under_lift_invalid_only']:.2f}, invalid_tests={row['support_invalid_tests']}, schemas={row['support_schemas']}."
            for row in rows[:n]
        ]

    def bullet_over(rows: list[dict[str, Any]], n: int = 8) -> list[str]:
        return [
            f"- `{row['context_feature']}={row['context_value']}`: rate={row['over_rate_valid_only']:.3f}, "
            f"lift={row['over_lift_valid_only']:.2f}, valid_tests={row['support_valid_tests']}, schemas={row['support_schemas']}."
            for row in rows[:n]
        ]

    lines = [
        "# Refined Feature Analysis v2",
        "",
        "## Baseline",
        "",
        f"- Total tests: {len(test_rows)}",
        f"- Total valid tests: {len(valid_rows)}",
        f"- Total invalid tests: {len(invalid_rows)}",
        f"- UNDER rate among invalid tests: {under_baseline:.4f}",
        f"- OVER rate among valid tests: {over_baseline:.4f}",
        "",
        "## Numeric UNDER Results",
        "",
        "Among invalid tests, the strongest non-low-support numeric contexts are:",
        *bullet_under([row for row in top_under if row["context_family"] == "numeric"]),
        "",
        "Interpretation: these rates condition on invalid examples only, so boundary cases are compared against the right denominator rather than all tests.",
        "",
        "## PatternProperties OVER Results",
        "",
        *bullet_over(top_pattern),
        "",
        "Interpretation: high patternProperties lifts should be read together with support; the support-vs-lift plot separates rare sharp signals from broader effects.",
        "",
        "## Combinator OVER Results",
        "",
        *bullet_over(top_comb),
        "",
        "Interpretation: branch count and matched-branch buckets help distinguish combinator presence from branch interaction cases.",
        "",
        "## Test-Level vs Schema-Level",
        "",
        "UNDER comparison:",
        *compare_schema_level(top_under, schema_risk, "under"),
        "",
        "OVER comparison:",
        *compare_schema_level(top_over, schema_risk, "over"),
        "",
        "If a context has high test-level lift but modest schema-level lift, it may be amplified by a smaller number of schemas with many tests.",
        "",
        "## Limitations",
        "",
        "- Results remain correlational.",
        "- HDD or controlled mutations are still needed for causal validation.",
        "- Low-support contexts should not be overinterpreted.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    input_dir = Path(args.input_dir) if args.input_dir else ROOT / "data" / dataset / "refined_feature_analysis"
    output_data_dir = Path(args.output_data_dir) if args.output_data_dir else ROOT / "data" / dataset / "refined_feature_analysis_v2"
    output_plot_dir = Path(args.output_plot_dir) if args.output_plot_dir else ROOT / "plots" / dataset / "refined_feature_analysis_v2"
    data_root = Path(args.data_root)
    output_data_dir.mkdir(parents=True, exist_ok=True)
    output_plot_dir.mkdir(parents=True, exist_ok=True)

    test_rows = read_csv(input_dir / "refined_test_features.csv")
    schema_rows = read_csv(input_dir / "refined_schema_features.csv")

    under_rows = conditional_under_risk(test_rows)
    over_rows = conditional_over_risk(test_rows)
    schema_rows_out = schema_level_risk(schema_rows, test_rows)

    write_csv(
        output_data_dir / "under_invalid_only_risk.csv",
        under_rows,
        [
            "context_family",
            "context_feature",
            "context_value",
            "support_invalid_tests",
            "support_schemas",
            "under_count",
            "under_rate_invalid_only",
            "baseline_under_rate_invalid_only",
            "under_lift_invalid_only",
            "low_support",
        ],
    )
    write_csv(
        output_data_dir / "over_valid_only_risk.csv",
        over_rows,
        [
            "context_family",
            "context_feature",
            "context_value",
            "support_valid_tests",
            "support_schemas",
            "over_count",
            "over_rate_valid_only",
            "baseline_over_rate_valid_only",
            "over_lift_valid_only",
            "low_support",
        ],
    )
    write_csv(output_data_dir / "schema_level_context_risk.csv", schema_rows_out)

    write_plots(output_plot_dir, test_rows, under_rows, over_rows)
    cooccurrence_heatmap(output_plot_dir / "summary" / "cooccurrence_under_schemas.svg", "Keyword co-occurrence in UNDER schemas", cooccurrence_rows(schema_rows, data_root, "under"))
    cooccurrence_heatmap(output_plot_dir / "summary" / "cooccurrence_over_schemas.svg", "Keyword co-occurrence in OVER schemas", cooccurrence_rows(schema_rows, data_root, "over"))

    examples = top_examples(test_rows, under_rows, over_rows, data_root)
    write_csv(output_data_dir / "top_context_examples.csv", examples)
    write_report(output_data_dir / "refined_feature_analysis_v2_report.md", test_rows, under_rows, over_rows, schema_rows_out)

    print(f"Wrote v2 conditional analysis to {output_data_dir}")
    print(f"Wrote v2 plots to {output_plot_dir}")


if __name__ == "__main__":
    main()
