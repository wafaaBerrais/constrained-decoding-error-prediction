#!/usr/bin/env python3
"""Run a MaskBench framework and log one JSONL record per test.

This script lives outside the original benchmark code. It reuses the public
engine interface from MaskBench, but writes extension-owned per-test logs that
can later be consumed by `build_schema_test_framework_index.py`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any


csv.field_size_limit(1024 * 1024 * 1024)

ROOT = Path(__file__).resolve().parents[2]
EXT_ROOT = ROOT / "extension_jsonschemabench"
DEFAULT_OUTPUT = EXT_ROOT / "results" / "per_test_results.jsonl"
DEFAULT_OUTPUT_DIR = EXT_ROOT / "results" / "per_dataset_runs"
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

# Make `from maskbench.runner import ...` resolve to maskbench/maskbench.
sys.path.insert(0, str(ROOT / "maskbench"))


FRAMEWORK_FLAGS = {
    "guidance": "--llg",
    "llg": "--llg",
    "xgr": "--xgr",
    "xgr-compliant": "--xgr-compliant",
    "xgr-cpp": "--xgr-cpp",
    "llamacpp": "--llamacpp",
    "outlines": "--outlines",
}


def time_us(prev: float) -> int:
    return int((time.monotonic() - prev) * 1000000)


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_input_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if raw_path.endswith(".json"):
            files.append(path)
        else:
            files.extend(sorted(path.glob("*.json")))
    return files


def dataset_id_from_schema_id(schema_id: str) -> str:
    if "---" in schema_id:
        return schema_id.split("---", 1)[0]
    stem = Path(schema_id).stem
    return re.sub(r"_\d+$", "", stem)


def dataset_id_from_path(path: Path) -> str:
    return dataset_id_from_schema_id(path.name)


def output_path_for_dataset(args: argparse.Namespace, engine: Any, schema_path: Path) -> Path:
    if not args.split_by_dataset:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        return output

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    return output_dir / args.framework / dataset_id_from_path(schema_path) / "per_test_results.jsonl"


def profile_path_for_output(args: argparse.Namespace, output: Path) -> Path | None:
    if args.profile_csv:
        profile_csv = Path(args.profile_csv)
        if not profile_csv.is_absolute():
            profile_csv = ROOT / profile_csv
        return profile_csv
    if args.profile_timings:
        return output.with_name("timing_profile.csv")
    return None


def schema_compile_profile_path_for_output(
    args: argparse.Namespace,
    output: Path,
    profile_output: Path | None,
) -> Path | None:
    if args.schema_compile_profile_csv:
        path = Path(args.schema_compile_profile_csv)
        if not path.is_absolute():
            path = ROOT / path
        return path
    if args.framework == "outlines" and (args.profile_timings or args.profile_csv):
        base = profile_output if profile_output is not None else output
        return base.with_name("schema_compile_profile.csv")
    return None


def timeout_checkpoint_path_for_output(
    args: argparse.Namespace,
    output: Path,
    schema_compile_profile_output: Path | None,
) -> Path | None:
    if args.timeout_checkpoints:
        path = Path(args.timeout_checkpoints)
        if not path.is_absolute():
            path = ROOT / path
        return path
    if args.framework == "outlines" and schema_compile_profile_output is not None:
        return schema_compile_profile_output.with_name("timeout_checkpoints.jsonl")
    return None


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def upsert_jsonl(path: Path, record: dict[str, Any], key_fields: tuple[str, ...]) -> None:
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
                same_key = all(existing.get(field) == record.get(field) for field in key_fields)
                if not same_key:
                    rows.append(existing)
    rows.append(record)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp_path.replace(path)


def write_csv_row_upsert(path: Path | None, columns: list[str], row: dict[str, Any], key_fields: tuple[str, ...]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {key: row.get(key, "") for key in columns}

    rows: list[dict[str, Any]] = []
    replaced = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for existing in reader:
                same_key = all(existing.get(field) == str(normalized.get(field, "")) for field in key_fields)
                if same_key:
                    rows.append(normalized)
                    replaced = True
                else:
                    rows.append({key: existing.get(key, "") for key in columns})
    if not replaced:
        rows.append(normalized)

    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def write_profile_row(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {key: row.get(key, "") for key in PROFILE_COLUMNS}
    if not row.get("schema_id") or not row.get("test_id") or not row.get("framework_id"):
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        return

    rows: list[dict[str, Any]] = []
    replaced = False
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for existing in reader:
                same_test = (
                    existing.get("schema_id") == row["schema_id"]
                    and existing.get("test_id") == row["test_id"]
                    and existing.get("framework_id") == row["framework_id"]
                )
                if same_test:
                    rows.append(row)
                    replaced = True
                else:
                    rows.append({key: existing.get(key, "") for key in PROFILE_COLUMNS})
    if not replaced:
        rows.append(row)

    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)


def write_schema_compile_profile_row(path: Path | None, row: dict[str, Any]) -> None:
    write_csv_row_upsert(
        path,
        SCHEMA_COMPILE_PROFILE_COLUMNS,
        row,
        key_fields=("schema_id", "framework_id"),
    )


def write_timeout_checkpoint(path: Path | None, record: dict[str, Any]) -> None:
    if path is None:
        return
    upsert_jsonl(path, record, key_fields=("schema_id", "framework_id"))


def trace(args: argparse.Namespace, message: str) -> None:
    if args.trace_stages:
        print(message, file=sys.stderr, flush=True)


def package_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return ""


def seconds_from_us(value: Any) -> Any:
    if value in {"", None}:
        return ""
    return round(float(value) / 1_000_000, 9)


def regex_syntax_proxies(regex: str) -> dict[str, int]:
    alternations = 0
    groups = 0
    repetitions = 0
    depth = 0
    max_depth = 0
    escaped = False
    in_char_class = False

    for char in regex:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "[" and not in_char_class:
            in_char_class = True
            continue
        if char == "]" and in_char_class:
            in_char_class = False
            continue
        if in_char_class:
            continue
        if char == "|":
            alternations += 1
        elif char == "(":
            groups += 1
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")" and depth > 0:
            depth -= 1
        elif char in "*+?{":
            repetitions += 1

    return {
        "regex_num_alternations_proxy": alternations,
        "regex_num_groups_proxy": groups,
        "regex_num_repetitions_proxy": repetitions,
        "regex_max_group_depth_proxy": max_depth,
    }


def compile_schema_profile_row_from_timings(timings: dict[str, Any]) -> dict[str, Any]:
    return {
        **timings,
        "schema_load_s": seconds_from_us(timings.get("schema_load_us")),
        "schema_serialize_s": seconds_from_us(timings.get("schema_serialize_us")),
        "regex_build_s": seconds_from_us(timings.get("regex_build_us")),
        "index_build_s": seconds_from_us(timings.get("index_build_us")),
        "guide_init_s": seconds_from_us(timings.get("guide_init_us")),
        "total_compile_s": seconds_from_us(timings.get("total_compile_us")),
    }


def compile_outlines_with_profile(
    args: argparse.Namespace,
    engine: Any,
    schema_path: Path,
    schema: dict[str, Any],
    schema_timings: dict[str, Any],
    schema_compile_profile_output: Path | None,
    timeout_checkpoint_output: Path | None,
) -> dict[str, Any]:
    from outlines_core import Guide, Index  # noqa: WPS433
    from outlines_core.json_schema import build_regex_from_schema  # noqa: WPS433

    schema_id = schema_path.name
    dataset_id = dataset_id_from_schema_id(schema_id)
    started = time.monotonic()
    profile: dict[str, Any] = {
        "schema_id": schema_id,
        "dataset_id": dataset_id,
        "schema_path": rel(schema_path),
        "framework_id": engine.get_id(),
        "framework": engine.get_name(),
        "outlines_core_version": package_version("outlines_core"),
        "schema_file_bytes": schema_timings.get("schema_file_bytes", ""),
        "schema_load_us": schema_timings.get("schema_load_us", ""),
        "schema_load_s": seconds_from_us(schema_timings.get("schema_load_us")),
        "regex_built": False,
        "index_built": False,
        "guide_built": False,
        "final_status": "running",
        "last_stage": "serializing_schema",
    }

    def update(stage: str, status: str = "running") -> None:
        profile["last_stage"] = stage
        profile["final_status"] = status
        engine._extension_compile_timings = dict(profile)
        checkpoint = {
            "schema_id": schema_id,
            "dataset_id": dataset_id,
            "schema_path": rel(schema_path),
            "framework_id": engine.get_id(),
            "framework": engine.get_name(),
            "last_stage": stage,
            "final_status": status,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "outlines_core_version": profile.get("outlines_core_version", ""),
            "exception_type": profile.get("exception_type", ""),
            "exception_message": profile.get("exception_message", ""),
        }
        write_schema_compile_profile_row(
            schema_compile_profile_output,
            compile_schema_profile_row_from_timings(profile),
        )
        write_timeout_checkpoint(timeout_checkpoint_output, checkpoint)

    try:
        trace(args, f"  outlines:serializing_schema:start schema={schema_id}")
        update("serializing_schema")
        serialize_t0 = time.monotonic()
        schema_json = json.dumps(schema)
        profile["schema_serialize_us"] = time_us(serialize_t0)
        profile["schema_json_chars"] = len(schema_json)
        trace(
            args,
            f"  outlines:serializing_schema:end schema={schema_id} schema_serialize_us={profile['schema_serialize_us']}",
        )

        trace(args, f"  outlines:building_regex:start schema={schema_id}")
        update("building_regex")
        regex_t0 = time.monotonic()
        regex = build_regex_from_schema(schema_json)
        profile["regex_build_us"] = time_us(regex_t0)
        regex_bytes = regex.encode("utf-8")
        profile.update(
            {
                "regex_built": True,
                "regex_chars": len(regex),
                "regex_bytes": len(regex_bytes),
                "regex_hash": hashlib.sha256(regex_bytes).hexdigest(),
                "regex_expansion_ratio": round(len(regex) / len(schema_json), 9) if schema_json else "",
                **regex_syntax_proxies(regex),
            }
        )
        trace(
            args,
            f"  outlines:building_regex:end schema={schema_id} regex_build_us={profile['regex_build_us']} "
            f"regex_chars={profile['regex_chars']}",
        )

        trace(args, f"  outlines:building_index:start schema={schema_id}")
        update("building_index")
        index_t0 = time.monotonic()
        engine.index = Index(regex, engine.vocabulary)
        profile["index_build_us"] = time_us(index_t0)
        profile["index_built"] = True
        trace(args, f"  outlines:building_index:end schema={schema_id} index_build_us={profile['index_build_us']}")

        trace(args, f"  outlines:initializing_guide:start schema={schema_id}")
        update("initializing_guide")
        guide_t0 = time.monotonic()
        engine.guide = Guide(engine.index)
        profile["guide_init_us"] = time_us(guide_t0)
        profile["guide_built"] = True
        profile["total_compile_us"] = time_us(started)
        update("completed", "completed")
        trace(args, f"  outlines:initializing_guide:end schema={schema_id} guide_init_us={profile['guide_init_us']}")
        return dict(profile)
    except Exception as exc:
        profile["total_compile_us"] = time_us(started)
        profile["exception_type"] = type(exc).__name__
        profile["exception_message"] = str(exc)
        update(str(profile.get("last_stage") or "unknown"), "compile_error")
        raise


def load_existing_result_keys(path: Path) -> set[tuple[str, str, str]]:
    """Return schema/test/framework keys already present in a JSONL output."""
    keys: set[tuple[str, str, str]] = set()
    if not path.exists():
        return keys

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
            framework = str(record.get("framework") or "")
            if schema_id and test_id and framework_id:
                keys.add((schema_id, test_id, framework_id))
            if schema_id and test_id and framework:
                keys.add((schema_id, test_id, framework))
    return keys


def expected_validity(test: Any) -> str:
    if isinstance(test, dict) and test.get("valid") is True:
        return "valid"
    if isinstance(test, dict) and test.get("valid") is False:
        return "invalid"
    return "unknown"


def result_from_acceptance(expected: str, accepted: bool) -> str:
    if expected == "valid":
        return "passed" if accepted else "failed"
    if expected == "invalid":
        return "passed" if not accepted else "failed"
    return "unknown"


def make_base_record(args: argparse.Namespace, engine: Any, schema_path: Path, test_index: int, test: Any) -> dict[str, Any]:
    schema_id = schema_path.name
    dataset_id = dataset_id_from_schema_id(schema_id)
    return {
        "schema_id": schema_id,
        "dataset_id": dataset_id,
        "schema_path": rel(schema_path),
        "test_index": test_index,
        "test_id": f"{schema_id}::test_{test_index:05d}",
        "test_path": f"{rel(schema_path)}#/tests/{test_index}",
        "expected_validity": expected_validity(test),
        "framework_id": engine.get_id(),
        "framework": engine.get_name(),
        "runner_or_command": f"python {rel(Path(__file__))} {FRAMEWORK_FLAGS[args.framework]} <files>",
        "result_available": True,
    }


def emit_compile_error_rows(
    args: argparse.Namespace,
    engine: Any,
    output: Path,
    profile_output: Path | None,
    schema_path: Path,
    indexed_tests: list[tuple[int, Any]],
    error: BaseException,
    timings: dict[str, Any],
) -> None:
    for test_index, test in indexed_tests:
        record = make_base_record(args, engine, schema_path, test_index, test)
        record.update(
            {
                "actual_result": "compile_error",
                "accepted": None,
                "error_message": repr(error),
                "notes": "Framework failed while compiling the schema; no individual test was executed.",
            }
        )
        write_jsonl(output, record)
        write_profile_row(
            profile_output,
            {
                **record,
                **timings,
                "actual_result": "compile_error",
                "accepted": None,
                "result_available": True,
                "instance_json_chars": "",
                "test_json_dumps_us": "",
                "tokenize_us": "",
                "reset_matcher_us": "",
                "validation_loop_us": "",
                "compute_mask_us": "",
                "commit_token_us": "",
                "max_compute_mask_us": "",
                "max_commit_token_us": "",
                "num_tokens": "",
                "tokens_checked": "",
                "first_rejected_token_index": "",
                "error_message": repr(error),
            },
        )


def quotas_are_full(args: argparse.Namespace, counts: dict[str, int]) -> bool:
    if args.max_tests is not None and counts["total"] >= args.max_tests:
        return True
    valid_full = args.max_valid_tests is not None and counts["valid"] >= args.max_valid_tests
    invalid_full = args.max_invalid_tests is not None and counts["invalid"] >= args.max_invalid_tests
    if args.max_valid_tests is not None and args.max_invalid_tests is not None:
        return valid_full and invalid_full
    return False


def select_tests(
    args: argparse.Namespace,
    schema_path: Path,
    tests: list[Any],
    counts: dict[str, int],
    existing_keys: set[tuple[str, str, str]],
    framework_id: str,
    framework_name: str,
) -> list[tuple[int, Any]]:
    selected: list[tuple[int, Any]] = []
    schema_id = schema_path.name
    for test_index, test in enumerate(tests):
        if quotas_are_full(args, counts):
            break

        expected = expected_validity(test)
        test_id = f"{schema_id}::test_{test_index:05d}"
        if (schema_id, test_id, framework_id) in existing_keys or (schema_id, test_id, framework_name) in existing_keys:
            continue
        if args.max_tests is not None and counts["total"] >= args.max_tests:
            continue
        if expected == "valid" and args.max_valid_tests is not None and counts["valid"] >= args.max_valid_tests:
            continue
        if expected == "invalid" and args.max_invalid_tests is not None and counts["invalid"] >= args.max_invalid_tests:
            continue

        selected.append((test_index, test))
        counts["total"] += 1
        if expected in {"valid", "invalid"}:
            counts[expected] += 1
    return selected


def process_schema_file(
    args: argparse.Namespace,
    engine: Any,
    output: Path,
    profile_output: Path | None,
    schema_path: Path,
    counts: dict[str, int],
    existing_keys: set[tuple[str, str, str]],
) -> int:
    schema_compile_profile_output = schema_compile_profile_path_for_output(args, output, profile_output)
    timeout_checkpoint_output = timeout_checkpoint_path_for_output(args, output, schema_compile_profile_output)
    outlines_compile_timings: dict[str, Any] = {}

    if args.framework == "outlines" and schema_compile_profile_output is not None:
        loading_row = {
            "schema_id": schema_path.name,
            "dataset_id": dataset_id_from_schema_id(schema_path.name),
            "schema_path": rel(schema_path),
            "framework_id": engine.get_id(),
            "framework": engine.get_name(),
            "outlines_core_version": package_version("outlines_core"),
            "schema_file_bytes": schema_path.stat().st_size,
            "final_status": "running",
            "last_stage": "loading_schema",
        }
        trace(args, f"  outlines:loading_schema:start schema={schema_path.name}")
        write_schema_compile_profile_row(schema_compile_profile_output, loading_row)
        write_timeout_checkpoint(
            timeout_checkpoint_output,
            {
                **loading_row,
                "elapsed_seconds": 0.0,
            },
        )

    schema_load_t0 = time.monotonic()
    payload = load_json(schema_path)
    schema_load_us = time_us(schema_load_t0)
    if args.framework == "outlines" and schema_compile_profile_output is not None:
        trace(args, f"  outlines:loading_schema:end schema={schema_path.name} schema_load_us={schema_load_us}")

    tests = payload.get("tests", [])
    if not isinstance(tests, list):
        raise ValueError(f"{schema_path} has no list-valued tests field")

    indexed_tests = select_tests(args, schema_path, tests, counts, existing_keys, engine.get_id(), engine.get_name())
    if not indexed_tests:
        return 0

    schema_json_chars = len(json.dumps(payload.get("schema", {}), ensure_ascii=False))
    schema_timings = {
        "schema_file_bytes": schema_path.stat().st_size,
        "schema_json_chars": schema_json_chars,
        "engine_tokenizer_load_us": args.engine_tokenizer_load_us,
        "engine_init_us": args.engine_init_us,
        "schema_load_us": schema_load_us,
    }

    for test_index, test in indexed_tests:
        checkpoint = make_base_record(args, engine, schema_path, test_index, test)
        write_profile_row(
            profile_output,
            {
                **checkpoint,
                **schema_timings,
                "actual_result": "running_compile_grammar",
                "accepted": "",
                "result_available": False,
                "error_message": "stage=compile_grammar; partial checkpoint before grammar compilation.",
            },
        )

    try:
        trace(args, f"  compile_grammar:start schema={schema_path.name} selected_tests={len(indexed_tests)}")
        t0 = time.monotonic()
        if args.framework == "outlines" and schema_compile_profile_output is not None:
            outlines_compile_timings = compile_outlines_with_profile(
                args,
                engine,
                schema_path,
                payload["schema"],
                schema_timings,
                schema_compile_profile_output,
                timeout_checkpoint_output,
            )
            ttfm_us = int(outlines_compile_timings.get("total_compile_us") or time_us(t0))
        else:
            engine.compile_grammar(payload["schema"])
            ttfm_us = time_us(t0)
        trace(args, f"  compile_grammar:end schema={schema_path.name} compile_grammar_us={ttfm_us}")
    except Exception as exc:
        if args.debug:
            traceback.print_exc()
        trace(args, f"  compile_grammar:error schema={schema_path.name} error={exc!r}")
        outlines_compile_timings = getattr(engine, "_extension_compile_timings", outlines_compile_timings)
        emit_compile_error_rows(
            args,
            engine,
            output,
            profile_output,
            schema_path,
            indexed_tests,
            exc,
            {**schema_timings, "compile_grammar_us": time_us(t0), **outlines_compile_timings},
        )
        return len(indexed_tests)

    for test_index, test in indexed_tests:
        checkpoint = make_base_record(args, engine, schema_path, test_index, test)
        write_profile_row(
            profile_output,
            {
                **checkpoint,
                **schema_timings,
                **outlines_compile_timings,
                "compile_grammar_us": ttfm_us,
                "actual_result": "compiled",
                "accepted": "",
                "result_available": False,
                "error_message": "stage=compiled; waiting for test validation.",
            },
        )

    for test_index, test in indexed_tests:
        record = make_base_record(args, engine, schema_path, test_index, test)
        record["ttfm_us"] = ttfm_us
        profile_base = {
            **record,
            **schema_timings,
            **outlines_compile_timings,
            "compile_grammar_us": ttfm_us,
        }
        trace(args, f"  test:start schema={schema_path.name} test_index={test_index}")

        if not isinstance(test, dict) or "data" not in test:
            record.update(
                {
                    "actual_result": "unknown",
                    "accepted": None,
                    "error_message": "Test record is not an object with a data field.",
                    "notes": "Malformed test record.",
                }
            )
            write_jsonl(output, record)
            write_profile_row(
                profile_output,
                {
                    **profile_base,
                    "actual_result": "unknown",
                    "accepted": None,
                    "result_available": True,
                    "error_message": "Test record is not an object with a data field.",
                },
            )
            continue

        reset_t0 = time.monotonic()
        engine.reset()
        reset_matcher_us = time_us(reset_t0)

        dumps_t0 = time.monotonic()
        instance = json.dumps(test["data"], indent=None, ensure_ascii=False)
        test_json_dumps_us = time_us(dumps_t0)

        tokenize_t0 = time.monotonic()
        tokens = engine.tokenizer.encode(instance, add_special_tokens=False)
        tokenize_us = time_us(tokenize_t0)
        trace(
            args,
            f"    prepared test={test_index} reset_matcher_us={reset_matcher_us} "
            f"test_json_dumps_us={test_json_dumps_us} tokenize_us={tokenize_us} tokens={len(tokens)}",
        )

        write_profile_row(
            profile_output,
            {
                **profile_base,
                "actual_result": "running_validation",
                "accepted": "",
                "result_available": False,
                "instance_json_chars": len(instance),
                "test_json_dumps_us": test_json_dumps_us,
                "tokenize_us": tokenize_us,
                "reset_matcher_us": reset_matcher_us,
                "validation_loop_us": "",
                "compute_mask_us": 0,
                "commit_token_us": 0,
                "max_compute_mask_us": 0,
                "max_commit_token_us": 0,
                "num_tokens": len(tokens),
                "tokens_checked": 0,
                "first_rejected_token_index": "",
                "error_message": "stage=validation; partial checkpoint before token loop.",
            },
        )

        accepted = True
        compute_mask_us = 0
        commit_token_us = 0
        max_compute_mask_us = 0
        max_commit_token_us = 0
        tokens_checked = 0
        first_rejected_token_index = None
        error_message = ""

        try:
            validation_t0 = time.monotonic()
            next_checkpoint = validation_t0 + max(args.profile_checkpoint_interval_seconds, 1.0)
            for token_index, token in enumerate(tokens):
                mask_t0 = time.monotonic()
                engine.compute_mask()
                one_compute_mask_us = time_us(mask_t0)

                commit_t0 = time.monotonic()
                ok = engine.commit_token(token)
                one_commit_token_us = time_us(commit_t0)

                compute_mask_us += one_compute_mask_us
                commit_token_us += one_commit_token_us
                max_compute_mask_us = max(max_compute_mask_us, one_compute_mask_us)
                max_commit_token_us = max(max_commit_token_us, one_commit_token_us)
                tokens_checked += 1

                if args.debug:
                    decoded = engine.tokenizer.decode([token])
                    engine.log_single(f"{schema_path.name} test #{test_index} token {token_index} {decoded!r}: {ok}")

                now = time.monotonic()
                if now >= next_checkpoint:
                    write_profile_row(
                        profile_output,
                        {
                            **profile_base,
                            "actual_result": "running_validation",
                            "accepted": "",
                            "result_available": False,
                            "instance_json_chars": len(instance),
                            "test_json_dumps_us": test_json_dumps_us,
                            "tokenize_us": tokenize_us,
                            "reset_matcher_us": reset_matcher_us,
                            "validation_loop_us": time_us(validation_t0),
                            "compute_mask_us": compute_mask_us,
                            "commit_token_us": commit_token_us,
                            "max_compute_mask_us": max_compute_mask_us,
                            "max_commit_token_us": max_commit_token_us,
                            "num_tokens": len(tokens),
                            "tokens_checked": tokens_checked,
                            "first_rejected_token_index": "",
                            "error_message": "stage=validation; partial checkpoint inside token loop.",
                        },
                    )
                    next_checkpoint = now + max(args.profile_checkpoint_interval_seconds, 1.0)

                if not ok:
                    accepted = False
                    first_rejected_token_index = token_index
                    break
            validation_loop_us = time_us(validation_t0)
        except Exception as exc:
            if args.debug:
                traceback.print_exc()
            accepted = False
            error_message = repr(exc)
            validation_loop_us = time_us(validation_t0)

        actual_result = result_from_acceptance(record["expected_validity"], accepted)
        record.update(
            {
                "actual_result": actual_result,
                "accepted": accepted,
                "error_message": error_message,
                "num_tokens": len(tokens),
                "tokens_checked": tokens_checked,
                "masks_us": compute_mask_us + commit_token_us,
                "max_mask_us": max(max_compute_mask_us, max_commit_token_us),
                "compute_mask_us": compute_mask_us,
                "commit_token_us": commit_token_us,
                "notes": "Per-test result produced by extension runner.",
            }
        )
        write_jsonl(output, record)
        write_profile_row(
            profile_output,
            {
                **profile_base,
                "actual_result": actual_result,
                "accepted": accepted,
                "result_available": True,
                "instance_json_chars": len(instance),
                "test_json_dumps_us": test_json_dumps_us,
                "tokenize_us": tokenize_us,
                "reset_matcher_us": reset_matcher_us,
                "validation_loop_us": validation_loop_us,
                "compute_mask_us": compute_mask_us,
                "commit_token_us": commit_token_us,
                "max_compute_mask_us": max_compute_mask_us,
                "max_commit_token_us": max_commit_token_us,
                "num_tokens": len(tokens),
                "tokens_checked": tokens_checked,
                "first_rejected_token_index": "" if first_rejected_token_index is None else first_rejected_token_index,
                "error_message": error_message,
            },
        )
        trace(
            args,
            f"  test:end schema={schema_path.name} test_index={test_index} actual_result={actual_result} "
            f"validation_loop_us={validation_loop_us} compute_mask_us={compute_mask_us} "
            f"commit_token_us={commit_token_us} tokens_checked={tokens_checked}/{len(tokens)}",
        )
    return len(indexed_tests)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one MaskBench framework and log per-test JSONL results.")
    parser.add_argument("files", nargs="+", help="JSON files or directories containing MaskBench data files.")
    parser.add_argument(
        "--framework",
        required=False,
        choices=sorted(FRAMEWORK_FLAGS),
        help="Framework to run.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="JSONL output path.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Base output directory used with --split-by-dataset.",
    )
    parser.add_argument(
        "--split-by-dataset",
        action="store_true",
        help="Write one JSONL per dataset under <output-dir>/<framework>/<dataset>/per_test_results.jsonl.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        default=None,
        help="Dataset id to run, for example Github_easy or BFCL_java. Can be repeated.",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        help="List dataset ids discovered from the input files and exit.",
    )
    parser.add_argument(
        "--tokenizer",
        default="unsloth/Meta-Llama-3.1-8B-Instruct",
        help="Tokenizer model ID.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional file limit for small trial runs.")
    parser.add_argument("--max-tests", type=int, default=None, help="Optional maximum number of individual tests to run.")
    parser.add_argument("--max-valid-tests", type=int, default=None, help="Optional maximum number of expected-valid tests to run.")
    parser.add_argument("--max-invalid-tests", type=int, default=None, help="Optional maximum number of expected-invalid tests to run.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose engine debug logging.")
    parser.add_argument("--trace-stages", action="store_true", help="Log coarse function-stage timings to stderr.")
    parser.add_argument("--profile-timings", action="store_true", help="Write per-test timing_profile.csv next to JSONL outputs.")
    parser.add_argument("--profile-csv", default=None, help="Optional CSV path for per-test timing profile rows.")
    parser.add_argument(
        "--schema-compile-profile-csv",
        default=None,
        help="Optional Outlines schema-level compile profile CSV path. Defaults to schema_compile_profile.csv next to timing_profile.csv for profiled Outlines runs.",
    )
    parser.add_argument(
        "--timeout-checkpoints",
        default=None,
        help="Optional Outlines checkpoint JSONL path. Defaults to timeout_checkpoints.jsonl next to the schema compile profile.",
    )
    parser.add_argument(
        "--profile-checkpoint-interval-seconds",
        type=float,
        default=30.0,
        help="Refresh incomplete timing_profile.csv rows at this interval during long validation loops.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the JSONL output file before running.")
    args = parser.parse_args()
    if not args.list_datasets and not args.framework:
        parser.error("--framework is required unless --list-datasets is used.")
    return args


def build_runner_args(args: argparse.Namespace) -> argparse.Namespace:
    runner_args = argparse.Namespace(
        xgr=args.framework == "xgr",
        xgr_compliant=args.framework == "xgr-compliant",
        xgr_cpp=args.framework == "xgr-cpp",
        llg=args.framework in {"guidance", "llg"},
        outlines=args.framework == "outlines",
        llamacpp=args.framework == "llamacpp",
        output=None,
        tokenizer=args.tokenizer,
        time_limit=900,
        mem_limit=40,
        num_threads=1,
        multi=False,
        debug=args.debug,
        files=args.files,
    )
    return runner_args


def main() -> None:
    args = parse_args()
    runner_args = build_runner_args(args)
    files = expand_input_files(runner_args.files)
    files = sorted(files, key=lambda path: path.name)

    dataset_counts = Counter(dataset_id_from_path(path) for path in files)
    if args.list_datasets:
        for dataset_id, count in sorted(dataset_counts.items()):
            print(f"{dataset_id}\t{count}")
        return

    if args.dataset:
        requested = set(args.dataset)
        unknown = requested.difference(dataset_counts)
        if unknown:
            available = ", ".join(sorted(dataset_counts))
            raise SystemExit(f"Unknown dataset id(s): {', '.join(sorted(unknown))}\nAvailable datasets: {available}")
        files = [path for path in files if dataset_id_from_path(path) in requested]

    if args.limit is not None:
        files = files[: args.limit]

    from maskbench.runner import get_engine  # noqa: WPS433
    from transformers import AutoTokenizer  # noqa: WPS433

    engine = get_engine(runner_args)
    engine.tokenizer_model_id = args.tokenizer
    engine.debug = args.debug
    trace(args, f"engine:get_engine framework={args.framework} engine={engine.get_name()}")
    tokenizer_t0 = time.monotonic()
    engine.tokenizer = AutoTokenizer.from_pretrained(engine.tokenizer_model_id)
    args.engine_tokenizer_load_us = time_us(tokenizer_t0)
    trace(args, f"engine:tokenizer_loaded tokenizer={engine.tokenizer_model_id} us={args.engine_tokenizer_load_us}")
    init_t0 = time.monotonic()
    engine.init()
    args.engine_init_us = time_us(init_t0)
    trace(args, f"engine:init_done us={args.engine_init_us}")

    output_cache: dict[Path, set[tuple[str, str, str]]] = {}
    if args.split_by_dataset:
        planned_outputs = sorted({output_path_for_dataset(args, engine, path) for path in files})
    else:
        planned_outputs = [output_path_for_dataset(args, engine, files[0])] if files else []

    if args.overwrite:
        for output in planned_outputs:
            if output.exists():
                output.unlink()
            profile_output = profile_path_for_output(args, output)
            if profile_output is not None and profile_output.exists():
                profile_output.unlink()
            schema_compile_profile_output = schema_compile_profile_path_for_output(args, output, profile_output)
            if schema_compile_profile_output is not None and schema_compile_profile_output.exists():
                schema_compile_profile_output.unlink()
            timeout_checkpoint_output = timeout_checkpoint_path_for_output(args, output, schema_compile_profile_output)
            if timeout_checkpoint_output is not None and timeout_checkpoint_output.exists():
                timeout_checkpoint_output.unlink()

    for output in planned_outputs:
        if output.exists():
            keys = load_existing_result_keys(output)
            output_cache[output] = keys
            print(f"Resuming from {rel(output)} with {len(keys)} existing result keys.", file=sys.stderr)
        else:
            output_cache[output] = set()

    if args.split_by_dataset:
        print(f"Writing split outputs under {rel(Path(args.output_dir))}.", file=sys.stderr)
    elif planned_outputs:
        print(f"Writing {rel(planned_outputs[0])}.", file=sys.stderr)

    counts = {"total": 0, "valid": 0, "invalid": 0}
    for index, schema_path in enumerate(files, start=1):
        if quotas_are_full(args, counts):
            break
        output = output_path_for_dataset(args, engine, schema_path)
        profile_output = profile_path_for_output(args, output)
        existing_keys = output_cache.setdefault(output, set())
        trace(args, f"schema:start index={index}/{len(files)} dataset={dataset_id_from_path(schema_path)} path={rel(schema_path)}")
        print(f"[{index}/{len(files)}] {dataset_id_from_path(schema_path)} {rel(schema_path)}", file=sys.stderr)
        written = process_schema_file(args, engine, output, profile_output, schema_path, counts, existing_keys)
        if written == 0:
            print(f"  skipped: no selected tests remain in this file", file=sys.stderr)
        trace(args, f"schema:end path={rel(schema_path)} written={written}")

    if args.split_by_dataset:
        print(f"Wrote split outputs under {rel(Path(args.output_dir))}")
    elif planned_outputs:
        print(f"Wrote {rel(planned_outputs[0])}")


if __name__ == "__main__":
    main()
