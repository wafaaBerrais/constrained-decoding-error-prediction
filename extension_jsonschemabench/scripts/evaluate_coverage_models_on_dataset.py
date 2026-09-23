#!/usr/bin/env python3
"""Evaluate trained coverage-prediction models on an external dataset.

This script does not train on the external dataset. It rebuilds the same
feature rows used by the coverage-prediction pipeline, loads the existing
model pickles, and reports out-of-distribution metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from build_outlines_coverage_prediction import (
    DEFAULT_DATA_ROOT,
    DEFAULT_RESULTS_ROOT,
    FRAMEWORK_ALIASES,
    ROOT,
    classification_report_rows,
    extract_dataset_features,
    framework_is_guidance,
    framework_uses_runtime_only,
    make_feature_matrix,
    make_modeling_rows,
    runtime_only_rows,
    sklearn_confusion_row,
    sklearn_metrics_row,
    write_csv,
)


DEFAULT_MODEL_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction" / "modeles_predictifs"
DEFAULT_OUTPUT_ROOT = DEFAULT_MODEL_ROOT.parent / "external_eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="Kubernetes")
    parser.add_argument("--framework", action="append", dest="frameworks", default=None)
    parser.add_argument("--results-root", default=str(DEFAULT_RESULTS_ROOT))
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--model-root", default=str(DEFAULT_MODEL_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--allow-incomplete", action="store_true", help="Evaluate even if the dataset has fewer tests than expected.")
    parser.add_argument("--expected-tests", type=int, default=0, help="Optional expected unique test count, for example 4588.")
    return parser.parse_args()


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for row in rows:
        key = (str(row.get("schema_id") or ""), str(row.get("test_id") or ""))
        if key not in by_key:
            order.append(key)
        by_key[key] = row
    return [by_key[key] for key in order]


def safe_load_model(model_root: Path, framework: str, target: str) -> tuple[dict[str, Any] | None, Path | None, str]:
    candidates = [
        model_root / framework / "models" / f"{target}_model.pkl",
        model_root / framework / "models_recovered" / f"{target}_model.pkl",
    ]
    errors: list[str] = []
    for path in candidates:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"{path}: missing_or_empty")
            continue
        try:
            model = joblib.load(path)
        except Exception as exc:
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        return model, path, ""
    return None, None, "; ".join(errors)


def target_rows(framework: str, rows: list[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    if target == "under":
        source = runtime_only_rows(rows) if framework_uses_runtime_only(framework) else rows
        return make_modeling_rows(source, "y_under", "UNDER", "CORRECT_INVALID")
    if target == "over":
        source = runtime_only_rows(rows) if framework_is_guidance(framework) or framework_uses_runtime_only(framework) else rows
        return make_modeling_rows(source, "y_over", "OVER", "CORRECT_VALID")
    raise ValueError(f"Unknown target: {target}")


def prediction_bucket(y_true: int, y_pred: int) -> str:
    if y_true == 1 and y_pred == 1:
        return "TP"
    if y_true == 1 and y_pred == 0:
        return "FN"
    if y_true == 0 and y_pred == 1:
        return "FP"
    return "TN"


def evaluate_target(
    framework: str,
    target: str,
    rows: list[dict[str, Any]],
    model_root: Path,
    output_root: Path,
    dataset: str,
) -> dict[str, Any]:
    model, model_path, error = safe_load_model(model_root, framework, target)
    label = f"y_{target}"
    eval_rows = target_rows(framework, rows, target)
    out_dir = output_root / framework
    out_dir.mkdir(parents=True, exist_ok=True)

    if not model:
        return {
            "framework": framework,
            "target": target,
            "dataset": dataset,
            "status": "skipped",
            "reason": error or "model_not_found",
            "n": len(eval_rows),
            "positives": sum(int(row.get(label, 0)) for row in eval_rows),
            "negatives": len(eval_rows) - sum(int(row.get(label, 0)) for row in eval_rows),
        }

    if not eval_rows:
        return {
            "framework": framework,
            "target": target,
            "dataset": dataset,
            "status": "skipped",
            "reason": "no_rows_for_target",
            "model_path": str(model_path),
            "n": 0,
            "positives": 0,
            "negatives": 0,
        }

    selected_features = list(model["selected_features"])
    threshold = float(model.get("threshold", 0.5))
    pipeline = model["pipeline"]
    model_name = str(model.get("model_name", "model"))
    x = make_feature_matrix(eval_rows, selected_features)
    y_true = np.asarray([int(row[label]) for row in eval_rows], dtype=int)
    y_score = pipeline.predict_proba(x)[:, 1]
    y_pred = (y_score >= threshold).astype(int)

    metric = sklearn_metrics_row(model_name, "external_test", y_true, y_score, dataset, threshold)
    metric.update({"framework": framework, "target": target, "model_path": str(model_path)})
    confusion = sklearn_confusion_row(model_name, "external_test", y_true, y_score, dataset, threshold)
    confusion.update({"framework": framework, "target": target, "model_path": str(model_path)})
    report_rows = classification_report_rows(model_name, "external_test", y_true, y_score, threshold)
    for row in report_rows:
        row.update({"framework": framework, "target": target, "dataset": dataset})

    prediction_rows: list[dict[str, Any]] = []
    for source, truth, score, pred in zip(eval_rows, y_true, y_score, y_pred):
        prediction_rows.append(
            {
                "framework": framework,
                "target": target,
                "dataset": dataset,
                "schema_id": source.get("schema_id", ""),
                "test_id": source.get("test_id", ""),
                "test_index": source.get("test_index", ""),
                "failure_type": source.get("failure_type", ""),
                "expected_validity": source.get("expected_validity", ""),
                "actual_result": source.get("actual_result", ""),
                "label": label,
                "y_true": int(truth),
                "predicted_probability": float(score),
                "threshold": threshold,
                "y_pred": int(pred),
                "prediction_bucket": prediction_bucket(int(truth), int(pred)),
            }
        )

    write_csv(out_dir / f"{target}_external_metrics.csv", [metric])
    write_csv(out_dir / f"{target}_external_confusion_matrix.csv", [confusion])
    write_csv(out_dir / f"{target}_external_classification_report.csv", report_rows)
    write_csv(out_dir / f"{target}_external_predictions.csv", prediction_rows)
    errors = [row for row in prediction_rows if row["prediction_bucket"] in {"FP", "FN"}]
    write_csv(out_dir / f"{target}_external_misclassified_tests.csv", errors)

    return {
        "framework": framework,
        "target": target,
        "dataset": dataset,
        "status": "evaluated",
        "model": model_name,
        "model_path": str(model_path),
        "threshold": threshold,
        "n": int(metric["n"]),
        "positives": int(metric["positives"]),
        "negatives": int(metric["negatives"]),
        "accuracy": metric["accuracy"],
        "precision": metric["precision"],
        "recall": metric["recall"],
        "f1": metric["f1"],
        "roc_auc": metric["roc_auc"],
        "pr_auc": metric["pr_auc"],
        "balanced_accuracy": metric["balanced_accuracy"],
        "tn": confusion["tn"],
        "fp": confusion["fp"],
        "fn": confusion["fn"],
        "tp": confusion["tp"],
    }


def count_unique_tests(results_root: Path, framework: str, dataset: str) -> int:
    path = results_root / framework / dataset / "per_test_results.jsonl"
    if not path.exists():
        return 0
    keys: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        keys.add((str(row.get("schema_id") or ""), str(row.get("test_id") or "")))
    return len(keys)


def format_metric(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        return f"{value:.4f}"
    return str(value)


def write_readme(output_root: Path, dataset: str, summary_rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# External Coverage Prediction Evaluation: {dataset}",
        "",
        "These metrics apply existing coverage-prediction models to an external dataset without retraining on it.",
        "",
        "| Framework | Target | Status | N | Positives | F1 | PR-AUC | ROC-AUC | Balanced accuracy | Confusion |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary_rows:
        confusion = ""
        if row.get("status") == "evaluated":
            confusion = f"tn={row['tn']}, fp={row['fp']}, fn={row['fn']}, tp={row['tp']}"
        else:
            confusion = str(row.get("reason", ""))
        lines.append(
            "| {framework} | {target} | {status} | {n} | {positives} | {f1} | {pr_auc} | {roc_auc} | {balanced_accuracy} | {confusion} |".format(
                framework=row.get("framework", ""),
                target=row.get("target", ""),
                status=row.get("status", ""),
                n=row.get("n", ""),
                positives=row.get("positives", ""),
                f1=format_metric(row.get("f1", "")),
                pr_auc=format_metric(row.get("pr_auc", "")),
                roc_auc=format_metric(row.get("roc_auc", "")),
                balanced_accuracy=format_metric(row.get("balanced_accuracy", "")),
                confusion=confusion,
            )
        )
    lines.append("")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    frameworks = args.frameworks or ["guidance", "xgr", "outlines"]
    results_root = Path(args.results_root)
    data_root = Path(args.data_root)
    model_root = Path(args.model_root)
    output_root = Path(args.output_root) / args.dataset
    output_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    for framework in frameworks:
        aliases = FRAMEWORK_ALIASES.get(framework, {framework})
        _ = aliases
        unique_tests = count_unique_tests(results_root, framework, args.dataset)
        if args.expected_tests and unique_tests < args.expected_tests and not args.allow_incomplete:
            summary_rows.append(
                {
                    "framework": framework,
                    "target": "all",
                    "dataset": args.dataset,
                    "status": "skipped",
                    "reason": f"incomplete_results unique_tests={unique_tests} expected={args.expected_tests}",
                    "n": 0,
                    "positives": 0,
                    "negatives": 0,
                }
            )
            continue

        rows = extract_dataset_features(args.dataset, framework, results_root, data_root)
        if not rows:
            summary_rows.append(
                {
                    "framework": framework,
                    "target": "all",
                    "dataset": args.dataset,
                    "status": "skipped",
                    "reason": "no_feature_rows",
                    "n": 0,
                    "positives": 0,
                    "negatives": 0,
                }
            )
            continue
        rows = dedupe_rows(rows)
        write_csv(
            output_root / framework / f"{args.dataset}_external_features.csv",
            rows,
            None,
        )
        for target in ["under", "over"]:
            summary_rows.append(evaluate_target(framework, target, rows, model_root, output_root, args.dataset))

    write_csv(output_root / "external_eval_summary.csv", summary_rows)
    write_readme(output_root, args.dataset, summary_rows)


if __name__ == "__main__":
    main()
