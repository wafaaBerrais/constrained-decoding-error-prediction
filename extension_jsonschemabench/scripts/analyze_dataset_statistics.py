#!/usr/bin/env python3
"""Build schema-level statistics and SVG plots for one dataset run.

The input directory is expected to contain per_test_results.jsonl,
timing_profile.csv, and optionally timed_out_schemas.jsonl. Outputs are written
to a plots/ directory next to those files.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_ROOT = ROOT / "extension_jsonschemabench" / "results" / "per_dataset_runs"
DEFAULT_DATA_ROOT = ROOT / "maskbench" / "data"

BASE_FEATURES = [
    "has_additionalProperties",
    "has_allOf",
    "has_anchor",
    "has_anyOf",
    "has_boolean_schema",
    "has_const",
    "has_contains",
    "has_content",
    "has_default",
    "has_defs",
    "has_dependentRequired",
    "has_dependentSchemas",
    "has_dynamicRef",
    "has_enum",
    "has_exclusiveMaximum",
    "has_exclusiveMinimum",
    "has_if_then_else",
    "has_infinite_loop_detection",
    "has_items",
    "has_maxContains",
    "has_maxItems",
    "has_maxLength",
    "has_maxProperties",
    "has_maximum",
    "has_minContains",
    "has_minItems",
    "has_minLength",
    "has_minProperties",
    "has_minimum",
    "has_multipleOf",
    "has_not",
    "has_oneOf",
    "has_pattern",
    "has_patternProperties",
    "has_prefixItems",
    "has_properties",
    "has_propertyNames",
    "has_ref",
    "has_required",
    "has_type",
    "has_unevaluatedItems",
    "has_unevaluatedProperties",
    "has_uniqueItems",
]

FEATURE_COLUMNS = BASE_FEATURES

NUMERIC_FEATURE_COLUMNS = [
    "nb_keywords",
    "nb_properties",
    "nb_required",
    "schema_depth",
    "nb_branches_combinators",
    "nb_enum_values",
    "nb_regex",
]

DERIVED_FEATURE_COLUMNS = [
    "large_enum",
    "many_required",
    "many_properties",
    "deep_schema",
]

ANALYZED_FEATURES = BASE_FEATURES + DERIVED_FEATURE_COLUMNS

MIN_SCHEMAS_WITH_CANDIDATE = 5
MIN_INVALID_TESTS_FOR_UNDER = 20
MIN_VALID_TESTS_FOR_OVER = 20
TIMEOUT_LIFT_THRESHOLD = 1.25
UNDER_LIFT_THRESHOLD = 1.15
OVER_LIFT_THRESHOLD = 1.15
UNDER_DELTA_THRESHOLD = 0.02
OVER_DELTA_THRESHOLD = 0.02
TOP_N_HEATMAP = 20

PHASE_COLUMNS = [
    ("compile_grammar_s", "compile"),
    ("validation_loop_mean_s", "validation"),
    ("compute_mask_mean_s", "mask"),
    ("commit_token_mean_s", "commit"),
]

PALETTE = {
    "blue": "#2F6BFF",
    "teal": "#008C7D",
    "orange": "#D96C06",
    "red": "#C43C39",
    "green": "#3B8C3A",
    "purple": "#7557B8",
    "gray": "#5C6670",
    "light_gray": "#E6E8EB",
    "grid": "#D9DEE5",
    "text": "#1F2933",
    "muted": "#667085",
    "bg": "#FFFFFF",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze one completed dataset run.")
    parser.add_argument("--framework", default="xgr", help="Framework id, default: xgr.")
    parser.add_argument("--dataset", required=True, help="Dataset id, for example Github_trivial.")
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", default=None, help="Default: <run_dir>/plots.")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format_value(row.get(key, "")) for key in fieldnames})


def format_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.6g}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return value


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int:
    f = to_float(value)
    if f is None:
        return 0
    return int(f)


def pct(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return part / total


def pct_text(value: float) -> str:
    return f"{value * 100:.1f}%"


def median(values: list[float]) -> float:
    return statistics.median(values) if values else math.nan


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else math.nan


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0 if values else math.nan


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return xs[low]
    return xs[low] * (high - pos) + xs[high] * (pos - low)


def safe_log10(value: float) -> float:
    return math.log10(max(value, 1e-9))


def load_schema(schema_id: str, data_root: Path) -> dict[str, Any]:
    path = data_root / schema_id
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def json_len(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def metadata_values(meta: dict[str, Any] | None) -> set[str]:
    values: set[str] = set()
    if not isinstance(meta, dict):
        return values
    for key in ("features", "raw_features"):
        raw = meta.get(key, [])
        if isinstance(raw, list):
            values.update(str(value) for value in raw)
    return values


def count_schema_features(schema: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    max_depth = 0
    meta_features = metadata_values(meta)

    subschema_keywords = {
        "additionalProperties",
        "contains",
        "contentSchema",
        "else",
        "if",
        "items",
        "not",
        "propertyNames",
        "then",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
    subschema_array_keywords = {"allOf", "anyOf", "oneOf", "prefixItems"}
    subschema_map_keywords = {"$defs", "definitions", "dependentSchemas", "patternProperties", "properties"}

    def visit(node: Any, depth: int = 0, schema_position: bool = True) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        if isinstance(node, bool):
            if schema_position:
                counts["__boolean_schema"] += 1
            return
        if isinstance(node, dict):
            for key, value in node.items():
                counts[key] += 1
                if key == "properties" and isinstance(value, dict):
                    counts["__properties_count"] += len(value)
                if key == "required" and isinstance(value, list):
                    counts["__required_count"] += len(value)
                if key in {"oneOf", "anyOf", "allOf"} and isinstance(value, list):
                    counts["__branches_count"] += len(value)
                if key == "enum" and isinstance(value, list):
                    counts["__enum_values"] += len(value)
                if key in {"pattern", "patternProperties"}:
                    if key == "patternProperties" and isinstance(value, dict):
                        counts["__regex_count"] += len(value)
                    else:
                        counts["__regex_count"] += 1
                if key in subschema_map_keywords and isinstance(value, dict):
                    for sub_schema in value.values():
                        visit(sub_schema, depth + 2, True)
                elif key in subschema_array_keywords and isinstance(value, list):
                    for sub_schema in value:
                        visit(sub_schema, depth + 2, True)
                elif key in subschema_keywords:
                    visit(value, depth + 1, True)
                elif isinstance(value, (dict, list)):
                    visit(value, depth + 1, False)
        elif isinstance(node, list):
            for item in node:
                visit(item, depth + 1, schema_position)

    visit(schema)

    features = {
        "has_additionalProperties": counts["additionalProperties"] > 0,
        "has_allOf": counts["allOf"] > 0,
        "has_anchor": counts["$anchor"] > 0,
        "has_anyOf": counts["anyOf"] > 0,
        "has_boolean_schema": counts["__boolean_schema"] > 0 or "_boolSchema" in meta_features,
        "has_const": counts["const"] > 0,
        "has_contains": counts["contains"] > 0,
        "has_content": any(counts[key] > 0 or key in meta_features for key in ("contentEncoding", "contentMediaType", "contentSchema")),
        "has_default": counts["default"] > 0,
        "has_defs": counts["$defs"] > 0 or counts["definitions"] > 0,
        "has_dependentRequired": counts["dependentRequired"] > 0,
        "has_dependentSchemas": counts["dependentSchemas"] > 0,
        "has_dynamicRef": counts["$dynamicRef"] > 0,
        "has_enum": counts["enum"] > 0,
        "has_exclusiveMaximum": counts["exclusiveMaximum"] > 0,
        "has_exclusiveMinimum": counts["exclusiveMinimum"] > 0,
        "has_if_then_else": any(counts[key] > 0 for key in ("if", "then", "else")),
        "has_infinite_loop_detection": any(
            name in meta_features
            for name in ("infinite-loop-detection", "infinite_loop_detection")
        ),
        "has_items": counts["items"] > 0,
        "has_maxContains": counts["maxContains"] > 0,
        "has_maxItems": counts["maxItems"] > 0,
        "has_maxLength": counts["maxLength"] > 0,
        "has_maxProperties": counts["maxProperties"] > 0,
        "has_maximum": counts["maximum"] > 0,
        "has_minContains": counts["minContains"] > 0,
        "has_minItems": counts["minItems"] > 0,
        "has_minLength": counts["minLength"] > 0,
        "has_minProperties": counts["minProperties"] > 0,
        "has_minimum": counts["minimum"] > 0,
        "has_multipleOf": counts["multipleOf"] > 0,
        "has_not": counts["not"] > 0,
        "has_oneOf": counts["oneOf"] > 0,
        "has_pattern": counts["pattern"] > 0,
        "has_patternProperties": counts["patternProperties"] > 0,
        "has_prefixItems": counts["prefixItems"] > 0,
        "has_properties": counts["properties"] > 0,
        "has_propertyNames": counts["propertyNames"] > 0,
        "has_ref": counts["$ref"] > 0,
        "has_required": counts["required"] > 0,
        "has_type": counts["type"] > 0,
        "has_unevaluatedItems": counts["unevaluatedItems"] > 0,
        "has_unevaluatedProperties": counts["unevaluatedProperties"] > 0,
        "has_uniqueItems": counts["uniqueItems"] > 0,
        "nb_keywords": sum(v for k, v in counts.items() if not k.startswith("__")),
        "nb_properties": counts["__properties_count"],
        "nb_required": counts["__required_count"],
        "schema_depth": max_depth,
        "nb_branches_combinators": counts["__branches_count"],
        "nb_enum_values": counts["__enum_values"],
        "nb_regex": counts["__regex_count"],
    }

    features["large_enum"] = features["nb_enum_values"] >= 10
    features["many_required"] = features["nb_required"] >= 5
    features["many_properties"] = features["nb_properties"] >= 10
    features["deep_schema"] = features["schema_depth"] >= 8
    return features


def constraint_case(row: dict[str, Any]) -> str:
    if not to_bool(row.get("result_available", True)):
        return "no_decision"
    expected = str(row.get("expected_validity", "")).lower()
    accepted = to_bool(row.get("accepted"))
    if expected == "valid" and accepted:
        return "correct_accept"
    if expected == "invalid" and not accepted:
        return "correct_reject"
    if expected == "invalid" and accepted:
        return "under_constraint"
    if expected == "valid" and not accepted:
        return "over_constraint"
    return "unknown"


def infer_timeout_stage(timeout: dict[str, Any] | None, timings: list[dict[str, str]]) -> str:
    if not timeout:
        return ""
    if timeout.get("timeout_stage"):
        return str(timeout["timeout_stage"])
    text = " ".join(
        str(row.get("actual_result", "")) + " " + str(row.get("error_message", ""))
        for row in timings
    ).lower()
    if "compile_grammar" in text or "running_compile_grammar" in text:
        return "compile_grammar"
    if "validation" in text or "running_validation" in text:
        return "validation"
    if "compiled" in text:
        return "compiled_waiting_validation"
    return "per_schema_timeout"


def collect_schema_rows(
    dataset: str,
    framework: str,
    run_dir: Path,
    data_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    per_test_rows = read_jsonl(run_dir / "per_test_results.jsonl")
    timing_rows = read_csv(run_dir / "timing_profile.csv")
    timeout_rows = read_jsonl(run_dir / "timed_out_schemas.jsonl")

    tests_by_schema: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_test_rows:
        tests_by_schema[row.get("schema_id", "")].append(row)

    timing_by_schema: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in timing_rows:
        timing_by_schema[row.get("schema_id", "")].append(row)

    timeout_by_schema = {row.get("schema_id", ""): row for row in timeout_rows if row.get("schema_id")}
    schema_ids = sorted(set(tests_by_schema) | set(timing_by_schema) | set(timeout_by_schema))

    schema_rows: list[dict[str, Any]] = []
    for schema_id in schema_ids:
        tests = tests_by_schema.get(schema_id, [])
        timings = timing_by_schema.get(schema_id, [])
        timeout = timeout_by_schema.get(schema_id)
        schema_doc = load_schema(schema_id, data_root)
        schema = schema_doc.get("schema", {}) if isinstance(schema_doc, dict) else {}
        meta = schema_doc.get("meta", {}) if isinstance(schema_doc, dict) else {}
        embedded_tests = schema_doc.get("tests", []) if isinstance(schema_doc, dict) else []
        features = count_schema_features(schema, meta)

        expected_valid = [r for r in tests if str(r.get("expected_validity", "")).lower() == "valid"]
        expected_invalid = [r for r in tests if str(r.get("expected_validity", "")).lower() == "invalid"]
        completed = [r for r in tests if to_bool(r.get("result_available", True))]
        completed_valid = [r for r in completed if str(r.get("expected_validity", "")).lower() == "valid"]
        completed_invalid = [r for r in completed if str(r.get("expected_validity", "")).lower() == "invalid"]
        cases = Counter(constraint_case(r) for r in completed)
        compile_values = [to_float(r.get("compile_grammar_us")) for r in timings]
        compile_values = [v / 1_000_000 for v in compile_values if v is not None]
        validation_values = [to_float(r.get("validation_loop_us")) for r in timings]
        validation_values = [v / 1_000_000 for v in validation_values if v is not None]
        mask_values = [to_float(r.get("compute_mask_us")) for r in timings]
        mask_values = [v / 1_000_000 for v in mask_values if v is not None]
        commit_values = [to_float(r.get("commit_token_us")) for r in timings]
        commit_values = [v / 1_000_000 for v in commit_values if v is not None]
        instance_chars = [to_float(r.get("instance_json_chars")) for r in timings]
        instance_chars = [v for v in instance_chars if v is not None]
        tokens = [to_float(r.get("num_tokens")) for r in timings]
        tokens = [v for v in tokens if v is not None]
        max_tokens = [to_float(r.get("num_tokens")) for r in timings]
        max_tokens = [v for v in max_tokens if v is not None]
        schema_path = timings[0].get("schema_path") if timings else (
            tests[0].get("schema_path") if tests else f"maskbench/data/{schema_id}"
        )
        schema_file = data_root / schema_id
        schema_bytes = schema_file.stat().st_size if schema_file.exists() else to_int(timings[0].get("schema_file_bytes")) if timings else 0
        schema_chars = json_len(schema) if schema else to_int(timings[0].get("schema_json_chars")) if timings else 0
        n_tests = len(tests) if tests else len(embedded_tests)
        n_valid = len(expected_valid) if tests else sum(1 for t in embedded_tests if t.get("valid") is True)
        n_invalid = len(expected_invalid) if tests else sum(1 for t in embedded_tests if t.get("valid") is False)
        n_timeout = max(n_tests - len(completed), 1) if timeout else 0
        timeout_status = "timeout" if timeout else "completed"
        timeout_stage = infer_timeout_stage(timeout, timings)
        timeout_rate = pct(n_timeout, max(n_tests, 1)) if timeout else 0.0
        row = {
            "dataset_id": dataset,
            "framework_id": framework,
            "schema_id": schema_id,
            "schema_path": schema_path,
            "n_tests": n_tests,
            "n_valid_tests": n_valid,
            "n_invalid_tests": n_invalid,
            "n_valid_completed": len(completed_valid),
            "n_invalid_completed": len(completed_invalid),
            "n_completed": len(completed),
            "n_timeout": n_timeout,
            "timeout_status": timeout_status,
            "timeout_stage": timeout_stage,
            "timeout_elapsed_s": to_float(timeout.get("elapsed_seconds")) if timeout else math.nan,
            "compile_grammar_s": compile_values[0] if compile_values else math.nan,
            "validation_loop_mean_s": mean(validation_values),
            "compute_mask_mean_s": mean(mask_values),
            "commit_token_mean_s": mean(commit_values),
            "schema_file_bytes": schema_bytes,
            "schema_json_chars": schema_chars,
            "mean_instance_json_chars": mean(instance_chars),
            "mean_num_tokens": mean(tokens),
            "max_num_tokens": max(max_tokens) if max_tokens else math.nan,
            "n_correct_accept": cases["correct_accept"],
            "n_correct_reject": cases["correct_reject"],
            "n_under_constraint": cases["under_constraint"],
            "n_over_constraint": cases["over_constraint"],
            "under_rate": pct(cases["under_constraint"], len(completed_invalid)),
            "over_rate": pct(cases["over_constraint"], len(completed_valid)),
            "timeout_rate": timeout_rate,
            "coverage_rate": pct(len(completed), max(n_tests, 1)),
            "accuracy_completed": pct(cases["correct_accept"] + cases["correct_reject"], len(completed)),
            "permissive_score": pct(cases["under_constraint"], len(completed_invalid))
            - pct(cases["over_constraint"], len(completed_valid)),
        }
        row.update(features)
        schema_rows.append(row)

    summary = {
        "per_test_rows": len(per_test_rows),
        "timing_rows": len(timing_rows),
        "timeout_rows": len(timeout_rows),
    }
    return schema_rows, summary


def feature_timeout_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    total = len(schema_rows)
    total_timeouts = sum(1 for r in schema_rows if r["timeout_status"] == "timeout")
    for feature in ANALYZED_FEATURES:
        present = [r for r in schema_rows if bool(r.get(feature))]
        absent = [r for r in schema_rows if not bool(r.get(feature))]
        if not present:
            continue
        with_timeout = sum(1 for r in present if r["timeout_status"] == "timeout")
        without_timeout = sum(1 for r in absent if r["timeout_status"] == "timeout")
        rate_with = pct(with_timeout, len(present))
        rate_without = pct(without_timeout, len(absent))
        lift = rate_with / rate_without if rate_without > 0 else math.inf if rate_with > 0 else 0
        rows.append(
            {
                "feature": feature,
                "schemas_with_feature": len(present),
                "schemas_without_feature": len(absent),
                "timeout_with_feature": with_timeout,
                "timeout_without_feature": without_timeout,
                "timeout_rate_with": rate_with,
                "timeout_rate_without": rate_without,
                "lift": lift,
                "support": pct(len(present), total),
                "global_timeout_rate": pct(total_timeouts, total),
            }
        )
    return sorted(rows, key=lambda r: (r["lift"] if math.isfinite(r["lift"]) else 999, r["timeout_rate_with"]), reverse=True)


def lift_value(rate_with: float, rate_without: float) -> float:
    if rate_without > 0:
        return rate_with / rate_without
    return math.inf if rate_with > 0 else 0.0


def lift_rank_value(value: float) -> float:
    if not math.isfinite(value):
        return 999.0 if value > 0 else 0.0
    return value


def feature_constraint_lift_rows(schema_rows: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    if metric not in {"under", "over"}:
        raise ValueError(f"Unsupported constraint metric: {metric}")
    rows = []
    total = len(schema_rows)
    global_denominator = sum(r["n_invalid_completed" if metric == "under" else "n_valid_completed"] for r in schema_rows)
    global_n = sum(r["n_under_constraint" if metric == "under" else "n_over_constraint"] for r in schema_rows)
    for feature in ANALYZED_FEATURES:
        present = [r for r in schema_rows if bool(r.get(feature))]
        absent = [r for r in schema_rows if not bool(r.get(feature))]
        if not present:
            continue
        numerator_key = "n_under_constraint" if metric == "under" else "n_over_constraint"
        denominator_key = "n_invalid_completed" if metric == "under" else "n_valid_completed"
        numerator_with = sum(r[numerator_key] for r in present)
        numerator_without = sum(r[numerator_key] for r in absent)
        denominator_with = sum(r[denominator_key] for r in present)
        denominator_without = sum(r[denominator_key] for r in absent)
        rate_with = pct(numerator_with, denominator_with)
        rate_without = pct(numerator_without, denominator_without)
        min_denominator = MIN_INVALID_TESTS_FOR_UNDER if metric == "under" else MIN_VALID_TESTS_FOR_OVER
        eligible = (
            len(present) >= MIN_SCHEMAS_WITH_CANDIDATE
            and denominator_with >= min_denominator
            and denominator_without >= min_denominator
        )
        rows.append(
            {
                "feature": feature,
                "schemas_with_feature": len(present),
                "schemas_without_feature": len(absent),
                f"{metric}_with_feature": numerator_with,
                f"{metric}_without_feature": numerator_without,
                f"{metric}_denominator_with": denominator_with,
                f"{metric}_denominator_without": denominator_without,
                f"{metric}_rate_with": rate_with,
                f"{metric}_rate_without": rate_without,
                "lift": lift_value(rate_with, rate_without),
                "delta": rate_with - rate_without,
                "support": pct(len(present), total),
                f"global_{metric}_rate": pct(global_n, global_denominator),
                "eligible_lift": eligible,
            }
        )
    return sorted(rows, key=lambda r: (r["eligible_lift"], lift_rank_value(r["lift"]), r["delta"], r[f"{metric}_rate_with"]), reverse=True)


def feature_constraint_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for feature in ANALYZED_FEATURES:
        present = [r for r in schema_rows if bool(r.get(feature))]
        completed = [r for r in present if r["n_completed"] > 0]
        if not completed:
            continue
        n_invalid = sum(r["n_invalid_completed"] for r in completed)
        n_valid = sum(r["n_valid_completed"] for r in completed)
        n_completed = sum(r["n_completed"] for r in completed)
        n_correct = sum(r["n_correct_accept"] + r["n_correct_reject"] for r in completed)
        rows.append(
            {
                "feature": feature,
                "n_schemas": len(present),
                "n_completed_tests": n_completed,
                "under_rate": pct(sum(r["n_under_constraint"] for r in completed), n_invalid),
                "over_rate": pct(sum(r["n_over_constraint"] for r in completed), n_valid),
                "correct_rate": pct(n_correct, n_completed),
                "timeout_rate": pct(sum(1 for r in present if r["timeout_status"] == "timeout"), len(present)),
            }
        )
    return sorted(rows, key=lambda r: (r["under_rate"] + r["over_rate"], r["n_schemas"]), reverse=True)


def feature_pair_lift_rows(schema_rows: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    if metric not in {"timeout", "under", "over"}:
        raise ValueError(f"Unsupported pair metric: {metric}")
    rows = []
    total = len(schema_rows)
    for feature_a, feature_b in combinations(BASE_FEATURES, 2):
        present = [r for r in schema_rows if bool(r.get(feature_a)) and bool(r.get(feature_b))]
        absent = [r for r in schema_rows if not (bool(r.get(feature_a)) and bool(r.get(feature_b)))]
        if not present:
            continue
        row = {
            "feature_pair": f"{feature_a}__AND__{feature_b}",
            "feature_a": feature_a,
            "feature_b": feature_b,
            "schemas_with_pair": len(present),
            "schemas_without_pair": len(absent),
            "support": pct(len(present), total),
        }
        if metric == "timeout":
            numerator_with = sum(1 for r in present if r["timeout_status"] == "timeout")
            numerator_without = sum(1 for r in absent if r["timeout_status"] == "timeout")
            denominator_with = len(present)
            denominator_without = len(absent)
            eligible = denominator_with >= MIN_SCHEMAS_WITH_CANDIDATE and denominator_without >= MIN_SCHEMAS_WITH_CANDIDATE
        elif metric == "under":
            numerator_with = sum(r["n_under_constraint"] for r in present)
            numerator_without = sum(r["n_under_constraint"] for r in absent)
            denominator_with = sum(r["n_invalid_completed"] for r in present)
            denominator_without = sum(r["n_invalid_completed"] for r in absent)
            eligible = (
                len(present) >= MIN_SCHEMAS_WITH_CANDIDATE
                and denominator_with >= MIN_INVALID_TESTS_FOR_UNDER
                and denominator_without >= MIN_INVALID_TESTS_FOR_UNDER
            )
        else:
            numerator_with = sum(r["n_over_constraint"] for r in present)
            numerator_without = sum(r["n_over_constraint"] for r in absent)
            denominator_with = sum(r["n_valid_completed"] for r in present)
            denominator_without = sum(r["n_valid_completed"] for r in absent)
            eligible = (
                len(present) >= MIN_SCHEMAS_WITH_CANDIDATE
                and denominator_with >= MIN_VALID_TESTS_FOR_OVER
                and denominator_without >= MIN_VALID_TESTS_FOR_OVER
            )
        rate_with = pct(numerator_with, denominator_with)
        rate_without = pct(numerator_without, denominator_without)
        row.update(
            {
                f"{metric}_with_pair": numerator_with,
                f"{metric}_without_pair": numerator_without,
                f"{metric}_denominator_with": denominator_with,
                f"{metric}_denominator_without": denominator_without,
                f"{metric}_rate_with": rate_with,
                f"{metric}_rate_without": rate_without,
                "lift": lift_value(rate_with, rate_without),
                "delta": rate_with - rate_without,
                "eligible_lift": eligible,
            }
        )
        rows.append(row)
    return sorted(
        rows,
        key=lambda r: (r["eligible_lift"], lift_rank_value(r["lift"]), r["delta"], r[f"{metric}_rate_with"], r["schemas_with_pair"]),
        reverse=True,
    )


def group_feature_heatmap_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = {
        "correct": [r for r in schema_rows if r["n_completed"] > 0 and r["n_under_constraint"] == 0 and r["n_over_constraint"] == 0 and r["timeout_status"] != "timeout"],
        "timeout": [r for r in schema_rows if r["timeout_status"] == "timeout"],
        "under": [r for r in schema_rows if r["n_under_constraint"] > 0],
        "over": [r for r in schema_rows if r["n_over_constraint"] > 0],
    }
    rows = []
    for feature in ANALYZED_FEATURES:
        if not any(bool(r.get(feature)) for r in schema_rows):
            continue
        row = {"feature": feature}
        for group, members in groups.items():
            row[group] = pct(sum(1 for r in members if bool(r.get(feature))), len(members))
            row[f"{group}_n"] = len(members)
        rows.append(row)
    return rows


def pair_label(feature_a: str, feature_b: str) -> str:
    return f"[P] {feature_a} + {feature_b}"


def pair_group_heatmap_rows(schema_rows: list[dict[str, Any]], top_n: int = TOP_N_HEATMAP) -> list[dict[str, Any]]:
    groups = {
        "correct": [r for r in schema_rows if r["n_completed"] > 0 and r["n_under_constraint"] == 0 and r["n_over_constraint"] == 0 and r["timeout_status"] != "timeout"],
        "timeout": [r for r in schema_rows if r["timeout_status"] == "timeout"],
        "under": [r for r in schema_rows if r["n_under_constraint"] > 0],
        "over": [r for r in schema_rows if r["n_over_constraint"] > 0],
    }
    rows = []
    for feature_a, feature_b in combinations(BASE_FEATURES, 2):
        present = [r for r in schema_rows if bool(r.get(feature_a)) and bool(r.get(feature_b))]
        if not present:
            continue
        absent = [r for r in schema_rows if not (bool(r.get(feature_a)) and bool(r.get(feature_b)))]
        schemas_with = len(present)
        timeout_with = pct(sum(1 for r in present if r["timeout_status"] == "timeout"), schemas_with)
        timeout_without = pct(sum(1 for r in absent if r["timeout_status"] == "timeout"), len(absent))
        invalid_with = sum(r["n_invalid_completed"] for r in present)
        invalid_without = sum(r["n_invalid_completed"] for r in absent)
        valid_with = sum(r["n_valid_completed"] for r in present)
        valid_without = sum(r["n_valid_completed"] for r in absent)
        under_with = pct(sum(r["n_under_constraint"] for r in present), invalid_with)
        under_without = pct(sum(r["n_under_constraint"] for r in absent), invalid_without)
        over_with = pct(sum(r["n_over_constraint"] for r in present), valid_with)
        over_without = pct(sum(r["n_over_constraint"] for r in absent), valid_without)
        timeout_lift = timeout_with / timeout_without if timeout_without > 0 else math.inf if timeout_with > 0 else 0
        under_lift = under_with / under_without if under_without > 0 else math.inf if under_with > 0 else 0
        over_lift = over_with / over_without if over_without > 0 else math.inf if over_with > 0 else 0
        timeout_delta = timeout_with - timeout_without
        under_delta = under_with - under_without
        over_delta = over_with - over_without
        timeout_risk = schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE and timeout_delta > 0 and timeout_lift > TIMEOUT_LIFT_THRESHOLD
        under_risk = (
            schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE
            and invalid_with >= MIN_INVALID_TESTS_FOR_UNDER
            and under_delta > UNDER_DELTA_THRESHOLD
            and under_lift > UNDER_LIFT_THRESHOLD
        )
        over_risk = (
            schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE
            and valid_with >= MIN_VALID_TESTS_FOR_OVER
            and over_delta > OVER_DELTA_THRESHOLD
            and over_lift > OVER_LIFT_THRESHOLD
        )
        risk_count = int(timeout_risk) + int(under_risk) + int(over_risk)
        max_lift = max(
            min(timeout_lift, 50) if math.isfinite(timeout_lift) else 50,
            min(under_lift, 50) if math.isfinite(under_lift) else 50,
            min(over_lift, 50) if math.isfinite(over_lift) else 50,
        )
        max_delta = max(timeout_delta, under_delta, over_delta)
        row = {
            "feature": pair_label(feature_a, feature_b),
            "feature_pair": f"{feature_a}__AND__{feature_b}",
            "feature_a": feature_a,
            "feature_b": feature_b,
            "n_schemas": schemas_with,
            "support": pct(schemas_with, len(schema_rows)),
            "timeout_lift": timeout_lift,
            "timeout_delta": timeout_delta,
            "under_lift": under_lift,
            "under_delta": under_delta,
            "over_lift": over_lift,
            "over_delta": over_delta,
            "risk_count": risk_count,
            "interest_score": risk_count * 1_000_000 + max_lift * 1_000 + max_delta * 100 + schemas_with / 1_000_000,
        }
        for group, members in groups.items():
            row[group] = pct(sum(1 for r in members if bool(r.get(feature_a)) and bool(r.get(feature_b))), len(members))
            row[f"{group}_n"] = len(members)
        rows.append(row)
    return sorted(
        rows,
        key=lambda r: (r["risk_count"], r["interest_score"], r["support"], r["n_schemas"]),
        reverse=True,
    )[:top_n]


def pair_feature_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    total = len(schema_rows)
    for a, b in combinations(BASE_FEATURES, 2):
        present = [r for r in schema_rows if bool(r.get(a)) and bool(r.get(b))]
        if not present:
            continue
        n_invalid = sum(r["n_invalid_completed"] for r in present if r["n_completed"] > 0)
        n_valid = sum(r["n_valid_completed"] for r in present if r["n_completed"] > 0)
        rows.append(
            {
                "feature_pair": f"{a}__AND__{b}",
                "feature_a": a,
                "feature_b": b,
                "n_schemas": len(present),
                "support": pct(len(present), total),
                "timeout_rate": pct(sum(1 for r in present if r["timeout_status"] == "timeout"), len(present)),
                "under_rate": pct(sum(r["n_under_constraint"] for r in present), n_invalid),
                "over_rate": pct(sum(r["n_over_constraint"] for r in present), n_valid),
            }
        )
    return sorted(rows, key=lambda r: (r["timeout_rate"], r["n_schemas"]), reverse=True)


def slow_quartile_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [
        r
        for r in schema_rows
        if r["timeout_status"] == "completed" and math.isfinite(r.get("compile_grammar_s", math.nan))
    ]
    if not completed:
        return []
    values = sorted(r["compile_grammar_s"] for r in completed)
    q1, q2, q3 = quantile(values, 0.25), quantile(values, 0.5), quantile(values, 0.75)
    buckets = {
        "fast": [],
        "medium": [],
        "slow": [],
        "very_slow": [],
    }
    for row in completed:
        v = row["compile_grammar_s"]
        if v <= q1:
            buckets["fast"].append(row)
        elif v <= q2:
            buckets["medium"].append(row)
        elif v <= q3:
            buckets["slow"].append(row)
        else:
            buckets["very_slow"].append(row)
    out = []
    for name, rows in buckets.items():
        n_invalid = sum(r["n_invalid_completed"] for r in rows)
        n_valid = sum(r["n_valid_completed"] for r in rows)
        out.append(
            {
                "compile_speed_group": name,
                "n_schemas": len(rows),
                "compile_min_s": min((r["compile_grammar_s"] for r in rows), default=math.nan),
                "compile_max_s": max((r["compile_grammar_s"] for r in rows), default=math.nan),
                "under_rate": pct(sum(r["n_under_constraint"] for r in rows), n_invalid),
                "over_rate": pct(sum(r["n_over_constraint"] for r in rows), n_valid),
                "accuracy_completed": pct(
                    sum(r["n_correct_accept"] + r["n_correct_reject"] for r in rows),
                    sum(r["n_completed"] for r in rows),
                ),
            }
        )
    return out


def over_rejection_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(run_dir / "timing_profile.csv"):
        if str(row.get("expected_validity", "")).lower() != "valid":
            continue
        if to_bool(row.get("accepted")):
            continue
        tokens_checked = to_float(row.get("tokens_checked"))
        num_tokens = to_float(row.get("num_tokens"))
        if tokens_checked is None or num_tokens in {None, 0}:
            continue
        rows.append(
            {
                "schema_id": row.get("schema_id", ""),
                "test_id": row.get("test_id", ""),
                "tokens_checked": tokens_checked,
                "num_tokens": num_tokens,
                "rejection_ratio": tokens_checked / num_tokens,
                "first_rejected_token_index": row.get("first_rejected_token_index", ""),
            }
        )
    return rows


def timeout_expected_validity_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeout_rows = [row for row in schema_rows if row["timeout_status"] == "timeout"]
    total_valid = sum(row["n_valid_tests"] for row in timeout_rows)
    total_invalid = sum(row["n_invalid_tests"] for row in timeout_rows)
    total = total_valid + total_invalid
    return [
        {
            "expected_validity": "valid",
            "n_tests": total_valid,
            "share": pct(total_valid, total),
            "n_timeout_schemas": len(timeout_rows),
        },
        {
            "expected_validity": "invalid",
            "n_tests": total_invalid,
            "share": pct(total_invalid, total),
            "n_timeout_schemas": len(timeout_rows),
        },
    ]


def phase_timing_summary_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phase_defs = [
        ("compile_grammar_s", "compile_grammar_s"),
        ("validation_loop_mean_s", "validation_loop_mean_s"),
        ("compute_mask_mean_s", "compute_mask_mean_s"),
        ("commit_token_mean_s", "commit_token_mean_s"),
        ("timeout_elapsed_s", "timeout_elapsed_s"),
    ]
    rows = []
    for status in ("completed", "timeout"):
        members = [row for row in schema_rows if row["timeout_status"] == status]
        for key, phase in phase_defs:
            values = [row.get(key, math.nan) for row in members]
            values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
            rows.append(
                {
                    "schema_status": status,
                    "phase": phase,
                    "n": len(values),
                    "mean_s": mean(values),
                    "std_s": stdev(values),
                    "median_s": median(values),
                    "p95_s": quantile(values, 0.95),
                    "min_s": min(values) if values else math.nan,
                    "max_s": max(values) if values else math.nan,
                }
            )
    return rows


def timing_result_case_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows = []
    for row in read_csv(run_dir / "timing_profile.csv"):
        case = constraint_case(row)
        values = {
            "schema_id": row.get("schema_id", ""),
            "test_id": row.get("test_id", ""),
            "expected_validity": row.get("expected_validity", ""),
            "actual_result": row.get("actual_result", ""),
            "accepted": row.get("accepted", ""),
            "result_available": row.get("result_available", ""),
            "constraint_case": case,
            "compile_grammar_s": (to_float(row.get("compile_grammar_us")) or math.nan) / 1_000_000,
            "validation_loop_s": (to_float(row.get("validation_loop_us")) or math.nan) / 1_000_000,
            "compute_mask_s": (to_float(row.get("compute_mask_us")) or math.nan) / 1_000_000,
            "commit_token_s": (to_float(row.get("commit_token_us")) or math.nan) / 1_000_000,
            "num_tokens": to_float(row.get("num_tokens")) or math.nan,
            "tokens_checked": to_float(row.get("tokens_checked")) or math.nan,
        }
        rows.append(values)
    return rows


def constraint_group(row: dict[str, Any]) -> str:
    if row["timeout_status"] == "timeout":
        return "timeout"
    has_under = row["n_under_constraint"] > 0
    has_over = row["n_over_constraint"] > 0
    if has_under and has_over:
        return "under_and_over"
    if has_under:
        return "under"
    if has_over:
        return "over"
    return "correct_only"


def schema_characteristic_constraint_rows(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    characteristics = [
        "schema_json_chars",
        "schema_file_bytes",
        "nb_keywords",
        "nb_properties",
        "nb_required",
        "schema_depth",
        "nb_branches_combinators",
        "nb_enum_values",
        "nb_regex",
        "n_tests",
        "mean_num_tokens",
    ]
    rows = []
    for characteristic in characteristics:
        usable = [
            row
            for row in schema_rows
            if isinstance(row.get(characteristic), (int, float)) and math.isfinite(row.get(characteristic))
        ]
        values = sorted(row[characteristic] for row in usable)
        if not values:
            continue
        q1, q2, q3 = quantile(values, 0.25), quantile(values, 0.5), quantile(values, 0.75)
        buckets = [
            ("q1_low", lambda v: v <= q1),
            ("q2_mid_low", lambda v: q1 < v <= q2),
            ("q3_mid_high", lambda v: q2 < v <= q3),
            ("q4_high", lambda v: v > q3),
        ]
        for bucket_name, predicate in buckets:
            members = [row for row in usable if predicate(row[characteristic])]
            completed = [row for row in members if row["n_completed"] > 0]
            n_valid = sum(row["n_valid_completed"] for row in completed)
            n_invalid = sum(row["n_invalid_completed"] for row in completed)
            rows.append(
                {
                    "characteristic": characteristic,
                    "bucket": bucket_name,
                    "n_schemas": len(members),
                    "value_min": min((row[characteristic] for row in members), default=math.nan),
                    "value_max": max((row[characteristic] for row in members), default=math.nan),
                    "schemas_with_under_rate": pct(sum(1 for row in members if row["n_under_constraint"] > 0), len(members)),
                    "schemas_with_over_rate": pct(sum(1 for row in members if row["n_over_constraint"] > 0), len(members)),
                    "under_test_rate": pct(sum(row["n_under_constraint"] for row in completed), n_invalid),
                    "over_test_rate": pct(sum(row["n_over_constraint"] for row in completed), n_valid),
                    "timeout_schema_rate": pct(sum(1 for row in members if row["timeout_status"] == "timeout"), len(members)),
                }
            )
    return rows


def svg_text(x: float, y: float, text: Any, size: int = 12, anchor: str = "start", weight: str = "400") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" fill="{PALETTE["text"]}" text-anchor="{anchor}" font-weight="{weight}">'
        f"{html.escape(str(text))}</text>"
    )


def svg_doc(width: int, height: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
        f'<rect width="100%" height="100%" fill="{PALETTE["bg"]}"/>'
        f"{svg_text(24, 30, title, 17, weight='700')}"
        f"{body}</svg>\n"
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


def bar_chart(path: Path, title: str, rows: list[tuple[str, float]], x_label: str = "", color: str = "blue") -> None:
    width, height = 920, max(260, 80 + len(rows) * 38)
    left, right, top, bottom = 230, 32, 54, 44
    plot_w = width - left - right
    max_v = nice_max(max((v for _, v in rows), default=1))
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        val = max_v * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, height - 18, f"{val:.2g}", 10, "middle"))
    for idx, (label, value) in enumerate(rows):
        y = top + idx * 38 + 8
        w = plot_w * value / max_v if max_v else 0
        body.append(svg_text(left - 10, y + 16, label, 11, "end"))
        body.append(f'<rect x="{left}" y="{y}" width="{max(w, 1):.2f}" height="22" rx="3" fill="{PALETTE[color]}"/>')
        body.append(svg_text(left + w + 7, y + 16, f"{value:.3g}", 11))
    if x_label:
        body.append(svg_text(left + plot_w / 2, height - 4, x_label, 11, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def grouped_bar_chart(path: Path, title: str, rows: list[tuple[str, float, float]], labels: tuple[str, str]) -> None:
    width, height = 960, max(300, 100 + len(rows) * 46)
    left, right, top, bottom = 240, 120, 58, 50
    plot_w = width - left - right
    max_v = nice_max(max((max(a, b) for _, a, b in rows), default=1))
    body = [
        f'<rect x="{width-105}" y="45" width="12" height="12" fill="{PALETTE["teal"]}"/>',
        svg_text(width - 88, 56, labels[0], 11),
        f'<rect x="{width-105}" y="64" width="12" height="12" fill="{PALETTE["orange"]}"/>',
        svg_text(width - 88, 75, labels[1], 11),
    ]
    for i in range(6):
        x = left + plot_w * i / 5
        val = max_v * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(x, height - 20, pct_text(val), 10, "middle"))
    for idx, (label, a, b) in enumerate(rows):
        y = top + idx * 46 + 7
        body.append(svg_text(left - 10, y + 22, label, 11, "end"))
        aw = plot_w * a / max_v if max_v else 0
        bw = plot_w * b / max_v if max_v else 0
        body.append(f'<rect x="{left}" y="{y}" width="{max(aw, 1):.2f}" height="15" rx="2" fill="{PALETTE["teal"]}"/>')
        body.append(f'<rect x="{left}" y="{y+18}" width="{max(bw, 1):.2f}" height="15" rx="2" fill="{PALETTE["orange"]}"/>')
        body.append(svg_text(left + aw + 6, y + 12, pct_text(a), 10))
        body.append(svg_text(left + bw + 6, y + 30, pct_text(b), 10))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def scatter_plot(
    path: Path,
    title: str,
    points: list[tuple[float, float, str]],
    x_label: str,
    y_label: str,
    log_x: bool = False,
    log_y: bool = False,
) -> None:
    width, height = 900, 560
    left, right, top, bottom = 82, 32, 56, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    clean = [(x, y, s) for x, y, s in points if x is not None and y is not None and x > 0 and y > 0 and math.isfinite(x) and math.isfinite(y)]
    if log_x:
        x_vals = [safe_log10(x) for x, _, _ in clean]
    else:
        x_vals = [x for x, _, _ in clean]
    if log_y:
        y_vals = [safe_log10(y) for _, y, _ in clean]
    else:
        y_vals = [y for _, y, _ in clean]
    if not clean:
        path.write_text(svg_doc(width, height, title, svg_text(450, 280, "No data", 14, "middle")), encoding="utf-8")
        return
    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        y = top + plot_h * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="{PALETTE["grid"]}"/>')
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
    for raw_x, raw_y, status in clean:
        x_val = safe_log10(raw_x) if log_x else raw_x
        y_val = safe_log10(raw_y) if log_y else raw_y
        cx = left + (x_val - x_min) / (x_max - x_min) * plot_w
        cy = top + plot_h - (y_val - y_min) / (y_max - y_min) * plot_h
        fill = PALETTE["red"] if status == "timeout" else PALETTE["blue"]
        body.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4.2" fill="{fill}" opacity="0.72"/>')
    body.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(svg_text(left + plot_w / 2, height - 22, x_label, 12, "middle"))
    body.append(svg_text(20, top + plot_h / 2, y_label, 12, "middle"))
    body.append(f'<rect x="{width-165}" y="48" width="12" height="12" fill="{PALETTE["blue"]}"/>')
    body.append(svg_text(width - 147, 59, "completed", 11))
    body.append(f'<rect x="{width-165}" y="68" width="12" height="12" fill="{PALETTE["red"]}"/>')
    body.append(svg_text(width - 147, 79, "timeout", 11))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def boxplot(path: Path, title: str, groups: list[tuple[str, list[float]]], y_label: str) -> None:
    width, height = 760, 500
    left, right, top, bottom = 76, 34, 56, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [v for _, vals in groups for v in vals if math.isfinite(v)]
    if not values:
        path.write_text(svg_doc(width, height, title, svg_text(380, 250, "No data", 14, "middle")), encoding="utf-8")
        return
    y_min, y_max = 0, nice_max(max(values))
    body = []
    for i in range(6):
        y = top + plot_h - plot_h * i / 5
        val = y_max * i / 5
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
        body.append(svg_text(left - 8, y + 4, f"{val:.2g}", 10, "end"))
    step = plot_w / max(len(groups), 1)
    for idx, (label, vals) in enumerate(groups):
        vals = sorted(v for v in vals if math.isfinite(v))
        if not vals:
            continue
        q1, q2, q3 = quantile(vals, 0.25), quantile(vals, 0.5), quantile(vals, 0.75)
        low, high = min(vals), max(vals)
        cx = left + step * idx + step / 2

        def y_pos(v: float) -> float:
            return top + plot_h - (v - y_min) / (y_max - y_min) * plot_h

        box_w = min(90, step * 0.45)
        body.append(f'<line x1="{cx:.2f}" y1="{y_pos(low):.2f}" x2="{cx:.2f}" y2="{y_pos(high):.2f}" stroke="{PALETTE["gray"]}" stroke-width="2"/>')
        body.append(f'<rect x="{cx-box_w/2:.2f}" y="{y_pos(q3):.2f}" width="{box_w:.2f}" height="{max(y_pos(q1)-y_pos(q3), 1):.2f}" fill="{PALETTE["teal"]}" opacity="0.7" stroke="{PALETTE["text"]}"/>')
        body.append(f'<line x1="{cx-box_w/2:.2f}" y1="{y_pos(q2):.2f}" x2="{cx+box_w/2:.2f}" y2="{y_pos(q2):.2f}" stroke="{PALETTE["text"]}" stroke-width="2"/>')
        body.append(svg_text(cx, height - 34, f"{label} (n={len(vals)})", 11, "middle"))
    body.append(svg_text(24, top + plot_h / 2, y_label, 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def stacked_phase_bar(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    completed = [
        r
        for r in rows
        if r["timeout_status"] == "completed" and math.isfinite(r.get("compile_grammar_s", math.nan))
    ]
    completed = sorted(completed, key=lambda r: r["compile_grammar_s"], reverse=True)[:12]
    width, height = 960, max(360, 92 + len(completed) * 34)
    left, right, top, bottom = 260, 180, 60, 42
    plot_w = width - left - right
    body = []
    colors = [PALETTE["blue"], PALETTE["teal"], PALETTE["orange"], PALETTE["purple"]]
    for i, (_, label) in enumerate(PHASE_COLUMNS):
        body.append(f'<rect x="{width-155}" y="{48+i*19}" width="12" height="12" fill="{colors[i]}"/>')
        body.append(svg_text(width - 138, 59 + i * 19, label, 11))
    for idx, row in enumerate(completed):
        y = top + idx * 34
        values = [row.get(col, math.nan) for col, _ in PHASE_COLUMNS]
        values = [v if math.isfinite(v) else 0.0 for v in values]
        total = sum(values)
        x = left
        body.append(svg_text(left - 10, y + 16, row["schema_id"].replace("Github_trivial---", ""), 10, "end"))
        for value, color in zip(values, colors):
            w = plot_w * value / total if total else 0
            if w > 0:
                body.append(f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="20" fill="{color}"/>')
            x += w
        body.append(svg_text(left + plot_w + 8, y + 15, f"{total:.3g}s", 10))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def ecdf_plot(path: Path, title: str, groups: list[tuple[str, list[float], str]], x_label: str) -> None:
    width, height = 860, 520
    left, right, top, bottom = 78, 34, 56, 68
    plot_w, plot_h = width - left - right, height - top - bottom
    all_values = [v for _, vals, _ in groups for v in vals if v > 0 and math.isfinite(v)]
    if not all_values:
        path.write_text(svg_doc(width, height, title, svg_text(430, 260, "No data", 14, "middle")), encoding="utf-8")
        return
    x_vals = [safe_log10(v) for v in all_values]
    x_min, x_max = min(x_vals), max(x_vals)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        y = top + plot_h * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="{PALETTE["grid"]}"/>')
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
    for group_idx, (label, vals, color_name) in enumerate(groups):
        vals = sorted(v for v in vals if v > 0 and math.isfinite(v))
        if not vals:
            continue
        points = []
        for idx, value in enumerate(vals, 1):
            x = left + (safe_log10(value) - x_min) / (x_max - x_min) * plot_w
            y = top + plot_h - (idx / len(vals)) * plot_h
            points.append(f"{x:.2f},{y:.2f}")
        body.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{PALETTE[color_name]}" stroke-width="2.5"/>')
        body.append(f'<rect x="{width-170}" y="{50+group_idx*20}" width="12" height="12" fill="{PALETTE[color_name]}"/>')
        body.append(svg_text(width - 152, 61 + group_idx * 20, f"{label} (n={len(vals)})", 11))
    body.append(svg_text(left + plot_w / 2, height - 22, x_label, 12, "middle"))
    body.append(svg_text(22, top + plot_h / 2, "ECDF", 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def heatmap(path: Path, title: str, rows: list[dict[str, Any]], groups: list[str]) -> None:
    rows = rows[:22]
    cell_w, cell_h = 105, 22
    max_label_len = max((len(str(row.get("feature", ""))) for row in rows), default=20)
    left = max(250, min(610, int(max_label_len * 6.2 + 34)))
    width, height = left + cell_w * len(groups) + 44, max(300, 92 + len(rows) * 28)
    top = 64
    body = []
    for j, group in enumerate(groups):
        body.append(svg_text(left + j * cell_w + cell_w / 2, top - 14, group, 11, "middle", "700"))
    for i, row in enumerate(rows):
        y = top + i * 28
        body.append(svg_text(left - 10, y + 15, row["feature"], 10, "end"))
        for j, group in enumerate(groups):
            value = row.get(group, 0.0)
            intensity = int(245 - 165 * value)
            fill = f"rgb({intensity},{max(95, intensity+12)},{245})"
            x = left + j * cell_w
            body.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h}" fill="{fill}" stroke="{PALETTE["bg"]}"/>')
            body.append(svg_text(x + (cell_w - 4) / 2, y + 15, pct_text(value), 10, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def histogram(path: Path, title: str, values: list[float], x_label: str) -> None:
    width, height = 980, 560
    left, right, top, bottom = 86, 36, 86, 96
    plot_w, plot_h = width - left - right, height - top - bottom
    values = [min(max(v, 0.0), 1.0) for v in values if math.isfinite(v)]
    if not values:
        path.write_text(svg_doc(width, height, title, svg_text(width / 2, height / 2, "No data", 14, "middle")), encoding="utf-8")
        return
    bins = 10
    low, high = 0.0, 1.0
    counts = [0] * bins
    for value in values:
        idx = min(bins - 1, int((value - low) / (high - low) * bins))
        counts[idx] += 1
    max_count = nice_max(max(counts))
    body = []
    bar_w = plot_w / bins
    for tick in range(6):
        y = top + plot_h - plot_h * tick / 5
        count = max_count * tick / 5
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        body.append(svg_text(left - 10, y + 4, f"{count:.0f}", 10, "end"))
    for idx, count in enumerate(counts):
        h = plot_h * count / max_count if max_count else 0
        x = left + idx * bar_w
        y = top + plot_h - h
        body.append(f'<rect x="{x+2:.2f}" y="{y:.2f}" width="{bar_w-4:.2f}" height="{h:.2f}" fill="{PALETTE["orange"]}"/>')
        if count:
            body.append(svg_text(x + bar_w / 2, y - 6, f"{count}", 10, "middle"))
        label_left = low + (high - low) * idx / bins
        label_right = low + (high - low) * (idx + 1) / bins
        body.append(svg_text(x + bar_w / 2, height - 58, f"{label_left:.1f}-{label_right:.1f}", 10, "middle"))
    median_v = median(values)
    p90_v = quantile(values, 0.9)
    median_x = left + plot_w * median_v
    body.append(f'<line x1="{median_x:.2f}" y1="{top}" x2="{median_x:.2f}" y2="{top+plot_h}" stroke="{PALETTE["text"]}" stroke-width="2" stroke-dasharray="5 4"/>')
    body.append(svg_text(median_x + 6, top + 14, f"median {median_v:.2f}", 11))
    body.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(svg_text(left + plot_w / 2, height - 24, x_label, 12, "middle"))
    body.append(svg_text(24, top + plot_h / 2, "over-constrained valid tests", 12, "middle"))
    body.append(svg_text(left, 58, f"0 = rejected at first token, 1 = rejected near the end | n={len(values)}, p90={p90_v:.2f}", 12))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def stacked_percent_chart(path: Path, title: str, rows: list[dict[str, Any]], label_key: str, value_key: str) -> None:
    width, height = 760, 240
    left, top, bar_w, bar_h = 70, 92, 560, 34
    total = sum(float(row.get(value_key, 0)) for row in rows)
    colors = [PALETTE["teal"], PALETTE["orange"], PALETTE["red"], PALETTE["blue"]]
    body = []
    x = left
    for idx, row in enumerate(rows):
        value = float(row.get(value_key, 0))
        share = pct(value, total)
        w = bar_w * share
        body.append(f'<rect x="{x:.2f}" y="{top}" width="{w:.2f}" height="{bar_h}" fill="{colors[idx % len(colors)]}"/>')
        if w > 44:
            body.append(svg_text(x + w / 2, top + 22, pct_text(share), 11, "middle", "700"))
        legend_x = left + idx * 220
        body.append(f'<rect x="{legend_x}" y="{top+64}" width="12" height="12" fill="{colors[idx % len(colors)]}"/>')
        body.append(svg_text(legend_x + 18, top + 75, f"{row[label_key]}: {int(value)} ({pct_text(share)})", 12))
        x += w
    body.append(f'<rect x="{left}" y="{top}" width="{bar_w}" height="{bar_h}" fill="none" stroke="{PALETTE["text"]}"/>')
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def phase_mean_std_chart(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    phases = ["compile_grammar_s", "validation_loop_mean_s", "compute_mask_mean_s", "commit_token_mean_s", "timeout_elapsed_s"]
    statuses = ["completed", "timeout"]
    width, height = 960, 440
    left, right, top, bottom = 82, 32, 64, 96
    plot_w, plot_h = width - left - right, height - top - bottom
    by_key = {(row["schema_status"], row["phase"]): row for row in rows}
    max_v = nice_max(max((row["mean_s"] + row["std_s"] for row in rows if math.isfinite(row["mean_s"])), default=1))
    body = []
    for i in range(6):
        y = top + plot_h - plot_h * i / 5
        val = max_v * i / 5
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
        body.append(svg_text(left - 8, y + 4, f"{val:.2g}", 10, "end"))
    cluster_w = plot_w / len(phases)
    bar_w = 24
    colors = {"completed": PALETTE["blue"], "timeout": PALETTE["red"]}

    def y_pos(v: float) -> float:
        return top + plot_h - (v / max_v) * plot_h

    for idx, phase in enumerate(phases):
        cx = left + cluster_w * idx + cluster_w / 2
        for offset_idx, status in enumerate(statuses):
            row = by_key.get((status, phase))
            if not row or not math.isfinite(row["mean_s"]):
                continue
            mean_v = row["mean_s"]
            std_v = row["std_s"] if math.isfinite(row["std_s"]) else 0.0
            x = cx + (-bar_w * 0.75 if offset_idx == 0 else bar_w * 0.75)
            y = y_pos(mean_v)
            h = top + plot_h - y
            body.append(f'<rect x="{x-bar_w/2:.2f}" y="{y:.2f}" width="{bar_w}" height="{max(h, 1):.2f}" fill="{colors[status]}" opacity="0.82"/>')
            y_low = y_pos(max(mean_v - std_v, 0))
            y_high = y_pos(mean_v + std_v)
            body.append(f'<line x1="{x:.2f}" y1="{y_high:.2f}" x2="{x:.2f}" y2="{y_low:.2f}" stroke="{PALETTE["text"]}"/>')
            body.append(f'<line x1="{x-7:.2f}" y1="{y_high:.2f}" x2="{x+7:.2f}" y2="{y_high:.2f}" stroke="{PALETTE["text"]}"/>')
            body.append(f'<line x1="{x-7:.2f}" y1="{y_low:.2f}" x2="{x+7:.2f}" y2="{y_low:.2f}" stroke="{PALETTE["text"]}"/>')
        body.append(svg_text(cx, height - 54, phase.replace("_mean", ""), 10, "middle"))
    body.append(f'<rect x="{width-170}" y="54" width="12" height="12" fill="{PALETTE["blue"]}"/>')
    body.append(svg_text(width - 152, 65, "completed", 11))
    body.append(f'<rect x="{width-170}" y="74" width="12" height="12" fill="{PALETTE["red"]}"/>')
    body.append(svg_text(width - 152, 85, "timeout", 11))
    body.append(svg_text(24, top + plot_h / 2, "seconds", 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def constraint_scatter_plot(
    path: Path,
    title: str,
    points: list[tuple[float, float, str]],
    x_label: str,
    y_label: str,
    log_x: bool = True,
    log_y: bool = False,
) -> None:
    width, height = 920, 560
    left, right, top, bottom = 82, 170, 56, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    clean = [
        (x, y, group)
        for x, y, group in points
        if x is not None and y is not None and x > 0 and y >= 0 and math.isfinite(x) and math.isfinite(y)
    ]
    if not clean:
        path.write_text(svg_doc(width, height, title, svg_text(460, 280, "No data", 14, "middle")), encoding="utf-8")
        return
    x_vals = [safe_log10(x) if log_x else x for x, _, _ in clean]
    y_vals = [safe_log10(y + 1) if log_y else y for _, y, _ in clean]
    x_min, x_max = min(x_vals), max(x_vals)
    y_min, y_max = min(y_vals), max(y_vals)
    if x_min == x_max:
        x_min -= 1
        x_max += 1
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    colors = {
        "correct_only": PALETTE["blue"],
        "under": PALETTE["orange"],
        "over": PALETTE["purple"],
        "under_and_over": PALETTE["red"],
        "timeout": PALETTE["gray"],
    }
    labels = {
        "correct_only": "correct only",
        "under": "under",
        "over": "over",
        "under_and_over": "under+over",
        "timeout": "timeout",
    }
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        y = top + plot_h * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="{PALETTE["grid"]}"/>')
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
    for raw_x, raw_y, group in clean:
        x_val = safe_log10(raw_x) if log_x else raw_x
        y_val = safe_log10(raw_y + 1) if log_y else raw_y
        cx = left + (x_val - x_min) / (x_max - x_min) * plot_w
        cy = top + plot_h - (y_val - y_min) / (y_max - y_min) * plot_h
        body.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="{colors.get(group, PALETTE["gray"])}" opacity="0.72"/>')
    for idx, key in enumerate(labels):
        y = 52 + idx * 21
        body.append(f'<rect x="{width-145}" y="{y}" width="12" height="12" fill="{colors[key]}"/>')
        body.append(svg_text(width - 127, y + 11, labels[key], 11))
    body.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="{PALETTE["text"]}"/>')
    body.append(svg_text(left + plot_w / 2, height - 22, x_label, 12, "middle"))
    body.append(svg_text(22, top + plot_h / 2, y_label, 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def make_plots(
    out_dir: Path,
    schema_rows: list[dict[str, Any]],
    feature_timeout: list[dict[str, Any]],
    feature_under_lift: list[dict[str, Any]],
    feature_over_lift: list[dict[str, Any]],
    feature_constraints: list[dict[str, Any]],
    heatmap_rows: list[dict[str, Any]],
    pair_heatmap_rows: list[dict[str, Any]],
    pair_timeout_lift: list[dict[str, Any]],
    pair_under_lift: list[dict[str, Any]],
    pair_over_lift: list[dict[str, Any]],
    over_rows: list[dict[str, Any]],
    quartiles: list[dict[str, Any]],
    timeout_validity: list[dict[str, Any]],
    phase_summary: list[dict[str, Any]],
    timing_cases: list[dict[str, Any]],
    characteristic_rows: list[dict[str, Any]],
) -> None:
    timeout_counts = Counter(r["timeout_stage"] or "completed" for r in schema_rows if r["timeout_status"] == "timeout")
    bar_chart(out_dir / "timeout_by_stage.svg", "Timeouts by stage", list(timeout_counts.items()) or [("none", 0)], "schemas", "red")

    completed_compile = [
        r["compile_grammar_s"]
        for r in schema_rows
        if r["timeout_status"] == "completed" and math.isfinite(r.get("compile_grammar_s", math.nan))
    ]
    timeout_elapsed = [r["timeout_elapsed_s"] for r in schema_rows if math.isfinite(r.get("timeout_elapsed_s", math.nan))]
    boxplot(out_dir / "compile_completed_vs_timeout_boxplot.svg", "Completed compile time vs timeout elapsed", [("completed compile", completed_compile), ("timeout elapsed", timeout_elapsed)], "seconds")

    stacked_phase_bar(out_dir / "phase_time_share_top_schemas.svg", "Phase time share for slowest completed schemas", schema_rows)

    top_slow = sorted(
        [
            (r["schema_id"], r["compile_grammar_s"])
            for r in schema_rows
            if r["timeout_status"] == "completed" and math.isfinite(r.get("compile_grammar_s", math.nan))
        ],
        key=lambda x: x[1],
        reverse=True,
    )[:15]
    bar_chart(out_dir / "top_slowest_schemas.svg", "Top slowest completed schemas", [(k.replace("Github_trivial---", ""), v) for k, v in top_slow], "compile_grammar_s", "blue")

    scatter_plot(
        out_dir / "schema_size_vs_compile.svg",
        "Schema size vs compile time",
        [(r["schema_json_chars"], r["compile_grammar_s"] if math.isfinite(r.get("compile_grammar_s", math.nan)) else r.get("timeout_elapsed_s", math.nan), r["timeout_status"]) for r in schema_rows],
        "schema_json_chars (log)",
        "seconds (log)",
        log_x=True,
        log_y=True,
    )
    scatter_plot(
        out_dir / "schema_depth_vs_compile.svg",
        "Schema depth vs compile time",
        [(r["schema_depth"], r["compile_grammar_s"] if math.isfinite(r.get("compile_grammar_s", math.nan)) else r.get("timeout_elapsed_s", math.nan), r["timeout_status"]) for r in schema_rows],
        "schema_depth",
        "seconds (log)",
        log_x=False,
        log_y=True,
    )
    ecdf_plot(
        out_dir / "schema_size_timeout_ecdf.svg",
        "Schema size ECDF: completed vs timeout",
        [
            ("completed", [r["schema_json_chars"] for r in schema_rows if r["timeout_status"] != "timeout"], "blue"),
            ("timeout", [r["schema_json_chars"] for r in schema_rows if r["timeout_status"] == "timeout"], "red"),
        ],
        "schema_json_chars (log)",
    )

    lift_rows = [
        (r["feature"], min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in feature_timeout[:15]
    ]
    bar_chart(out_dir / "feature_timeout_lift.svg", "Feature timeout lift (capped at 12x)", lift_rows, "lift", "purple")
    under_lift_rows = [
        (r["feature"], min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in feature_under_lift
        if r["eligible_lift"]
    ][:15]
    bar_chart(out_dir / "feature_under_lift.svg", "Feature under-constraint lift (capped at 12x)", under_lift_rows, "lift", "teal")
    over_lift_rows = [
        (r["feature"], min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in feature_over_lift
        if r["eligible_lift"]
    ][:15]
    bar_chart(out_dir / "feature_over_lift.svg", "Feature over-constraint lift (capped at 12x)", over_lift_rows, "lift", "orange")

    fc = feature_constraints[:15]
    grouped_bar_chart(
        out_dir / "feature_under_over_rates.svg",
        "Under vs over rates by feature",
        [(r["feature"], r["under_rate"], r["over_rate"]) for r in fc],
        ("under", "over"),
    )
    heatmap(out_dir / "feature_group_heatmap.svg", "Feature prevalence by schema group", heatmap_rows, ["correct", "timeout", "under", "over"])
    heatmap(out_dir / "feature_pair_group_heatmap.svg", "Pair prevalence by schema group", pair_heatmap_rows, ["correct", "timeout", "under", "over"])
    pair_timeout_plot_rows = [
        (r["feature_pair"].replace("__AND__", " + "), min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in pair_timeout_lift
        if r["eligible_lift"]
    ][:15]
    bar_chart(out_dir / "feature_pair_timeout_lift.svg", "Feature-pair timeout lift (capped at 12x)", pair_timeout_plot_rows, "lift", "purple")
    pair_under_plot_rows = [
        (r["feature_pair"].replace("__AND__", " + "), min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in pair_under_lift
        if r["eligible_lift"]
    ][:15]
    bar_chart(out_dir / "feature_pair_under_lift.svg", "Feature-pair under-constraint lift (capped at 12x)", pair_under_plot_rows, "lift", "teal")
    pair_over_plot_rows = [
        (r["feature_pair"].replace("__AND__", " + "), min(r["lift"], 12) if math.isfinite(r["lift"]) else 12)
        for r in pair_over_lift
        if r["eligible_lift"]
    ][:15]
    bar_chart(out_dir / "feature_pair_over_lift.svg", "Feature-pair over-constraint lift (capped at 12x)", pair_over_plot_rows, "lift", "orange")

    timing_rows = read_csv(out_dir.parent / "timing_profile.csv")
    scatter_plot(
        out_dir / "tokens_vs_validation_loop.svg",
        "Tokens vs validation loop time",
        [(to_float(r.get("num_tokens")) or 0, (to_float(r.get("validation_loop_us")) or 0) / 1_000_000, "completed") for r in timing_rows],
        "num_tokens (log)",
        "validation_loop_s (log)",
        log_x=True,
        log_y=True,
    )
    histogram(out_dir / "over_rejection_ratio.svg", "Over-constraint rejection ratio", [r["rejection_ratio"] for r in over_rows], "tokens_checked / num_tokens")

    grouped_bar_chart(
        out_dir / "slow_completed_under_over_rates.svg",
        "Under/over rates by compile speed group",
        [(r["compile_speed_group"], r["under_rate"], r["over_rate"]) for r in quartiles],
        ("under", "over"),
    )

    stacked_percent_chart(
        out_dir / "timeout_expected_validity_share.svg",
        "Expected validity among timeout tests",
        timeout_validity,
        "expected_validity",
        "n_tests",
    )
    phase_mean_std_chart(
        out_dir / "phase_timing_mean_std_by_status.svg",
        "Phase timing mean +/- std by schema status",
        phase_summary,
    )

    case_order = ["correct_accept", "correct_reject", "under_constraint", "over_constraint", "no_decision"]
    boxplot(
        out_dir / "compile_time_by_result_case_boxplot.svg",
        "Compile time by result case",
        [
            (case, [row["compile_grammar_s"] for row in timing_cases if row["constraint_case"] == case])
            for case in case_order
        ],
        "compile_grammar_s",
    )
    boxplot(
        out_dir / "validation_time_by_result_case_boxplot.svg",
        "Validation time by result case",
        [
            (case, [row["validation_loop_s"] for row in timing_cases if row["constraint_case"] == case])
            for case in case_order
        ],
        "validation_loop_s",
    )

    for characteristic, y_label in [
        ("nb_keywords", "nb_keywords"),
        ("schema_depth", "schema_depth"),
        ("nb_properties", "nb_properties"),
        ("nb_required", "nb_required"),
        ("nb_branches_combinators", "nb_branches_combinators"),
    ]:
        constraint_scatter_plot(
            out_dir / f"schema_size_vs_{characteristic}_constraint_group.svg",
            f"Schema size vs {characteristic} by constraint group",
            [(row["schema_json_chars"], row[characteristic], constraint_group(row)) for row in schema_rows],
            "schema_json_chars (log)",
            y_label,
            log_x=True,
            log_y=False,
        )

    size_rows = [row for row in characteristic_rows if row["characteristic"] == "schema_json_chars"]
    grouped_bar_chart(
        out_dir / "schema_size_quartiles_under_over_rates.svg",
        "Under/over rates by schema size quartile",
        [(row["bucket"], row["under_test_rate"], row["over_test_rate"]) for row in size_rows],
        ("under", "over"),
    )


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if i == 0 else "---:" for i in range(len(headers))) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def make_readme(
    out_dir: Path,
    dataset: str,
    framework: str,
    schema_rows: list[dict[str, Any]],
    source_counts: dict[str, Any],
    feature_timeout: list[dict[str, Any]],
    feature_constraints: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
    pair_heatmap_rows: list[dict[str, Any]],
    quartiles: list[dict[str, Any]],
    timeout_validity: list[dict[str, Any]],
    phase_summary: list[dict[str, Any]],
) -> None:
    total_schemas = len(schema_rows)
    timeout_schemas = [r for r in schema_rows if r["timeout_status"] == "timeout"]
    completed_schemas = [r for r in schema_rows if r["timeout_status"] == "completed"]
    total_tests = sum(r["n_tests"] for r in schema_rows)
    completed_tests = sum(r["n_completed"] for r in schema_rows)
    under = sum(r["n_under_constraint"] for r in schema_rows)
    over = sum(r["n_over_constraint"] for r in schema_rows)
    correct = sum(r["n_correct_accept"] + r["n_correct_reject"] for r in schema_rows)
    invalid_completed = sum(r["n_invalid_completed"] for r in schema_rows)
    valid_completed = sum(r["n_valid_completed"] for r in schema_rows)
    compile_values = [
        r["compile_grammar_s"]
        for r in schema_rows
        if r["timeout_status"] == "completed" and math.isfinite(r.get("compile_grammar_s", math.nan))
    ]
    timeout_counts = Counter(r["timeout_stage"] for r in timeout_schemas)
    timeout_validity_table = [
        [
            row["expected_validity"],
            row["n_tests"],
            pct_text(row["share"]),
        ]
        for row in timeout_validity
    ]
    phase_summary_table = [
        [
            row["schema_status"],
            row["phase"],
            row["n"],
            f"{row['mean_s']:.3g}" if math.isfinite(row["mean_s"]) else "",
            f"{row['std_s']:.3g}" if math.isfinite(row["std_s"]) else "",
            f"{row['median_s']:.3g}" if math.isfinite(row["median_s"]) else "",
            f"{row['p95_s']:.3g}" if math.isfinite(row["p95_s"]) else "",
        ]
        for row in phase_summary
        if row["n"] > 0
    ]

    top_feature_timeout = [
        [
            f"`{r['feature']}`",
            r["schemas_with_feature"],
            pct_text(r["timeout_rate_with"]),
            pct_text(r["timeout_rate_without"]),
            "inf" if not math.isfinite(r["lift"]) else f"{r['lift']:.2f}",
        ]
        for r in feature_timeout[:10]
    ]
    top_feature_constraints = [
        [
            f"`{r['feature']}`",
            r["n_schemas"],
            pct_text(r["under_rate"]),
            pct_text(r["over_rate"]),
            pct_text(r["correct_rate"]),
        ]
        for r in feature_constraints[:10]
    ]
    top_pairs = [
        [
            f"`{r['feature_pair']}`",
            r["n_schemas"],
            pct_text(r["timeout_rate"]),
            pct_text(r["under_rate"]),
            pct_text(r["over_rate"]),
        ]
        for r in pair_rows[:10]
    ]
    top_pair_heatmap = [
        [
            f"`{r['feature_pair']}`",
            r["n_schemas"],
            r["risk_count"],
            f"{r['interest_score']:.3g}",
            pct_text(r["timeout"]),
            pct_text(r["under"]),
            pct_text(r["over"]),
        ]
        for r in pair_heatmap_rows[:10]
    ]
    quartile_table = [
        [
            r["compile_speed_group"],
            r["n_schemas"],
            f"{r['compile_min_s']:.3g}",
            f"{r['compile_max_s']:.3g}",
            pct_text(r["under_rate"]),
            pct_text(r["over_rate"]),
            pct_text(r["accuracy_completed"]),
        ]
        for r in quartiles
    ]

    lines = [
        f"# Statistical study: {dataset} / {framework}",
        "",
        "This folder contains schema-level statistics and SVG plots generated from the dataset run files. Compile time is analyzed once per schema, not once per test, to avoid overweighting schemas that contain many tests.",
        "",
        "## Inputs",
        "",
        f"- `per_test_results.jsonl`: {source_counts['per_test_rows']} rows",
        f"- `timing_profile.csv`: {source_counts['timing_rows']} rows",
        f"- `timed_out_schemas.jsonl`: {source_counts['timeout_rows']} rows",
        "",
        "## Main summary",
        "",
        markdown_table(
            ["metric", "value"],
            [
                ["schemas", total_schemas],
                ["completed schemas", len(completed_schemas)],
                ["timeout schemas", len(timeout_schemas)],
                ["schema timeout rate", pct_text(pct(len(timeout_schemas), total_schemas))],
                ["tests", total_tests],
                ["completed tests", completed_tests],
                ["coverage rate", pct_text(pct(completed_tests, total_tests))],
                ["accuracy on completed tests", pct_text(pct(correct, completed_tests))],
                ["under-constraint rate", pct_text(pct(under, invalid_completed))],
                ["over-constraint rate", pct_text(pct(over, valid_completed))],
                ["median compile_grammar_s", f"{median(compile_values):.3g}"],
                ["p95 compile_grammar_s", f"{quantile(compile_values, 0.95):.3g}"],
                ["max compile_grammar_s", f"{max(compile_values) if compile_values else math.nan:.3g}"],
            ],
        ),
        "",
        "## Timeout stages",
        "",
        markdown_table(
            ["timeout_stage", "schemas"],
            [[stage or "unknown", count] for stage, count in timeout_counts.most_common()] or [["none", 0]],
        ),
        "",
        "Timeout stages are inferred from the timeout log when available, otherwise from partial checkpoints in `timing_profile.csv`.",
        "",
        "## Expected validity among timeout tests",
        "",
        markdown_table(["expected_validity", "tests", "share"], timeout_validity_table),
        "",
        "## Timing by schema status",
        "",
        markdown_table(["status", "phase", "n", "mean_s", "std_s", "median_s", "p95_s"], phase_summary_table),
        "",
        "For timeout schemas, phase values are partial checkpoints when available; `timeout_elapsed_s` is the supervisor elapsed time.",
        "",
        "## Feature extraction",
        "",
        "Raw structural features are `has_*` indicators for explicit JSON Schema keywords or benchmark categories. `$ref`, `$anchor`, `$dynamicRef`, `$defs`/`definitions`, `if`/`then`/`else`, and content keywords are mapped directly from the schema; `boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `infinite-loop-detection` is only read from benchmark metadata when present because it is not a JSON Schema keyword.",
        "",
        "Derived indicators (`large_enum`, `many_required`, `many_properties`, `deep_schema`) are kept separate from raw keyword features. Pair rows are generated automatically with `itertools.combinations(BASE_FEATURES, 2)`; a pair is present only when both base features are present in the same schema.",
        "",
        "## Features associated with timeout",
        "",
        markdown_table(["feature", "schemas", "timeout with", "timeout without", "lift"], top_feature_timeout),
        "",
        "## Features associated with under/over-constraint",
        "",
        markdown_table(["feature", "schemas", "under_rate", "over_rate", "correct_rate"], top_feature_constraints),
        "",
        "## Simple feature pairs",
        "",
        markdown_table(["feature_pair", "schemas", "timeout_rate", "under_rate", "over_rate"], top_pairs),
        "",
        "## Selected pair heatmap candidates",
        "",
        "The pair heatmap keeps the most interesting generated pairs. The ranking first requires usable support, then prioritizes the number of signals among timeout/under/over, then capped lift, delta, and support. This avoids filling the plot with rare pairs that only look strong because the denominator is tiny.",
        "",
        markdown_table(["feature_pair", "schemas", "risk_count", "interest_score", "timeout_group", "under_group", "over_group"], top_pair_heatmap),
        "",
        "## Very slow completed schemas and errors",
        "",
        markdown_table(["group", "schemas", "compile_min_s", "compile_max_s", "under_rate", "over_rate", "accuracy"], quartile_table),
        "",
        "## Generated files",
        "",
        "- `schema_level_stats.csv`: one row per schema with timing, correctness, timeout status, and JSON Schema features.",
        "- `feature_timeout_lift.csv`: P(timeout | feature), P(timeout | absence), and lift.",
        "- `feature_under_lift.csv`: P(under | feature), P(under | absence), and lift using completed invalid tests.",
        "- `feature_over_lift.csv`: P(over | feature), P(over | absence), and lift using completed valid tests.",
        "- `feature_constraint_rates.csv`: under/over/correct rates for schemas containing each feature.",
        "- `feature_group_heatmap.csv`: feature prevalence for correct, timeout, under, and over schema groups.",
        "- `feature_pair_group_heatmap.csv`: selected pair prevalence for correct, timeout, under, and over schema groups.",
        "- `feature_pair_rates.csv`: automatically generated pairwise rates over all raw base features.",
        "- `feature_pair_timeout_lift.csv`: P(timeout | feature pair), P(timeout | absence), and lift.",
        "- `feature_pair_under_lift.csv`: P(under | feature pair), P(under | absence), and lift using completed invalid tests.",
        "- `feature_pair_over_lift.csv`: P(over | feature pair), P(over | absence), and lift using completed valid tests.",
        "- `slow_completed_constraint_quartiles.csv`: under/over rates by compile-time quartile.",
        "- `timeout_expected_validity.csv`: valid vs invalid expected tests among timeout schemas.",
        "- `phase_timing_summary_by_status.csv`: mean/std timing by phase for completed and timeout schemas.",
        "- `timing_by_result_case.csv`: per-test timing classified as correct_accept, correct_reject, under, over, or no_decision.",
        "- `schema_characteristic_constraint_bins.csv`: non-feature schema characteristics binned by quartile with under/over rates.",
        "- SVG plots: open directly from this folder.",
        "",
        "## Plots to inspect first",
        "",
        "- `schema_size_vs_compile.svg` and `schema_depth_vs_compile.svg` for the size/depth relationship.",
        "- `feature_timeout_lift.svg`, `feature_under_lift.svg`, and `feature_over_lift.svg` for single-feature lift signals.",
        "- `feature_under_over_rates.svg` and `feature_group_heatmap.svg` for isolated feature errors.",
        "- `feature_pair_timeout_lift.svg`, `feature_pair_under_lift.svg`, and `feature_pair_over_lift.svg` for pairwise lift signals.",
        "- `feature_pair_group_heatmap.svg` for the most interesting generated pairwise combinations.",
        "- `phase_time_share_top_schemas.svg` to verify whether compile time dominates the slow completed schemas.",
        "- `timeout_expected_validity_share.svg` for the valid/invalid mix inside timeout schemas.",
        "- `compile_time_by_result_case_boxplot.svg` and `validation_time_by_result_case_boxplot.svg` for timing by result type.",
        "- `schema_size_vs_*_constraint_group.svg` and `schema_size_quartiles_under_over_rates.svg` for schema size/complexity vs under/over.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)
    data_root = Path(args.data_root)
    run_dir = results_root / args.framework / args.dataset
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")
    out_dir = Path(args.output_dir) if args.output_dir else run_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_rows, source_counts = collect_schema_rows(args.dataset, args.framework, run_dir, data_root)
    feature_timeout = feature_timeout_rows(schema_rows)
    feature_under_lift = feature_constraint_lift_rows(schema_rows, "under")
    feature_over_lift = feature_constraint_lift_rows(schema_rows, "over")
    feature_constraints = feature_constraint_rows(schema_rows)
    heat_rows = group_feature_heatmap_rows(schema_rows)
    pair_heat_rows = pair_group_heatmap_rows(schema_rows)
    pair_timeout_lift = feature_pair_lift_rows(schema_rows, "timeout")
    pair_under_lift = feature_pair_lift_rows(schema_rows, "under")
    pair_over_lift = feature_pair_lift_rows(schema_rows, "over")
    pair_rows = pair_feature_rows(schema_rows)
    quartiles = slow_quartile_rows(schema_rows)
    over_rows = over_rejection_rows(run_dir)
    timeout_validity = timeout_expected_validity_rows(schema_rows)
    phase_summary = phase_timing_summary_rows(schema_rows)
    timing_cases = timing_result_case_rows(run_dir)
    characteristic_rows = schema_characteristic_constraint_rows(schema_rows)

    schema_fields = [
        "dataset_id",
        "framework_id",
        "schema_id",
        "n_tests",
        "n_valid_tests",
        "n_invalid_tests",
        "n_valid_completed",
        "n_invalid_completed",
        "n_completed",
        "n_timeout",
        "timeout_status",
        "timeout_stage",
        "timeout_elapsed_s",
        "compile_grammar_s",
        "validation_loop_mean_s",
        "compute_mask_mean_s",
        "commit_token_mean_s",
        "schema_file_bytes",
        "schema_json_chars",
        "mean_instance_json_chars",
        "mean_num_tokens",
        "max_num_tokens",
        "n_correct_accept",
        "n_correct_reject",
        "n_under_constraint",
        "n_over_constraint",
        "under_rate",
        "over_rate",
        "timeout_rate",
        "coverage_rate",
        "accuracy_completed",
        "permissive_score",
        *FEATURE_COLUMNS,
        *NUMERIC_FEATURE_COLUMNS,
        *DERIVED_FEATURE_COLUMNS,
    ]
    write_csv(out_dir / "schema_level_stats.csv", schema_rows, schema_fields)
    write_csv(
        out_dir / "feature_timeout_lift.csv",
        feature_timeout,
        [
            "feature",
            "schemas_with_feature",
            "schemas_without_feature",
            "timeout_with_feature",
            "timeout_without_feature",
            "timeout_rate_with",
            "timeout_rate_without",
            "lift",
            "support",
            "global_timeout_rate",
        ],
    )
    write_csv(
        out_dir / "feature_under_lift.csv",
        feature_under_lift,
        [
            "feature",
            "schemas_with_feature",
            "schemas_without_feature",
            "under_with_feature",
            "under_without_feature",
            "under_denominator_with",
            "under_denominator_without",
            "under_rate_with",
            "under_rate_without",
            "lift",
            "delta",
            "support",
            "global_under_rate",
            "eligible_lift",
        ],
    )
    write_csv(
        out_dir / "feature_over_lift.csv",
        feature_over_lift,
        [
            "feature",
            "schemas_with_feature",
            "schemas_without_feature",
            "over_with_feature",
            "over_without_feature",
            "over_denominator_with",
            "over_denominator_without",
            "over_rate_with",
            "over_rate_without",
            "lift",
            "delta",
            "support",
            "global_over_rate",
            "eligible_lift",
        ],
    )
    write_csv(
        out_dir / "feature_constraint_rates.csv",
        feature_constraints,
        ["feature", "n_schemas", "n_completed_tests", "under_rate", "over_rate", "correct_rate", "timeout_rate"],
    )
    write_csv(
        out_dir / "feature_group_heatmap.csv",
        heat_rows,
        ["feature", "correct", "timeout", "under", "over", "correct_n", "timeout_n", "under_n", "over_n"],
    )
    write_csv(
        out_dir / "feature_pair_group_heatmap.csv",
        pair_heat_rows,
        [
            "feature",
            "feature_pair",
            "feature_a",
            "feature_b",
            "n_schemas",
            "support",
            "risk_count",
            "interest_score",
            "timeout_lift",
            "timeout_delta",
            "under_lift",
            "under_delta",
            "over_lift",
            "over_delta",
            "correct",
            "timeout",
            "under",
            "over",
            "correct_n",
            "timeout_n",
            "under_n",
            "over_n",
        ],
    )
    write_csv(
        out_dir / "feature_pair_rates.csv",
        pair_rows,
        ["feature_pair", "feature_a", "feature_b", "n_schemas", "support", "timeout_rate", "under_rate", "over_rate"],
    )
    write_csv(
        out_dir / "feature_pair_timeout_lift.csv",
        pair_timeout_lift,
        [
            "feature_pair",
            "feature_a",
            "feature_b",
            "schemas_with_pair",
            "schemas_without_pair",
            "support",
            "timeout_with_pair",
            "timeout_without_pair",
            "timeout_denominator_with",
            "timeout_denominator_without",
            "timeout_rate_with",
            "timeout_rate_without",
            "lift",
            "delta",
            "eligible_lift",
        ],
    )
    write_csv(
        out_dir / "feature_pair_under_lift.csv",
        pair_under_lift,
        [
            "feature_pair",
            "feature_a",
            "feature_b",
            "schemas_with_pair",
            "schemas_without_pair",
            "support",
            "under_with_pair",
            "under_without_pair",
            "under_denominator_with",
            "under_denominator_without",
            "under_rate_with",
            "under_rate_without",
            "lift",
            "delta",
            "eligible_lift",
        ],
    )
    write_csv(
        out_dir / "feature_pair_over_lift.csv",
        pair_over_lift,
        [
            "feature_pair",
            "feature_a",
            "feature_b",
            "schemas_with_pair",
            "schemas_without_pair",
            "support",
            "over_with_pair",
            "over_without_pair",
            "over_denominator_with",
            "over_denominator_without",
            "over_rate_with",
            "over_rate_without",
            "lift",
            "delta",
            "eligible_lift",
        ],
    )
    write_csv(
        out_dir / "slow_completed_constraint_quartiles.csv",
        quartiles,
        ["compile_speed_group", "n_schemas", "compile_min_s", "compile_max_s", "under_rate", "over_rate", "accuracy_completed"],
    )
    write_csv(
        out_dir / "over_rejection_ratio.csv",
        over_rows,
        ["schema_id", "test_id", "tokens_checked", "num_tokens", "rejection_ratio", "first_rejected_token_index"],
    )
    write_csv(
        out_dir / "timeout_expected_validity.csv",
        timeout_validity,
        ["expected_validity", "n_tests", "share", "n_timeout_schemas"],
    )
    write_csv(
        out_dir / "phase_timing_summary_by_status.csv",
        phase_summary,
        ["schema_status", "phase", "n", "mean_s", "std_s", "median_s", "p95_s", "min_s", "max_s"],
    )
    write_csv(
        out_dir / "timing_by_result_case.csv",
        timing_cases,
        [
            "schema_id",
            "test_id",
            "expected_validity",
            "actual_result",
            "accepted",
            "result_available",
            "constraint_case",
            "compile_grammar_s",
            "validation_loop_s",
            "compute_mask_s",
            "commit_token_s",
            "num_tokens",
            "tokens_checked",
        ],
    )
    write_csv(
        out_dir / "schema_characteristic_constraint_bins.csv",
        characteristic_rows,
        [
            "characteristic",
            "bucket",
            "n_schemas",
            "value_min",
            "value_max",
            "schemas_with_under_rate",
            "schemas_with_over_rate",
            "under_test_rate",
            "over_test_rate",
            "timeout_schema_rate",
        ],
    )

    make_plots(
        out_dir,
        schema_rows,
        feature_timeout,
        feature_under_lift,
        feature_over_lift,
        feature_constraints,
        heat_rows,
        pair_heat_rows,
        pair_timeout_lift,
        pair_under_lift,
        pair_over_lift,
        over_rows,
        quartiles,
        timeout_validity,
        phase_summary,
        timing_cases,
        characteristic_rows,
    )
    make_readme(
        out_dir,
        args.dataset,
        args.framework,
        schema_rows,
        source_counts,
        feature_timeout,
        feature_constraints,
        pair_rows,
        pair_heat_rows,
        quartiles,
        timeout_validity,
        phase_summary,
    )

    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
