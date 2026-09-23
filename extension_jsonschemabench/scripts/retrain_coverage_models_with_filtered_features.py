#!/usr/bin/env python3
"""Retrain coverage models with retained feature lists from feature filtering."""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Any

from build_outlines_coverage_prediction import (
    ROOT,
    train_one,
    union_fieldnames,
    write_csv,
    write_skipped_target,
)


DEFAULT_COVERAGE_ROOT = ROOT / "extension_jsonschemabench" / "coverage_prediction"
DEFAULT_FRAMEWORKS = ["guidance", "outlines", "xgr"]
DEFAULT_TARGETS = ["under", "over"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage-root", default=str(DEFAULT_COVERAGE_ROOT))
    parser.add_argument("--feature-filter-root", default="")
    parser.add_argument("--output-root", default="")
    parser.add_argument("--frameworks", nargs="+", default=DEFAULT_FRAMEWORKS)
    parser.add_argument("--targets", nargs="+", default=DEFAULT_TARGETS)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--validation-size", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=800)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_feature_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def can_train_target(rows: list[dict[str, Any]], label: str, retained_features: list[str]) -> tuple[bool, str]:
    if not rows:
        return False, "missing_dataset"
    if label not in rows[0]:
        return False, "missing_label"
    values = {int(row[label]) for row in rows}
    if values != {0, 1}:
        return False, "single_class"
    if not retained_features:
        return False, "no_retained_features"
    return True, "ok"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_summary_readme(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Filtered Coverage Model Retraining",
        "",
        "Models in this directory were retrained from existing global modeling datasets using retained feature lists from `coverage_prediction/feature_filter`.",
        "",
        "| framework | target | status | rows | positives | retained features | selected model |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['framework']} | {row['target']} | {row['status']} | {row['rows']} | "
            f"{row['positives']} | {row['retained_features']} | {row['selected_model']} |"
        )
    write_text(path, "\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    coverage_root = Path(args.coverage_root)
    feature_filter_root = Path(args.feature_filter_root) if args.feature_filter_root else coverage_root / "feature_filter"
    output_root = Path(args.output_root) if args.output_root else coverage_root / "filtered_retrained"
    output_root.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    for framework in args.frameworks:
        source_root = coverage_root / "modeles_predictifs" / framework
        framework_output = output_root / framework
        for child in ("features", "modeling", "models", "metrics"):
            (framework_output / child).mkdir(parents=True, exist_ok=True)

        for target in args.targets:
            label = f"y_{target}"
            rows = read_csv(source_root / "modeling" / f"{target}_dataset.csv")
            retained_features = read_feature_list(feature_filter_root / framework / target / "retained_features.txt")
            write_csv(framework_output / "modeling" / f"{target}_dataset.csv", rows, union_fieldnames(rows))
            source_filter_csv = feature_filter_root / framework / target / "feature_filter_decisions.csv"
            if source_filter_csv.exists():
                shutil.copyfile(source_filter_csv, framework_output / "modeling" / f"{target}_feature_filter_decisions.csv")

            ok, reason = can_train_target(rows, label, retained_features)
            positives = sum(int(row[label]) for row in rows) if rows and label in rows[0] else 0
            selected_model = ""
            if ok:
                train_one(
                    target,
                    rows,
                    label,
                    retained_features,
                    framework_output,
                    args.seed + (1 if target == "over" else 0),
                    args.validation_size,
                    args.test_size,
                    args.epochs,
                    store_candidate_models=False,
                )
                model_selection = read_csv(framework_output / "metrics" / f"{target}_model_selection.csv")
                if model_selection:
                    def score(row: dict[str, Any]) -> tuple[float, float, float, float]:
                        return (
                            float(row.get("pr_auc", -1) or -1),
                            float(row.get("f1", 0) or 0),
                            float(row.get("recall", 0) or 0),
                            float(row.get("precision", 0) or 0),
                        )

                    selected_model = str(max(model_selection, key=score).get("model", ""))
                status = "trained"
            else:
                write_skipped_target(framework_output, target, rows, label, reason)
                (framework_output / "modeling" / f"selected_{target}_features.txt").write_text("", encoding="utf-8")
                status = reason

            summary = {
                "framework": framework,
                "target": target,
                "status": status,
                "rows": len(rows),
                "positives": positives,
                "retained_features": len(retained_features),
                "selected_model": selected_model,
            }
            summary_rows.append(summary)
            print(
                f"{framework}/{target}: {status}, rows={len(rows)}, "
                f"positives={positives}, features={len(retained_features)}, model={selected_model}"
            )

    write_csv(
        output_root / "filtered_retraining_summary.csv",
        summary_rows,
        ["framework", "target", "status", "rows", "positives", "retained_features", "selected_model"],
    )
    write_summary_readme(output_root / "README.md", summary_rows)
    write_summary_readme(output_root / "README.md", summary_rows)
    print(f"wrote filtered retrained models to {output_root}")


if __name__ == "__main__":
    main()
