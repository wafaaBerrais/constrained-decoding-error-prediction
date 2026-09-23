#!/usr/bin/env python3
"""Resume Outlines Github_hard one schema at a time.

Some Github_hard schemas terminate the Outlines child process during regex or
index construction before the normal supervisor can write a final status. This
driver keeps the outer process alive, records those schemas as blocking
timeouts, and continues with the next schema.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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
DATASET = "Github_hard"
DEFAULT_OUTPUT_DIR = ROOT / "extension_jsonschemabench" / "results" / "per_dataset_runs"
RUNNER = SCRIPT_DIR / "run_dataset_with_timeouts.py"


def output_path(output_dir: Path) -> Path:
    return output_dir / FRAMEWORK / DATASET / "per_test_results.jsonl"


def profile_path(output_dir: Path) -> Path:
    return output_dir / FRAMEWORK / DATASET / "timing_profile.csv"


def schema_compile_profile_path(output_dir: Path) -> Path:
    return output_dir / FRAMEWORK / DATASET / "schema_compile_profile.csv"


def append_driver_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def schema_has_completed_or_timeout(schema_path: Path, output_dir: Path) -> bool:
    expected_tests = test_ids_for_schema(schema_path)
    if not expected_tests:
        return True

    timeout_log = timeout_path(output_dir, FRAMEWORK, DATASET)
    if schema_path.name in load_timed_out_schemas(timeout_log):
        return True

    completed = load_completed_tests(output_path(output_dir), FRAMEWORK)
    return expected_tests.issubset(completed)


def mark_process_terminated(schema_path: Path, output_dir: Path, elapsed: float) -> None:
    checkpoint_path = timeout_checkpoints_path(output_dir, FRAMEWORK, DATASET)
    stage = load_timeout_checkpoint_stage(checkpoint_path, schema_path.name, FRAMEWORK) or "unknown"
    message = f"process_terminated_during_{stage}"

    mark_timeout_profile_rows(profile_path(output_dir), schema_path, FRAMEWORK, elapsed)
    mark_timeout_schema_compile_profile(
        schema_compile_profile_path(output_dir),
        schema_path,
        FRAMEWORK,
        elapsed,
        stage,
    )

    record_base: dict[str, Any] = {
        "schema_id": schema_path.name,
        "dataset_id": dataset_id_from_schema_id(schema_path.name),
        "schema_path": rel(schema_path),
        "framework_id": FRAMEWORK,
    }
    upsert_timeout_record(
        timeout_path(output_dir, FRAMEWORK, DATASET),
        {
            **record_base,
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
            **record_base,
            "framework": "Outlines",
            "last_stage": stage,
            "final_status": "timeout",
            "elapsed_seconds": round(elapsed, 3),
            "timeout_seconds": round(elapsed, 3),
            "exception_type": "ProcessTerminated",
            "exception_message": message,
        },
    )


def run_one_schema(args: argparse.Namespace, schema_path: Path) -> int:
    cmd = [
        sys.executable,
        str(RUNNER),
        "--framework",
        FRAMEWORK,
        "--dataset",
        DATASET,
        "--timeout-minutes",
        str(args.timeout_minutes),
        "--progress-interval-minutes",
        str(args.progress_interval_minutes),
        "--profile-timings",
        "--profile-checkpoint-interval-seconds",
        str(args.profile_checkpoint_interval_seconds),
        "--trace-stages",
        "--continue-on-error",
        str(schema_path),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("HF_HOME", str(ROOT / ".hf_cache"))
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_OFFLINE", "1")

    started = time.monotonic()
    with args.child_log.open("a", encoding="utf-8") as log:
        log.write(f"\n===== resilient {schema_path.name} =====\n")
        log.flush()
        completed = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=log, text=True)
    elapsed = time.monotonic() - started

    if completed.returncode != 0 and not schema_has_completed_or_timeout(schema_path, args.output_dir):
        mark_process_terminated(schema_path, args.output_dir, elapsed)
        append_driver_log(
            args.driver_log,
            f"{schema_path.name}: child_returncode={completed.returncode} marked process terminated after {elapsed:.3f}s",
        )
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "maskbench" / "data")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-at-schema", default=None)
    parser.add_argument("--timeout-minutes", type=float, default=10.0)
    parser.add_argument("--progress-interval-minutes", type=float, default=1.0)
    parser.add_argument("--profile-checkpoint-interval-seconds", type=float, default=10.0)
    parser.add_argument(
        "--driver-log",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / FRAMEWORK / DATASET / "resilient_driver_20260706.log",
    )
    parser.add_argument(
        "--child-log",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / FRAMEWORK / DATASET / "resilient_child_20260706.log",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.data_dir = args.data_dir if args.data_dir.is_absolute() else ROOT / args.data_dir
    args.output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    args.driver_log = args.driver_log if args.driver_log.is_absolute() else ROOT / args.driver_log
    args.child_log = args.child_log if args.child_log.is_absolute() else ROOT / args.child_log

    files = sorted(args.data_dir.glob(f"{DATASET}---*.json"), key=lambda path: path.name)
    if args.start_at_schema:
        files = files[next(index for index, path in enumerate(files) if path.name == args.start_at_schema) :]

    append_driver_log(args.driver_log, f"selected={len(files)} start={files[0].name if files else 'none'}")
    for index, schema_path in enumerate(files, start=1):
        if schema_has_completed_or_timeout(schema_path, args.output_dir):
            append_driver_log(args.driver_log, f"[{index}/{len(files)}] {schema_path.name}: skipped done/timeout/no-tests")
            continue
        append_driver_log(args.driver_log, f"[{index}/{len(files)}] {schema_path.name}: running")
        run_one_schema(args, schema_path)
    append_driver_log(args.driver_log, "done")


if __name__ == "__main__":
    main()
