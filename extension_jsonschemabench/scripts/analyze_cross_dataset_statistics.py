#!/usr/bin/env python3
"""Compare schema-level statistics across completed dataset runs."""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from analyze_dataset_statistics import (
    ANALYZED_FEATURES,
    BASE_FEATURES,
    PALETTE,
    MIN_INVALID_TESTS_FOR_UNDER,
    MIN_SCHEMAS_WITH_CANDIDATE,
    MIN_VALID_TESTS_FOR_OVER,
    OVER_DELTA_THRESHOLD,
    OVER_LIFT_THRESHOLD,
    DEFAULT_RESULTS_ROOT,
    TIMEOUT_LIFT_THRESHOLD,
    TOP_N_HEATMAP,
    UNDER_DELTA_THRESHOLD,
    UNDER_LIFT_THRESHOLD,
    mean,
    median,
    pct,
    pct_text,
    quantile,
    read_csv,
    safe_log10,
    stdev,
    svg_doc,
    svg_text,
    to_bool,
    to_float,
    write_csv,
)


DEFAULT_DATASETS = [
    "Github_trivial",
    "Github_easy",
    "Github_medium",
    "Github_hard",
    "Github_ultra",
]

SHORT_NAMES = {
    "Github_trivial": "trivial",
    "Github_easy": "easy",
    "Github_medium": "medium",
    "Github_hard": "hard",
    "Github_ultra": "ultra",
}

PHASES = [
    "compile_grammar_s",
    "validation_loop_mean_s",
    "compute_mask_mean_s",
    "commit_token_mean_s",
    "timeout_elapsed_s",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cross-dataset statistical study.")
    parser.add_argument("--framework", default="xgr")
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--plots-dir-name", default="plots", help="Per-dataset plots folder to read.")
    return parser.parse_args()


def number(row: dict[str, Any], key: str) -> float:
    value = to_float(row.get(key))
    return value if value is not None else 0.0


def finite_number(row: dict[str, Any], key: str) -> float | None:
    value = to_float(row.get(key))
    if value is None or not math.isfinite(value):
        return None
    return value


def short(dataset: str) -> str:
    return SHORT_NAMES.get(dataset, dataset.replace("Github_", ""))


def load_dataset_tables(
    results_root: Path,
    framework: str,
    dataset: str,
    plots_dir_name: str = "plots",
) -> dict[str, list[dict[str, str]]]:
    plots = results_root / framework / dataset / plots_dir_name
    if not plots.exists():
        raise SystemExit(f"Missing plots directory for {dataset}: {plots}")
    return {
        "schema": read_csv(plots / "schema_level_stats.csv"),
        "phase": read_csv(plots / "phase_timing_summary_by_status.csv"),
        "timeout_features": read_csv(plots / "feature_timeout_lift.csv"),
        "constraint_features": read_csv(plots / "feature_constraint_rates.csv"),
    }


def summarize_dataset(dataset: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    completed = [row for row in rows if row.get("timeout_status") == "completed"]
    timeout = [row for row in rows if row.get("timeout_status") == "timeout"]
    total_tests = sum(number(row, "n_tests") for row in rows)
    completed_tests = sum(number(row, "n_completed") for row in rows)
    timeout_tests = sum(number(row, "n_timeout") for row in rows)
    valid_completed = sum(number(row, "n_valid_completed") for row in rows)
    invalid_completed = sum(number(row, "n_invalid_completed") for row in rows)
    correct = sum(number(row, "n_correct_accept") + number(row, "n_correct_reject") for row in rows)
    under = sum(number(row, "n_under_constraint") for row in rows)
    over = sum(number(row, "n_over_constraint") for row in rows)
    compile_values = [finite_number(row, "compile_grammar_s") for row in completed]
    compile_values = [v for v in compile_values if v is not None]
    validation_values = [finite_number(row, "validation_loop_mean_s") for row in completed]
    validation_values = [v for v in validation_values if v is not None]
    schema_sizes = [finite_number(row, "schema_json_chars") for row in rows]
    schema_sizes = [v for v in schema_sizes if v is not None]
    depths = [finite_number(row, "schema_depth") for row in rows]
    depths = [v for v in depths if v is not None]
    keywords = [finite_number(row, "nb_keywords") for row in rows]
    keywords = [v for v in keywords if v is not None]

    return {
        "dataset_id": dataset,
        "dataset": short(dataset),
        "n_schemas": len(rows),
        "completed_schemas": len(completed),
        "timeout_schemas": len(timeout),
        "schema_timeout_rate": pct(len(timeout), len(rows)),
        "n_tests": total_tests,
        "completed_tests": completed_tests,
        "timeout_tests": timeout_tests,
        "coverage_rate": pct(completed_tests, total_tests),
        "test_timeout_rate": pct(timeout_tests, total_tests),
        "accuracy_completed": pct(correct, completed_tests),
        "under_rate": pct(under, invalid_completed),
        "over_rate": pct(over, valid_completed),
        "balanced_error_rate": (pct(under, invalid_completed) + pct(over, valid_completed)) / 2,
        "permissive_score": pct(under, invalid_completed) - pct(over, valid_completed),
        "median_compile_s": median(compile_values),
        "mean_compile_s": mean(compile_values),
        "std_compile_s": stdev(compile_values),
        "p95_compile_s": quantile(compile_values, 0.95),
        "max_compile_s": max(compile_values) if compile_values else math.nan,
        "median_validation_s": median(validation_values),
        "p95_validation_s": quantile(validation_values, 0.95),
        "median_schema_json_chars": median(schema_sizes),
        "median_schema_depth": median(depths),
        "median_nb_keywords": median(keywords),
    }


def phase_summary_rows(dataset: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "dataset_id": dataset,
                "dataset": short(dataset),
                "schema_status": row.get("schema_status", ""),
                "phase": row.get("phase", ""),
                "n": number(row, "n"),
                "mean_s": number(row, "mean_s"),
                "std_s": number(row, "std_s"),
                "median_s": number(row, "median_s"),
                "p95_s": number(row, "p95_s"),
                "max_s": number(row, "max_s"),
            }
        )
    return out


def timeout_stage_rows(dataset: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts = Counter(row.get("timeout_stage") or "none" for row in rows if row.get("timeout_status") == "timeout")
    total = sum(counts.values())
    return [
        {
            "dataset_id": dataset,
            "dataset": short(dataset),
            "timeout_stage": stage,
            "schemas": count,
            "share": pct(count, total),
        }
        for stage, count in sorted(counts.items())
    ]


def feature_rates_by_dataset(dataset: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    global_timeout = pct(sum(1 for row in rows if row.get("timeout_status") == "timeout"), len(rows))
    global_under = pct(
        sum(number(row, "n_under_constraint") for row in rows),
        sum(number(row, "n_invalid_completed") for row in rows),
    )
    global_over = pct(
        sum(number(row, "n_over_constraint") for row in rows),
        sum(number(row, "n_valid_completed") for row in rows),
    )

    for feature in ANALYZED_FEATURES:
        with_feature = [row for row in rows if to_bool(row.get(feature))]
        without_feature = [row for row in rows if not to_bool(row.get(feature))]
        if not with_feature:
            continue
        timeout_with = pct(sum(1 for row in with_feature if row.get("timeout_status") == "timeout"), len(with_feature))
        timeout_without = pct(
            sum(1 for row in without_feature if row.get("timeout_status") == "timeout"),
            len(without_feature),
        )
        invalid_with = sum(number(row, "n_invalid_completed") for row in with_feature)
        invalid_without = sum(number(row, "n_invalid_completed") for row in without_feature)
        valid_with = sum(number(row, "n_valid_completed") for row in with_feature)
        valid_without = sum(number(row, "n_valid_completed") for row in without_feature)
        under_with = pct(sum(number(row, "n_under_constraint") for row in with_feature), invalid_with)
        under_without = pct(sum(number(row, "n_under_constraint") for row in without_feature), invalid_without)
        over_with = pct(sum(number(row, "n_over_constraint") for row in with_feature), valid_with)
        over_without = pct(sum(number(row, "n_over_constraint") for row in without_feature), valid_without)
        out.append(
            {
                "dataset_id": dataset,
                "dataset": short(dataset),
                "feature": feature,
                "schemas_with_feature": len(with_feature),
                "support": pct(len(with_feature), len(rows)),
                "timeout_rate_with": timeout_with,
                "timeout_rate_without": timeout_without,
                "timeout_lift": timeout_with / timeout_without if timeout_without > 0 else math.inf if timeout_with > 0 else 0,
                "timeout_delta": timeout_with - timeout_without,
                "global_timeout_rate": global_timeout,
                "under_rate_with": under_with,
                "under_rate_without": under_without,
                "under_lift": under_with / under_without if under_without > 0 else math.inf if under_with > 0 else 0,
                "under_delta": under_with - under_without,
                "global_under_rate": global_under,
                "over_rate_with": over_with,
                "over_rate_without": over_without,
                "over_lift": over_with / over_without if over_without > 0 else math.inf if over_with > 0 else 0,
                "over_delta": over_with - over_without,
                "global_over_rate": global_over,
            }
        )
    return out


def common_feature_rows(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_feature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        by_feature[row["feature"]].append(row)

    out = []
    for feature, rows in by_feature.items():
        timeout_risky = [
            row for row in rows if row["schemas_with_feature"] >= 5 and row["timeout_delta"] > 0 and row["timeout_lift"] > 1.25
        ]
        under_risky = [
            row for row in rows if row["schemas_with_feature"] >= 5 and row["under_delta"] > 0.02 and row["under_lift"] > 1.15
        ]
        over_risky = [
            row for row in rows if row["schemas_with_feature"] >= 5 and row["over_delta"] > 0.02 and row["over_lift"] > 1.15
        ]
        out.append(
            {
                "feature": feature,
                "datasets_seen": len(rows),
                "timeout_risk_datasets": len(timeout_risky),
                "under_risk_datasets": len(under_risky),
                "over_risk_datasets": len(over_risky),
                "mean_timeout_lift": mean([min(row["timeout_lift"], 50) for row in timeout_risky]),
                "max_timeout_lift": max([min(row["timeout_lift"], 50) for row in timeout_risky], default=math.nan),
                "mean_under_delta": mean([row["under_delta"] for row in under_risky]),
                "mean_over_delta": mean([row["over_delta"] for row in over_risky]),
                "risk_score": len(timeout_risky) + len(under_risky) + len(over_risky),
                "datasets_timeout": ", ".join(row["dataset"] for row in timeout_risky),
                "datasets_under": ", ".join(row["dataset"] for row in under_risky),
                "datasets_over": ", ".join(row["dataset"] for row in over_risky),
            }
        )
    return sorted(out, key=lambda row: (row["risk_score"], row["timeout_risk_datasets"], row["over_risk_datasets"]), reverse=True)


def pair_candidate_name(feature_a: str, feature_b: str) -> str:
    return f"{feature_a}__AND__{feature_b}"


def candidate_specs() -> list[dict[str, str]]:
    specs = [
        {
            "candidate_type": "single",
            "candidate": feature,
            "feature_a": feature,
            "feature_b": "",
        }
        for feature in BASE_FEATURES
    ]
    specs.extend(
        {
            "candidate_type": "pair",
            "candidate": pair_candidate_name(feature_a, feature_b),
            "feature_a": feature_a,
            "feature_b": feature_b,
        }
        for feature_a, feature_b in combinations(BASE_FEATURES, 2)
    )
    return specs


def has_candidate(row: dict[str, Any], spec: dict[str, str]) -> bool:
    if spec["candidate_type"] == "single":
        return to_bool(row.get(spec["feature_a"]))
    return to_bool(row.get(spec["feature_a"])) and to_bool(row.get(spec["feature_b"]))


def lift(rate_with: float, rate_without: float) -> float:
    if rate_without > 0:
        return rate_with / rate_without
    return math.inf if rate_with > 0 else 0.0


def candidate_risk_rows_by_dataset(dataset: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    total = len(rows)
    for spec in candidate_specs():
        with_candidate = [row for row in rows if has_candidate(row, spec)]
        without_candidate = [row for row in rows if not has_candidate(row, spec)]

        timeout_rate_with = pct(
            sum(1 for row in with_candidate if row.get("timeout_status") == "timeout"),
            len(with_candidate),
        )
        timeout_rate_without = pct(
            sum(1 for row in without_candidate if row.get("timeout_status") == "timeout"),
            len(without_candidate),
        )

        n_invalid_completed_with = sum(number(row, "n_invalid_completed") for row in with_candidate)
        n_invalid_completed_without = sum(number(row, "n_invalid_completed") for row in without_candidate)
        n_valid_completed_with = sum(number(row, "n_valid_completed") for row in with_candidate)
        n_valid_completed_without = sum(number(row, "n_valid_completed") for row in without_candidate)

        under_rate_with = pct(sum(number(row, "n_under_constraint") for row in with_candidate), n_invalid_completed_with)
        under_rate_without = pct(
            sum(number(row, "n_under_constraint") for row in without_candidate),
            n_invalid_completed_without,
        )
        over_rate_with = pct(sum(number(row, "n_over_constraint") for row in with_candidate), n_valid_completed_with)
        over_rate_without = pct(
            sum(number(row, "n_over_constraint") for row in without_candidate),
            n_valid_completed_without,
        )

        schemas_with = len(with_candidate)
        out.append(
            {
                "dataset_id": dataset,
                "dataset": short(dataset),
                "candidate_type": spec["candidate_type"],
                "candidate": spec["candidate"],
                "feature_a": spec["feature_a"],
                "feature_b": spec["feature_b"],
                "schemas_with_candidate": schemas_with,
                "schemas_without_candidate": len(without_candidate),
                "support": pct(schemas_with, total),
                "timeout_rate_with": timeout_rate_with,
                "timeout_rate_without": timeout_rate_without,
                "timeout_lift": lift(timeout_rate_with, timeout_rate_without),
                "timeout_delta": timeout_rate_with - timeout_rate_without,
                "n_invalid_completed_with": n_invalid_completed_with,
                "n_invalid_completed_without": n_invalid_completed_without,
                "under_rate_with": under_rate_with,
                "under_rate_without": under_rate_without,
                "under_lift": lift(under_rate_with, under_rate_without),
                "under_delta": under_rate_with - under_rate_without,
                "n_valid_completed_with": n_valid_completed_with,
                "n_valid_completed_without": n_valid_completed_without,
                "over_rate_with": over_rate_with,
                "over_rate_without": over_rate_without,
                "over_lift": lift(over_rate_with, over_rate_without),
                "over_delta": over_rate_with - over_rate_without,
                "eligible_timeout": schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE,
                "eligible_under": schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE
                and n_invalid_completed_with >= MIN_INVALID_TESTS_FOR_UNDER,
                "eligible_over": schemas_with >= MIN_SCHEMAS_WITH_CANDIDATE
                and n_valid_completed_with >= MIN_VALID_TESTS_FOR_OVER,
            }
        )
    return out


def finite_lift_for_ranking(value: float) -> float:
    if not math.isfinite(value):
        return 50.0
    return min(value, 50.0)


def metric_risky(row: dict[str, Any], metric: str) -> bool:
    if metric == "timeout":
        return (
            row["eligible_timeout"]
            and row["timeout_delta"] > 0
            and row["timeout_lift"] > TIMEOUT_LIFT_THRESHOLD
        )
    if metric == "under":
        return (
            row["eligible_under"]
            and row["under_delta"] > UNDER_DELTA_THRESHOLD
            and row["under_lift"] > UNDER_LIFT_THRESHOLD
        )
    if metric == "over":
        return (
            row["eligible_over"]
            and row["over_delta"] > OVER_DELTA_THRESHOLD
            and row["over_lift"] > OVER_LIFT_THRESHOLD
        )
    raise ValueError(f"Unknown metric: {metric}")


def rank_candidate_rows(candidate_rows: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_candidate[row["candidate"]].append(row)

    ranked = []
    for candidate, rows in by_candidate.items():
        risky = [row for row in rows if metric_risky(row, metric)]
        lifts = [row[f"{metric}_lift"] for row in risky]
        capped_lifts = [finite_lift_for_ranking(value) for value in lifts]
        deltas = [row[f"{metric}_delta"] for row in risky]
        first = rows[0]
        risk_datasets = len(risky)
        mean_lift = mean(capped_lifts)
        median_lift = median(capped_lifts)
        max_lift = math.inf if any(not math.isfinite(value) and value > 0 for value in lifts) else max(lifts, default=math.nan)
        mean_delta = mean(deltas)
        median_delta = median(deltas)
        total_schemas = sum(number(row, "schemas_with_candidate") for row in rows)
        total_support = sum(number(row, "support") for row in rows)
        risk_score = (
            risk_datasets * 1_000_000
            + (median_lift if math.isfinite(median_lift) else 0) * 1_000
            + (mean_delta if math.isfinite(mean_delta) else 0) * 100
            + total_schemas / 1_000_000
        )
        ranked.append(
            {
                "candidate_type": first["candidate_type"],
                "candidate": candidate,
                "feature_a": first["feature_a"],
                "feature_b": first["feature_b"],
                "datasets_seen": sum(1 for row in rows if row["schemas_with_candidate"] > 0),
                f"{metric}_risk_datasets": risk_datasets,
                f"datasets_{metric}": ", ".join(row["dataset"] for row in risky),
                f"mean_{metric}_lift": mean_lift,
                f"median_{metric}_lift": median_lift,
                f"max_{metric}_lift": max_lift,
                f"mean_{metric}_delta": mean_delta,
                f"median_{metric}_delta": median_delta,
                "total_schemas_with_candidate": total_schemas,
                "total_support_across_datasets": total_support,
                f"{metric}_risk_score": risk_score,
            }
        )

    ranked.sort(
        key=lambda row: (
            row[f"{metric}_risk_datasets"],
            row[f"median_{metric}_lift"] if math.isfinite(row[f"median_{metric}_lift"]) else -1,
            row[f"mean_{metric}_delta"] if math.isfinite(row[f"mean_{metric}_delta"]) else -1,
            row["total_schemas_with_candidate"],
        ),
        reverse=True,
    )
    for idx, row in enumerate(ranked, 1):
        row["ranking_position"] = idx
    return ranked


def candidate_label(row: dict[str, Any]) -> str:
    if row["candidate_type"] == "pair":
        return f"[P] {row['feature_a']} + {row['feature_b']}"
    return f"[S] {row['feature_a']}"


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" if idx == 0 else "---:" for idx in range(len(headers))) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def hgroup_percent_chart(path: Path, title: str, rows: list[dict[str, Any]], series: list[tuple[str, str, str]]) -> None:
    width, height = 1000, max(320, 90 + len(rows) * 58)
    left, right, top, bottom = 150, 130, 60, 50
    plot_w = width - left - right
    row_h = 52
    max_v = max((row[key] for row in rows for key, _, _ in series), default=1)
    max_v = max(max_v, 0.01)
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        val = max_v * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="{PALETTE["grid"]}"/>')
        body.append(svg_text(x, height - 20, pct_text(val), 10, "middle"))
    for sidx, (_, label, color) in enumerate(series):
        body.append(f'<rect x="{width-120}" y="{50+sidx*20}" width="12" height="12" fill="{PALETTE[color]}"/>')
        body.append(svg_text(width - 103, 61 + sidx * 20, label, 11))
    for ridx, row in enumerate(rows):
        y = top + ridx * row_h + 6
        body.append(svg_text(left - 12, y + 22, row["dataset"], 12, "end"))
        for sidx, (key, _, color) in enumerate(series):
            value = row[key]
            bar_h = 12
            yy = y + sidx * 15
            w = plot_w * value / max_v
            body.append(f'<rect x="{left}" y="{yy}" width="{max(w, 1):.2f}" height="{bar_h}" rx="2" fill="{PALETTE[color]}"/>')
            body.append(svg_text(left + w + 5, yy + 10, pct_text(value), 9))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def grouped_log_phase_chart(path: Path, title: str, rows: list[dict[str, Any]], status: str) -> None:
    datasets = list(dict.fromkeys(row["dataset"] for row in rows))
    phases = [phase for phase in PHASES if any(row["schema_status"] == status and row["phase"] == phase and row["n"] > 0 for row in rows)]
    width, height = 1040, 520
    left, right, top, bottom = 82, 150, 62, 92
    plot_w, plot_h = width - left - right, height - top - bottom
    values = []
    by_key = {}
    for row in rows:
        if row["schema_status"] != status:
            continue
        by_key[(row["dataset"], row["phase"])] = row
        if row["mean_s"] > 0:
            values.append(row["mean_s"])
    if not values:
        path.write_text(svg_doc(width, height, title, svg_text(width / 2, height / 2, "No data", 14, "middle")), encoding="utf-8")
        return
    log_min = math.floor(min(safe_log10(v) for v in values))
    log_max = math.ceil(max(safe_log10(v) for v in values))
    if log_min == log_max:
        log_max += 1
    colors = ["blue", "teal", "orange", "purple", "red"]
    body = []
    for i in range(log_min, log_max + 1):
        y = top + plot_h - (i - log_min) / (log_max - log_min) * plot_h
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
        body.append(svg_text(left - 8, y + 4, f"1e{i}", 10, "end"))
    cluster_w = plot_w / max(len(datasets), 1)
    bar_w = min(18, cluster_w / max(len(phases), 1) * 0.55)
    for pidx, phase in enumerate(phases):
        body.append(f'<rect x="{width-136}" y="{50+pidx*20}" width="12" height="12" fill="{PALETTE[colors[pidx % len(colors)]]}"/>')
        body.append(svg_text(width - 119, 61 + pidx * 20, phase.replace("_mean", ""), 10))
    for didx, dataset in enumerate(datasets):
        cx = left + didx * cluster_w + cluster_w / 2
        for pidx, phase in enumerate(phases):
            row = by_key.get((dataset, phase))
            if not row or row["mean_s"] <= 0:
                continue
            lv = safe_log10(row["mean_s"])
            y = top + plot_h - (lv - log_min) / (log_max - log_min) * plot_h
            x = cx + (pidx - (len(phases) - 1) / 2) * (bar_w + 4)
            h = top + plot_h - y
            body.append(f'<rect x="{x-bar_w/2:.2f}" y="{y:.2f}" width="{bar_w}" height="{max(h, 1):.2f}" fill="{PALETTE[colors[pidx % len(colors)]]}"/>')
        body.append(svg_text(cx, height - 50, dataset, 11, "middle"))
    body.append(svg_text(left + plot_w / 2, height - 18, "dataset", 12, "middle"))
    body.append(svg_text(22, top + plot_h / 2, "mean seconds, log scale", 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def stacked_stage_chart(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    datasets = list(dict.fromkeys(row["dataset"] for row in rows))
    stages = sorted({row["timeout_stage"] for row in rows})
    colors = ["red", "orange", "purple", "gray", "teal", "blue"]
    width, height = 980, max(320, 110 + len(datasets) * 44)
    left, right, top, bottom = 150, 190, 62, 48
    plot_w = width - left - right
    by_dataset: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        by_dataset[row["dataset"]][row["timeout_stage"]] = row["schemas"]
    max_total = max((sum(by_dataset[d].values()) for d in datasets), default=1)
    body = []
    for sidx, stage in enumerate(stages):
        body.append(f'<rect x="{width-170}" y="{48+sidx*20}" width="12" height="12" fill="{PALETTE[colors[sidx % len(colors)]]}"/>')
        body.append(svg_text(width - 153, 59 + sidx * 20, stage, 10))
    for didx, dataset in enumerate(datasets):
        y = top + didx * 44 + 8
        x = left
        body.append(svg_text(left - 12, y + 16, dataset, 12, "end"))
        total = sum(by_dataset[dataset].values())
        for sidx, stage in enumerate(stages):
            value = by_dataset[dataset].get(stage, 0)
            w = plot_w * value / max_total
            if w > 0:
                body.append(f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="22" fill="{PALETTE[colors[sidx % len(colors)]]}"/>')
                if w > 26:
                    body.append(svg_text(x + w / 2, y + 15, int(value), 10, "middle", "700"))
            x += w
        body.append(svg_text(left + plot_w + 8, y + 16, int(total), 11))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def feature_heatmap(path: Path, title: str, rows: list[dict[str, Any]], value_key: str, top_features: list[str]) -> None:
    datasets = list(dict.fromkeys(row["dataset"] for row in rows))
    by_key = {(row["feature"], row["dataset"]): row for row in rows}
    width, height = 880, max(340, 92 + len(top_features) * 30)
    left, top = 270, 68
    cell_w, cell_h = 92, 23
    body = []
    for didx, dataset in enumerate(datasets):
        body.append(svg_text(left + didx * cell_w + cell_w / 2, top - 16, dataset, 11, "middle", "700"))
    for fidx, feature in enumerate(top_features):
        y = top + fidx * 30
        body.append(svg_text(left - 12, y + 16, feature, 10, "end"))
        for didx, dataset in enumerate(datasets):
            row = by_key.get((feature, dataset))
            value = row.get(value_key, 0.0) if row else 0.0
            finite = math.isfinite(value)
            capped = min(value, 10.0) if finite else 10.0
            intensity = int(245 - 160 * (capped / 10.0))
            fill = f"rgb(245,{max(95, intensity)},140)" if "timeout" in value_key else f"rgb({intensity},210,245)"
            x = left + didx * cell_w
            body.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h}" fill="{fill}" stroke="{PALETTE["bg"]}"/>')
            label = "inf" if not finite and value > 0 else f"{value:.1f}"
            body.append(svg_text(x + (cell_w - 4) / 2, y + 15, label, 10, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def candidate_lift_heatmap(
    path: Path,
    title: str,
    candidate_rows: list[dict[str, Any]],
    ranking_rows: list[dict[str, Any]],
    value_key: str,
    top_n: int = TOP_N_HEATMAP,
) -> None:
    datasets = list(dict.fromkeys(row["dataset"] for row in candidate_rows))
    selected = ranking_rows[:top_n]
    by_key = {(row["candidate"], row["dataset"]): row for row in candidate_rows}
    width, height = 1160, max(360, 92 + len(selected) * 30)
    left, top = 520, 68
    cell_w, cell_h = 92, 23
    body = []
    for didx, dataset in enumerate(datasets):
        body.append(svg_text(left + didx * cell_w + cell_w / 2, top - 16, dataset, 11, "middle", "700"))
    for ridx, rank_row in enumerate(selected):
        y = top + ridx * 30
        body.append(svg_text(left - 12, y + 16, candidate_label(rank_row), 10, "end"))
        for didx, dataset in enumerate(datasets):
            row = by_key.get((rank_row["candidate"], dataset))
            value = row.get(value_key, 0.0) if row else 0.0
            finite = math.isfinite(value)
            capped = min(value, 10.0) if finite else 10.0
            intensity = int(245 - 160 * (capped / 10.0))
            fill = f"rgb(245,{max(95, intensity)},140)" if "timeout" in value_key else f"rgb({intensity},210,245)"
            x = left + didx * cell_w
            body.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h}" fill="{fill}" stroke="{PALETTE["bg"]}"/>')
            label = "inf" if not finite and value > 0 else f"{value:.1f}"
            body.append(svg_text(x + (cell_w - 4) / 2, y + 15, label, 10, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def reliability_scatter(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    width, height = 860, 560
    left, right, top, bottom = 82, 140, 60, 72
    plot_w, plot_h = width - left - right, height - top - bottom
    xvals = [safe_log10(row["median_compile_s"]) for row in rows if row["median_compile_s"] > 0]
    yvals = [row["balanced_error_rate"] for row in rows]
    x_min, x_max = min(xvals), max(xvals)
    y_min, y_max = 0.0, max(yvals) * 1.1
    if x_min == x_max:
        x_max += 1
    body = []
    for i in range(6):
        x = left + plot_w * i / 5
        y = top + plot_h * i / 5
        body.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top+plot_h}" stroke="{PALETTE["grid"]}"/>')
        body.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left+plot_w}" y2="{y:.2f}" stroke="{PALETTE["grid"]}"/>')
    for row in rows:
        x = left + (safe_log10(row["median_compile_s"]) - x_min) / (x_max - x_min) * plot_w
        y = top + plot_h - (row["balanced_error_rate"] - y_min) / (y_max - y_min) * plot_h
        radius = 8 + 28 * row["schema_timeout_rate"]
        body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{PALETTE["teal"]}" opacity="0.72"/>')
        body.append(svg_text(x + radius + 4, y + 4, row["dataset"], 11))
    body.append(svg_text(left + plot_w / 2, height - 22, "median compile_grammar_s, log scale", 12, "middle"))
    body.append(svg_text(24, top + plot_h / 2, "balanced error rate", 12, "middle"))
    path.write_text(svg_doc(width, height, title, "".join(body)), encoding="utf-8")


def make_readme(
    out_dir: Path,
    summary_rows: list[dict[str, Any]],
    timeout_ranking: list[dict[str, Any]],
    under_ranking: list[dict[str, Any]],
    over_ranking: list[dict[str, Any]],
) -> None:
    summary_table = [
        [
            row["dataset"],
            int(row["n_schemas"]),
            int(row["timeout_schemas"]),
            pct_text(row["coverage_rate"]),
            pct_text(row["schema_timeout_rate"]),
            pct_text(row["under_rate"]),
            pct_text(row["over_rate"]),
            f"{row['median_compile_s']:.3g}",
            f"{row['p95_compile_s']:.3g}",
            pct_text(row["accuracy_completed"]),
        ]
        for row in summary_rows
    ]
    timeout_table = [
        [
            row["timeout_risk_datasets"],
            f"`{row['candidate']}`",
            row["candidate_type"],
            row["datasets_timeout"] or "-",
            f"{row['median_timeout_lift']:.2f}" if math.isfinite(row["median_timeout_lift"]) else "",
            f"{row['mean_timeout_delta']:.3f}" if math.isfinite(row["mean_timeout_delta"]) else "",
            int(row["total_schemas_with_candidate"]),
        ]
        for row in timeout_ranking
        if row["timeout_risk_datasets"] > 0
    ][:10]
    under_table = [
        [
            row["under_risk_datasets"],
            f"`{row['candidate']}`",
            row["candidate_type"],
            row["datasets_under"] or "-",
            f"{row['median_under_lift']:.2f}" if math.isfinite(row["median_under_lift"]) else "",
            f"{row['mean_under_delta']:.3f}" if math.isfinite(row["mean_under_delta"]) else "",
            int(row["total_schemas_with_candidate"]),
        ]
        for row in under_ranking
        if row["under_risk_datasets"] > 0
    ][:10]
    over_table = [
        [
            row["over_risk_datasets"],
            f"`{row['candidate']}`",
            row["candidate_type"],
            row["datasets_over"] or "-",
            f"{row['median_over_lift']:.2f}" if math.isfinite(row["median_over_lift"]) else "",
            f"{row['mean_over_delta']:.3f}" if math.isfinite(row["mean_over_delta"]) else "",
            int(row["total_schemas_with_candidate"]),
        ]
        for row in over_ranking
        if row["over_risk_datasets"] > 0
    ][:10]
    lines = [
        "# Cross-Dataset Statistical Study: XGrammar All Features + Pairs",
        "",
        "This folder compares the schema-level studies generated for `Github_trivial`, `Github_easy`, `Github_medium`, `Github_hard`, and `Github_ultra`.",
        "",
        "## Dataset Summary",
        "",
        markdown_table(
            ["dataset", "schemas", "timeouts", "coverage", "timeout_rate", "under", "over", "median_compile_s", "p95_compile_s", "accuracy"],
            summary_table,
        ),
        "",
        "## Candidate Feature Method",
        "",
        "The analysis uses raw structural `has_*` JSON Schema features and automatically generated pairwise candidates over all base features. A pair such as `has_oneOf__AND__has_required` is present only when both features are present in the same schema; its comparison group is every schema that does not contain both at once.",
        "",
        "`boolean_schema` is detected from boolean schema nodes and the benchmark `_boolSchema` metadata. `content` covers `contentEncoding`, `contentMediaType`, and `contentSchema`. `infinite-loop-detection` is read only from benchmark metadata when present because it is not a JSON Schema keyword.",
        "",
        "Timeout is measured at schema level. Under/over remain test-level: under is `n_under_constraint / n_invalid_completed`, and over is `n_over_constraint / n_valid_completed`.",
        "",
        "Candidates are not removed when support is low. Instead, `eligible_timeout`, `eligible_under`, and `eligible_over` document whether the candidate met the support thresholds: schema support >= 5, invalid completed tests >= 20 for under, and valid completed tests >= 20 for over.",
        "",
        "These are associative signals, not causal explanations. A high lift can reflect correlated schema patterns, dataset composition, or support effects.",
        "",
        "## Top Timeout Candidates",
        "",
        markdown_table(
            ["risk_datasets", "candidate", "type", "datasets", "median_lift", "mean_delta", "schemas"],
            timeout_table,
        ),
        "",
        "## Top Under-Constraint Candidates",
        "",
        markdown_table(
            ["risk_datasets", "candidate", "type", "datasets", "median_lift", "mean_delta", "schemas"],
            under_table,
        ),
        "",
        "## Top Over-Constraint Candidates",
        "",
        markdown_table(
            ["risk_datasets", "candidate", "type", "datasets", "median_lift", "mean_delta", "schemas"],
            over_table,
        ),
        "",
        "",
        "## Generated CSV Files",
        "",
        "- `dataset_summary.csv`: coverage, timeout, under/over, accuracy, compile timing, and schema complexity by dataset.",
        "- `phase_summary_by_dataset.csv`: mean/std/median/p95 timing by dataset, status, and phase.",
        "- `timeout_stage_by_dataset.csv`: timeout stage counts and shares per dataset.",
        "- `feature_risk_by_dataset.csv`: legacy single-feature rates for quick comparison.",
        "- `common_feature_risks.csv`: legacy single-feature cross-dataset summary.",
        "- `candidate_risk_by_dataset.csv`: single and pair candidate rates by dataset, including support and eligibility flags.",
        "- `candidate_timeout_ranking.csv`, `candidate_under_ranking.csv`, `candidate_over_ranking.csv`: independent rankings used by each heatmap.",
        "",
        "## Plots To Inspect First",
        "",
        "- `dataset_timeout_under_over_rates.svg`: direct comparison of timeout/under/over rates.",
        "- `completed_phase_mean_by_dataset.svg`: phase timing on completed schemas, log scale.",
        "- `timeout_phase_mean_by_dataset.svg`: partial timeout phase timing and elapsed timeout time, log scale.",
        "- `candidate_timeout_lift_heatmap.svg`, `candidate_under_lift_heatmap.svg`, `candidate_over_lift_heatmap.svg`: independently ranked single/pair candidates.",
        "- `feature_timeout_lift_heatmap.svg`, `feature_under_lift_heatmap.svg`, `feature_over_lift_heatmap.svg`: compatibility aliases containing the same mixed single/pair candidate heatmaps.",
        "- `timeout_stage_distribution.svg`: where the runs stop by dataset.",
        "- `compile_vs_error_tradeoff.svg`: median compile time vs balanced error rate, bubble size proportional to timeout rate.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    results_root = Path(args.results_root)
    out_dir = (
        Path(args.output_dir)
        if args.output_dir
        else results_root / args.framework / "cross_dataset_analysis"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        dataset: load_dataset_tables(results_root, args.framework, dataset, args.plots_dir_name)
        for dataset in args.datasets
    }
    summary_rows = [summarize_dataset(dataset, tables[dataset]["schema"]) for dataset in args.datasets]
    phase_rows = [row for dataset in args.datasets for row in phase_summary_rows(dataset, tables[dataset]["phase"])]
    stage_rows = [row for dataset in args.datasets for row in timeout_stage_rows(dataset, tables[dataset]["schema"])]
    feature_rows = [row for dataset in args.datasets for row in feature_rates_by_dataset(dataset, tables[dataset]["schema"])]
    common_features = common_feature_rows(feature_rows)
    candidate_rows = [
        row
        for dataset in args.datasets
        for row in candidate_risk_rows_by_dataset(dataset, tables[dataset]["schema"])
    ]
    timeout_ranking = rank_candidate_rows(candidate_rows, "timeout")
    under_ranking = rank_candidate_rows(candidate_rows, "under")
    over_ranking = rank_candidate_rows(candidate_rows, "over")

    write_csv(
        out_dir / "dataset_summary.csv",
        summary_rows,
        [
            "dataset_id",
            "dataset",
            "n_schemas",
            "completed_schemas",
            "timeout_schemas",
            "schema_timeout_rate",
            "n_tests",
            "completed_tests",
            "timeout_tests",
            "coverage_rate",
            "test_timeout_rate",
            "accuracy_completed",
            "under_rate",
            "over_rate",
            "balanced_error_rate",
            "permissive_score",
            "median_compile_s",
            "mean_compile_s",
            "std_compile_s",
            "p95_compile_s",
            "max_compile_s",
            "median_validation_s",
            "p95_validation_s",
            "median_schema_json_chars",
            "median_schema_depth",
            "median_nb_keywords",
        ],
    )
    write_csv(
        out_dir / "phase_summary_by_dataset.csv",
        phase_rows,
        ["dataset_id", "dataset", "schema_status", "phase", "n", "mean_s", "std_s", "median_s", "p95_s", "max_s"],
    )
    write_csv(
        out_dir / "timeout_stage_by_dataset.csv",
        stage_rows,
        ["dataset_id", "dataset", "timeout_stage", "schemas", "share"],
    )
    write_csv(
        out_dir / "feature_risk_by_dataset.csv",
        feature_rows,
        [
            "dataset_id",
            "dataset",
            "feature",
            "schemas_with_feature",
            "support",
            "timeout_rate_with",
            "timeout_rate_without",
            "timeout_lift",
            "timeout_delta",
            "global_timeout_rate",
            "under_rate_with",
            "under_rate_without",
            "under_lift",
            "under_delta",
            "global_under_rate",
            "over_rate_with",
            "over_rate_without",
            "over_lift",
            "over_delta",
            "global_over_rate",
        ],
    )
    write_csv(
        out_dir / "common_feature_risks.csv",
        common_features,
        [
            "feature",
            "datasets_seen",
            "timeout_risk_datasets",
            "under_risk_datasets",
            "over_risk_datasets",
            "mean_timeout_lift",
            "max_timeout_lift",
            "mean_under_delta",
            "mean_over_delta",
            "risk_score",
            "datasets_timeout",
            "datasets_under",
            "datasets_over",
        ],
    )
    candidate_fields = [
        "dataset_id",
        "dataset",
        "candidate_type",
        "candidate",
        "feature_a",
        "feature_b",
        "schemas_with_candidate",
        "schemas_without_candidate",
        "support",
        "timeout_rate_with",
        "timeout_rate_without",
        "timeout_lift",
        "timeout_delta",
        "n_invalid_completed_with",
        "n_invalid_completed_without",
        "under_rate_with",
        "under_rate_without",
        "under_lift",
        "under_delta",
        "n_valid_completed_with",
        "n_valid_completed_without",
        "over_rate_with",
        "over_rate_without",
        "over_lift",
        "over_delta",
        "eligible_timeout",
        "eligible_under",
        "eligible_over",
    ]
    write_csv(out_dir / "candidate_risk_by_dataset.csv", candidate_rows, candidate_fields)

    def ranking_fields(metric: str) -> list[str]:
        return [
            "candidate_type",
            "candidate",
            "feature_a",
            "feature_b",
            "datasets_seen",
            f"{metric}_risk_datasets",
            f"datasets_{metric}",
            f"mean_{metric}_lift",
            f"median_{metric}_lift",
            f"max_{metric}_lift",
            f"mean_{metric}_delta",
            f"median_{metric}_delta",
            "total_schemas_with_candidate",
            "total_support_across_datasets",
            f"{metric}_risk_score",
            "ranking_position",
        ]

    write_csv(out_dir / "candidate_timeout_ranking.csv", timeout_ranking, ranking_fields("timeout"))
    write_csv(out_dir / "candidate_under_ranking.csv", under_ranking, ranking_fields("under"))
    write_csv(out_dir / "candidate_over_ranking.csv", over_ranking, ranking_fields("over"))

    hgroup_percent_chart(
        out_dir / "dataset_timeout_under_over_rates.svg",
        "Timeout, under, and over rates by dataset",
        summary_rows,
        [
            ("schema_timeout_rate", "timeout", "red"),
            ("under_rate", "under", "orange"),
            ("over_rate", "over", "purple"),
        ],
    )
    hgroup_percent_chart(
        out_dir / "dataset_coverage_accuracy.svg",
        "Coverage and accuracy by dataset",
        summary_rows,
        [
            ("coverage_rate", "coverage", "teal"),
            ("accuracy_completed", "accuracy", "blue"),
        ],
    )
    grouped_log_phase_chart(
        out_dir / "completed_phase_mean_by_dataset.svg",
        "Mean phase timing on completed schemas",
        phase_rows,
        "completed",
    )
    grouped_log_phase_chart(
        out_dir / "timeout_phase_mean_by_dataset.svg",
        "Mean phase timing on timeout schemas",
        phase_rows,
        "timeout",
    )
    stacked_stage_chart(out_dir / "timeout_stage_distribution.svg", "Timeout stage distribution by dataset", stage_rows)
    reliability_scatter(out_dir / "compile_vs_error_tradeoff.svg", "Compile time vs balanced error", summary_rows)

    timeout_candidate_rows = [row for row in timeout_ranking if row["timeout_risk_datasets"] > 0]
    under_candidate_rows = [row for row in under_ranking if row["under_risk_datasets"] > 0]
    over_candidate_rows = [row for row in over_ranking if row["over_risk_datasets"] > 0]
    candidate_lift_heatmap(
        out_dir / "candidate_timeout_lift_heatmap.svg",
        "Timeout lift by candidate and dataset",
        candidate_rows,
        timeout_candidate_rows,
        "timeout_lift",
    )
    candidate_lift_heatmap(
        out_dir / "candidate_under_lift_heatmap.svg",
        "Under-constraint lift by candidate and dataset",
        candidate_rows,
        under_candidate_rows,
        "under_lift",
    )
    candidate_lift_heatmap(
        out_dir / "candidate_over_lift_heatmap.svg",
        "Over-constraint lift by candidate and dataset",
        candidate_rows,
        over_candidate_rows,
        "over_lift",
    )
    candidate_lift_heatmap(
        out_dir / "feature_timeout_lift_heatmap.svg",
        "Timeout lift by candidate and dataset",
        candidate_rows,
        timeout_candidate_rows,
        "timeout_lift",
    )
    candidate_lift_heatmap(
        out_dir / "feature_under_lift_heatmap.svg",
        "Under-constraint lift by candidate and dataset",
        candidate_rows,
        under_candidate_rows,
        "under_lift",
    )
    candidate_lift_heatmap(
        out_dir / "feature_over_lift_heatmap.svg",
        "Over-constraint lift by candidate and dataset",
        candidate_rows,
        over_candidate_rows,
        "over_lift",
    )

    make_readme(out_dir, summary_rows, timeout_ranking, under_ranking, over_ranking)
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
