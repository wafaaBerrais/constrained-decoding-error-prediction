#!/usr/bin/env python3
"""Build coverage prediction features, datasets, models, and metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score as sklearn_roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", message="X does not have valid feature names, but LGBMClassifier was fitted with feature names")

try:
    from lightgbm import LGBMClassifier
except ImportError:
    LGBMClassifier = None

from analyze_refined_features import (
    DEFAULT_DATA_ROOT,
    DEFAULT_RESULTS_ROOT,
    ROOT,
    add_buckets,
    analyze_instance,
    analyze_schema,
    collect_string_patterns,
    expected_is_valid,
    failure_type,
    format_value,
    load_dataset_file,
    read_jsonl,
    write_csv,
)


DEFAULT_DATASETS = ["Github_trivial", "Github_easy", "Github_medium", "Github_hard", "Github_ultra"]
DEFAULT_OUTPUT_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction" / "modeles_predictifs" / "outlines"
FRAMEWORK_ALIASES = {
    "guidance": {"guidance", "llg", "LLGuidance"},
    "llg": {"guidance", "llg", "LLGuidance"},
    "xgr": {"xgr", "XGrammar", "xgrammar"},
    "outlines": {"outlines", "Outlines"},
}

METADATA_COLUMNS = ["dataset", "schema_id", "test_id", "test_index", "failure_type"]
INSTANCE_BUCKET_FEATURES_TO_DROP = {
    "instance_string_count_bucket",
    "instance_string_max_length_bucket",
    "instance_total_array_items_bucket",
    "instance_max_array_length_bucket",
    "instance_max_object_depth_bucket",
    "instance_total_object_properties_recursive_bucket",
    "instance_matching_pattern_keys_count_bucket",
}
REMOVED_SCHEMA_FEATURES = {
    "schema_dependency_keyword_count",
    "schema_advanced_keywords_present",
    "patternProperties_regex_complexity_score",
    "type_validation_case",
}
REDUNDANT_ALIAS_FEATURES = {
    "allOf_satisfied_all_branch_count",
    "anyOf_satisfied_branch_ratio",
    "oneOf_satisfied_branch_ratio",
}
EXCLUDED_FEATURE_COLUMNS = {
    "failure_type",
    "accepted",
    "outlines_result",
    "actual_result",
    "expected_validity",
    "schema_id",
    "test_id",
    "test_index",
    "dataset",
    "numeric_constraints_count",
    "numeric_keywords_present",
    "instance_number_count",
    "instance_num_numeric_values",
    *REMOVED_SCHEMA_FEATURES,
    *REDUNDANT_ALIAS_FEATURES,
    *INSTANCE_BUCKET_FEATURES_TO_DROP,
}

COMBINATOR_DOMAIN_FEATURES = [
    "branches_have_different_type",
    "combinator_same_type_count",
    "combinator_different_type_count",
    "combinator_same_type_ratio",
    "combinator_different_type_ratio",
    "combinator_have_required_count",
    "combinator_have_properties_count",
    "combinator_have_numeric_count",
    "combinator_have_not_count",
    "combinator_have_additionalProperties_count",
    "branches_with_required_count",
    "branches_with_properties_count",
    "branches_with_numeric_count",
    "branches_with_not_count",
    "branches_with_additionalProperties_count",
    "branches_with_additionalProperties_true_count",
    "branches_with_additionalProperties_false_count",
    "branches_with_additionalProperties_schema_count",
    "branches_with_required_ratio",
    "branches_with_properties_ratio",
    "branches_with_numeric_ratio",
    "branches_with_not_ratio",
    "branches_with_additionalProperties_ratio",
    "combinator_with_additionalProperties_true",
    "combinator_with_additionalProperties_false",
    "combinator_with_additionalProperties_schema",
    "allOf_is_satisfied_for_instance",
    "anyOf_is_satisfied_for_instance",
    "oneOf_is_satisfied_for_instance",
    "allOf_occurrence_satisfied_count",
    "allOf_occurrence_failed_count",
    "allOf_ratio_min",
    "allOf_ratio_max",
    "allOf_ratio_avg",
    "anyOf_occurrence_satisfied_count",
    "anyOf_occurrence_failed_count",
    "anyOf_satisfied_all_branch_count",
    "anyOf_ratio_min",
    "anyOf_ratio_max",
    "anyOf_ratio_avg",
    "oneOf_occurrence_satisfied_count",
    "oneOf_occurrence_failed_count",
    "oneOf_satisfied_all_branch_count",
    "oneOf_ratio_min",
    "oneOf_ratio_max",
    "oneOf_ratio_avg",
]

UNDER_FEATURES = [
    "has_minimum",
    "has_maximum",
    "has_exclusiveMinimum",
    "has_exclusiveMaximum",
    "has_multipleOf",
    "numeric_keyword_count",
    "numeric_target_type",
    "numeric_is_in_properties",
    "numeric_property_required",
    "numeric_has_default",
    "numeric_has_min_and_max",
    "numeric_parent_keyword",
    "numeric_depth",
    "instance_numeric_value_count",
    "numeric_boundary_case",
    "combinator_count",
    "combinator_type",
    "combinator_branch_count_max",
    *COMBINATOR_DOMAIN_FEATURES,
    "complex_keywords_same_node_max",
    "missing_required_count",
    "extra_properties_disallowed_count",
    "string_pattern_violation_count",
    "string_length_violation_count",
    "enum_value_mismatch_count",
    "enum_type_match_but_value_mismatch",
    "const_mismatch_count",
    "oneOf_valid_branch_count_for_instance",
    "anyOf_valid_branch_count_for_instance",
    "allOf_failed_branch_count_for_instance",
]

OVER_FEATURES = [
    "has_patternProperties",
    "patternProperties_occurrence_count",
    "patternProperties_pattern_count",
    "patternProperties_with_properties",
    "patternProperties_with_properties_count",
    "patternProperties_has_additionalProperties",
    "additionalProperties_value",
    "patternProperties_regex_has_anchor",
    "patternProperties_regex_has_dotstar",
    "patternProperties_regex_has_alternation",
    "patternProperties_regex_has_charclass",
    "patternProperties_unanchored_count",
    "patternProperties_anchor_mix",
    "pattern_key_search_vs_fullmatch_mismatch_count",
    "pattern_key_partial_match_ratio",
    "unmatched_keys_allowed_by_additionalProperties",
    "unmatched_key_count_when_additionalProperties_true",
    "additionalProperties_mode",
    "additionalProperties_schema_depth",
    "instance_num_properties",
    "instance_matching_pattern_keys_count",
    "instance_has_unmatched_keys",
    "combinator_with_patternProperties",
    "combinator_with_additionalProperties",
    *COMBINATOR_DOMAIN_FEATURES,
    "has_allOf",
    "has_anyOf",
    "has_oneOf",
    "allOf_count",
    "anyOf_count",
    "oneOf_count",
    "combinator_count",
    "combinator_type",
    "combinator_branch_count_min",
    "combinator_branch_count_max",
    "combinator_branch_count_avg",
    "branches_have_same_type",
    "branches_conflicting_types",
    "branches_have_required",
    "branches_have_properties",
    "branches_have_not",
    "branches_have_enum",
    "branches_overlapping_properties",
    "allOf_satisfied_branch_count",
    "anyOf_satisfied_branch_count",
    "oneOf_satisfied_branch_count",
    "has_not",
    "not_count",
    "not_depth_min",
    "not_depth_max",
    "not_depth_avg",
    "not_parent_keyword",
    "not_target_type",
    "not_contains_enum",
    "not_contains_const",
    "not_contains_pattern",
    "not_contains_properties",
    "not_contains_required",
    "not_contains_anyOf",
    "not_contains_allOf",
    "not_contains_oneOf",
    "not_sibling_keyword_count",
    "instance_satisfies_not_subschema",
]

CATEGORICAL_FEATURES = {
    "numeric_target_type",
    "numeric_parent_keyword",
    "numeric_boundary_case",
    "instance_type",
    "additionalProperties_mode",
    "patternProperties_anchor_mix",
    "object_parent_keyword",
    "object_target_type",
    "object_required_case",
    "object_property_count_boundary_case",
    "object_additional_properties_case",
    "additionalProperties_value",
    "required_property_count_total_bucket",
    "object_properties_count_bucket",
    "object_required_count_bucket",
    "object_missing_required_count_bucket",
    "object_extra_properties_count_bucket",
    "missing_required_count_bucket",
    "pattern_key_search_vs_fullmatch_mismatch_count_bucket",
    "unmatched_keys_allowed_by_additionalProperties_bucket",
    "string_pattern_violation_count_bucket",
    "string_length_violation_count_bucket",
    "enum_value_mismatch_count_bucket",
    "object_property_bound_violation_count_bucket",
    "array_length_violation_count_bucket",
    "array_contains_violation_count_bucket",
    "enum_size_bucket",
    "array_prefixItems_count_bucket",
    "array_invalid_items_count_bucket",
    "combinator_type",
    "combinator_branch_count_bucket",
    "anyOf_satisfied_branch_count_bucket",
    "oneOf_satisfied_branch_count_bucket",
    "not_parent_keyword",
    "not_target_type",
    "instance_satisfies_not_subschema",
    "enum_target_type",
    "enum_parent_keyword",
    "enum_validation_case",
    "const_target_type",
    "const_parent_keyword",
    "const_type",
    "const_validation_case",
    "string_parent_keyword",
    "string_target_type",
    "string_format_value",
    "string_validation_case",
    "array_parent_keyword",
    "array_target_type",
    "array_items_kind",
    "array_validation_case",
}

GUIDANCE_RUNTIME_OVER_FEATURES = OVER_FEATURES + [
    "schema_keyword_count",
    "schema_max_depth",
    "schema_total_properties_recursive",
    "required_property_count_total",
    "required_property_count_total_bucket",
    "numeric_keyword_count",
    "numeric_target_type",
    "numeric_is_in_properties",
    "numeric_property_required",
    "numeric_has_default",
    "numeric_has_min_and_max",
    "numeric_parent_keyword",
    "numeric_depth",
    "numeric_constraints_with_integer_type",
    "has_minimum",
    "has_maximum",
    "has_exclusiveMinimum",
    "has_exclusiveMaximum",
    "has_multipleOf",
    "object_context_count",
    "object_parent_keyword",
    "object_target_type",
    "object_properties_count_max",
    "object_properties_count_bucket",
    "object_required_count_max",
    "object_required_count_bucket",
    "object_has_minProperties",
    "object_has_maxProperties",
    "object_has_min_and_max_properties",
    "object_has_propertyNames",
    "object_required_subset_of_properties",
    "object_required_subset_valid_context_count",
    "object_required_subset_invalid_context_count",
    "object_has_required_outside_properties",
    "object_depth_max",
    "enum_context_count",
    "enum_target_type",
    "enum_parent_keyword",
    "enum_total_values",
    "enum_size_max",
    "enum_size_bucket",
    "enum_string_values_count",
    "enum_contains_null",
    "enum_contains_mixed_types",
    "const_context_count",
    "const_target_type",
    "const_parent_keyword",
    "const_type",
    "string_context_count",
    "string_parent_keyword",
    "string_target_type",
    "string_has_pattern",
    "string_has_minLength",
    "string_has_maxLength",
    "string_has_min_and_max_length",
    "string_has_format",
    "string_format_value",
    "string_pattern_count",
    "string_pattern_max_length",
    "string_pattern_avg_length",
    "string_pattern_has_anchor",
    "string_pattern_has_charclass",
    "string_pattern_has_repetition",
    "string_pattern_has_alternation",
    "string_pattern_complexity_score",
    "array_context_count",
    "array_parent_keyword",
    "array_target_type",
    "array_items_kind",
    "array_prefixItems_count_max",
    "array_prefixItems_count_bucket",
    "array_has_minItems",
    "array_has_maxItems",
    "array_has_min_and_max_items",
    "array_has_uniqueItems",
    "array_has_contains",
    "array_has_minContains",
    "array_has_maxContains",
    "array_items_schema_depth",
    "array_items_object_properties_max",
    "instance_type",
    "instance_numeric_value_count",
    "instance_integer_count",
    "instance_max_abs_numeric_value",
    "instance_has_large_integer",
    "instance_has_int32_boundary_risk",
    "instance_num_properties",
    "instance_string_count",
    "instance_string_total_length",
    "instance_string_max_length",
    "instance_strings_matching_pattern_count",
    "instance_array_count",
    "instance_total_array_items",
    "instance_max_array_length",
    "array_nested_object_count",
    "instance_total_object_properties_recursive",
    "instance_max_object_depth",
    "instance_max_container_depth",
    "numeric_boundary_case",
    "object_required_case",
    "object_missing_required_count",
    "object_missing_required_count_bucket",
    "object_property_count_boundary_case",
    "object_additional_properties_case",
    "object_extra_properties_count",
    "object_extra_properties_count_bucket",
    "enum_validation_case",
    "const_validation_case",
    "string_validation_case",
    "array_validation_case",
    "array_invalid_items_count",
    "array_invalid_items_count_bucket",
    "complex_keywords_same_node_max",
    "complex_keywords_same_node_avg",
    "logical_complex_keywords_same_node_count",
    "object_complex_keywords_same_node_count",
    "regex_complex_keywords_same_node_count",
    "same_node_properties_and_required",
    "same_node_properties_and_additionalProperties",
    "same_node_combinator_and_numeric",
    "same_node_combinator_and_required",
    "same_node_combinator_and_properties",
]

XGR_EXTRA_CONTEXT_FEATURES = [
    "schema_keyword_count",
    "schema_max_depth",
    "schema_total_properties_recursive",
    "required_property_count_total",
    "required_property_count_total_bucket",
    "schema_boolean_schema_count",
    "schema_ref_count",
    "schema_defs_count",
    "schema_conditional_keyword_count",
    "schema_dependentSchemas_count",
    "schema_dependentRequired_count",
    "schema_legacy_dependencies_count",
    "schema_unevaluated_keyword_count",
    "schema_propertyNames_count",
    "schema_contains_keyword_count",
    "schema_format_keyword_count",
    "schema_type_union_count",
    "schema_nullable_type_count",
    "schema_advanced_keyword_count",
    "object_context_count",
    "object_parent_keyword",
    "object_target_type",
    "object_properties_count_max",
    "object_properties_count_bucket",
    "object_required_count_max",
    "object_required_count_bucket",
    "object_has_minProperties",
    "object_has_maxProperties",
    "object_has_min_and_max_properties",
    "object_has_propertyNames",
    "object_required_subset_of_properties",
    "object_required_subset_valid_context_count",
    "object_required_subset_invalid_context_count",
    "object_has_required_outside_properties",
    "object_depth_max",
    "enum_context_count",
    "enum_target_type",
    "enum_parent_keyword",
    "enum_total_values",
    "enum_size_max",
    "enum_size_bucket",
    "enum_string_values_count",
    "enum_contains_null",
    "enum_contains_mixed_types",
    "const_context_count",
    "const_target_type",
    "const_parent_keyword",
    "const_type",
    "string_context_count",
    "string_parent_keyword",
    "string_target_type",
    "string_has_pattern",
    "string_has_minLength",
    "string_has_maxLength",
    "string_has_min_and_max_length",
    "string_has_format",
    "string_format_value",
    "string_pattern_count",
    "string_pattern_max_length",
    "string_pattern_avg_length",
    "string_pattern_has_anchor",
    "string_pattern_has_charclass",
    "string_pattern_has_repetition",
    "string_pattern_has_alternation",
    "string_pattern_complexity_score",
    "array_context_count",
    "array_parent_keyword",
    "array_target_type",
    "array_items_kind",
    "array_prefixItems_count_max",
    "array_prefixItems_count_bucket",
    "array_has_minItems",
    "array_has_maxItems",
    "array_has_min_and_max_items",
    "array_has_uniqueItems",
    "array_has_contains",
    "array_has_minContains",
    "array_has_maxContains",
    "array_items_schema_depth",
    "array_items_object_properties_max",
    "instance_type",
    "instance_boolean_count",
    "instance_null_count",
    "instance_numeric_value_count",
    "instance_integer_count",
    "instance_max_abs_numeric_value",
    "instance_has_large_integer",
    "instance_has_int32_boundary_risk",
    "instance_num_properties",
    "instance_string_count",
    "instance_string_total_length",
    "instance_string_max_length",
    "instance_strings_matching_pattern_count",
    "instance_array_count",
    "instance_total_array_items",
    "instance_max_array_length",
    "instance_empty_array_count",
    "instance_nested_array_count",
    "array_nested_object_count",
    "instance_total_object_properties_recursive",
    "instance_empty_object_count",
    "instance_max_object_depth",
    "instance_max_container_depth",
    "any_visited_type_mismatch",
    "type_mismatch_count",
    "object_property_bound_violation_count",
    "object_property_bound_violation_count_bucket",
    "object_required_case",
    "object_missing_required_count",
    "object_missing_required_count_bucket",
    "object_property_count_boundary_case",
    "object_additional_properties_case",
    "object_extra_properties_count",
    "object_extra_properties_count_bucket",
    "array_validation_case",
    "array_invalid_items_count",
    "array_invalid_items_count_bucket",
    "array_length_violation_count",
    "array_length_violation_count_bucket",
    "array_unique_items_violation_count",
    "array_contains_violation_count",
    "array_contains_violation_count_bucket",
    "enum_validation_case",
    "const_validation_case",
    "string_validation_case",
    "complex_keywords_same_node_max",
    "complex_keywords_same_node_avg",
    "logical_complex_keywords_same_node_count",
    "object_complex_keywords_same_node_count",
    "regex_complex_keywords_same_node_count",
    "same_node_properties_and_required",
    "same_node_properties_and_additionalProperties",
    "same_node_combinator_and_numeric",
    "same_node_combinator_and_required",
    "same_node_combinator_and_properties",
]

XGR_RUNTIME_UNDER_FEATURES = UNDER_FEATURES + XGR_EXTRA_CONTEXT_FEATURES
XGR_RUNTIME_OVER_FEATURES = OVER_FEATURES + XGR_EXTRA_CONTEXT_FEATURES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", default="outlines")
    parser.add_argument("--datasets", nargs="+", default=DEFAULT_DATASETS)
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--validation-size", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=800)
    parser.add_argument(
        "--feature-filter-mode",
        choices=["none", "impact"],
        default="none",
        help="Use 'impact' to retrain with only the most important source features.",
    )
    parser.add_argument(
        "--impact-min-importance-share",
        type=float,
        default=0.003,
        help="Keep features whose grouped importance share is at least this value.",
    )
    parser.add_argument(
        "--impact-cumulative-importance-share",
        type=float,
        default=0.95,
        help="Keep top grouped features until this cumulative importance share is reached.",
    )
    parser.add_argument(
        "--impact-min-features",
        type=int,
        default=12,
        help="Minimum number of source features to keep when impact filtering is enabled.",
    )
    parser.add_argument(
        "--impact-max-features",
        type=int,
        default=0,
        help="Maximum number of source features to keep; 0 means no cap.",
    )
    return parser.parse_args()


def log(message: str) -> None:
    print(f"[coverage-prediction] {message}", flush=True)


def union_fieldnames(rows: list[dict[str, Any]], prefix: list[str] | None = None) -> list[str]:
    prefix = prefix or []
    seen = set(prefix)
    fields = list(prefix)
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    return fields


def extract_dataset_features(dataset: str, framework: str, results_root: Path, data_root: Path) -> list[dict[str, Any]] | None:
    per_test_path = results_root / framework / dataset / "per_test_results.jsonl"
    if not per_test_path.exists():
        log(f"SKIP {dataset}: missing {per_test_path}")
        return None

    aliases = FRAMEWORK_ALIASES.get(framework, {framework})
    all_per_test_results = read_jsonl(per_test_path)
    per_test_results = [
        row
        for row in all_per_test_results
        if str(row.get("framework_id", row.get("framework", framework))) in aliases
        or str(row.get("framework", "")) in aliases
    ]
    if not per_test_results:
        per_test_results = all_per_test_results
    if not per_test_results:
        log(f"SKIP {dataset}: no rows for framework={framework}")
        return None

    by_schema: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in per_test_results:
        schema_id = row.get("schema_id")
        if schema_id:
            by_schema[str(schema_id)].append(row)

    rows: list[dict[str, Any]] = []
    for schema_id, result_rows in sorted(by_schema.items()):
        try:
            dataset_doc = load_dataset_file(data_root, schema_id)
        except FileNotFoundError:
            log(f"SKIP schema {schema_id}: missing data file")
            continue
        schema = dataset_doc.get("schema", dataset_doc)
        tests = dataset_doc.get("tests", [])
        schema_features = analyze_schema(schema)
        string_patterns = collect_string_patterns(schema)

        for result in sorted(result_rows, key=lambda row: int(row.get("test_index", 0))):
            test_index = int(result.get("test_index", 0))
            test_doc = tests[test_index] if 0 <= test_index < len(tests) else {}
            instance = test_doc.get("data")
            expected_valid = expected_is_valid(result.get("expected_validity"))
            accepted = bool(result.get("accepted"))

            row = {
                "dataset": dataset,
                "schema_id": schema_id,
                "test_id": result.get("test_id", f"{schema_id}::test_{test_index:05d}"),
                "test_index": test_index,
                "expected_validity": "valid" if expected_valid else "invalid",
                "outlines_result": "accepted" if accepted else "rejected",
                "actual_result": result.get("actual_result", ""),
                "failure_type": failure_type(expected_valid, accepted),
            }
            row.update(schema_features)
            row.update(analyze_instance(schema, instance, schema_features, string_patterns))
            add_buckets(row)
            rows.append(row)

    log(f"{dataset}: extracted {len(rows)} test rows from {len(by_schema)} schemas")
    return rows


def write_text_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + "\n", encoding="utf-8")


def make_modeling_rows(rows: list[dict[str, Any]], label_name: str, positive: str, negative: str) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if row.get("failure_type") not in {positive, negative}:
            continue
        copy = dict(row)
        copy[label_name] = 1 if row.get("failure_type") == positive else 0
        out.append(copy)
    return out


def framework_is_guidance(framework: str) -> bool:
    return framework in FRAMEWORK_ALIASES.get("guidance", set()) or framework in FRAMEWORK_ALIASES.get("llg", set())


def framework_is_outlines(framework: str) -> bool:
    return framework in FRAMEWORK_ALIASES.get("outlines", set())


def framework_is_xgr(framework: str) -> bool:
    return framework in FRAMEWORK_ALIASES.get("xgr", set())


def framework_uses_runtime_only(framework: str) -> bool:
    return framework_is_outlines(framework) or framework_is_xgr(framework)


def runtime_only_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("actual_result") in {"passed", "failed"}]


def value_is_floatable(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    text = str(value).strip().lower()
    if text in {"", "true", "false"}:
        return True
    try:
        float(text)
    except ValueError:
        return False
    return True


def all_usable_features(rows: list[dict[str, Any]], label: str) -> list[str]:
    blocked = set(EXCLUDED_FEATURE_COLUMNS) | {label, "y_under", "y_over", "local_cooccurrence_pairs"}
    features: list[str] = []
    for feature in union_fieldnames(rows):
        if feature in blocked or feature.endswith("_bucket"):
            continue
        values = [row.get(feature, "") for row in rows]
        if feature in CATEGORICAL_FEATURES or all(value_is_floatable(value) for value in values):
            features.append(feature)
    return features


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


def split_groups(rows: list[dict[str, Any]], seed: int, validation_size: float, test_size: float) -> dict[str, set[str]]:
    groups = sorted({str(row["schema_id"]) for row in rows})
    rng = random.Random(seed)
    rng.shuffle(groups)
    n_groups = len(groups)
    n_test = max(1, round(n_groups * test_size)) if n_groups >= 3 else 1
    n_validation = max(1, round(n_groups * validation_size)) if n_groups >= 4 else 1
    test = set(groups[:n_test])
    validation = set(groups[n_test : n_test + n_validation])
    train = set(groups[n_test + n_validation :])
    if not train:
        train = validation
        validation = set()
    return {"train": train, "validation": validation, "test": test}


def build_encoder(rows: list[dict[str, Any]], features: list[str]) -> dict[str, Any]:
    categorical = [feature for feature in features if feature in CATEGORICAL_FEATURES]
    numeric = [feature for feature in features if feature not in categorical]
    categories = {
        feature: sorted({str(row.get(feature, "")) if str(row.get(feature, "")) else "absent" for row in rows})
        for feature in categorical
    }
    means = {feature: float(np.mean([as_float(row.get(feature, 0)) for row in rows])) for feature in numeric}
    stds = {}
    for feature in numeric:
        std = float(np.std([as_float(row.get(feature, 0)) for row in rows]))
        stds[feature] = std if std > 1e-12 else 1.0
    output_names = list(numeric)
    for feature in categorical:
        output_names.extend(f"{feature}={value}" for value in categories[feature])
    return {"numeric": numeric, "categorical": categorical, "categories": categories, "means": means, "stds": stds, "output_names": output_names}


def transform(rows: list[dict[str, Any]], encoder: dict[str, Any]) -> np.ndarray:
    matrix: list[list[float]] = []
    for row in rows:
        values: list[float] = []
        for feature in encoder["numeric"]:
            values.append((as_float(row.get(feature, 0)) - encoder["means"][feature]) / encoder["stds"][feature])
        for feature in encoder["categorical"]:
            value = str(row.get(feature, "")) if str(row.get(feature, "")) else "absent"
            values.extend(1.0 if value == category else 0.0 for category in encoder["categories"][feature])
        matrix.append(values)
    return np.asarray(matrix, dtype=float)


def fit_logistic_regression(x: np.ndarray, y: np.ndarray, epochs: int) -> dict[str, Any]:
    n_rows, n_features = x.shape
    weights = np.zeros(n_features, dtype=float)
    intercept = 0.0
    positives = max(float(y.sum()), 1.0)
    negatives = max(float(len(y) - y.sum()), 1.0)
    sample_weights = np.where(y == 1, len(y) / (2.0 * positives), len(y) / (2.0 * negatives))
    lr = 0.05
    l2 = 0.001
    for epoch in range(epochs):
        logits = np.clip(x @ weights + intercept, -35.0, 35.0)
        preds = 1.0 / (1.0 + np.exp(-logits))
        error = (preds - y) * sample_weights
        grad_w = (x.T @ error) / n_rows + l2 * weights
        grad_b = float(error.mean())
        step = lr / math.sqrt(1.0 + epoch / 100.0)
        weights -= step * grad_w
        intercept -= step * grad_b
    return {"weights": weights, "intercept": intercept, "class_weight": "balanced", "epochs": epochs, "model_type": "numpy_logistic_regression"}


def predict_proba(x: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    logits = np.clip(x @ model["weights"] + model["intercept"], -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-logits))


def roc_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    positives = int(y_true.sum())
    negatives = int(len(y_true) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    order = np.argsort(y_score)
    ranks = np.empty(len(y_score), dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    pos_rank_sum = float(ranks[y_true == 1].sum())
    return (pos_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def pr_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    positives = int(y_true.sum())
    if positives == 0:
        return float("nan")
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    tp = np.cumsum(y_sorted == 1)
    fp = np.cumsum(y_sorted == 0)
    recall = tp / positives
    precision = tp / np.maximum(tp + fp, 1)
    recall = np.concatenate([[0.0], recall])
    precision = np.concatenate([[1.0], precision])
    return float(np.trapezoid(precision, recall))


def metrics_row(model_name: str, split: str, y_true: np.ndarray, y_score: np.ndarray, dataset: str = "all") -> dict[str, Any]:
    y_pred = (y_score >= 0.5).astype(int)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "model": model_name,
        "split": split,
        "dataset": dataset,
        "n": len(y_true),
        "positives": int(y_true.sum()),
        "negatives": int(len(y_true) - y_true.sum()),
        "accuracy": (tp + tn) / len(y_true) if len(y_true) else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc_score(y_true, y_score),
        "pr_auc": pr_auc_score(y_true, y_score),
        "balanced_accuracy": (recall + specificity) / 2.0,
    }


def confusion_row(model_name: str, split: str, y_true: np.ndarray, y_score: np.ndarray, dataset: str = "all") -> dict[str, Any]:
    y_pred = (y_score >= 0.5).astype(int)
    return {
        "model": model_name,
        "split": split,
        "dataset": dataset,
        "tn": int(((y_true == 0) & (y_pred == 0)).sum()),
        "fp": int(((y_true == 0) & (y_pred == 1)).sum()),
        "fn": int(((y_true == 1) & (y_pred == 0)).sum()),
        "tp": int(((y_true == 1) & (y_pred == 1)).sum()),
    }


def make_feature_matrix(rows: list[dict[str, Any]], features: list[str]) -> np.ndarray:
    matrix: list[list[Any]] = []
    for row in rows:
        values: list[Any] = []
        for feature in features:
            if feature in CATEGORICAL_FEATURES:
                raw = str(row.get(feature, ""))
                values.append(raw if raw else "absent")
            else:
                values.append(as_float(row.get(feature, 0)))
        matrix.append(values)
    return np.asarray(matrix, dtype=object)


def make_preprocessor(features: list[str]) -> ColumnTransformer:
    numeric_indices = [idx for idx, feature in enumerate(features) if feature not in CATEGORICAL_FEATURES]
    categorical_indices = [idx for idx, feature in enumerate(features) if feature in CATEGORICAL_FEATURES]
    transformers = []
    if numeric_indices:
        transformers.append(("numeric", StandardScaler(), numeric_indices))
    if categorical_indices:
        transformers.append(("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_indices))
    return ColumnTransformer(transformers, sparse_threshold=0.0, verbose_feature_names_out=False)


def candidate_models(seed: int) -> list[tuple[str, Any]]:
    models = [
        (
            "logistic_regression_c0.3",
            LogisticRegression(C=0.3, class_weight="balanced", max_iter=2000, solver="lbfgs", random_state=seed),
        ),
        (
            "logistic_regression_c1",
            LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, solver="lbfgs", random_state=seed),
        ),
        (
            "logistic_regression_c3",
            LogisticRegression(C=3.0, class_weight="balanced", max_iter=2000, solver="lbfgs", random_state=seed),
        ),
        (
            "random_forest_leaf1_sqrt",
            RandomForestClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=1,
                max_features="sqrt",
                n_jobs=-1,
                random_state=seed,
            ),
        ),
        (
            "random_forest_leaf2_sqrt",
            RandomForestClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=2,
                max_features="sqrt",
                n_jobs=-1,
                random_state=seed,
            ),
        ),
        (
            "random_forest_leaf5_sqrt",
            RandomForestClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=5,
                max_features="sqrt",
                n_jobs=-1,
                random_state=seed,
            ),
        ),
        (
            "random_forest_leaf2_0.7",
            RandomForestClassifier(
                n_estimators=400,
                class_weight="balanced",
                min_samples_leaf=2,
                max_features=0.7,
                n_jobs=-1,
                random_state=seed,
            ),
        ),
        (
            "hist_gradient_boosting_lr0.03_l2_0",
            HistGradientBoostingClassifier(
                class_weight="balanced",
                learning_rate=0.03,
                max_iter=350,
                max_leaf_nodes=31,
                l2_regularization=0.0,
                random_state=seed,
            ),
        ),
        (
            "hist_gradient_boosting_lr0.03_l2_0.05",
            HistGradientBoostingClassifier(
                class_weight="balanced",
                learning_rate=0.03,
                max_iter=350,
                max_leaf_nodes=31,
                l2_regularization=0.05,
                random_state=seed,
            ),
        ),
        (
            "hist_gradient_boosting_lr0.06_l2_0.01",
            HistGradientBoostingClassifier(
                class_weight="balanced",
                learning_rate=0.06,
                max_iter=250,
                max_leaf_nodes=31,
                l2_regularization=0.01,
                random_state=seed,
            ),
        ),
        (
            "hist_gradient_boosting_lr0.08_leaf15",
            HistGradientBoostingClassifier(
                class_weight="balanced",
                learning_rate=0.08,
                max_iter=220,
                max_leaf_nodes=15,
                l2_regularization=0.01,
                random_state=seed,
            ),
        ),
    ]
    if LGBMClassifier is not None:
        models.extend(
            [
                (
                    "lightgbm_lr0.03_leaves15",
                    LGBMClassifier(
                        class_weight="balanced",
                        n_estimators=500,
                        learning_rate=0.03,
                        num_leaves=15,
                        min_child_samples=20,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=seed,
                        n_jobs=-1,
                        verbose=-1,
                    ),
                ),
                (
                    "lightgbm_lr0.03_leaves31",
                    LGBMClassifier(
                        class_weight="balanced",
                        n_estimators=500,
                        learning_rate=0.03,
                        num_leaves=31,
                        min_child_samples=20,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=seed,
                        n_jobs=-1,
                        verbose=-1,
                    ),
                ),
                (
                    "lightgbm_lr0.05_leaves31",
                    LGBMClassifier(
                        class_weight="balanced",
                        n_estimators=350,
                        learning_rate=0.05,
                        num_leaves=31,
                        min_child_samples=20,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=seed,
                        n_jobs=-1,
                        verbose=-1,
                    ),
                ),
                (
                    "lightgbm_lr0.05_leaves63",
                    LGBMClassifier(
                        class_weight="balanced",
                        n_estimators=350,
                        learning_rate=0.05,
                        num_leaves=63,
                        min_child_samples=20,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=seed,
                        n_jobs=-1,
                        verbose=-1,
                    ),
                ),
            ]
        )
    return models


def safe_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(set(int(v) for v in y_true)) < 2:
        return float("nan")
    return float(sklearn_roc_auc_score(y_true, y_score))


def safe_pr_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if int(np.sum(y_true)) == 0:
        return float("nan")
    return float(average_precision_score(y_true, y_score))


def sklearn_metrics_row(
    model_name: str,
    split: str,
    y_true: np.ndarray,
    y_score: np.ndarray,
    dataset: str = "all",
    threshold: float = 0.5,
) -> dict[str, Any]:
    y_pred = (y_score >= threshold).astype(int)
    return {
        "model": model_name,
        "split": split,
        "dataset": dataset,
        "threshold": threshold,
        "n": int(len(y_true)),
        "positives": int(np.sum(y_true)),
        "negatives": int(len(y_true) - np.sum(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)) if len(y_true) else 0.0,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": safe_roc_auc(y_true, y_score),
        "pr_auc": safe_pr_auc(y_true, y_score),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)) if len(set(int(v) for v in y_true)) >= 2 else float("nan"),
    }


def sklearn_confusion_row(
    model_name: str,
    split: str,
    y_true: np.ndarray,
    y_score: np.ndarray,
    dataset: str = "all",
    threshold: float = 0.5,
) -> dict[str, Any]:
    y_pred = (y_score >= threshold).astype(int)
    labels = [0, 1]
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=labels).ravel()
    return {"model": model_name, "split": split, "dataset": dataset, "threshold": threshold, "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def classification_report_rows(model_name: str, split: str, y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> list[dict[str, Any]]:
    y_pred = (y_score >= threshold).astype(int)
    report = classification_report(y_true, y_pred, labels=[0, 1], output_dict=True, zero_division=0)
    rows = []
    for label, stats in report.items():
        if isinstance(stats, dict):
            row = {"model": model_name, "split": split, "label": label, "threshold": threshold}
            row.update(stats)
            rows.append(row)
    return rows


def choose_threshold(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if int(np.sum(y_true)) == 0:
        return 0.5
    best_threshold = 0.5
    best_score = (-1.0, -1.0, -1.0)
    for threshold in np.linspace(0.05, 0.95, 91):
        y_pred = (y_score >= threshold).astype(int)
        precision = float(precision_score(y_true, y_pred, zero_division=0))
        recall = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        candidate_score = (f1, recall, precision)
        if candidate_score > best_score:
            best_score = candidate_score
            best_threshold = float(threshold)
    return best_threshold


def model_scores(metrics: dict[str, Any]) -> tuple[float, float, float, float]:
    pr_auc = metrics.get("pr_auc", float("nan"))
    if isinstance(pr_auc, float) and math.isnan(pr_auc):
        pr_auc = -1.0
    return (float(pr_auc), float(metrics.get("f1", 0.0)), float(metrics.get("recall", 0.0)), float(metrics.get("precision", 0.0)))


def transformed_feature_names(pipeline: Pipeline, features: list[str]) -> list[str]:
    preprocessor = pipeline.named_steps["preprocess"]
    try:
        return [str(name) for name in preprocessor.get_feature_names_out(features)]
    except Exception:
        transformed = preprocessor.transform(np.asarray([[0 if f not in CATEGORICAL_FEATURES else "absent" for f in features]], dtype=object))
        return [f"feature_{idx}" for idx in range(transformed.shape[1])]


def feature_importance_rows(
    pipeline: Pipeline,
    model_name: str,
    features: list[str],
    x_test: np.ndarray,
    y_test: np.ndarray,
    seed: int,
) -> list[dict[str, Any]]:
    classifier = pipeline.named_steps["classifier"]
    if hasattr(classifier, "feature_importances_"):
        names = transformed_feature_names(pipeline, features)
        values = classifier.feature_importances_
        return [
            {"model": model_name, "feature": name, "importance": float(value), "importance_type": "feature_importances_"}
            for name, value in sorted(zip(names, values), key=lambda item: item[1], reverse=True)
        ]
    if hasattr(classifier, "coef_"):
        names = transformed_feature_names(pipeline, features)
        values = classifier.coef_[0]
        return [
            {
                "model": model_name,
                "feature": name,
                "importance": abs(float(value)),
                "coefficient": float(value),
                "importance_type": "coefficient_abs",
            }
            for name, value in sorted(zip(names, values), key=lambda item: abs(item[1]), reverse=True)
        ]

    result = permutation_importance(
        pipeline,
        x_test,
        y_test,
        scoring="average_precision",
        n_repeats=5,
        random_state=seed,
        n_jobs=-1,
    )
    return [
        {
            "model": model_name,
            "feature": feature,
            "importance": float(mean),
            "importance_std": float(std),
            "importance_type": "permutation_average_precision",
        }
        for feature, mean, std in sorted(
            zip(features, result.importances_mean, result.importances_std),
            key=lambda item: item[1],
            reverse=True,
        )
    ]


def original_feature_name(transformed_feature: str, selected_features: list[str]) -> str:
    for feature in sorted(selected_features, key=len, reverse=True):
        if transformed_feature == feature:
            return feature
        if transformed_feature.startswith(f"{feature}_") or transformed_feature.startswith(f"{feature}="):
            return feature
    return transformed_feature


def grouped_feature_importance_rows(
    importance_rows: list[dict[str, Any]],
    selected_features: list[str],
) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    top_component: dict[str, tuple[str, float]] = {}
    for row in importance_rows:
        feature = original_feature_name(str(row.get("feature", "")), selected_features)
        importance = max(0.0, float(row.get("importance", 0.0)))
        totals[feature] += importance
        if feature not in top_component or importance > top_component[feature][1]:
            top_component[feature] = (str(row.get("feature", "")), importance)

    total_importance = sum(totals.values())
    out: list[dict[str, Any]] = []
    for feature in selected_features:
        importance = totals.get(feature, 0.0)
        component, component_importance = top_component.get(feature, ("", 0.0))
        out.append(
            {
                "feature": feature,
                "importance": importance,
                "importance_share": importance / total_importance if total_importance else 0.0,
                "top_transformed_feature": component,
                "top_transformed_importance": component_importance,
            }
        )
    return sorted(out, key=lambda row: float(row["importance"]), reverse=True)


def impact_filtered_features(
    grouped_importances: list[dict[str, Any]],
    min_importance_share: float,
    cumulative_importance_share: float,
    min_features: int,
    max_features: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    if not grouped_importances:
        return [], []

    feature_count = len(grouped_importances)
    max_count = max_features if max_features > 0 else feature_count
    max_count = min(max_count, feature_count)
    min_count = min(max(1, min_features), max_count)
    min_share = max(0.0, min_importance_share)
    cumulative_target = min(max(cumulative_importance_share, 0.0), 1.0)

    retained: list[str] = []
    cumulative = 0.0
    audit_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(grouped_importances, start=1):
        share = float(row["importance_share"])
        keep_for_minimum = len(retained) < min_count
        keep_for_cumulative = cumulative_target > 0 and cumulative < cumulative_target
        keep_for_share = share >= min_share
        under_cap = len(retained) < max_count
        keep = under_cap and (keep_for_minimum or keep_for_cumulative or keep_for_share)
        reason = (
            "minimum_count"
            if keep and keep_for_minimum
            else "cumulative_importance"
            if keep and keep_for_cumulative
            else "importance_share"
            if keep and keep_for_share
            else "dropped_low_impact"
        )
        if keep:
            retained.append(str(row["feature"]))
            cumulative += share
        audit = dict(row)
        audit.update(
            {
                "rank": rank,
                "cumulative_importance_share_after_retained": cumulative,
                "retained": keep,
                "filter_reason": reason,
            }
        )
        audit_rows.append(audit)

    if not retained:
        retained = [str(row["feature"]) for row in grouped_importances[:min_count]]
        retained_set = set(retained)
        for row in audit_rows:
            if row["feature"] in retained_set:
                row["retained"] = True
                row["filter_reason"] = "fallback_minimum_count"

    return retained, audit_rows


def train_one(
    name: str,
    rows: list[dict[str, Any]],
    label: str,
    selected_features: list[str],
    output_root: Path,
    seed: int,
    validation_size: float,
    test_size: float,
    epochs: int,
    feature_filter_mode: str = "none",
    impact_min_importance_share: float = 0.003,
    impact_cumulative_importance_share: float = 0.95,
    impact_min_features: int = 12,
    impact_max_features: int = 0,
    store_candidate_models: bool = True,
) -> None:
    _ = epochs
    available_features = []
    seen_features: set[str] = set()
    for feature in selected_features:
        if feature in seen_features or feature not in rows[0] or feature in EXCLUDED_FEATURE_COLUMNS or feature.endswith("_bucket"):
            continue
        seen_features.add(feature)
        available_features.append(feature)
    if feature_filter_mode == "impact":
        write_text_list(output_root / "modeling" / f"candidate_{name}_features.txt", available_features)

    split_schema_ids = split_groups(rows, seed, validation_size, test_size)
    split_rows = {
        split: [row for row in rows if str(row["schema_id"]) in schema_ids]
        for split, schema_ids in split_schema_ids.items()
    }
    train_rows = split_rows["train"]
    y_by_split = {
        split: np.asarray([int(row[label]) for row in split_data], dtype=int)
        for split, split_data in split_rows.items()
    }

    def fit_candidates(features: list[str], persist_candidate_models: bool) -> dict[str, Any]:
        x_by_split = {split: make_feature_matrix(split_data, features) for split, split_data in split_rows.items()}
        x_train = x_by_split["train"]
        y_train = y_by_split["train"]
        metric_rows: list[dict[str, Any]] = []
        confusion_rows: list[dict[str, Any]] = []
        report_rows: list[dict[str, Any]] = []
        selection_rows: list[dict[str, Any]] = []
        fitted_models: dict[str, Pipeline] = {}
        fitted_thresholds: dict[str, float] = {}

        for model_name, classifier in candidate_models(seed):
            pipeline = Pipeline(
                steps=[
                    ("preprocess", make_preprocessor(features)),
                    ("classifier", classifier),
                ]
            )
            try:
                pipeline.fit(x_train, y_train)
            except Exception as exc:
                log(f"{name}/{model_name}: skipped after training error: {exc}")
                continue
            validation_score = pipeline.predict_proba(x_by_split["validation"])[:, 1] if len(split_rows["validation"]) else np.asarray([])
            threshold = choose_threshold(y_by_split["validation"], validation_score) if len(validation_score) else 0.5
            fitted_models[model_name] = pipeline
            fitted_thresholds[model_name] = threshold
            if persist_candidate_models:
                dump(
                    {
                        "label": label,
                        "selected_features": features,
                        "model_name": model_name,
                        "threshold": threshold,
                        "pipeline": pipeline,
                        "split_schema_ids": {key: sorted(value) for key, value in split_schema_ids.items()},
                    },
                    output_root / "models" / f"{name}_{model_name}_model.pkl",
                )

            for split, split_data in split_rows.items():
                if not split_data:
                    continue
                y_split = y_by_split[split]
                score = pipeline.predict_proba(x_by_split[split])[:, 1]
                row = sklearn_metrics_row(model_name, split, y_split, score, threshold=threshold)
                metric_rows.append(row)
                confusion_rows.append(sklearn_confusion_row(model_name, split, y_split, score, threshold=threshold))
                if split == "validation":
                    selection_rows.append({"model": model_name, "selection_split": split, **row})
                if split == "test":
                    report_rows.extend(classification_report_rows(model_name, split, y_split, score, threshold))
                    by_dataset: dict[str, list[int]] = defaultdict(list)
                    for idx, source_row in enumerate(split_data):
                        by_dataset[str(source_row["dataset"])].append(idx)
                    for dataset, indices in sorted(by_dataset.items()):
                        idx = np.asarray(indices, dtype=int)
                        metric_rows.append(sklearn_metrics_row(model_name, "test_by_dataset", y_split[idx], score[idx], dataset, threshold))
                        confusion_rows.append(sklearn_confusion_row(model_name, "test_by_dataset", y_split[idx], score[idx], dataset, threshold))

        if not selection_rows:
            raise RuntimeError(f"No model was trained for {name}")
        best_selection = max(selection_rows, key=model_scores)
        best_name = str(best_selection["model"])
        best_pipeline = fitted_models[best_name]
        x_test = x_by_split["test"]
        y_test = y_by_split["test"]
        importance_rows = feature_importance_rows(best_pipeline, best_name, features, x_test, y_test, seed)
        return {
            "features": features,
            "metric_rows": metric_rows,
            "confusion_rows": confusion_rows,
            "report_rows": report_rows,
            "selection_rows": selection_rows,
            "fitted_models": fitted_models,
            "fitted_thresholds": fitted_thresholds,
            "best_selection": best_selection,
            "best_name": best_name,
            "best_pipeline": best_pipeline,
            "importance_rows": importance_rows,
        }

    result = fit_candidates(available_features, persist_candidate_models=store_candidate_models and feature_filter_mode != "impact")
    if feature_filter_mode == "impact":
        grouped_importances = grouped_feature_importance_rows(result["importance_rows"], available_features)
        retained_features, audit_rows = impact_filtered_features(
            grouped_importances,
            impact_min_importance_share,
            impact_cumulative_importance_share,
            impact_min_features,
            impact_max_features,
        )
        write_csv(
            output_root / "modeling" / f"{name}_impact_feature_filter.csv",
            audit_rows,
            [
                "rank",
                "feature",
                "importance",
                "importance_share",
                "cumulative_importance_share_after_retained",
                "retained",
                "filter_reason",
                "top_transformed_feature",
                "top_transformed_importance",
            ],
        )
        if retained_features != available_features:
            log(
                f"{name}: impact filter retained {len(retained_features)}/{len(available_features)} features "
                f"(min_share={impact_min_importance_share:.4g}, cumulative={impact_cumulative_importance_share:.3g})"
            )
            result = fit_candidates(retained_features, persist_candidate_models=store_candidate_models)
        else:
            log(f"{name}: impact filter kept all {len(available_features)} available features")
            for model_name, pipeline in result["fitted_models"].items():
                dump(
                    {
                        "label": label,
                        "selected_features": available_features,
                        "model_name": model_name,
                        "threshold": result["fitted_thresholds"][model_name],
                        "pipeline": pipeline,
                        "split_schema_ids": {key: sorted(value) for key, value in split_schema_ids.items()},
                    },
                    output_root / "models" / f"{name}_{model_name}_model.pkl",
                )

    final_features = list(result["features"])
    best_name = str(result["best_name"])
    best_pipeline = result["best_pipeline"]
    best_selection = result["best_selection"]
    fitted_thresholds = result["fitted_thresholds"]

    write_text_list(output_root / "modeling" / f"selected_{name}_features.txt", final_features)
    write_csv(output_root / "metrics" / f"{name}_metrics.csv", result["metric_rows"])
    write_csv(output_root / "metrics" / f"{name}_confusion_matrix.csv", result["confusion_rows"])
    write_csv(output_root / "metrics" / f"{name}_classification_report.csv", result["report_rows"])
    write_csv(output_root / "metrics" / f"{name}_feature_importance.csv", result["importance_rows"])
    write_csv(output_root / "metrics" / f"{name}_model_selection.csv", result["selection_rows"])
    model_path = output_root / "models" / f"{name}_model.pkl"
    tmp_model_path = model_path.with_suffix(model_path.suffix + ".tmp")
    dump(
        {
            "label": label,
            "selected_features": final_features,
            "model_name": best_name,
            "threshold": fitted_thresholds[best_name],
            "pipeline": best_pipeline,
            "split_schema_ids": {key: sorted(value) for key, value in split_schema_ids.items()},
            "selection": best_selection,
            "feature_filter": {
                "mode": feature_filter_mode,
                "candidate_features": len(available_features),
                "retained_features": len(final_features),
                "impact_min_importance_share": impact_min_importance_share,
                "impact_cumulative_importance_share": impact_cumulative_importance_share,
                "impact_min_features": impact_min_features,
                "impact_max_features": impact_max_features,
            },
        },
        tmp_model_path,
        compress=3,
    )
    tmp_model_path.replace(model_path)
    log(
        f"{name}: trained {len(result['fitted_models'])} sklearn models on {len(train_rows)} rows, "
        f"selected={best_name}, test rows={len(split_rows['test'])}, features={len(final_features)}"
    )


def can_train_target(rows: list[dict[str, Any]], label: str) -> bool:
    values = {int(row[label]) for row in rows}
    return values == {0, 1}


def write_skipped_target(output_root: Path, name: str, rows: list[dict[str, Any]], label: str, reason: str) -> None:
    positives = sum(1 for row in rows if int(row[label]) == 1)
    negatives = len(rows) - positives
    write_text_list(output_root / "modeling" / f"selected_{name}_features.txt", [])
    write_csv(
        output_root / "metrics" / f"{name}_metrics.csv",
        [
            {
                "model": "skipped",
                "split": "all",
                "dataset": "all",
                "n": len(rows),
                "positives": positives,
                "negatives": negatives,
                "reason": reason,
            }
        ],
    )
    write_csv(output_root / "metrics" / f"{name}_confusion_matrix.csv", [])
    write_csv(output_root / "metrics" / f"{name}_classification_report.csv", [])
    write_csv(output_root / "metrics" / f"{name}_feature_importance.csv", [])
    write_csv(output_root / "metrics" / f"{name}_model_selection.csv", [])
    log(f"{name}: skipped training ({reason}; positives={positives}, negatives={negatives})")


def write_report(
    output_root: Path,
    framework: str,
    datasets: list[str],
    skipped: list[str],
    under_rows: list[dict[str, Any]],
    over_rows: list[dict[str, Any]],
    trained_targets: list[str],
    notes: list[str] | None = None,
) -> None:
    under_counts = Counter(row["failure_type"] for row in under_rows)
    over_counts = Counter(row["failure_type"] for row in over_rows)
    lines = [
        f"# {framework} Coverage Prediction Report",
        "",
        "## Scope",
        "",
        f"- Included datasets: {', '.join(f'`{dataset}`' for dataset in datasets) if datasets else 'none'}",
        f"- Skipped datasets: {', '.join(f'`{dataset}`' for dataset in skipped) if skipped else 'none'}",
        f"- Framework: `{framework}`",
        "- Split: grouped by `schema_id` with train/validation/test partitions.",
        "- Candidate models: tuned variants of `LogisticRegression`, `RandomForestClassifier`, `HistGradientBoostingClassifier`, and `LGBMClassifier` when LightGBM is installed.",
        "- Model selection: best validation PR-AUC, then F1, recall, and precision as tie-breakers.",
        "- Decision threshold: selected on validation to maximize F1 for each candidate model.",
        f"- Trained targets: {', '.join(f'`{target}`' for target in trained_targets) if trained_targets else 'none'}",
        "",
        "## Modeling Tables",
        "",
        f"- UNDER rows: {len(under_rows)} ({dict(under_counts)})",
        f"- OVER rows: {len(over_rows)} ({dict(over_counts)})",
        "",
        "## Notes",
        "",
        "- `dataset` is kept as metadata and is not used as an input feature.",
        "- A target is skipped when it has only one class, because binary classifiers cannot be trained meaningfully.",
    ]
    for note in notes or []:
        lines.append(f"- {note}")
    lines.append("")
    (output_root / "coverage_prediction_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)
    data_root = Path(args.data_root)
    output_root = Path(args.output_root)
    for child in ("features", "modeling", "models", "metrics"):
        (output_root / child).mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    included: list[str] = []
    skipped: list[str] = []
    for dataset in args.datasets:
        rows = extract_dataset_features(dataset, args.framework, results_root, data_root)
        if not rows:
            skipped.append(dataset)
            continue
        included.append(dataset)
        all_rows.extend(rows)
        write_csv(output_root / "features" / f"{dataset}_refined_test_features.csv", rows, union_fieldnames(rows, ["dataset", "schema_id", "test_id", "test_index", "expected_validity", "outlines_result", "actual_result", "failure_type"]))

    if not all_rows:
        raise SystemExit("No datasets available; nothing to model.")

    write_csv(output_root / "features" / "all_datasets_refined_test_features.csv", all_rows, union_fieldnames(all_rows, ["dataset", "schema_id", "test_id", "test_index", "expected_validity", "outlines_result", "actual_result", "failure_type"]))

    under_source_rows = runtime_only_rows(all_rows) if framework_uses_runtime_only(args.framework) else all_rows
    over_source_rows = runtime_only_rows(all_rows) if framework_is_guidance(args.framework) or framework_uses_runtime_only(args.framework) else all_rows
    under_rows = make_modeling_rows(under_source_rows, "y_under", "UNDER", "CORRECT_INVALID")
    over_rows = make_modeling_rows(over_source_rows, "y_over", "OVER", "CORRECT_VALID")
    write_csv(output_root / "modeling" / "under_dataset.csv", under_rows, union_fieldnames(under_rows, METADATA_COLUMNS + ["expected_validity", "y_under"]))
    write_csv(output_root / "modeling" / "over_dataset.csv", over_rows, union_fieldnames(over_rows, METADATA_COLUMNS + ["expected_validity", "y_over"]))

    trained_targets: list[str] = []
    if can_train_target(under_rows, "y_under"):
        if framework_is_outlines(args.framework) or framework_is_xgr(args.framework):
            under_features = all_usable_features(under_rows, "y_under")
        else:
            under_features = UNDER_FEATURES
        train_one(
            "under",
            under_rows,
            "y_under",
            under_features,
            output_root,
            args.seed,
            args.validation_size,
            args.test_size,
            args.epochs,
            args.feature_filter_mode,
            args.impact_min_importance_share,
            args.impact_cumulative_importance_share,
            args.impact_min_features,
            args.impact_max_features,
        )
        trained_targets.append("under")
    else:
        write_skipped_target(output_root, "under", under_rows, "y_under", "single_class")

    if can_train_target(over_rows, "y_over"):
        if framework_is_guidance(args.framework):
            over_features = GUIDANCE_RUNTIME_OVER_FEATURES
        elif framework_is_xgr(args.framework):
            over_features = XGR_RUNTIME_OVER_FEATURES
        else:
            over_features = OVER_FEATURES
        train_one(
            "over",
            over_rows,
            "y_over",
            over_features,
            output_root,
            args.seed + 1,
            args.validation_size,
            args.test_size,
            args.epochs,
            args.feature_filter_mode,
            args.impact_min_importance_share,
            args.impact_cumulative_importance_share,
            args.impact_min_features,
            args.impact_max_features,
        )
        trained_targets.append("over")
    else:
        write_skipped_target(output_root, "over", over_rows, "y_over", "single_class")

    notes = []
    if framework_is_guidance(args.framework):
        notes.append("For `guidance`, the `OVER` modeling table excludes `compile_error` rows and keeps only runtime `passed`/`failed` results.")
        notes.append("For `guidance`, the `OVER` model uses an expanded runtime feature set covering string/regex, numeric, array, enum, object-size, and instance-shape signals.")
    if framework_is_outlines(args.framework):
        notes.append("For `outlines`, both `UNDER` and `OVER` modeling tables exclude `compile_error` rows and keep only runtime `passed`/`failed` results.")
        notes.append("For `outlines`, the `UNDER` model uses all usable refined runtime features from the fused feature table.")
    if framework_is_xgr(args.framework):
        notes.append("For `xgr`, both `UNDER` and `OVER` modeling tables exclude `compile_error` rows and keep only runtime `passed`/`failed` results.")
        notes.append("For `xgr`, the `UNDER` model uses all usable refined runtime features from the fused feature table.")
        notes.append("For `xgr`, the `OVER` model uses an expanded runtime feature set covering schema size, advanced JSON Schema keywords, object/string/array/enum violations, type mismatches, and instance shape.")
    if args.feature_filter_mode == "impact":
        notes.append(
            "Impact feature filtering was enabled: each target is first trained with the candidate feature set, "
            "source features are grouped by model importance, then the final model is retrained with the retained features."
        )
        notes.append(
            f"Impact filter settings: min importance share `{args.impact_min_importance_share:.4g}`, "
            f"cumulative importance share `{args.impact_cumulative_importance_share:.3g}`, "
            f"minimum features `{args.impact_min_features}`, maximum features "
            f"`{args.impact_max_features if args.impact_max_features > 0 else 'none'}`."
        )
    write_report(output_root, args.framework, included, skipped, under_rows, over_rows, trained_targets, notes)
    log(f"done: {output_root}")


if __name__ == "__main__":
    main()
