#!/usr/bin/env python3
"""Run schemas with per-schema timeouts while writing timing rows to one CSV."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from run_dataset_with_timeouts import (
    ROOT,
    RUNNER,
    detect_stage,
    discover_files,
    load_timeout_checkpoint_stage,
    mark_timeout_profile_rows,
    mark_timeout_schema_compile_profile,
    rel,
    terminate_process,
    test_ids_for_schema,
    timeout_status_for_stage,
    upsert_timeout_record,
)


RUNNING_RESULTS = {"", "running_compile_grammar", "compiled", "running_validation"}


def load_final_profile_keys(path: Path, framework: str) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if not path.exists() or path.stat().st_size == 0:
        return keys
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("framework_id") != framework:
                continue
            schema_id = str(row.get("schema_id") or "")
            test_id = str(row.get("test_id") or "")
            actual = str(row.get("actual_result") or "")
            if schema_id and test_id and actual not in RUNNING_RESULTS:
                keys.add((schema_id, test_id))
    return keys


def terminated_by_signal(status: str) -> bool:
    if not status.startswith("exit_-"):
        return False
    try:
        int(status.removeprefix("exit_"))
    except ValueError:
        return False
    return True


def run_schema(args: argparse.Namespace, schema_path: Path, log_path: Path) -> tuple[str, float]:
    cmd = [
        sys.executable,
        str(RUNNER),
        "--framework",
        args.framework,
        "--output",
        str(args.output),
        "--profile-csv",
        str(args.profile_csv),
        "--profile-checkpoint-interval-seconds",
        str(args.profile_checkpoint_interval_seconds),
    ]
    if args.tokenizer:
        cmd.extend(["--tokenizer", args.tokenizer])
    if args.trace_stages:
        cmd.append("--trace-stages")
    cmd.append(str(schema_path))

    started = time.monotonic()
    compile_timeout = args.compile_timeout_minutes if args.compile_timeout_minutes is not None else args.timeout_minutes
    validation_timeout = args.validation_timeout_minutes if args.validation_timeout_minutes is not None else args.timeout_minutes
    deadline = started + compile_timeout * 60
    progress_interval = max(args.progress_interval_minutes * 60, 1)
    next_progress = started + progress_interval
    stage = "compile_grammar"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== {schema_path.name} =====\n")
        log.flush()
        log_start_offset = log.tell()
        process = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=log, text=True)
        while process.poll() is None:
            now = time.monotonic()
            detected_stage = detect_stage(log_path, log_start_offset)
            if detected_stage != stage:
                stage = detected_stage
                if stage in {"after_compile", "validation"}:
                    deadline = started + validation_timeout * 60
            if now >= deadline:
                terminate_process(process)
                return timeout_status_for_stage(stage), time.monotonic() - started
            if now >= next_progress:
                print(f"  still running after {(now - started) / 60:.2f} min stage={stage}", flush=True)
                next_progress = now + progress_interval
            time.sleep(min(5, max(deadline - now, 0.1)))

        if process.returncode == 0:
            return "ok", time.monotonic() - started
        return f"exit_{process.returncode}", time.monotonic() - started


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="MaskBench data directory or one schema JSON file.")
    parser.add_argument("--framework", required=True)
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--output", required=True, type=Path, help="Temporary JSONL output for replayed results.")
    parser.add_argument("--profile-csv", required=True, type=Path, help="Timing CSV to create/update.")
    parser.add_argument("--timeout-log", required=True, type=Path, help="JSONL timeout log for this replay.")
    parser.add_argument("--supervisor-log", required=True, type=Path, help="Combined child stdout/stderr log.")
    parser.add_argument("--timeout-minutes", type=float, default=30.0)
    parser.add_argument("--compile-timeout-minutes", type=float, default=None)
    parser.add_argument("--validation-timeout-minutes", type=float, default=None)
    parser.add_argument("--progress-interval-minutes", type=float, default=1.0)
    parser.add_argument("--profile-checkpoint-interval-seconds", type=float, default=30.0)
    parser.add_argument("--tokenizer", default="unsloth/Meta-Llama-3.1-8B-Instruct")
    parser.add_argument("--trace-stages", action="store_true")
    return parser.parse_args()


def absolute_under_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    args.input = absolute_under_root(Path(args.input))
    args.output = absolute_under_root(args.output)
    args.profile_csv = absolute_under_root(args.profile_csv)
    args.timeout_log = absolute_under_root(args.timeout_log)
    args.supervisor_log = absolute_under_root(args.supervisor_log)

    datasets = set(args.dataset) if args.dataset else None
    files = discover_files(args.input, datasets)
    if not files:
        raise SystemExit("No schema files selected.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.profile_csv.parent.mkdir(parents=True, exist_ok=True)
    args.timeout_log.parent.mkdir(parents=True, exist_ok=True)
    args.supervisor_log.parent.mkdir(parents=True, exist_ok=True)

    print(f"Selected schema files: {len(files)}", flush=True)
    print(f"Timing CSV: {rel(args.profile_csv)}", flush=True)
    print(f"Temporary JSONL: {rel(args.output)}", flush=True)
    print(f"Timeout per schema: {args.timeout_minutes} minutes", flush=True)
    if args.compile_timeout_minutes is not None or args.validation_timeout_minutes is not None:
        print(f"Compile timeout: {args.compile_timeout_minutes or args.timeout_minutes} minutes", flush=True)
        print(f"Validation timeout: {args.validation_timeout_minutes or args.timeout_minutes} minutes", flush=True)

    for index, schema_path in enumerate(files, start=1):
        expected_tests = test_ids_for_schema(schema_path)
        final_profile_keys = load_final_profile_keys(args.profile_csv, args.framework)
        if expected_tests and expected_tests.issubset(final_profile_keys):
            print(f"[{index}/{len(files)}] {schema_path.name}: already profiled", flush=True)
            continue
        if not expected_tests:
            print(f"[{index}/{len(files)}] {schema_path.name}: skipped no tests", flush=True)
            continue

        print(f"[{index}/{len(files)}] {schema_path.name}: running", flush=True)
        status, elapsed = run_schema(args, schema_path, args.supervisor_log)
        print(f"  {status} after {elapsed / 60:.2f} min", flush=True)

        if status.startswith("timeout") or terminated_by_signal(status):
            mark_timeout_profile_rows(args.profile_csv, schema_path, args.framework, elapsed)
            timeout_stage = status.removeprefix("timeout_") if status != "timeout" else "unknown"
            if terminated_by_signal(status):
                timeout_stage = f"terminated_signal_{status.removeprefix('exit_-')}"
            checkpoint_path = args.timeout_log.with_name("timeout_checkpoints.jsonl")
            checkpoint_stage = load_timeout_checkpoint_stage(checkpoint_path, schema_path.name, args.framework)
            if checkpoint_stage:
                timeout_stage = checkpoint_stage
            if args.framework == "outlines":
                mark_timeout_schema_compile_profile(
                    args.profile_csv.with_name("schema_compile_profile.csv"),
                    schema_path,
                    args.framework,
                    elapsed,
                    timeout_stage,
                )
                upsert_timeout_record(
                    checkpoint_path,
                    {
                        "schema_id": schema_path.name,
                        "dataset_id": schema_path.name.split("---", 1)[0] if "---" in schema_path.name else "",
                        "schema_path": rel(schema_path),
                        "framework_id": args.framework,
                        "last_stage": timeout_stage,
                        "final_status": "timeout",
                        "elapsed_seconds": round(elapsed, 3),
                        "timeout_seconds": round(elapsed, 3),
                        "exception_type": "TimeoutError",
                        "exception_message": f"supervisor_timeout_after_seconds={elapsed:.3f}",
                    },
                )
            upsert_timeout_record(
                args.timeout_log,
                {
                    "schema_id": schema_path.name,
                    "schema_path": rel(schema_path),
                    "framework_id": args.framework,
                    "timeout_minutes": args.timeout_minutes,
                    "compile_timeout_minutes": args.compile_timeout_minutes,
                    "validation_timeout_minutes": args.validation_timeout_minutes,
                    "elapsed_seconds": round(elapsed, 3),
                    "timeout_stage": timeout_stage,
                    "notes": "Schema run exceeded per-schema timeout or was terminated during timing-profile replay.",
                },
            )
        elif status.startswith("exit_"):
            raise SystemExit(f"Stopping after {schema_path.name} returned {status}. See {rel(args.supervisor_log)}.")

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
