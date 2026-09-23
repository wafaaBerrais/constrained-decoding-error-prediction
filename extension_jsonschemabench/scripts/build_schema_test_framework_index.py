#!/usr/bin/env python3
"""Build a schema/test/framework index for JSONSchemaBench/MaskBench.

The script is read-only with respect to benchmark sources. It writes generated
CSV/JSON files under extension_jsonschemabench/results/ and a Markdown report
under extension_jsonschemabench/reports/.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXT_ROOT = ROOT / "extension_jsonschemabench"
RESULTS_DIR = EXT_ROOT / "results"
REPORTS_DIR = EXT_ROOT / "reports"

CSV_PATH = RESULTS_DIR / "schema_test_framework_index.csv"
JSON_PATH = RESULTS_DIR / "schema_test_framework_index.json"
UNRESOLVED_PATH = RESULTS_DIR / "unresolved_links.json"
REPORT_PATH = REPORTS_DIR / "linking_report.md"

COLUMNS = [
    "schema_id",
    "dataset_id",
    "schema_path",
    "schema_name",
    "test_id",
    "test_path",
    "expected_validity",
    "framework",
    "runner_or_command",
    "source_file",
    "result_available",
    "actual_result",
    "constraint_case",
    "notes",
]

ENGINE_IDS = {
    "llg": "LLGuidance",
    "xgr": "XGrammar",
    "xgr-compliant": "XGrammar (compliant)",
    "xgr-cpp": "XGrammar.cpp",
    "llamacpp": "llama.cpp",
    "outlines": "Outlines",
}

KNOWN_FRAMEWORK_FLAGS = {
    "llg": "--llg",
    "xgr": "--xgr",
    "xgr-compliant": "--xgr-compliant",
    "xgr-cpp": "--xgr-cpp",
    "llamacpp": "--llamacpp",
    "outlines": "--outlines",
}


@dataclass
class ResultFolder:
    path: Path
    framework_id: str
    framework_name: str
    runner_or_command: str
    result_files: dict[str, Path]
    result_folder_available: bool = True


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_load_json(path: Path) -> Any | None:
    try:
        return load_json(path)
    except Exception:
        return None


def dataset_id_from_schema_id(schema_id: str) -> str:
    if "---" in schema_id:
        return schema_id.split("---", 1)[0]
    stem = Path(schema_id).stem
    return re.sub(r"_\d+$", "", stem)


def schema_source_path(schema_id: str) -> tuple[str, str]:
    """Return likely original schema file and note."""
    if "---" not in schema_id:
        return "not_found", "No Dataset---file naming pattern; source schema is embedded in maskbench/data only."

    dataset, filename = schema_id.split("---", 1)
    candidate = ROOT / "data" / dataset / filename
    if candidate.exists():
        return rel(candidate), "Linked by Dataset---filename convention."

    return "not_found", f"Dataset---filename convention points to {rel(candidate)}, but the file was not found."


def discover_result_folders() -> list[ResultFolder]:
    folders: list[Path] = []
    for base in [
        ROOT / "tmp",
        ROOT / "maskbench" / "tmp",
        EXT_ROOT / "results" / "raw_runs",
    ]:
        if base.exists():
            folders.extend(p for p in base.glob("out--*") if p.is_dir())

    result_folders: list[ResultFolder] = []
    for folder in sorted(folders):
        meta_path = folder / "meta.txt"
        meta = safe_load_json(meta_path) if meta_path.exists() else None
        folder_id = folder.name.removeprefix("out--")

        if isinstance(meta, dict):
            framework_id = str(meta.get("id") or folder_id or "unknown")
            framework_name = str(meta.get("name") or ENGINE_IDS.get(framework_id, framework_id))
            cmd = meta.get("cmd")
            if isinstance(cmd, list):
                runner_or_command = " ".join(str(part) for part in cmd)
            else:
                runner_or_command = str(meta.get("info") or meta.get("cmd") or rel(folder))
        else:
            framework_id = folder_id or "unknown"
            framework_name = ENGINE_IDS.get(framework_id, framework_id)
            runner_or_command = rel(folder)

        result_files = {
            path.name: path
            for path in folder.glob("*.json")
            if path.name not in {"meta.txt", "stats.txt", "entries.txt"}
        }
        result_folders.append(
            ResultFolder(
                path=folder,
                framework_id=framework_id,
                framework_name=framework_name,
                runner_or_command=runner_or_command,
                result_files=result_files,
            )
        )
    return result_folders


def known_framework_candidates() -> list[ResultFolder]:
    """Return frameworks supported by the MaskBench runner.

    These records are used only when no `tmp/out--*` folders are present. They
    expose the framework dimension without claiming that an execution result is
    available in the local checkout.
    """
    candidates: list[ResultFolder] = []
    for framework_id, framework_name in ENGINE_IDS.items():
        flag = KNOWN_FRAMEWORK_FLAGS[framework_id]
        candidates.append(
            ResultFolder(
                path=ROOT / "tmp" / f"out--{framework_id}",
                framework_id=framework_id,
                framework_name=framework_name,
                runner_or_command=f"python -m maskbench.runner {flag} <files>",
                result_files={},
                result_folder_available=False,
            )
        )
    return candidates


def parse_validation_error(message: str) -> tuple[int | None, str]:
    match = re.search(r"test #(\d+):\s*(.*)", message)
    if not match:
        return None, message
    return int(match.group(1)), match.group(2)


def infer_actual_result(result_data: dict[str, Any], test_index: int) -> tuple[str, str]:
    if "pending_file" in result_data:
        return "unknown", "Result file is a pending marker."

    if "compile_error" in result_data:
        return "compile_error", "Framework failed while compiling the schema."

    validation_error = result_data.get("validation_error")
    if isinstance(validation_error, str):
        error_index, detail = parse_validation_error(validation_error)
        if error_index == test_index:
            return "failed", f"Runner reported validation_error for this test: {detail}"
        if error_index is not None:
            return (
                "unknown",
                "Schema result contains a validation_error for another test; runner output is not complete per-test logging.",
            )
        return "unknown", "Schema result contains validation_error but no parseable test index."

    return "passed", "No compile_error or validation_error recorded for the schema result."


def classify_constraint_case(expected_validity: str, actual_result: str) -> str:
    if actual_result == "passed":
        return "correct"
    if actual_result in {"compile_error", "timeout"}:
        return actual_result
    if actual_result != "failed":
        return "unknown"
    if expected_validity == "valid":
        return "over_constraint"
    if expected_validity == "invalid":
        return "under_constraint"
    return "unknown"


def load_all_stats() -> dict[str, dict[str, Any]]:
    path = ROOT / "maskbench" / "metainfo" / "all_stats.json"
    payload = safe_load_json(path)
    if not isinstance(payload, list):
        return {}
    return {str(item.get("id")): item for item in payload if isinstance(item, dict) and item.get("id")}


def load_per_test_results() -> tuple[dict[tuple[str, str, str], dict[str, Any]], list[str], int]:
    """Load extension-owned per-test JSONL result logs if they exist."""
    result_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    log_paths: list[str] = []
    record_count = 0
    paths = sorted(RESULTS_DIR.rglob("per_test_results*.jsonl"), key=lambda item: (item.stat().st_mtime, str(item)))
    for path in paths:
        log_paths.append(rel(path))
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
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
                framework = str(record.get("framework") or "")
                framework_id = str(record.get("framework_id") or "")
                if not schema_id or not test_id:
                    continue
                record_count += 1
                record["_log_path"] = rel(path)
                record["_log_line"] = line_number
                if framework:
                    result_map[(schema_id, test_id, framework)] = record
                if framework_id:
                    result_map[(schema_id, test_id, framework_id)] = record
    return result_map, log_paths, record_count


def load_timeout_results() -> tuple[dict[tuple[str, str], dict[str, Any]], list[str], int]:
    """Load schema-level timeout records produced by run_dataset_with_timeouts.py."""
    result_map: dict[tuple[str, str], dict[str, Any]] = {}
    log_paths: list[str] = []
    record_count = 0
    paths = sorted(RESULTS_DIR.rglob("timed_out_schemas.jsonl"), key=lambda item: (item.stat().st_mtime, str(item)))
    for path in paths:
        log_paths.append(rel(path))
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
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
                framework_id = str(record.get("framework_id") or "")
                if not schema_id or not framework_id:
                    continue
                record_count += 1
                record["_log_path"] = rel(path)
                record["_log_line"] = line_number
                result_map[(schema_id, framework_id)] = record
    return result_map, log_paths, record_count


def build_rows(limit: int | None = None) -> tuple[list[dict[str, str]], list[dict[str, Any]], dict[str, Any]]:
    maskbench_data = ROOT / "maskbench" / "data"
    result_folders = discover_result_folders()
    framework_runs = result_folders if result_folders else known_framework_candidates()
    per_test_results, per_test_logs, per_test_record_count = load_per_test_results()
    timeout_results, timeout_logs, timeout_record_count = load_timeout_results()
    all_stats = load_all_stats()
    rows: list[dict[str, str]] = []
    unresolved: list[dict[str, Any]] = []

    files = sorted(maskbench_data.glob("*.json"))
    if limit is not None:
        files = files[:limit]

    for schema_path in files:
        schema_id = schema_path.name
        payload = safe_load_json(schema_path)
        if not isinstance(payload, dict):
            unresolved.append(
                {
                    "type": "schema_file_parse_error",
                    "schema_id": schema_id,
                    "schema_path": rel(schema_path),
                    "notes": "Could not parse schema/test JSON file.",
                }
            )
            continue

        tests = payload.get("tests")
        if not isinstance(tests, list):
            unresolved.append(
                {
                    "type": "schema_tests_missing",
                    "schema_id": schema_id,
                    "schema_path": rel(schema_path),
                    "notes": "File does not contain a list-valued tests field.",
                }
            )
            tests = []

        source_file, source_note = schema_source_path(schema_id)
        if source_file == "not_found":
            unresolved.append(
                {
                    "type": "schema_source_not_found",
                    "schema_id": schema_id,
                    "schema_path": rel(schema_path),
                    "notes": source_note,
                }
            )

        if schema_id not in all_stats:
            unresolved.append(
                {
                    "type": "all_stats_entry_not_found",
                    "schema_id": schema_id,
                    "schema_path": rel(schema_path),
                    "notes": "No matching aggregate entry in maskbench/metainfo/all_stats.json.",
                }
            )

        schema_name = str(payload.get("description") or schema_id)
        frameworks_to_emit = framework_runs

        for idx, test in enumerate(tests):
            if isinstance(test, dict):
                expected = test.get("valid")
                expected_validity = "valid" if expected is True else "invalid" if expected is False else "unknown"
            else:
                expected_validity = "unknown"
                unresolved.append(
                    {
                        "type": "test_record_not_object",
                        "schema_id": schema_id,
                        "test_index": idx,
                        "notes": "Test entry is not a JSON object.",
                    }
                )

            test_id = f"{schema_id}::test_{idx:05d}"
            test_path = f"{rel(schema_path)}#/tests/{idx}"

            for result_folder in frameworks_to_emit:
                notes = [source_note]
                framework = result_folder.framework_name
                runner_or_command = result_folder.runner_or_command
                per_test_result = per_test_results.get((schema_id, test_id, result_folder.framework_name))
                if per_test_result is None:
                    per_test_result = per_test_results.get((schema_id, test_id, result_folder.framework_id))
                timeout_result = timeout_results.get((schema_id, result_folder.framework_id))

                if per_test_result is not None:
                    result_available = "true"
                    actual_result = str(per_test_result.get("actual_result") or "unknown")
                    runner_or_command = str(per_test_result.get("runner_or_command") or runner_or_command)
                    notes.append(
                        f"Actual result loaded from {per_test_result.get('_log_path')} line {per_test_result.get('_log_line')}."
                    )
                    error_message = per_test_result.get("error_message")
                    if error_message:
                        notes.append(f"Error message: {error_message}")
                elif timeout_result is not None:
                    result_available = "true"
                    actual_result = "timeout"
                    runner_or_command = f"python {rel(EXT_ROOT / 'scripts' / 'run_dataset_with_timeouts.py')} --framework {result_folder.framework_id} <files>"
                    notes.append(
                        f"Schema-level timeout loaded from {timeout_result.get('_log_path')} line {timeout_result.get('_log_line')}."
                    )
                    timeout_minutes = timeout_result.get("timeout_minutes")
                    if timeout_minutes:
                        notes.append(f"Timeout after {timeout_minutes} minutes; individual test was not executed.")
                elif not result_folder.result_folder_available:
                    result_available = "false"
                    actual_result = "unknown"
                    notes.append(
                        "Framework inferred from MaskBench runner support; no local tmp/out--* result folder was found, so this is not proof of an executed run."
                    )
                    unresolved.append(
                        {
                            "type": "result_folder_not_found",
                            "schema_id": schema_id,
                            "test_id": test_id,
                            "test_path": test_path,
                            "framework": framework,
                            "expected_result_folder": rel(result_folder.path),
                            "notes": "Framework is known from runner configuration, but no benchmark result folder is present.",
                        }
                    )
                else:
                    result_path = result_folder.result_files.get(schema_id)
                    if result_path is None:
                        result_available = "false"
                        actual_result = "not_found"
                        notes.append(f"No result file found in {rel(result_folder.path)} for this schema.")
                        unresolved.append(
                            {
                                "type": "result_file_not_found",
                                "schema_id": schema_id,
                                "test_id": test_id,
                                "framework": framework,
                                "result_folder": rel(result_folder.path),
                                "notes": "Framework folder exists, but the schema result JSON is missing.",
                            }
                        )
                    else:
                        result_available = "true"
                        result_data = safe_load_json(result_path)
                        if isinstance(result_data, dict):
                            actual_result, result_note = infer_actual_result(result_data, idx)
                            notes.append(result_note)
                            if actual_result == "unknown":
                                unresolved.append(
                                    {
                                        "type": "result_to_test_ambiguous",
                                        "schema_id": schema_id,
                                        "test_id": test_id,
                                        "framework": framework,
                                        "result_file": rel(result_path),
                                        "notes": result_note,
                                    }
                                )
                        else:
                            actual_result = "unknown"
                            notes.append("Could not parse result JSON file.")
                            unresolved.append(
                                {
                                    "type": "result_file_parse_error",
                                    "schema_id": schema_id,
                                    "test_id": test_id,
                                    "framework": framework,
                                    "result_file": rel(result_path),
                                    "notes": "Could not parse result JSON file.",
                                }
                            )

                rows.append(
                    {
                        "schema_id": schema_id,
                        "dataset_id": dataset_id_from_schema_id(schema_id),
                        "schema_path": rel(schema_path),
                        "schema_name": schema_name,
                        "test_id": test_id,
                        "test_path": test_path,
                        "expected_validity": expected_validity,
                        "framework": framework,
                        "runner_or_command": runner_or_command,
                        "source_file": source_file,
                        "result_available": result_available,
                        "actual_result": actual_result,
                        "constraint_case": classify_constraint_case(expected_validity, actual_result),
                        "notes": " ".join(notes),
                    }
                )

    summary = {
        "maskbench_schema_files_seen": len(files),
        "rows": len(rows),
        "result_folders": [rel(folder.path) for folder in result_folders],
        "framework_rows_source": "result_folders" if result_folders else "known_runner_frameworks",
        "per_test_result_logs": per_test_logs,
        "per_test_result_records": per_test_record_count,
        "timeout_logs": timeout_logs,
        "timeout_records": timeout_record_count,
        "frameworks": [
            {
                "id": folder.framework_id,
                "name": folder.framework_name,
                "path": rel(folder.path),
                "result_files": len(folder.result_files),
                "result_folder_available": folder.result_folder_available,
            }
            for folder in framework_runs
        ],
        "unresolved_count": len(unresolved),
        "all_stats_entries": len(all_stats),
    }
    return rows, unresolved, summary


def write_outputs(rows: list[dict[str, str]], unresolved: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    JSON_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    unresolved_payload = {
        "summary": summary,
        "unresolved": unresolved,
    }
    UNRESOLVED_PATH.write_text(json.dumps(unresolved_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    write_report(rows, unresolved, summary)


def write_report(rows: list[dict[str, str]], unresolved: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    expected_counts: dict[str, int] = {}
    framework_counts: dict[str, int] = {}
    result_counts: dict[str, int] = {}
    actual_counts: dict[str, int] = {}
    constraint_counts: dict[str, int] = {}
    unresolved_counts: dict[str, int] = {}

    for row in rows:
        expected_counts[row["expected_validity"]] = expected_counts.get(row["expected_validity"], 0) + 1
        framework_counts[row["framework"]] = framework_counts.get(row["framework"], 0) + 1
        result_counts[row["result_available"]] = result_counts.get(row["result_available"], 0) + 1
        actual_counts[row["actual_result"]] = actual_counts.get(row["actual_result"], 0) + 1
        constraint_counts[row["constraint_case"]] = constraint_counts.get(row["constraint_case"], 0) + 1
    for item in unresolved:
        key = str(item.get("type", "unknown"))
        unresolved_counts[key] = unresolved_counts.get(key, 0) + 1

    lines: list[str] = []
    lines.append("# Schema-Test-Framework Linking Report\n")
    lines.append("This report was generated by `extension_jsonschemabench/scripts/build_schema_test_framework_index.py`.\n")

    lines.append("## Generated Outputs\n")
    lines.append(f"- CSV index: `{rel(CSV_PATH)}`")
    lines.append(f"- JSON index: `{rel(JSON_PATH)}`")
    lines.append(f"- Unresolved links: `{rel(UNRESOLVED_PATH)}`")
    lines.append("")

    lines.append("## Sources Used\n")
    lines.append("- `maskbench/data/*.json`: primary source for schemas and individual tests.")
    lines.append("- `data/<dataset>/*.json`: source schema files when a `Dataset---file.json` name maps back cleanly.")
    lines.append("- `maskbench/metainfo/all_stats.json`: aggregate validation/test counts used only as metadata.")
    lines.append("- `tmp/out--*` and `maskbench/tmp/out--*`: optional benchmark result folders when present.")
    lines.append("- `meta.txt` inside result folders: optional framework/command metadata.")
    lines.append("- `extension_jsonschemabench/results/per_test_results*.jsonl`: optional per-test execution logs produced by the extension runner.")
    lines.append("")

    lines.append("## Summary\n")
    lines.append(f"- MaskBench schema files scanned: {summary['maskbench_schema_files_seen']}")
    lines.append(f"- Index rows written: {summary['rows']}")
    lines.append(f"- Aggregate metadata entries: {summary['all_stats_entries']}")
    lines.append(f"- Result folders found: {len(summary['result_folders'])}")
    lines.append(f"- Framework rows source: `{summary['framework_rows_source']}`")
    lines.append(f"- Per-test result logs found: {len(summary['per_test_result_logs'])}")
    lines.append(f"- Per-test result records loaded: {summary['per_test_result_records']}")
    lines.append(f"- Unresolved link records: {summary['unresolved_count']}")
    lines.append("")

    def add_counts(title: str, counts: dict[str, int]) -> None:
        lines.append(f"## {title}\n")
        if not counts:
            lines.append("No entries.")
            lines.append("")
            return
        lines.append("| Value | Count |")
        lines.append("| --- | ---: |")
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{key}` | {value} |")
        lines.append("")

    add_counts("Expected Validity Counts", expected_counts)
    add_counts("Framework Counts", framework_counts)
    add_counts("Result Availability Counts", result_counts)
    add_counts("Actual Result Counts", actual_counts)
    add_counts("Constraint Case Counts", constraint_counts)
    add_counts("Unresolved Link Types", unresolved_counts)

    lines.append("## How Schema To Test Links Are Built\n")
    lines.append("Each file in `maskbench/data/*.json` is treated as one benchmark schema record.")
    lines.append("The file name is used as `schema_id`. Each element of the `tests` array becomes one row.")
    lines.append("The stable `test_id` is `schema_id::test_<zero-padded-index>`, and `test_path` points to the JSON pointer-like location `#/tests/<index>`.")
    lines.append("Expected validity comes directly from the test object's `valid` field.")
    lines.append("")

    lines.append("## How Schema Source Links Are Built\n")
    lines.append("For schema IDs shaped like `Dataset---filename.json`, the script tries to link back to `data/Dataset/filename.json`.")
    lines.append("This works for the original top-level JSONSchemaBench datasets. Other MaskBench additions such as BFCL, JME, MCPspec, Handwritten, and Synthesized often have no matching file under top-level `data/`, so their source is reported as `not_found` while the embedded schema remains available in `maskbench/data`.")
    lines.append("")

    lines.append("## How Test To Framework Links Are Built\n")
    lines.append("If result folders such as `tmp/out--llg` exist, each folder is treated as one framework run.")
    lines.append("The framework name is read from `meta.txt` when available, otherwise inferred from the folder name.")
    lines.append("If no result folder exists, rows are expanded across the frameworks supported by `maskbench/maskbench/runner.py`: LLGuidance, XGrammar, XGrammar compliant, XGrammar.cpp, llama.cpp, and Outlines.")
    lines.append("In that fallback case, `framework` is a runner-supported candidate, not proof that a local execution happened. The row keeps `result_available=false` and explains the missing output folder in `notes`.")
    lines.append("If extension per-test JSONL logs exist, they take precedence for matching `schema_id`, `test_id`, and framework, and `actual_result` is filled from those records.")
    lines.append("")

    lines.append("## How Result Links Are Built\n")
    lines.append("Result files are matched by schema file name inside each result folder.")
    lines.append("Current MaskBench result files are schema-level summaries. If there is no `compile_error` or `validation_error`, all tests for that schema/framework are marked `passed`.")
    lines.append("If there is a `compile_error`, all tests for that schema/framework are marked `compile_error`.")
    lines.append("If there is a parseable `validation_error` like `test #3: should accept but didn't`, that test is marked `failed`; other tests for the same schema remain ambiguous because the runner does not store complete per-test outcomes.")
    lines.append("")

    lines.append("## Limits Of `all_stats.json`\n")
    lines.append("`all_stats.json` is useful for aggregate counts, features, and test sizes, but it does not include:")
    lines.append("- individual test data")
    lines.append("- individual test IDs")
    lines.append("- per-test expected validity beyond aggregate counts")
    lines.append("- framework name or command")
    lines.append("- per-test actual result")
    lines.append("- result file paths")
    lines.append("")

    lines.append("## Recommended Runner Logging Changes\n")
    lines.append("To make future linking exact, `maskbench/maskbench/runner.py` should write a structured per-test record for every execution. Suggested fields:")
    lines.append("- `schema_id`")
    lines.append("- `schema_path`")
    lines.append("- `framework_id` and `framework_name`")
    lines.append("- `runner_command` or normalized runner options")
    lines.append("- `test_index`")
    lines.append("- `test_id`")
    lines.append("- `expected_validity`")
    lines.append("- `accepted`")
    lines.append("- `actual_result` such as `passed`, `failed`, `compile_error`, `exception`, or `timeout`")
    lines.append("- `constraint_case` such as `correct`, `under_constraint`, `over_constraint`, `compile_error`, or `unknown`")
    lines.append("- `error_message`")
    lines.append("- timing fields per test, if needed")
    lines.append("")
    lines.append("A JSONL file next to each schema-level result would be enough, for example `tmp/out--llg/per_test_results.jsonl`.")
    lines.append("This extension already provides a non-invasive version of that idea in `extension_jsonschemabench/scripts/run_per_test_framework_logging.py`.")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build schema/test/framework index files.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for quick debugging.")
    args = parser.parse_args()

    rows, unresolved, summary = build_rows(limit=args.limit)
    write_outputs(rows, unresolved, summary)
    print(f"Wrote {rel(CSV_PATH)}")
    print(f"Wrote {rel(JSON_PATH)}")
    print(f"Wrote {rel(UNRESOLVED_PATH)}")
    print(f"Wrote {rel(REPORT_PATH)}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
