#!/usr/bin/env python3
"""Small helper for the Bash Github_hard resilient runner."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from run_dataset_with_timeouts import (  # noqa: E402
    dataset_id_from_schema_id,
    load_completed_tests,
    load_timeout_checkpoint_stage,
    load_timed_out_schemas,
    mark_timeout_profile_rows,
    mark_timeout_schema_compile_profile,
    rel,
    test_ids_for_schema,
    timeout_checkpoints_path,
    timeout_path,
    upsert_timeout_record,
)

FRAMEWORK = "outlines"
DATASET = os.environ.get("OUTLINES_DATASET", "Github_hard")
OUTPUT_DIR = ROOT / "extension_jsonschemabench" / "results" / "per_dataset_runs"
RUN_DIR = OUTPUT_DIR / FRAMEWORK / DATASET


def output_path() -> Path:
    return RUN_DIR / "per_test_results.jsonl"


def profile_path() -> Path:
    return RUN_DIR / "timing_profile.csv"


def schema_compile_profile_path() -> Path:
    return RUN_DIR / "schema_compile_profile.csv"


def should_run(schema_path: Path) -> bool:
    expected_tests = test_ids_for_schema(schema_path)
    if not expected_tests:
        return False
    if schema_path.name in load_timed_out_schemas(timeout_path(OUTPUT_DIR, FRAMEWORK, DATASET)):
        return False
    completed = load_completed_tests(output_path(), FRAMEWORK)
    return not expected_tests.issubset(completed)


def mark(schema_path: Path, elapsed: float, returncode: str) -> None:
    checkpoint_path = timeout_checkpoints_path(OUTPUT_DIR, FRAMEWORK, DATASET)
    stage = load_timeout_checkpoint_stage(checkpoint_path, schema_path.name, FRAMEWORK) or "unknown"
    message = f"process_terminated_during_{stage}; returncode={returncode}"

    mark_timeout_profile_rows(profile_path(), schema_path, FRAMEWORK, elapsed)
    mark_timeout_schema_compile_profile(
        schema_compile_profile_path(),
        schema_path,
        FRAMEWORK,
        elapsed,
        stage,
    )

    base = {
        "schema_id": schema_path.name,
        "dataset_id": dataset_id_from_schema_id(schema_path.name),
        "schema_path": rel(schema_path),
        "framework_id": FRAMEWORK,
    }
    upsert_timeout_record(
        timeout_path(OUTPUT_DIR, FRAMEWORK, DATASET),
        {
            **base,
            "timeout_minutes": None,
            "compile_timeout_minutes": None,
            "validation_timeout_minutes": None,
            "elapsed_seconds": round(elapsed, 3),
            "timeout_stage": stage,
            "notes": message,
        },
    )
    upsert_timeout_record(
        checkpoint_path,
        {
            **base,
            "framework": "Outlines",
            "last_stage": stage,
            "final_status": "timeout",
            "elapsed_seconds": round(elapsed, 3),
            "timeout_seconds": round(elapsed, 3),
            "exception_type": "ProcessTerminated",
            "exception_message": message,
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("schema", type=Path)

    mark_parser = subparsers.add_parser("mark")
    mark_parser.add_argument("schema", type=Path)
    mark_parser.add_argument("elapsed", type=float)
    mark_parser.add_argument("returncode")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    schema_path = args.schema if args.schema.is_absolute() else ROOT / args.schema
    if args.command == "status":
        raise SystemExit(0 if should_run(schema_path) else 1)
    if args.command == "mark":
        mark(schema_path, args.elapsed, args.returncode)
        raise SystemExit(0)


if __name__ == "__main__":
    main()
