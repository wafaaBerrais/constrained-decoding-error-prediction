#!/usr/bin/env python3
"""Cross-validate retained coverage-prediction models by schema_id groups."""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.model_selection import GroupKFold
try:
    from sklearn.model_selection import StratifiedGroupKFold
except ImportError:  # pragma: no cover - compatibility fallback
    StratifiedGroupKFold = None
from sklearn.pipeline import Pipeline

from build_outlines_coverage_prediction import (
    ROOT,
    choose_threshold,
    make_feature_matrix,
    make_preprocessor,
    sklearn_confusion_row,
    sklearn_metrics_row,
    write_csv,
)


DEFAULT_COVERAGE_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction"
DEFAULT_FRAMEWORKS = ["guidance", "outlines", "xgr"]
DEFAULT_TARGETS = ["under", "over"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-root", default=str(DEFAULT_COVERAGE_ROOT))
    parser.add_argument("--frameworks", nargs="+", default=DEFAULT_FRAMEWORKS)
    parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--inner-validation-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260729)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def resolved_model_path(framework_root: Path, target: str) -> Path | None:
    recovered_path = framework_root / "models_recovered" / f"{target}_model.pkl"
    if recovered_path.exists() and recovered_path.stat().st_size > 0:
        return recovered_path
    model_path = framework_root / "models" / f"{target}_model.pkl"
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path
    return model_path if model_path.exists() else None


def numeric_summary(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(arr)) if len(arr) else float("nan"),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)) if len(arr) else float("nan"),
        "max": float(np.max(arr)) if len(arr) else float("nan"),
    }


def split_inner_train_validation(rows: list[dict[str, Any]], seed: int, validation_size: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups = sorted({str(row["schema_id"]) for row in rows})
    rng = random.Random(seed)
    rng.shuffle(groups)
    n_validation = max(1, round(len(groups) * validation_size)) if len(groups) >= 4 else 1
    validation_groups = set(groups[:n_validation])
    train_rows = [row for row in rows if str(row["schema_id"]) not in validation_groups]
    validation_rows = [row for row in rows if str(row["schema_id"]) in validation_groups]
    if len({str(row["schema_id"]) for row in train_rows}) == 0 or len({int(row["_cv_label"]) for row in validation_rows}) < 2:
        return rows, []
    return train_rows, validation_rows


def grouped_splits(rows: list[dict[str, Any]], label: str, folds: int, seed: int):
    y = np.asarray([int(row[label]) for row in rows], dtype=int)
    groups = np.asarray([str(row["schema_id"]) for row in rows], dtype=object)
    indices = np.arange(len(rows))
    n_groups = len(set(groups))
    n_splits = min(folds, n_groups)
    if n_splits < 2:
        raise ValueError("Need at least two schema groups for cross-validation")
    if StratifiedGroupKFold is not None and len(set(y)) == 2:
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        yield from splitter.split(indices, y, groups)
    else:
        splitter = GroupKFold(n_splits=n_splits)
        yield from splitter.split(indices, y, groups)


def evaluate_retained_model(
    framework_root: Path,
    framework: str,
    target: str,
    folds: int,
    inner_validation_size: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    model_path = resolved_model_path(framework_root, target)
    data_path = framework_root / "modeling" / f"{target}_dataset.csv"
    if model_path is None or not data_path.exists():
        return [], [], None

    retained = joblib.load(model_path)
    label = str(retained["label"])
    features = list(retained["selected_features"])
    model_name = str(retained["model_name"])
    base_classifier = retained["pipeline"].named_steps["classifier"]

    rows = read_csv(data_path)
    rows = [row for row in rows if row.get("actual_result") in {"passed", "failed"}]
    if not rows or len({int(row[label]) for row in rows}) < 2:
        return [], [], {
            "framework": framework,
            "target": target,
            "model": model_name,
            "status": "skipped_single_class",
            "rows": len(rows),
            "features": len(features),
        }
    for row in rows:
        row["_cv_label"] = int(row[label])

    fold_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    for fold_idx, (train_val_idx, test_idx) in enumerate(grouped_splits(rows, label, folds, seed), start=1):
        train_val_rows = [rows[int(idx)] for idx in train_val_idx]
        test_rows = [rows[int(idx)] for idx in test_idx]
        train_rows, validation_rows = split_inner_train_validation(train_val_rows, seed + fold_idx, inner_validation_size)
        pipeline = Pipeline(
            steps=[
                ("preprocess", make_preprocessor(features)),
                ("classifier", clone(base_classifier)),
            ]
        )
        x_train = make_feature_matrix(train_rows, features)
        y_train = np.asarray([int(row[label]) for row in train_rows], dtype=int)
        pipeline.fit(x_train, y_train)

        if validation_rows:
            x_validation = make_feature_matrix(validation_rows, features)
            y_validation = np.asarray([int(row[label]) for row in validation_rows], dtype=int)
            validation_score = pipeline.predict_proba(x_validation)[:, 1]
            threshold = choose_threshold(y_validation, validation_score)
        else:
            threshold = float(retained.get("threshold", 0.5))

        x_test = make_feature_matrix(test_rows, features)
        y_test = np.asarray([int(row[label]) for row in test_rows], dtype=int)
        test_score = pipeline.predict_proba(x_test)[:, 1]
        metrics = sklearn_metrics_row(model_name, f"fold_{fold_idx}", y_test, test_score, dataset="all", threshold=threshold)
        confusion = sklearn_confusion_row(model_name, f"fold_{fold_idx}", y_test, test_score, dataset="all", threshold=threshold)
        fold_rows.append(
            {
                "framework": framework,
                "target": target,
                "fold": fold_idx,
                "schema_groups_test": len({str(row["schema_id"]) for row in test_rows}),
                "features": len(features),
                **metrics,
            }
        )
        confusion_rows.append({"framework": framework, "target": target, "fold": fold_idx, **confusion})

    metric_names = ["accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "balanced_accuracy"]
    summary: dict[str, Any] = {
        "framework": framework,
        "target": target,
        "model": model_name,
        "status": "ok",
        "folds": len(fold_rows),
        "rows": len(rows),
        "positives": sum(int(row[label]) for row in rows),
        "negatives": len(rows) - sum(int(row[label]) for row in rows),
        "features": len(features),
        "tp_sum": sum(int(row["tp"]) for row in confusion_rows),
        "fn_sum": sum(int(row["fn"]) for row in confusion_rows),
        "fp_sum": sum(int(row["fp"]) for row in confusion_rows),
        "tn_sum": sum(int(row["tn"]) for row in confusion_rows),
    }
    for metric in metric_names:
        stats = numeric_summary([float(row[metric]) for row in fold_rows if math.isfinite(float(row[metric]))])
        for stat_name, value in stats.items():
            summary[f"{metric}_{stat_name}"] = value
    return fold_rows, confusion_rows, summary


def main() -> None:
    args = parse_args()
    coverage_root = Path(args.coverage_root)
    all_fold_rows: list[dict[str, Any]] = []
    all_confusion_rows: list[dict[str, Any]] = []
    all_summaries: list[dict[str, Any]] = []

    for framework in args.frameworks:
        framework_root = coverage_root / "modeles_predictifs" / framework
        output_root = framework_root / "cross_validation"
        output_root.mkdir(parents=True, exist_ok=True)
        framework_fold_rows: list[dict[str, Any]] = []
        framework_confusion_rows: list[dict[str, Any]] = []
        framework_summaries: list[dict[str, Any]] = []
        for target in args.targets:
            fold_rows, confusion_rows, summary = evaluate_retained_model(
                framework_root,
                framework,
                target,
                args.folds,
                args.inner_validation_size,
                args.seed,
            )
            if fold_rows:
                write_csv(output_root / f"{target}_fold_metrics.csv", fold_rows)
                write_csv(output_root / f"{target}_fold_confusion_matrix.csv", confusion_rows)
            if summary is not None:
                framework_summaries.append(summary)
            framework_fold_rows.extend(fold_rows)
            framework_confusion_rows.extend(confusion_rows)
        write_csv(output_root / "cv_summary.csv", framework_summaries)
        framework_fold_rows and write_csv(output_root / "all_fold_metrics.csv", framework_fold_rows)
        framework_confusion_rows and write_csv(output_root / "all_fold_confusion_matrix.csv", framework_confusion_rows)
        all_fold_rows.extend(framework_fold_rows)
        all_confusion_rows.extend(framework_confusion_rows)
        all_summaries.extend(framework_summaries)

    write_csv(coverage_root / "cross_validation_summary.csv", all_summaries)
    all_fold_rows and write_csv(coverage_root / "cross_validation_fold_metrics.csv", all_fold_rows)
    all_confusion_rows and write_csv(coverage_root / "cross_validation_confusion_matrix.csv", all_confusion_rows)
    for row in all_summaries:
        if row.get("status") != "ok":
            print(f"{row['framework']} {row['target']}: {row['status']}")
            continue
        print(
            f"{row['framework']} {row['target']}: "
            f"F1={row['f1_mean']:.3f}+/-{row['f1_std']:.3f}, "
            f"P={row['precision_mean']:.3f}, R={row['recall_mean']:.3f}, "
            f"PR-AUC={row['pr_auc_mean']:.3f}, ROC-AUC={row['roc_auc_mean']:.3f}"
        )


if __name__ == "__main__":
    main()
