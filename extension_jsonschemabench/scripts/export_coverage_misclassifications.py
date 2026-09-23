#!/usr/bin/env python3
"""Export misclassified tests for the selected coverage prediction models."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import numpy as np
from joblib import load

from build_outlines_coverage_prediction import DEFAULT_OUTPUT_ROOT, make_feature_matrix


TARGETS = {
    "under": {
        "label": "y_under",
        "positive_name": "UNDER",
        "negative_name": "CORRECT_INVALID",
    },
    "over": {
        "label": "y_over",
        "positive_name": "OVER",
        "negative_name": "CORRECT_VALID",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--split", default="test", choices=["train", "validation", "test", "all"])
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def output_fieldnames(selected_features: list[str]) -> list[str]:
    base = [
        "target",
        "model_name",
        "split",
        "dataset",
        "schema_id",
        "test_id",
        "test_index",
        "expected_validity",
        "failure_type",
        "true_class",
        "predicted_class",
        "error_type",
        "y_true",
        "y_pred",
        "predicted_probability",
        "threshold",
        "margin_to_threshold",
        "wrong_confidence",
    ]
    return base + selected_features


def split_rows(rows: list[dict[str, str]], split_schema_ids: dict[str, list[str]], split: str) -> list[dict[str, str]]:
    if split == "all":
        wanted = set().union(*(set(values) for values in split_schema_ids.values()))
    else:
        wanted = set(split_schema_ids[split])
    return [row for row in rows if row.get("schema_id") in wanted]


def resolved_model_path(output_root: Path, target: str) -> Path | None:
    recovered_path = output_root / "models_recovered" / f"{target}_model.pkl"
    if recovered_path.exists() and recovered_path.stat().st_size > 0:
        return recovered_path
    model_path = output_root / "models" / f"{target}_model.pkl"
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path
    return model_path if model_path.exists() else None


def export_target(output_root: Path, target: str, split: str) -> tuple[list[dict[str, Any]], list[str]]:
    config = TARGETS[target]
    model_path = resolved_model_path(output_root, target)
    if model_path is None:
        print(f"{target}: skipped export, missing model")
        return [], output_fieldnames([])
    model_bundle = load(model_path)
    model_name = str(model_bundle["model_name"])
    threshold = float(model_bundle["threshold"])
    selected_features = list(model_bundle["selected_features"])
    pipeline = model_bundle["pipeline"]
    rows = read_csv(output_root / "modeling" / f"{target}_dataset.csv")
    rows = split_rows(rows, model_bundle["split_schema_ids"], split)
    x = make_feature_matrix(rows, selected_features)
    scores = pipeline.predict_proba(x)[:, 1]
    y_true = np.asarray([int(row[config["label"]]) for row in rows], dtype=int)
    y_pred = (scores >= threshold).astype(int)

    mistakes: list[dict[str, Any]] = []
    for row, actual, predicted, score in zip(rows, y_true, y_pred, scores):
        if int(actual) == int(predicted):
            continue
        error_type = "false_negative" if int(actual) == 1 else "false_positive"
        margin = float(score - threshold)
        true_class = config["positive_name"] if int(actual) == 1 else config["negative_name"]
        predicted_class = config["positive_name"] if int(predicted) == 1 else config["negative_name"]
        out = {
            "target": target,
            "model_name": model_name,
            "split": split,
            "dataset": row.get("dataset", ""),
            "schema_id": row.get("schema_id", ""),
            "test_id": row.get("test_id", ""),
            "test_index": row.get("test_index", ""),
            "expected_validity": row.get("expected_validity", ""),
            "failure_type": row.get("failure_type", ""),
            "true_class": true_class,
            "predicted_class": predicted_class,
            "error_type": error_type,
            "y_true": int(actual),
            "y_pred": int(predicted),
            "predicted_probability": f"{float(score):.8g}",
            "threshold": f"{threshold:.8g}",
            "margin_to_threshold": f"{margin:.8g}",
            "wrong_confidence": f"{abs(margin):.8g}",
        }
        for feature in selected_features:
            out[feature] = row.get(feature, "")
        mistakes.append(out)

    mistakes.sort(key=lambda item: (item["error_type"], -float(item["wrong_confidence"]), item["dataset"], item["schema_id"], int(item["test_index"])))
    return mistakes, output_fieldnames(selected_features)


def summary_rows(all_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], int] = {}
    for row in all_rows:
        key = (str(row["target"]), str(row["dataset"]), str(row["error_type"]))
        groups[key] = groups.get(key, 0) + 1
    return [
        {"target": target, "dataset": dataset, "error_type": error_type, "count": count}
        for (target, dataset, error_type), count in sorted(groups.items())
    ]


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    error_dir = output_root / "errors"
    combined: list[dict[str, Any]] = []
    combined_fields: list[str] = []
    seen_fields: set[str] = set()

    for target in ("under", "over"):
        rows, fields = export_target(output_root, target, args.split)
        write_csv(error_dir / f"{target}_{args.split}_misclassified_tests.csv", rows, fields)
        combined.extend(rows)
        for field in fields:
            if field not in seen_fields:
                seen_fields.add(field)
                combined_fields.append(field)
        print(f"{target}: wrote {len(rows)} misclassified rows")

    write_csv(error_dir / f"all_{args.split}_misclassified_tests.csv", combined, combined_fields)
    write_csv(error_dir / f"{args.split}_misclassification_summary.csv", summary_rows(combined), ["target", "dataset", "error_type", "count"])
    print(f"Wrote misclassification exports to {error_dir}")


if __name__ == "__main__":
    main()
