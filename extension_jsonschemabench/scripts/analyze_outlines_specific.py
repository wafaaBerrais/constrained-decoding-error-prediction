#!/usr/bin/env python3
"""Build Outlines-specific cross-dataset analyses.

The current study intentionally excludes Github_hard until its Outlines
execution issues are resolved.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from analyze_dataset_statistics import (
    ANALYZED_FEATURES,
    BASE_FEATURES,
    DEFAULT_RESULTS_ROOT,
    PALETTE,
    read_csv,
    svg_doc,
    svg_text,
    to_bool,
    to_float,
    write_csv,
)


DEFAULT_DATASETS = ["Github_trivial", "Github_easy", "Github_medium", "Github_ultra"]
SHORT = {
    "Github_trivial": "trivial",
    "Github_easy": "easy",
    "Github_medium": "medium",
    "Github_ultra": "ultra",
}
MIN_SCHEMAS_WITH_CANDIDATE = 5


def short(dataset: str) -> str:
    return SHORT.get(dataset, dataset.replace("Github_", ""))


def finite(value: Any) -> float | None:
    parsed = to_float(value)
    if parsed is None or not math.isfinite(parsed):
        return None
    return parsed


def median(values: list[float]) -> float:
    return statistics.median(values) if values else math.nan


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else math.nan


def quantile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] * (high - pos) + ordered[high] * (pos - low)


def status(row: dict[str, str]) -> str:
    final = str(row.get("final_status") or "").lower()
    exc = str(row.get("exception_type") or "")
    if final == "completed":
        return "completed"
    if exc == "ProcessTerminated" or "process_terminated" in str(row.get("exception_message") or ""):
        return "process_terminated"
    if final == "compile_error":
        return "compile_error"
    if final == "timeout":
        return "timeout"
    if final == "running":
        return "incomplete"
    return final or "unknown"


def load_dataset(results_root: Path, dataset: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    run_dir = results_root / "outlines" / dataset
    plots = run_dir / "plots"
    schema_rows = read_csv(plots / "schema_level_stats.csv")
    compile_rows = read_csv(run_dir / "schema_compile_profile.csv")
    if not schema_rows:
        raise SystemExit(f"Missing schema stats for {dataset}: {plots / 'schema_level_stats.csv'}")
    if not compile_rows:
        raise SystemExit(f"Missing schema compile profile for {dataset}: {run_dir / 'schema_compile_profile.csv'}")
    return schema_rows, compile_rows


def merge_rows(dataset: str, schema_rows: list[dict[str, str]], compile_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_schema = {row.get("schema_id", ""): row for row in schema_rows}
    rows: list[dict[str, Any]] = []
    for compile_row in compile_rows:
        schema_id = compile_row.get("schema_id", "")
        schema_row = by_schema.get(schema_id, {})
        merged: dict[str, Any] = {
            **schema_row,
            **compile_row,
            "dataset": short(dataset),
            "status_group": status(compile_row),
        }
        rows.append(merged)
    return rows


def summarize_numbers(values: list[float], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_n": len(values),
        f"{prefix}_mean": mean(values),
        f"{prefix}_median": median(values),
        f"{prefix}_p95": quantile(values, 0.95),
        f"{prefix}_max": max(values) if values else math.nan,
    }


def failure_stage_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], int] = Counter()
    reached_index: Counter[str] = Counter()
    failed_index: Counter[str] = Counter()
    for row in rows:
        dataset = str(row["dataset_id"])
        st = row["status_group"]
        stage = str(row.get("last_stage") or "unknown")
        grouped[(dataset, st, stage)] += 1
        if to_bool(row.get("regex_built")) or stage in {"building_index", "index_built", "initializing_guide", "completed"}:
            reached_index[dataset] += 1
            if st in {"timeout", "process_terminated"} and stage == "building_index":
                failed_index[dataset] += 1
    out = [
        {
            "dataset_id": dataset,
            "dataset": short(dataset),
            "status": st,
            "last_stage": stage,
            "schemas": count,
        }
        for (dataset, st, stage), count in sorted(grouped.items())
    ]
    for dataset in sorted(reached_index):
        out.append(
            {
                "dataset_id": dataset,
                "dataset": short(dataset),
                "status": "conditional",
                "last_stage": "P(index_failure|regex_built)",
                "schemas": failed_index[dataset],
                "denominator": reached_index[dataset],
                "rate": failed_index[dataset] / reached_index[dataset] if reached_index[dataset] else 0,
            }
        )
    return out


def regex_phase_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for dataset in sorted({str(row["dataset_id"]) for row in rows}):
        subset = [row for row in rows if row["dataset_id"] == dataset]
        for st in ["completed", "timeout", "process_terminated", "compile_error", "incomplete"]:
            group = [row for row in subset if row["status_group"] == st]
            if not group:
                continue
            row_out: dict[str, Any] = {"dataset_id": dataset, "dataset": short(dataset), "status": st, "schemas": len(group)}
            for col in [
                "schema_serialize_s",
                "regex_build_s",
                "index_build_s",
                "guide_init_s",
                "total_compile_s",
                "regex_chars",
                "regex_expansion_ratio",
            ]:
                vals = [finite(row.get(col)) for row in group]
                vals = [v for v in vals if v is not None]
                row_out.update(summarize_numbers(vals, col))
            out.append(row_out)
    return out


def regex_outliers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in rows if finite(row.get("regex_expansion_ratio")) is not None]
    ratios = [finite(row.get("regex_expansion_ratio")) for row in candidates]
    ratios = [v for v in ratios if v is not None]
    threshold = max(10.0, quantile(ratios, 0.95)) if ratios else math.inf
    out = []
    for row in candidates:
        ratio = finite(row.get("regex_expansion_ratio")) or 0.0
        if ratio < threshold:
            continue
        features = [feature for feature in BASE_FEATURES if to_bool(row.get(feature))]
        out.append(
            {
                "dataset_id": row["dataset_id"],
                "schema_id": row["schema_id"],
                "schema_json_chars": row.get("schema_json_chars", ""),
                "regex_chars": row.get("regex_chars", ""),
                "regex_expansion_ratio": row.get("regex_expansion_ratio", ""),
                "regex_build_s": row.get("regex_build_s", ""),
                "index_build_s": row.get("index_build_s", ""),
                "final_status": row.get("final_status", ""),
                "last_stage": row.get("last_stage", ""),
                "status_group": row.get("status_group", ""),
                "features_present": ";".join(features),
            }
        )
    return sorted(out, key=lambda r: finite(r["regex_expansion_ratio"]) or 0, reverse=True)


def proxy_bins(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for proxy in [
        "regex_num_alternations_proxy",
        "regex_num_groups_proxy",
        "regex_num_repetitions_proxy",
        "regex_max_group_depth_proxy",
    ]:
        values = [finite(row.get(proxy)) for row in rows]
        values = [v for v in values if v is not None]
        if not values:
            continue
        cuts = [quantile(values, q) for q in [0, 0.25, 0.5, 0.75, 1]]
        for i in range(4):
            lo, hi = cuts[i], cuts[i + 1]
            if i == 3:
                group = [row for row in rows if (finite(row.get(proxy)) is not None and lo <= (finite(row.get(proxy)) or 0) <= hi)]
            else:
                group = [row for row in rows if (finite(row.get(proxy)) is not None and lo <= (finite(row.get(proxy)) or 0) < hi)]
            if not group:
                continue
            problems = [row for row in group if row["status_group"] in {"timeout", "process_terminated"}]
            index_vals = [finite(row.get("index_build_s")) for row in group]
            index_vals = [v for v in index_vals if v is not None]
            out.append(
                {
                    "proxy": proxy,
                    "bin": f"Q{i + 1}",
                    "min_value": lo,
                    "max_value": hi,
                    "schemas": len(group),
                    "problem_schemas": len(problems),
                    "problem_rate": len(problems) / len(group),
                    "index_build_median_s": median(index_vals),
                    "index_build_p95_s": quantile(index_vals, 0.95),
                }
            )
    return out


def candidate_names(rows: list[dict[str, Any]]) -> list[tuple[str, str, tuple[str, ...]]]:
    singles = [(feature, "single", (feature,)) for feature in ANALYZED_FEATURES]
    pairs = []
    for left, right in combinations(ANALYZED_FEATURES, 2):
        support = sum(1 for row in rows if to_bool(row.get(left)) and to_bool(row.get(right)))
        if support >= MIN_SCHEMAS_WITH_CANDIDATE:
            pairs.append((f"{left}__AND__{right}", "pair", (left, right)))
    return singles + pairs


def row_has_candidate(row: dict[str, Any], features: tuple[str, ...]) -> bool:
    return all(to_bool(row.get(feature)) for feature in features)


def candidate_regex_complexity(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for dataset in sorted({str(row["dataset_id"]) for row in rows}):
        subset = [row for row in rows if row["dataset_id"] == dataset]
        for name, typ, features in candidate_names(subset):
            with_rows = [row for row in subset if row_has_candidate(row, features)]
            without_rows = [row for row in subset if not row_has_candidate(row, features)]
            if len(with_rows) < MIN_SCHEMAS_WITH_CANDIDATE:
                continue
            def med(col: str, group: list[dict[str, Any]]) -> float:
                vals = [finite(row.get(col)) for row in group]
                return median([v for v in vals if v is not None])
            out.append(
                {
                    "dataset_id": dataset,
                    "dataset": short(dataset),
                    "candidate": name,
                    "candidate_type": typ,
                    "schemas_with_candidate": len(with_rows),
                    "schemas_without_candidate": len(without_rows),
                    "regex_expansion_median_with": med("regex_expansion_ratio", with_rows),
                    "regex_expansion_median_without": med("regex_expansion_ratio", without_rows),
                    "regex_expansion_delta": med("regex_expansion_ratio", with_rows) - med("regex_expansion_ratio", without_rows),
                    "regex_size_median_with": med("regex_chars", with_rows),
                    "regex_size_median_without": med("regex_chars", without_rows),
                    "index_build_median_with": med("index_build_s", with_rows),
                    "index_build_median_without": med("index_build_s", without_rows),
                    "index_build_delta": med("index_build_s", with_rows) - med("index_build_s", without_rows),
                }
            )
    return out


def within_size_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = [row for row in rows if finite(row.get("schema_json_chars")) is not None and finite(row.get("regex_expansion_ratio")) is not None]
    sizes = [finite(row.get("schema_json_chars")) or 0 for row in usable]
    cuts = [quantile(sizes, q) for q in [0, 0.25, 0.5, 0.75, 1]] if sizes else []
    out = []
    for i in range(4):
        lo, hi = cuts[i], cuts[i + 1]
        group = [row for row in usable if lo <= (finite(row.get("schema_json_chars")) or 0) <= hi]
        if len(group) < 10:
            continue
        ratios = [finite(row.get("regex_expansion_ratio")) or 0 for row in group]
        high_cut = quantile(ratios, 0.75)
        low_cut = quantile(ratios, 0.25)
        high = [row for row in group if (finite(row.get("regex_expansion_ratio")) or 0) >= high_cut]
        low = [row for row in group if (finite(row.get("regex_expansion_ratio")) or 0) <= low_cut]
        for feature in ANALYZED_FEATURES:
            high_support = sum(1 for row in high if to_bool(row.get(feature)))
            low_support = sum(1 for row in low if to_bool(row.get(feature)))
            if high_support + low_support == 0:
                continue
            out.append(
                {
                    "size_bin": f"Q{i + 1}",
                    "feature": feature,
                    "high_expansion_support": high_support,
                    "high_expansion_rate": high_support / len(high) if high else 0,
                    "low_expansion_support": low_support,
                    "low_expansion_rate": low_support / len(low) if low else 0,
                    "rate_delta": (high_support / len(high) if high else 0) - (low_support / len(low) if low else 0),
                    "schemas_in_bin": len(group),
                }
            )
    return sorted(out, key=lambda row: abs(row["rate_delta"]), reverse=True)


def regex_constraint_bins(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row.get("status_group") == "completed"]
    out = []
    for metric in ["regex_chars", "regex_expansion_ratio"]:
        values = [finite(row.get(metric)) for row in completed]
        values = [v for v in values if v is not None]
        if not values:
            continue
        cuts = [quantile(values, q) for q in [0, 0.25, 0.5, 0.75, 1]]
        for i in range(4):
            lo, hi = cuts[i], cuts[i + 1]
            group = [row for row in completed if finite(row.get(metric)) is not None and lo <= (finite(row.get(metric)) or 0) <= hi]
            invalid_completed = sum(int(float(row.get("n_invalid_completed") or 0)) for row in group)
            valid_completed = sum(int(float(row.get("n_valid_completed") or 0)) for row in group)
            under = sum(int(float(row.get("n_under_constraint") or 0)) for row in group)
            over = sum(int(float(row.get("n_over_constraint") or 0)) for row in group)
            out.append(
                {
                    "metric": metric,
                    "bin": f"Q{i + 1}",
                    "min_value": lo,
                    "max_value": hi,
                    "schemas": len(group),
                    "invalid_completed": invalid_completed,
                    "valid_completed": valid_completed,
                    "under": under,
                    "over": over,
                    "under_rate": under / invalid_completed if invalid_completed else 0,
                    "over_rate": over / valid_completed if valid_completed else 0,
                }
            )
    return out


def explanatory_candidates(candidate_rows: list[dict[str, Any]], risk_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    risk_by_candidate = defaultdict(list)
    for row in risk_rows:
        risk_by_candidate[row.get("candidate", "")].append(row)
    out = []
    for row in sorted(candidate_rows, key=lambda r: (abs(float(r.get("regex_expansion_delta") or 0)), abs(float(r.get("index_build_delta") or 0))), reverse=True)[:100]:
        risks = risk_by_candidate.get(str(row["candidate"]), [])
        problem = "performance"
        risk_note = ""
        for metric in ["timeout", "under", "over"]:
            risky = [r for r in risks if str(r.get(f"{metric}_eligible", "")).lower() == "true" and float(r.get(f"{metric}_lift") or 0) > 1.0]
            if risky:
                problem = metric
                risk_note = ";".join(sorted({r.get("dataset", "") for r in risky}))
                break
        out.append(
            {
                "problem_target": problem,
                "datasets_concerned": row.get("dataset", ""),
                "support_total": row.get("schemas_with_candidate", ""),
                "candidate": row.get("candidate", ""),
                "candidate_type": row.get("candidate_type", ""),
                "risk_signal_datasets": risk_note,
                "regex_expansion_delta": row.get("regex_expansion_delta", ""),
                "index_build_delta": row.get("index_build_delta", ""),
                "evidence_level": "association",
                "notes": "Candidate generated from observed feature/internal-metric association; not causal.",
            }
        )
    return out


def simple_bar_svg(path: Path, title: str, rows: list[dict[str, Any]], label_key: str, value_key: str) -> None:
    rows = rows[:30]
    width, height = 1000, max(260, 70 + 26 * len(rows))
    left, top, bar_w = 260, 46, 650
    max_value = max([float(row.get(value_key) or 0) for row in rows], default=1)
    body = [svg_text(24, 28, title, 18, weight="700")]
    for i, row in enumerate(rows):
        y = top + i * 26
        value = float(row.get(value_key) or 0)
        w = 0 if max_value == 0 else value / max_value * bar_w
        body.append(svg_text(left - 8, y + 14, str(row.get(label_key, ""))[:32], 11, "end"))
        body.append(f'<rect x="{left}" y="{y}" width="{w:.2f}" height="18" fill="{PALETTE["blue"]}"/>')
        body.append(svg_text(left + w + 5, y + 14, f"{value:.3g}", 11))
    path.write_text(svg_doc(width, height, body), encoding="utf-8")


def scatter_svg(path: Path, title: str, rows: list[dict[str, Any]], x_key: str, y_key: str) -> None:
    points = [(finite(row.get(x_key)), finite(row.get(y_key)), row.get("status_group", "")) for row in rows]
    points = [(x, y, s) for x, y, s in points if x is not None and y is not None and x > 0 and y > 0]
    width, height = 900, 560
    left, right, top, bottom = 80, 30, 50, 70
    plot_w, plot_h = width - left - right, height - top - bottom
    body = [svg_text(24, 28, title, 18, weight="700")]
    if not points:
        body.append(svg_text(24, 80, "No finite positive values available.", 13))
        path.write_text(svg_doc(width, height, body), encoding="utf-8")
        return
    xs = [math.log10(x) for x, _, _ in points]
    ys = [math.log10(y) for _, y, _ in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    color = {"completed": PALETTE["green"], "timeout": PALETTE["orange"], "process_terminated": PALETTE["red"], "compile_error": PALETTE["purple"]}
    for x, y, st in points:
        lx, ly = math.log10(x), math.log10(y)
        px = left + (lx - xmin) / (xmax - xmin or 1) * plot_w
        py = top + plot_h - (ly - ymin) / (ymax - ymin or 1) * plot_h
        body.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3" fill="{color.get(st, PALETTE["gray"])}" opacity="0.65"/>')
    body.append(svg_text(width / 2, height - 24, f"log10 {x_key}", 12, "middle"))
    body.append(svg_text(24, top + plot_h / 2, f"log10 {y_key}", 12))
    path.write_text(svg_doc(width, height, body), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--datasets", nargs="*", default=DEFAULT_DATASETS)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    results_root = Path(args.results_root)
    out_dir = Path(args.output_dir) if args.output_dir else results_root / "outlines" / "cross_dataset_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, Any]] = []
    all_risk_rows: list[dict[str, str]] = []
    for dataset in args.datasets:
        schema_rows, compile_rows = load_dataset(results_root, dataset)
        all_rows.extend(merge_rows(dataset, schema_rows, compile_rows))
        risk_path = results_root / "outlines" / dataset / "plots" / "candidate_risk_by_dataset.csv"
        if risk_path.exists():
            all_risk_rows.extend(read_csv(risk_path))

    failure_rows = failure_stage_summary(all_rows)
    phase_rows = regex_phase_summary(all_rows)
    outlier_rows = regex_outliers(all_rows)
    proxy_rows = proxy_bins(all_rows)
    candidate_rows = candidate_regex_complexity(all_rows)
    within_rows = within_size_candidates(all_rows)
    constraint_bins = regex_constraint_bins(all_rows)
    explanatory_rows = explanatory_candidates(candidate_rows, all_risk_rows)

    write_csv(out_dir / "outlines_failure_stage_summary.csv", failure_rows, ["dataset_id", "dataset", "status", "last_stage", "schemas", "denominator", "rate"])
    write_csv(out_dir / "failure_stage_by_dataset.csv", failure_rows, ["dataset_id", "dataset", "status", "last_stage", "schemas", "denominator", "rate"])
    write_csv(out_dir / "regex_phase_summary_by_dataset.csv", phase_rows, sorted({key for row in phase_rows for key in row}))
    write_csv(out_dir / "regex_expansion_summary_by_dataset.csv", phase_rows, sorted({key for row in phase_rows for key in row}))
    write_csv(out_dir / "regex_expansion_outliers.csv", outlier_rows, ["dataset_id", "schema_id", "schema_json_chars", "regex_chars", "regex_expansion_ratio", "regex_build_s", "index_build_s", "final_status", "last_stage", "status_group", "features_present"])
    write_csv(out_dir / "regex_proxy_status_bins.csv", proxy_rows, ["proxy", "bin", "min_value", "max_value", "schemas", "problem_schemas", "problem_rate", "index_build_median_s", "index_build_p95_s"])
    write_csv(out_dir / "regex_proxy_vs_index_time.csv", proxy_rows, ["proxy", "bin", "min_value", "max_value", "schemas", "index_build_median_s", "index_build_p95_s", "problem_rate"])
    write_csv(out_dir / "candidate_regex_complexity.csv", candidate_rows, sorted({key for row in candidate_rows for key in row}))
    expansion_rank = sorted(candidate_rows, key=lambda row: float(row.get("regex_expansion_delta") or 0), reverse=True)
    index_rank = sorted(candidate_rows, key=lambda row: float(row.get("index_build_delta") or 0), reverse=True)
    write_csv(out_dir / "candidate_regex_expansion_ranking.csv", expansion_rank, sorted({key for row in candidate_rows for key in row}))
    write_csv(out_dir / "candidate_index_cost_ranking.csv", index_rank, sorted({key for row in candidate_rows for key in row}))
    write_csv(out_dir / "regex_complexity_risk_by_dataset.csv", candidate_rows, sorted({key for row in candidate_rows for key in row}))
    write_csv(out_dir / "within_size_regex_expansion_candidates.csv", within_rows, ["size_bin", "feature", "high_expansion_support", "high_expansion_rate", "low_expansion_support", "low_expansion_rate", "rate_delta", "schemas_in_bin"])
    write_csv(out_dir / "regex_characteristic_constraint_bins.csv", constraint_bins, ["metric", "bin", "min_value", "max_value", "schemas", "invalid_completed", "valid_completed", "under", "over", "under_rate", "over_rate"])
    write_csv(out_dir / "outlines_internal_metric_group_summary.csv", phase_rows, sorted({key for row in phase_rows for key in row}))
    write_csv(out_dir / "outlines_explanatory_candidates.csv", explanatory_rows, ["problem_target", "datasets_concerned", "support_total", "candidate", "candidate_type", "risk_signal_datasets", "regex_expansion_delta", "index_build_delta", "evidence_level", "notes"])

    unavailable = [{"dataset_id": dataset, "note": "No oracle diagnostics or failure_traces.jsonl were available in the current results."} for dataset in args.datasets]
    write_csv(out_dir / "oracle_under_reason_by_dataset.csv", unavailable, ["dataset_id", "note"])
    write_csv(out_dir / "under_oracle_reason_summary.csv", unavailable, ["dataset_id", "note"])
    write_csv(out_dir / "over_rejection_context_by_dataset.csv", unavailable, ["dataset_id", "note"])
    write_csv(out_dir / "over_rejection_summary.csv", unavailable, ["dataset_id", "note"])

    scatter_svg(out_dir / "schema_size_vs_regex_size.svg", "Schema size vs regex size", all_rows, "schema_json_chars", "regex_chars")
    scatter_svg(out_dir / "schema_size_vs_regex_expansion.svg", "Schema size vs regex expansion", all_rows, "schema_json_chars", "regex_expansion_ratio")
    scatter_svg(out_dir / "regex_size_vs_regex_build.svg", "Regex size vs regex build time", all_rows, "regex_chars", "regex_build_s")
    scatter_svg(out_dir / "regex_size_vs_index_build.svg", "Regex size vs index build time", all_rows, "regex_chars", "index_build_s")
    scatter_svg(out_dir / "regex_expansion_vs_index_build.svg", "Regex expansion vs index build time", all_rows, "regex_expansion_ratio", "index_build_s")
    simple_bar_svg(out_dir / "candidate_regex_expansion_heatmap.svg", "Top candidate regex expansion deltas", expansion_rank[:30], "candidate", "regex_expansion_delta")
    simple_bar_svg(out_dir / "candidate_index_cost_heatmap.svg", "Top candidate index build deltas", index_rank[:30], "candidate", "index_build_delta")
    stage_bars = sorted([row for row in failure_rows if row.get("status") != "conditional"], key=lambda row: float(row.get("schemas") or 0), reverse=True)
    simple_bar_svg(out_dir / "outlines_failure_stage_by_dataset.svg", "Outlines failure/status stages", stage_bars, "last_stage", "schemas")
    simple_bar_svg(out_dir / "outlines_failure_stage_status_heatmap.svg", "Outlines status-stage counts", stage_bars, "status", "schemas")

    readme = [
        "# Outlines cross-dataset analysis",
        "",
        "Current scope excludes Github_hard by request. Included datasets: " + ", ".join(args.datasets) + ".",
        "",
        "Regex proxy metrics are syntactic proxies, not FSM state counts.",
        "Associations in candidate tables are not causal claims.",
        "Oracle under and over rejection diagnostic files were not present, so those tables document unavailability.",
    ]
    (out_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
