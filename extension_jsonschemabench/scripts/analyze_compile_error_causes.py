#!/usr/bin/env python3
"""Create compile-error cause and feature plots for one dataset run."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import os
import re
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-jsonschemabench")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_dataset_statistics import ANALYZED_FEATURES, count_schema_features


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_ROOT = ROOT / "extension_jsonschemabench" / "results" / "per_dataset_runs"
DEFAULT_DATA_ROOT = ROOT / "maskbench" / "data"

PALETTE = {
    "blue": "#2F6BFF",
    "teal": "#008C7D",
    "orange": "#D96C06",
    "red": "#C43C39",
    "gray": "#5C6670",
    "grid": "#D9DEE5",
    "text": "#1F2933",
}

UNSUPPORTED_KEYWORD_HINTS = [
    "patternProperties",
    "dependencies",
    "dependentRequired",
    "dependentSchemas",
    "minProperties",
    "maxProperties",
    "propertyNames",
    "unevaluatedProperties",
    "unevaluatedItems",
    "prefixItems",
    "contains",
    "maxContains",
    "minContains",
    "oneOf",
    "anyOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "$ref",
    "$dynamicRef",
    "$anchor",
]

ANNOTATION_ONLY_KEYS = {
    "description",
    "title",
    "example",
    "examples",
    "default",
    "deprecated",
    "readOnly",
    "writeOnly",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze compile-error causes.")
    parser.add_argument("--framework", required=True, help="Framework id: xgr, outlines, guidance.")
    parser.add_argument("--dataset", required=True, help="Dataset id, for example Github_medium.")
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", default=None, help="Default: <run_dir>/plots.")
    parser.add_argument("--top-n", type=int, default=15)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: format_value(row.get(name, "")) for name in fieldnames})


def format_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.6g}"
    return value


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def unwrap_exception_message(message: str) -> str:
    message = (message or "").strip()
    match = re.match(r"^[A-Za-z_]+Error\((.*)\)$", message, flags=re.DOTALL)
    if not match:
        return message
    try:
        return str(ast.literal_eval(match.group(1)))
    except Exception:
        return message


def normalize_message(message: str) -> str:
    message = unwrap_exception_message(message)
    message = re.sub(r"^\[\d\d:\d\d:\d\d\]\s+", "", message)
    message = re.sub(r"/project/cpp/[^:]+:\d+:\s*", "", message)
    message = re.sub(r"\s+", " ", message)
    return message.strip()


def parse_unimplemented_keys(message: str) -> list[str]:
    match = re.search(r"Unimplemented keys:\s*(\[[^\]]+\])", message)
    if not match:
        return []
    try:
        value = ast.literal_eval(match.group(1))
    except Exception:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def parse_json_object_from_message(message: str) -> Any | None:
    match = re.search(r"Unsupported JSON Schema structure\s+(.+?)\s+Make sure", message, flags=re.DOTALL)
    if not match:
        return None
    raw = match.group(1).strip()
    if raw == "false":
        return False
    try:
        return json.loads(raw)
    except Exception:
        return None


def object_has_only_annotations(value: Any) -> bool:
    return isinstance(value, dict) and bool(value) and set(value).issubset(ANNOTATION_ONLY_KEYS)


def infer_compile_causes(framework: str, raw_message: str) -> list[str]:
    message = normalize_message(raw_message)
    lower = message.lower()

    causes: list[str] = []

    for key in parse_unimplemented_keys(message):
        causes.append(f"keyword: {key}")

    unknown_format = re.search(r"Unknown format:\s*([^'\"\s]+)", message)
    if unknown_format:
        causes.append(f"format: {unknown_format.group(1)}")

    unsupported_format = re.search(r"Format\s+([^'\"\s]+)\s+is not supported", message)
    if unsupported_format:
        causes.append(f"format: {unsupported_format.group(1)}")

    json_format = re.search(r'"format"\s*:\s*"([^"]+)"', message)
    if json_format:
        causes.append(f"format: {json_format.group(1)}")

    if "oneof constraints are not supported" in lower:
        causes.append("keyword: oneOf")
    if "lookarounds not supported" in lower:
        causes.append("regex: lookaround unsupported")
    if "invalid escape sequence" in lower:
        causes.append("regex/string escape unsupported")
    if "vocabulary provided is incompatible with the regex" in lower:
        causes.append("tokenizer/regex incompatible")
    if "dfa states exceeds limit" in lower:
        causes.append("DFA state limit")
    if "maximum must be an integer" in lower:
        causes.append("numeric bound: non-integer maximum")
    if "schema should not be false" in lower or "unsupported json schema structure false" in lower:
        causes.append("boolean false schema")
    if "schema should be an object or bool, but got [" in lower:
        causes.append("schema node is array")

    unsupported_object = parse_json_object_from_message(message)
    if object_has_only_annotations(unsupported_object):
        causes.append("annotation-only/metadata schema")

    for keyword in UNSUPPORTED_KEYWORD_HINTS:
        if re.search(rf'"{re.escape(keyword)}"\s*:', message):
            causes.append(f"keyword: {keyword}")

    if not causes and "unsupported json schema structure" in lower:
        causes.append("unsupported schema structure")
    if not causes:
        causes.append("other compile error")

    deduped = []
    for cause in causes:
        if cause not in deduped:
            deduped.append(cause)
    return deduped


def schema_id_from_path(path: Path) -> str:
    return path.name


def load_schema_features(
    data_root: Path, dataset: str, schema_ids: set[str] | None = None
) -> dict[str, dict[str, Any]]:
    features_by_schema = {}
    if schema_ids is None:
        paths = sorted(data_root.glob(f"{dataset}---*.json"))
    else:
        paths = [data_root / schema_id for schema_id in sorted(schema_ids)]
    for path in paths:
        if not path.exists():
            continue
        schema_id = schema_id_from_path(path)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        features_by_schema[schema_id] = count_schema_features(
            payload.get("schema"), payload.get("meta") or {}
        )
    return features_by_schema


def load_run_schema_ids(run_dir: Path, result_rows: list[dict[str, Any]]) -> set[str]:
    schema_ids = {str(row.get("schema_id")) for row in result_rows if row.get("schema_id")}
    timeout_path = run_dir / "timed_out_schemas.jsonl"
    if timeout_path.exists():
        for row in read_jsonl(timeout_path):
            if row.get("schema_id"):
                schema_ids.add(str(row["schema_id"]))
    return schema_ids


def build_cause_rows(framework: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
    schema_causes: dict[str, set[str]] = defaultdict(set)
    cause_tests: Counter[str] = Counter()
    compile_error_schemas = set()

    for row in rows:
        if row.get("actual_result") != "compile_error":
            continue
        schema_id = str(row.get("schema_id", ""))
        compile_error_schemas.add(schema_id)
        for cause in infer_compile_causes(framework, str(row.get("error_message") or "")):
            schema_causes[schema_id].add(cause)
            cause_tests[cause] += 1

    cause_schemas = Counter()
    for causes in schema_causes.values():
        for cause in causes:
            cause_schemas[cause] += 1

    cause_rows = [
        {
            "cause": cause,
            "schema_count": schema_count,
            "test_count": cause_tests[cause],
        }
        for cause, schema_count in cause_schemas.items()
    ]
    cause_rows.sort(key=lambda row: (-row["schema_count"], -row["test_count"], row["cause"]))
    return cause_rows, compile_error_schemas


def build_feature_rows(
    features_by_schema: dict[str, dict[str, Any]], compile_error_schemas: set[str]
) -> list[dict[str, Any]]:
    total_schemas = len(features_by_schema)
    total_compile_error = len(compile_error_schemas)
    rows = []

    for feature in ANALYZED_FEATURES:
        total_with = sum(1 for features in features_by_schema.values() if bool(features.get(feature)))
        error_with = sum(
            1
            for schema_id, features in features_by_schema.items()
            if schema_id in compile_error_schemas and bool(features.get(feature))
        )
        total_without = total_schemas - total_with
        error_without = total_compile_error - error_with
        rate_with = error_with / total_with if total_with else 0.0
        rate_without = error_without / total_without if total_without else 0.0
        lift = rate_with / rate_without if rate_without else math.inf if rate_with else 0.0
        rows.append(
            {
                "feature": feature,
                "schemas_with_feature": total_with,
                "compile_error_schemas_with_feature": error_with,
                "compile_error_rate_with_feature": rate_with,
                "compile_error_rate_without_feature": rate_without,
                "lift": lift,
            }
        )

    rows.sort(
        key=lambda row: (
            -row["compile_error_schemas_with_feature"],
            -row["compile_error_rate_with_feature"],
            row["feature"],
        )
    )
    return rows


def clean_label(label: str) -> str:
    label = label.replace("has_", "")
    label = label.replace("_", " ")
    label = label.replace("if then else", "if/then/else")
    return label


def wrapped_labels(labels: list[str], width: int = 34) -> list[str]:
    return ["\n".join(textwrap.wrap(clean_label(label), width=width)) for label in labels]


def plot_horizontal_bars(
    path: Path,
    rows: list[dict[str, Any]],
    label_key: str,
    value_key: str,
    title: str,
    xlabel: str,
    color: str,
    annotation,
) -> None:
    if not rows:
        return
    labels = [str(row[label_key]) for row in rows]
    values = [float(row[value_key]) for row in rows]
    fig_height = max(4.0, 1.5 + len(rows) * 0.46)
    fig, ax = plt.subplots(figsize=(10.5, fig_height))
    y_positions = list(range(len(rows)))
    ax.barh(y_positions, values, color=color)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(wrapped_labels(labels))
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontsize=14, color=PALETTE["text"], pad=12)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", color=PALETTE["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    max_value = max(values) if values else 1.0
    ax.set_xlim(0, max_value * 1.22 if max_value else 1.0)
    for index, row in enumerate(rows):
        ax.text(
            values[index] + max_value * 0.015,
            index,
            annotation(row),
            va="center",
            fontsize=9,
            color=PALETTE["gray"],
        )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, format="svg", bbox_inches="tight")
    plt.close(fig)


def plot_outputs(out_dir: Path, cause_rows: list[dict[str, Any]], feature_rows: list[dict[str, Any]], top_n: int) -> None:
    top_causes = cause_rows[:top_n]
    plot_horizontal_bars(
        out_dir / "compile_error_top_causes.svg",
        top_causes,
        "cause",
        "schema_count",
        "Top compile-error causes",
        "schemas with compile_error",
        PALETTE["red"],
        lambda row: f"{row['schema_count']} schemas / {row['test_count']} tests",
    )

    top_features = [
        row for row in feature_rows if row["compile_error_schemas_with_feature"] > 0
    ][:top_n]
    plot_horizontal_bars(
        out_dir / "compile_error_top_schema_features.svg",
        top_features,
        "feature",
        "compile_error_schemas_with_feature",
        "Most common features inside compile-error schemas",
        "compile-error schemas containing feature",
        PALETTE["orange"],
        lambda row: (
            f"{row['compile_error_schemas_with_feature']}/{row['schemas_with_feature']} "
            f"({pct(row['compile_error_rate_with_feature'])})"
        ),
    )

    lift_rows = [
        row
        for row in feature_rows
        if row["compile_error_schemas_with_feature"] >= 5 and math.isfinite(float(row["lift"]))
    ]
    lift_rows.sort(
        key=lambda row: (
            -float(row["lift"]),
            -row["compile_error_schemas_with_feature"],
            row["feature"],
        )
    )
    lift_rows = lift_rows[:top_n]
    plot_horizontal_bars(
        out_dir / "compile_error_feature_lift.svg",
        lift_rows,
        "feature",
        "lift",
        "Features most associated with compile_error",
        "lift vs schemas without feature",
        PALETTE["teal"],
        lambda row: (
            f"rate {pct(row['compile_error_rate_with_feature'])}; "
            f"{row['compile_error_schemas_with_feature']} schemas"
        ),
    )


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int = 8) -> str:
    lines = []
    lines.append("| " + " | ".join(title for title, _ in columns) + " |")
    lines.append("| " + " | ".join("---:" if key.endswith("count") or "rate" in key or key == "lift" else "---" for _, key in columns) + " |")
    for row in rows[:limit]:
        values = []
        for _, key in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                if "rate" in key:
                    value = pct(value)
                elif math.isinf(value):
                    value = "inf"
                else:
                    value = f"{value:.2f}"
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def update_plots_readme(
    out_dir: Path,
    dataset: str,
    framework: str,
    cause_rows: list[dict[str, Any]],
    feature_rows: list[dict[str, Any]],
) -> None:
    readme = out_dir / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.exists() else f"# Statistical study: {dataset} / {framework}\n"

    start = "<!-- compile-error-causes:start -->"
    end = "<!-- compile-error-causes:end -->"
    block_pattern = re.compile(rf"\n?{re.escape(start)}.*?{re.escape(end)}\n?", flags=re.DOTALL)
    text = re.sub(block_pattern, "\n", text).rstrip()

    lift_rows = [
        row
        for row in feature_rows
        if row["compile_error_schemas_with_feature"] >= 5 and math.isfinite(float(row["lift"]))
    ]
    lift_rows.sort(
        key=lambda row: (
            -float(row["lift"]),
            -row["compile_error_schemas_with_feature"],
            row["feature"],
        )
    )

    block = f"""

{start}
## Compile-error causes

These files summarize compile errors by explicit framework message and by JSON Schema features present in the affected schemas.

- `compile_error_top_causes.csv` / `compile_error_top_causes.svg`: normalized causes extracted from `error_message`.
- `compile_error_top_schema_features.csv` / `compile_error_top_schema_features.svg`: most frequent schema features among compile-error schemas.
- `compile_error_feature_lift.csv` / `compile_error_feature_lift.svg`: features with the strongest compile-error lift compared with schemas that do not contain the feature.

Top causes by affected schemas:

{markdown_table(cause_rows, [("cause", "cause"), ("schemas", "schema_count"), ("tests", "test_count")])}

Top feature lift signals:

{markdown_table(lift_rows, [("feature", "feature"), ("schemas", "compile_error_schemas_with_feature"), ("rate", "compile_error_rate_with_feature"), ("lift", "lift")])}
{end}
"""
    readme.write_text(text + block, encoding="utf-8")


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)
    data_root = Path(args.data_root)
    run_dir = results_root / args.framework / args.dataset
    out_dir = Path(args.output_dir) if args.output_dir else run_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    result_path = run_dir / "per_test_results.jsonl"
    rows = read_jsonl(result_path)
    cause_rows, compile_error_schemas = build_cause_rows(args.framework, rows)
    run_schema_ids = load_run_schema_ids(run_dir, rows)
    features_by_schema = load_schema_features(data_root, args.dataset, run_schema_ids)
    feature_rows = build_feature_rows(features_by_schema, compile_error_schemas)

    write_csv(
        out_dir / "compile_error_top_causes.csv",
        cause_rows,
        ["cause", "schema_count", "test_count"],
    )
    write_csv(
        out_dir / "compile_error_top_schema_features.csv",
        feature_rows,
        [
            "feature",
            "schemas_with_feature",
            "compile_error_schemas_with_feature",
            "compile_error_rate_with_feature",
            "compile_error_rate_without_feature",
            "lift",
        ],
    )
    lift_rows = [
        row
        for row in feature_rows
        if row["compile_error_schemas_with_feature"] >= 5 and math.isfinite(float(row["lift"]))
    ]
    lift_rows.sort(
        key=lambda row: (
            -float(row["lift"]),
            -row["compile_error_schemas_with_feature"],
            row["feature"],
        )
    )
    write_csv(
        out_dir / "compile_error_feature_lift.csv",
        lift_rows,
        [
            "feature",
            "schemas_with_feature",
            "compile_error_schemas_with_feature",
            "compile_error_rate_with_feature",
            "compile_error_rate_without_feature",
            "lift",
        ],
    )

    plot_outputs(out_dir, cause_rows, feature_rows, args.top_n)
    update_plots_readme(out_dir, args.dataset, args.framework, cause_rows, feature_rows)
    print(f"Wrote compile-error study to {out_dir}")


if __name__ == "__main__":
    main()
