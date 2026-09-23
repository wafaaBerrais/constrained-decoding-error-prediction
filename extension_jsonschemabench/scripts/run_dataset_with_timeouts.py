#!/usr/bin/env python3
"""Run per-test logging one schema at a time with a per-schema timeout.

This supervisor is slower than a single long runner process because it starts a
new Python process per schema. The benefit is robustness on Windows: if one
schema gets stuck in a framework implementation, the child process can be
terminated and the next schema can continue.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[2]
EXT_ROOT = ROOT / "extension_jsonschemabench"
DEFAULT_OUTPUT_DIR = EXT_ROOT / "results" / "per_dataset_runs"
RUNNER = EXT_ROOT / "scripts" / "run_per_test_framework_logging.py"
FRAMEWORK_NAMES = {
    "guidance": "LLGuidance",
    "llg": "LLGuidance",
    "xgr": "XGrammar",
    "xgr-compliant": "XGrammar (compliant)",
    "xgr-cpp": "XGrammar.cpp",
    "llamacpp": "llama.cpp",
    "outlines": "Outlines",
}
FRAMEWORK_RESULT_IDS = {
    "guidance": {"guidance", "llg", "LLGuidance"},
}


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def dataset_id_from_schema_id(schema_id: str) -> str:
    if "---" in schema_id:
        return schema_id.split("---", 1)[0]
    stem = Path(schema_id).stem
    return re.sub(r"_\d+$", "", stem)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def output_path(output_dir: Path, framework: str, dataset_id: str) -> Path:
    return output_dir / framework / dataset_id / "per_test_results.jsonl"


def timeout_path(output_dir: Path, framework: str, dataset_id: str) -> Path:
    return output_dir / framework / dataset_id / "timed_out_schemas.jsonl"


def schema_compile_profile_path(output_dir: Path, framework: str, dataset_id: str) -> Path:
    return output_dir / framework / dataset_id / "schema_compile_profile.csv"


def timeout_checkpoints_path(output_dir: Path, framework: str, dataset_id: str) -> Path:
    return output_dir / framework / dataset_id / "timeout_checkpoints.jsonl"


PROFILE_COLUMNS = [
    "schema_id",
    "dataset_id",
    "schema_path",
    "test_id",
    "test_index",
    "expected_validity",
    "framework_id",
    "framework",
    "actual_result",
    "accepted",
    "result_available",
    "schema_file_bytes",
    "schema_json_chars",
    "instance_json_chars",
    "engine_tokenizer_load_us",
    "engine_init_us",
    "schema_load_us",
    "compile_grammar_us",
    "test_json_dumps_us",
    "tokenize_us",
    "reset_matcher_us",
    "validation_loop_us",
    "compute_mask_us",
    "commit_token_us",
    "max_compute_mask_us",
    "max_commit_token_us",
    "num_tokens",
    "tokens_checked",
    "first_rejected_token_index",
    "error_message",
    "outlines_core_version",
    "schema_serialize_us",
    "regex_build_us",
    "regex_built",
    "regex_chars",
    "regex_bytes",
    "regex_hash",
    "regex_expansion_ratio",
    "regex_num_alternations_proxy",
    "regex_num_groups_proxy",
    "regex_num_repetitions_proxy",
    "regex_max_group_depth_proxy",
    "index_build_us",
    "index_built",
    "guide_init_us",
    "guide_built",
    "total_compile_us",
    "final_status",
    "last_stage",
    "exception_type",
    "exception_message",
]

SCHEMA_COMPILE_PROFILE_COLUMNS = [
    "dataset_id",
    "schema_id",
    "framework_id",
    "framework",
    "schema_path",
    "outlines_core_version",
    "schema_file_bytes",
    "schema_json_chars",
    "schema_load_s",
    "schema_serialize_s",
    "regex_build_s",
    "regex_built",
    "regex_chars",
    "regex_bytes",
    "regex_hash",
    "regex_expansion_ratio",
    "regex_num_alternations_proxy",
    "regex_num_groups_proxy",
    "regex_num_repetitions_proxy",
    "regex_max_group_depth_proxy",
    "index_build_s",
    "index_built",
    "guide_init_s",
    "guide_built",
    "total_compile_s",
    "final_status",
    "last_stage",
    "exception_type",
    "exception_message",
    "timeout_seconds",
]


def load_completed_tests(path: Path, framework: str) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    framework_ids = FRAMEWORK_RESULT_IDS.get(framework, {framework})
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            schema_id = str(record.get("schema_id") or "")
            test_id = str(record.get("test_id") or "")
            framework_id = str(record.get("framework_id") or "")
            framework_name = str(record.get("framework") or "")
            if schema_id and test_id and (framework_id in framework_ids or framework_name in framework_ids):
                completed.add((schema_id, test_id))
    return completed


def discover_resume_paths(output_dir: Path, framework: str, include_global: bool = True) -> list[Path]:
    """Find existing JSONL outputs that can be used for resume decisions."""
    paths = set(output_dir.glob(f"{framework}/*/per_test_results.jsonl"))
    if include_global:
        paths.update(EXT_ROOT.glob("results/per_test_results*.jsonl"))
    return sorted(path for path in paths if path.exists())


def load_completed_tests_from_paths(paths: list[Path], framework: str) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    for path in paths:
        completed.update(load_completed_tests(path, framework))
    return completed


def load_timed_out_schemas(path: Path) -> set[str]:
    timed_out: set[str] = set()
    if not path.exists():
        return timed_out
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("schema_id"):
                timed_out.add(str(record["schema_id"]))
    return timed_out


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def mark_timeout_result_rows(output_path: Path, schema_path: Path, framework: str, elapsed: float) -> None:
    framework_ids = FRAMEWORK_RESULT_IDS.get(framework, {framework})
    existing_rows: list[dict[str, Any]] = []
    existing_keys: set[tuple[str, str]] = set()

    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                existing_rows.append(record)
                framework_id = str(record.get("framework_id") or "")
                framework_name = str(record.get("framework") or "")
                if framework_id in framework_ids or framework_name in framework_ids:
                    schema_id = str(record.get("schema_id") or "")
                    test_id = str(record.get("test_id") or "")
                    if schema_id and test_id:
                        existing_keys.add((schema_id, test_id))

    rows_to_add = []
    for row in make_timeout_profile_rows(schema_path, framework, elapsed):
        key = (str(row.get("schema_id") or ""), str(row.get("test_id") or ""))
        if key in existing_keys:
            continue
        rows_to_add.append(
            {
                "schema_id": row["schema_id"],
                "dataset_id": row["dataset_id"],
                "schema_path": row["schema_path"],
                "test_id": row["test_id"],
                "test_index": row["test_index"],
                "test_path": f"{row['schema_path']}#/tests/{row['test_index']}",
                "expected_validity": row["expected_validity"],
                "framework_id": row["framework_id"],
                "framework": row["framework"],
                "actual_result": "timeout",
                "accepted": None,
                "result_available": False,
                "error_message": row["error_message"],
                "notes": "Schema run exceeded per-schema timeout before this test produced a result.",
            }
        )

    if not rows_to_add:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_name(
        f".{output_path.name}.{schema_path.stem}.{os.getpid()}.{time.time_ns()}.timeout.tmp"
    )
    with tmp_path.open("w", encoding="utf-8") as handle:
        for row in [*existing_rows, *rows_to_add]:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp_path.replace(output_path)


def upsert_timeout_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(existing, dict):
                    continue
                if existing.get("schema_id") != record.get("schema_id"):
                    rows.append(existing)
    rows.append(record)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def expected_validity(test: Any) -> str:
    if isinstance(test, dict) and test.get("valid") is True:
        return "valid"
    if isinstance(test, dict) and test.get("valid") is False:
        return "invalid"
    return "unknown"


def make_timeout_profile_rows(schema_path: Path, framework: str, elapsed: float) -> list[dict[str, Any]]:
    payload = load_json(schema_path)
    tests = payload.get("tests", []) if isinstance(payload, dict) else []
    if not isinstance(tests, list):
        tests = []
    schema = payload.get("schema", {}) if isinstance(payload, dict) else {}
    schema_json_chars = len(json.dumps(schema, ensure_ascii=False))
    rows: list[dict[str, Any]] = []
    for test_index, test in enumerate(tests):
        row = {key: "" for key in PROFILE_COLUMNS}
        row.update(
            {
                "schema_id": schema_path.name,
                "dataset_id": dataset_id_from_schema_id(schema_path.name),
                "schema_path": rel(schema_path),
                "test_id": f"{schema_path.name}::test_{test_index:05d}",
                "test_index": test_index,
                "expected_validity": expected_validity(test),
                "framework_id": framework,
                "framework": FRAMEWORK_NAMES.get(framework, ""),
                "actual_result": "timeout",
                "accepted": "",
                "result_available": False,
                "schema_file_bytes": schema_path.stat().st_size,
                "schema_json_chars": schema_json_chars,
                "error_message": f"supervisor_timeout_after_seconds={elapsed:.3f}",
            }
        )
        rows.append(row)
    return rows


def mark_timeout_profile_rows(profile_path: Path, schema_path: Path, framework: str, elapsed: float) -> None:
    rows: list[dict[str, Any]] = []
    changed = False
    seen_target = False
    if profile_path.exists() and profile_path.stat().st_size > 0:
        with profile_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {key: row.get(key, "") for key in PROFILE_COLUMNS}
                is_target = normalized.get("schema_id") == schema_path.name and normalized.get("framework_id") == framework
                if is_target:
                    seen_target = True
                is_final = str(normalized.get("result_available")).lower() == "true"
                if is_target and not is_final:
                    previous_error = str(normalized.get("error_message") or "").strip()
                    timeout_note = f"supervisor_timeout_after_seconds={elapsed:.3f}"
                    normalized["actual_result"] = "timeout"
                    normalized["accepted"] = ""
                    normalized["result_available"] = False
                    normalized["error_message"] = f"{previous_error} {timeout_note}".strip()
                    changed = True
                rows.append(normalized)

    if not seen_target:
        fallback_rows = make_timeout_profile_rows(schema_path, framework, elapsed)
        if fallback_rows:
            rows.extend(fallback_rows)
            changed = True

    if not changed:
        return

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = profile_path.with_name(
        f".{profile_path.name}.{schema_path.stem}.{os.getpid()}.{time.time_ns()}.timeout.tmp"
    )
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(profile_path)


def load_timeout_checkpoint_stage(path: Path, schema_id: str, framework: str) -> str:
    if not path.exists():
        return ""
    latest_stage = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            if record.get("schema_id") == schema_id and record.get("framework_id") == framework:
                latest_stage = str(record.get("last_stage") or "")
    return latest_stage


def mark_timeout_schema_compile_profile(
    profile_path: Path,
    schema_path: Path,
    framework: str,
    elapsed: float,
    last_stage: str,
) -> None:
    rows: list[dict[str, Any]] = []
    changed = False
    if profile_path.exists() and profile_path.stat().st_size > 0:
        with profile_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = {key: row.get(key, "") for key in SCHEMA_COMPILE_PROFILE_COLUMNS}
                is_target = normalized.get("schema_id") == schema_path.name and normalized.get("framework_id") == framework
                if is_target and normalized.get("final_status") != "completed":
                    normalized["final_status"] = "timeout"
                    normalized["last_stage"] = last_stage or normalized.get("last_stage") or "unknown"
                    normalized["timeout_seconds"] = f"{elapsed:.3f}"
                    normalized["exception_type"] = normalized.get("exception_type") or "TimeoutError"
                    normalized["exception_message"] = (
                        normalized.get("exception_message") or f"supervisor_timeout_after_seconds={elapsed:.3f}"
                    )
                    changed = True
                rows.append(normalized)

    if not changed:
        rows.append(
            {
                key: ""
                for key in SCHEMA_COMPILE_PROFILE_COLUMNS
            }
        )
        rows[-1].update(
            {
                "dataset_id": dataset_id_from_schema_id(schema_path.name),
                "schema_id": schema_path.name,
                "framework_id": framework,
                "framework": FRAMEWORK_NAMES.get(framework, ""),
                "schema_path": rel(schema_path),
                "final_status": "timeout",
                "last_stage": last_stage or "unknown",
                "timeout_seconds": f"{elapsed:.3f}",
                "exception_type": "TimeoutError",
                "exception_message": f"supervisor_timeout_after_seconds={elapsed:.3f}",
            }
        )

    profile_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = profile_path.with_name(
        f".{profile_path.name}.{schema_path.stem}.{os.getpid()}.{time.time_ns()}.timeout.tmp"
    )
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCHEMA_COMPILE_PROFILE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(profile_path)


def test_ids_for_schema(schema_path: Path) -> set[tuple[str, str]]:
    schema_id = schema_path.name
    payload = load_json(schema_path)
    tests = payload.get("tests", []) if isinstance(payload, dict) else []
    if not isinstance(tests, list):
        tests = []
    return {(schema_id, f"{schema_id}::test_{index:05d}") for index, _ in enumerate(tests)}


def discover_files(input_path: Path, datasets: set[str] | None) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix in {".lst", ".txt"}:
            files = []
            with input_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw_path = line.strip()
                    if not raw_path or raw_path.startswith("#"):
                        continue
                    path = Path(raw_path)
                    if not path.is_absolute():
                        path = ROOT / path
                    files.append(path)
        else:
            files = [input_path]
    else:
        files = sorted(input_path.glob("*.json"), key=lambda path: path.name)
    if datasets:
        files = [path for path in files if dataset_id_from_schema_id(path.name) in datasets]
    return files


def terminate_process(process: subprocess.Popen[str]) -> None:
    try:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def detect_stage(log_path: Path, start_offset: int) -> str:
    if not log_path.exists():
        return "compile_grammar"
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(start_offset)
            text = handle.read()
    except OSError:
        return "compile_grammar"
    markers = [
        ("loading_schema", "  outlines:loading_schema:start "),
        ("serializing_schema", "  outlines:serializing_schema:start "),
        ("building_regex", "  outlines:building_regex:start "),
        ("regex_built", "  outlines:building_regex:end "),
        ("building_index", "  outlines:building_index:start "),
        ("index_built", "  outlines:building_index:end "),
        ("initializing_guide", "  outlines:initializing_guide:start "),
        ("guide_built", "  outlines:initializing_guide:end "),
        ("after_compile", "  compile_grammar:end "),
        ("validation", "  test:start "),
        ("validation", "    prepared test="),
        ("validation", "  test:end "),
    ]
    latest_pos = -1
    latest_stage = "compile_grammar"
    for stage, marker in markers:
        pos = text.rfind(marker)
        if pos > latest_pos:
            latest_pos = pos
            latest_stage = stage
    return latest_stage


def timeout_status_for_stage(stage: str) -> str:
    if stage in {
        "loading_schema",
        "serializing_schema",
        "building_regex",
        "regex_built",
        "building_index",
        "index_built",
        "initializing_guide",
        "guide_built",
    }:
        return f"timeout_{stage}"
    if stage == "compile_grammar":
        return "timeout_compile_grammar"
    if stage in {"after_compile", "validation"}:
        return "timeout_validation"
    return "timeout"


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
        "--output-dir",
        args.output_dir,
        "--split-by-dataset",
        str(schema_path),
    ]
    if args.tokenizer:
        cmd.extend(["--tokenizer", args.tokenizer])
    if args.profile_timings:
        cmd.append("--profile-timings")
        cmd.extend(["--profile-checkpoint-interval-seconds", str(args.profile_checkpoint_interval_seconds)])
    if args.trace_stages:
        cmd.append("--trace-stages")

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
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log,
            stderr=log,
            text=True,
        )
        while process.poll() is None:
            now = time.monotonic()
            if args.compile_timeout_minutes is not None or args.validation_timeout_minutes is not None:
                detected_stage = detect_stage(log_path, log_start_offset)
                if detected_stage != stage:
                    stage = detected_stage
                    if stage in {"after_compile", "validation"}:
                        deadline = started + validation_timeout * 60
            if now >= deadline:
                terminate_process(process)
                return timeout_status_for_stage(stage), time.monotonic() - started
            if now >= next_progress:
                print(f"  still running after {(now - started) / 60:.2f} min stage={stage}")
                next_progress = now + progress_interval
            time.sleep(min(5, max(deadline - now, 0.1)))

        if process.returncode == 0:
            return "ok", time.monotonic() - started
        return f"exit_{process.returncode}", time.monotonic() - started


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dataset schemas with per-schema timeouts.")
    parser.add_argument("input", help="MaskBench data directory or one schema JSON file.")
    parser.add_argument("--framework", required=True, help="Framework id, for example xgr.")
    parser.add_argument("--dataset", action="append", default=None, help="Dataset id to run. Can be repeated.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Base split output directory.")
    parser.add_argument("--timeout-minutes", type=float, default=30.0, help="Timeout per schema.")
    parser.add_argument("--compile-timeout-minutes", type=float, default=None, help="Timeout while schema compilation is still running.")
    parser.add_argument("--validation-timeout-minutes", type=float, default=None, help="Total timeout after schema compilation has finished.")
    parser.add_argument("--progress-interval-minutes", type=float, default=1.0, help="Print elapsed time for a running schema at this interval.")
    parser.add_argument("--retry-timeouts", action="store_true", help="Retry schemas already listed in timed_out_schemas.jsonl.")
    parser.add_argument(
        "--ignore-global-resume",
        action="store_true",
        help="Only resume from split outputs under --output-dir, ignoring legacy extension_jsonschemabench/results/per_test_results*.jsonl files.",
    )
    parser.add_argument("--continue-on-error", action="store_true", help="Continue after a child runner exits with a non-zero status.")
    parser.add_argument("--start-at-schema", default=None, help="Resume consideration at this schema file name.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of schema files to consider.")
    parser.add_argument("--tokenizer", default="unsloth/Meta-Llama-3.1-8B-Instruct", help="Tokenizer model ID.")
    parser.add_argument("--profile-timings", action="store_true", help="Write per-test timing_profile.csv files from child runners.")
    parser.add_argument("--profile-checkpoint-interval-seconds", type=float, default=30.0, help="Refresh incomplete timing_profile.csv rows at this interval during long validation loops.")
    parser.add_argument("--trace-stages", action="store_true", help="Ask child runners to log coarse function-stage timings.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    datasets = set(args.dataset) if args.dataset else None
    files = discover_files(input_path, datasets)
    if args.start_at_schema:
        try:
            start_index = next(index for index, path in enumerate(files) if path.name == args.start_at_schema)
        except StopIteration:
            raise SystemExit(f"Start schema not found in selected files: {args.start_at_schema}") from None
        files = files[start_index:]
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No schema files selected.")

    print(f"Selected schema files: {len(files)}")
    print(f"Timeout per schema: {args.timeout_minutes} minutes")
    print(f"Progress interval: {args.progress_interval_minutes} minutes")

    resume_paths = discover_resume_paths(output_dir, args.framework, include_global=not args.ignore_global_resume)
    global_completed_tests = load_completed_tests_from_paths(resume_paths, args.framework)
    if resume_paths:
        print(f"Loaded {len(global_completed_tests)} completed test ids from {len(resume_paths)} existing JSONL file(s).")

    for index, schema_path in enumerate(files, start=1):
        dataset_id = dataset_id_from_schema_id(schema_path.name)
        out_path = output_path(output_dir, args.framework, dataset_id)
        timeout_log_path = timeout_path(output_dir, args.framework, dataset_id)
        combined_log_path = output_dir / args.framework / dataset_id / "supervisor.log"

        expected_tests = test_ids_for_schema(schema_path)
        if not expected_tests:
            print(f"[{index}/{len(files)}] {dataset_id} {schema_path.name}: skipped no tests")
            continue
        completed_tests_before = global_completed_tests | load_completed_tests(out_path, args.framework)
        if expected_tests and expected_tests.issubset(completed_tests_before):
            print(f"[{index}/{len(files)}] {dataset_id} {schema_path.name}: already complete")
            continue

        timed_out = load_timed_out_schemas(timeout_log_path)
        timed_out_before = schema_path.name in timed_out
        if timed_out_before and not args.retry_timeouts:
            print(f"[{index}/{len(files)}] {dataset_id} {schema_path.name}: skipped previous timeout")
            continue

        print(f"[{index}/{len(files)}] {dataset_id} {schema_path.name}: running")
        status, elapsed = run_schema(args, schema_path, combined_log_path)
        print(f"  {status} after {elapsed / 60:.2f} min")
        if status.startswith("exit_") and not terminated_by_signal(status) and not args.continue_on_error:
            raise SystemExit(
                f"Stopping after {schema_path.name} returned {status}. "
                f"See {rel(combined_log_path)} for the traceback. "
                "Use --continue-on-error to keep going anyway."
            )

        if status.startswith("timeout") or terminated_by_signal(status):
            mark_timeout_result_rows(out_path, schema_path, args.framework, elapsed)
            if args.profile_timings:
                mark_timeout_profile_rows(out_path.with_name("timing_profile.csv"), schema_path, args.framework, elapsed)
            timeout_stage = status.removeprefix("timeout_") if status != "timeout" else "unknown"
            if terminated_by_signal(status):
                timeout_stage = f"terminated_signal_{status.removeprefix('exit_-')}"
            checkpoint_path = timeout_checkpoints_path(output_dir, args.framework, dataset_id)
            checkpoint_stage = load_timeout_checkpoint_stage(checkpoint_path, schema_path.name, args.framework)
            if checkpoint_stage:
                timeout_stage = checkpoint_stage
            if args.profile_timings and args.framework == "outlines":
                mark_timeout_schema_compile_profile(
                    schema_compile_profile_path(output_dir, args.framework, dataset_id),
                    schema_path,
                    args.framework,
                    elapsed,
                    timeout_stage,
                )
                upsert_timeout_record(
                    checkpoint_path,
                    {
                        "schema_id": schema_path.name,
                        "dataset_id": dataset_id,
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
                timeout_log_path,
                {
                    "schema_id": schema_path.name,
                    "dataset_id": dataset_id,
                    "schema_path": rel(schema_path),
                    "framework_id": args.framework,
                    "timeout_minutes": args.timeout_minutes,
                    "compile_timeout_minutes": args.compile_timeout_minutes,
                    "validation_timeout_minutes": args.validation_timeout_minutes,
                    "elapsed_seconds": round(elapsed, 3),
                    "timeout_stage": timeout_stage,
                    "notes": "Schema run exceeded per-schema timeout and was skipped by supervisor.",
                },
            )

    print(f"Done. Split results are under {rel(output_dir / args.framework)}")


if __name__ == "__main__":
    main()
