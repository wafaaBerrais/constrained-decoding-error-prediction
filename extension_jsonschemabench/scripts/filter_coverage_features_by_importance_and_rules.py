#!/usr/bin/env python3
"""Select high-impact coverage-prediction features from model importance and rules."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction"
DEFAULT_FRAMEWORKS = ["guidance", "outlines", "xgr"]
DEFAULT_TARGETS = ["under", "over"]

CONDITION_RE = re.compile(r"([A-Za-z_$][A-Za-z0-9_$.-]*)\s*(?:<=|>=|<|>|=)")

FORCED_NUMERIC_FEATURES = {
    "has_minimum",
    "has_maximum",
    "has_exclusiveMinimum",
    "has_exclusiveMaximum",
    "has_multipleOf",
    "numeric_is_in_properties",
    "numeric_property_required",
    "numeric_has_min_and_max",
    "instance_has_large_integer",
    "instance_has_int32_boundary_risk",
}
FORCED_COMBINATOR_FEATURES = {
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
}
EXCLUDED_DOMAIN_FEATURES = {
    "numeric_keywords_present",
    "instance_number_count",
    "instance_num_numeric_values",
    "schema_dependency_keyword_count",
    "schema_advanced_keywords_present",
    "patternProperties_regex_complexity_score",
    "type_validation_case",
    "allOf_satisfied_all_branch_count",
    "allOf_satisfied_branch_ratio",
    "anyOf_satisfied_branch_ratio",
    "oneOf_satisfied_branch_ratio",
    "object_additionalProperties_value",
    "instance_string_count_bucket",
    "instance_string_max_length_bucket",
    "instance_total_array_items_bucket",
    "instance_max_array_length_bucket",
    "instance_max_object_depth_bucket",
    "instance_total_object_properties_recursive_bucket",
    "instance_matching_pattern_keys_count_bucket",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-root", default=str(DEFAULT_COVERAGE_ROOT))
    parser.add_argument("--frameworks", nargs="+", default=DEFAULT_FRAMEWORKS)
    parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    parser.add_argument("--min-importance-share", type=float, default=0.003)
    parser.add_argument("--cumulative-importance-share", type=float, default=0.95)
    parser.add_argument("--min-features", type=int, default=12)
    parser.add_argument("--max-features", type=int, default=0, help="0 means no cap.")
    parser.add_argument("--ignore-rule-features", action="store_true")
    parser.add_argument("--output-dir", default="")
    return parser.parse_args()


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
            writer.writerow(row)


def read_feature_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text_list(path: Path, values: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


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


def features_from_rules(rules_root: Path, framework: str, target: str, selected_features: list[str]) -> set[str]:
    target_root = rules_root / framework / target
    candidates: set[str] = set()

    tree_path = target_root / f"{target}_tree.txt"
    if tree_path.exists():
        candidates.update(CONDITION_RE.findall(tree_path.read_text(encoding="utf-8")))

    for csv_name in (f"{target}_positive_rules.csv", f"{target}_all_leaf_rules.csv"):
        for row in read_csv(target_root / csv_name):
            candidates.update(CONDITION_RE.findall(str(row.get("rule", ""))))

    return {
        original_feature_name(feature, selected_features)
        for feature in candidates
        if original_feature_name(feature, selected_features) in selected_features
    }


def importance_rows(framework_root: Path, target: str, selected_features: list[str]) -> list[dict[str, Any]]:
    grouped_path = framework_root / "plots" / "feature_importance" / f"{target}_grouped_feature_importance.csv"
    grouped = read_csv(grouped_path)
    by_feature = {str(row.get("feature", "")): row for row in grouped}
    out: list[dict[str, Any]] = []
    for feature in selected_features:
        row = by_feature.get(feature, {})
        out.append(
            {
                "feature": feature,
                "importance": to_float(row.get("importance", 0.0)),
                "importance_share": to_float(row.get("importance_share", 0.0)),
                "top_transformed_feature": row.get("top_transformed_feature", ""),
                "top_transformed_importance": to_float(row.get("top_transformed_importance", 0.0)),
            }
        )
    return sorted(out, key=lambda row: float(row["importance"]), reverse=True)


def decide_features(
    rows: list[dict[str, Any]],
    rule_features: set[str],
    min_importance_share: float,
    cumulative_importance_share: float,
    min_features: int,
    max_features: int,
    include_rule_features: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    feature_count = len(rows)
    if feature_count == 0:
        return [], [], []
    max_count = feature_count if max_features <= 0 else min(max_features, feature_count)
    min_count = min(max(1, min_features), max_count)
    min_share = max(0.0, min_importance_share)
    cumulative_target = min(max(cumulative_importance_share, 0.0), 1.0)

    retained: list[str] = []
    retained_set: set[str] = set()
    cumulative = 0.0
    audit_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        feature = str(row["feature"])
        share = float(row["importance_share"])
        is_rule_feature = feature in rule_features
        keep_for_minimum = len(retained) < min_count
        keep_for_cumulative = cumulative_target > 0 and cumulative < cumulative_target
        keep_for_share = share >= min_share
        keep_for_rule = include_rule_features and is_rule_feature
        under_cap = len(retained) < max_count or keep_for_rule
        keep = under_cap and (keep_for_minimum or keep_for_cumulative or keep_for_share or keep_for_rule)
        reason = (
            "rule_feature"
            if keep_for_rule
            else "minimum_count"
            if keep and keep_for_minimum
            else "cumulative_importance"
            if keep and keep_for_cumulative
            else "importance_share"
            if keep and keep_for_share
            else "dropped_low_impact"
        )
        if keep and feature not in retained_set:
            retained.append(feature)
            retained_set.add(feature)
            cumulative += share
        audit = dict(row)
        audit.update(
            {
                "rank": rank,
                "cumulative_importance_share_after_retained": cumulative,
                "present_in_rules": is_rule_feature,
                "retained": keep,
                "decision_reason": reason,
            }
        )
        audit_rows.append(audit)

    dropped = [str(row["feature"]) for row in audit_rows if not row["retained"]]
    return audit_rows, retained, dropped


def apply_domain_feature_policy(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    for row in decisions:
        feature = str(row["feature"])
        if feature in EXCLUDED_DOMAIN_FEATURES or feature.endswith("_bucket"):
            row["retained"] = False
            row["decision_reason"] = "dropped_redundant_or_complex_feature"
        elif feature in FORCED_NUMERIC_FEATURES:
            row["retained"] = True
            row["decision_reason"] = "retained_numeric_domain_feature"
        elif feature in FORCED_COMBINATOR_FEATURES:
            row["retained"] = True
            row["decision_reason"] = "retained_combinator_domain_feature"

    retained = [str(row["feature"]) for row in decisions if row["retained"]]
    dropped = [str(row["feature"]) for row in decisions if not row["retained"]]
    return decisions, retained, dropped


def write_markdown(path: Path, summary_rows: list[dict[str, Any]], settings: dict[str, Any]) -> None:
    lines = [
        "# Coverage Feature Filter",
        "",
        "This report selects retained features from existing model importances and decision-tree rules.",
        "",
        "## Settings",
        "",
        f"- Minimum importance share: `{settings['min_importance_share']}`",
        f"- Cumulative importance share: `{settings['cumulative_importance_share']}`",
        f"- Minimum retained features: `{settings['min_features']}`",
        f"- Maximum retained features: `{settings['max_features'] if settings['max_features'] else 'none'}`",
        f"- Rule features included: `{settings['include_rule_features']}`",
        "",
        "## Summary",
        "",
        "| framework | target | candidates | retained | dropped | rule features |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['framework']} | {row['target']} | {row['candidate_features']} | "
            f"{row['retained_features']} | {row['dropped_features']} | {row['rule_features']} |"
        )
    lines.extend(
        [
            "",
            "Each target folder contains:",
            "",
            "- `feature_filter_decisions.csv`: full audit for every candidate feature.",
            "- `retained_features.txt`: features to keep for a simplified model.",
            "- `dropped_features.txt`: low-impact features to remove from the simplified model.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    coverage_root = Path(args.coverage_root)
    output_root = Path(args.output_dir) if args.output_dir else coverage_root / "feature_filter"
    include_rule_features = not args.ignore_rule_features
    summary_rows: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []

    for framework in args.frameworks:
        framework_root = coverage_root / "modeles_predictifs" / framework
        for target in args.targets:
            selected_features = read_feature_list(framework_root / "modeling" / f"selected_{target}_features.txt")
            rows = importance_rows(framework_root, target, selected_features)
            rule_features = features_from_rules(coverage_root / "rules", framework, target, selected_features)
            decisions, retained, dropped = decide_features(
                rows,
                rule_features,
                args.min_importance_share,
                args.cumulative_importance_share,
                args.min_features,
                args.max_features,
                include_rule_features,
            )
            decisions, retained, dropped = apply_domain_feature_policy(decisions)
            target_output = output_root / framework / target
            fieldnames = [
                "framework",
                "target",
                "rank",
                "feature",
                "importance",
                "importance_share",
                "cumulative_importance_share_after_retained",
                "present_in_rules",
                "retained",
                "decision_reason",
                "top_transformed_feature",
                "top_transformed_importance",
            ]
            target_decisions = [{"framework": framework, "target": target, **row} for row in decisions]
            write_csv(target_output / "feature_filter_decisions.csv", target_decisions, fieldnames)
            write_text_list(target_output / "retained_features.txt", retained)
            write_text_list(target_output / "dropped_features.txt", dropped)
            summary = {
                "framework": framework,
                "target": target,
                "candidate_features": len(selected_features),
                "retained_features": len(retained),
                "dropped_features": len(dropped),
                "rule_features": len(rule_features),
            }
            summary_rows.append(summary)
            all_decisions.extend(target_decisions)
            print(
                f"{framework}/{target}: retained {len(retained)}/{len(selected_features)} "
                f"features, dropped {len(dropped)}, rule_features={len(rule_features)}"
            )

    write_csv(
        output_root / "feature_filter_summary.csv",
        summary_rows,
        ["framework", "target", "candidate_features", "retained_features", "dropped_features", "rule_features"],
    )
    write_csv(
        output_root / "all_feature_filter_decisions.csv",
        all_decisions,
        [
            "framework",
            "target",
            "rank",
            "feature",
            "importance",
            "importance_share",
            "cumulative_importance_share_after_retained",
            "present_in_rules",
            "retained",
            "decision_reason",
            "top_transformed_feature",
            "top_transformed_importance",
        ],
    )
    write_markdown(
        output_root / "README.md",
        summary_rows,
        {
            "min_importance_share": args.min_importance_share,
            "cumulative_importance_share": args.cumulative_importance_share,
            "min_features": args.min_features,
            "max_features": args.max_features,
            "include_rule_features": include_rule_features,
        },
    )
    print(f"wrote feature filter outputs to {output_root}")


if __name__ == "__main__":
    main()
