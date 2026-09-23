#!/usr/bin/env python3
"""Greedy HDD minimization for Outlines mismatches on JSONSchemaBench."""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import re
import shutil
import sys
import time
import warnings
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    from jsonschema.validators import validator_for
except ModuleNotFoundError as exc:  # pragma: no cover - exercised before real runs.
    raise SystemExit(
        "Missing dependency: jsonschema. Install it in the project venv first, for example:\n"
        "  .venv/bin/pip install jsonschema"
    ) from exc


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "maskbench" / "data"
DEFAULT_RESULTS = ROOT / "extension_jsonschemabench" / "results" / "per_dataset_runs"
DEFAULT_OUTPUT_DIR = DEFAULT_RESULTS / "outlines" / "Github_medium" / "hdd_minimized_outlines"

sys.path.insert(0, str(ROOT / "maskbench"))
warnings.filterwarnings("ignore", category=FutureWarning, module=r"jsonschema\._format")

KEYWORDS = [
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "prefixItems",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "enum",
    "const",
    "pattern",
    "patternProperties",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "$ref",
    "$defs",
]

NESTED_PATTERNS = [
    ("not", "enum"),
    ("not", "const"),
    ("allOf", "not"),
    ("allOf", "properties"),
    ("properties", "not"),
    ("properties", "enum"),
    ("allOf", "properties", "required"),
    ("anyOf", "type"),
    ("oneOf", "required"),
]

SCHEMA_CHILD_KEYS = {
    "additionalItems",
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
}
SCHEMA_ARRAY_KEYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
SCHEMA_MAP_KEYS = {"$defs", "definitions", "dependentSchemas", "patternProperties", "properties"}
_OUTLINES_ENGINE: Any | None = None


class CaseTimeout(Exception):
    """Raised when one minimization case exceeds its time budget."""


@dataclass
class ValidationResult:
    schema_valid: bool
    instance_valid: bool | None
    error_type: str = ""
    error_message: str = ""
    validator_error_keyword: str = ""
    validator_error_path: str = ""
    validator_error_schema_path: str = ""


@dataclass
class Classification:
    status: str
    validator_status: str
    outlines_result: str
    error_type: str = ""
    error_message: str = ""
    validator_error_keyword: str = ""
    validator_error_path: str = ""
    validator_error_schema_path: str = ""


@dataclass
class Mutation:
    mutation_type: str
    path: tuple[Any, ...]
    apply: Callable[[Any], Any]
    keyword: str = ""


@dataclass
class MutationStats:
    num_mutations_tried: int = 0
    num_mutations_kept: int = 0


@dataclass
class Case:
    schema_id: str
    schema_path: Path
    test_id: str
    test_index: int
    failure_type: str
    instance: Any
    original_expected_validity: str
    original_outlines_accepted: bool


def path_text(path: Iterable[Any]) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def stored_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_stored_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def keyword_count(value: Any) -> int:
    if isinstance(value, dict):
        return len(value) + sum(keyword_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(keyword_count(child) for child in value)
    return 0


def iter_keywords(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from iter_keywords(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_keywords(child)


def get_node(document: Any, path: tuple[Any, ...]) -> Any:
    node = document
    for part in path:
        node = node[part]
    return node


def mutate_copy(document: Any, mutator: Callable[[Any], None]) -> Any:
    candidate = deepcopy(document)
    mutator(candidate)
    return candidate


def parent_and_key(document: Any, path: tuple[Any, ...]) -> tuple[Any, Any]:
    if not path:
        raise ValueError("Root path has no parent")
    return get_node(document, path[:-1]), path[-1]


def delete_dict_key(path: tuple[Any, ...], key: str) -> Callable[[Any], Any]:
    def apply(document: Any) -> Any:
        def op(candidate: Any) -> None:
            get_node(candidate, path).pop(key, None)

        return mutate_copy(document, op)

    return apply


def delete_list_index(path: tuple[Any, ...], index: int) -> Callable[[Any], Any]:
    def apply(document: Any) -> Any:
        def op(candidate: Any) -> None:
            del get_node(candidate, path)[index]

        return mutate_copy(document, op)

    return apply


def replace_node(path: tuple[Any, ...], replacement: Any) -> Callable[[Any], Any]:
    def apply(document: Any) -> Any:
        if not path:
            return deepcopy(replacement)

        def op(candidate: Any) -> None:
            parent, key = parent_and_key(candidate, path)
            parent[key] = deepcopy(replacement)

        return mutate_copy(document, op)

    return apply


def remove_required_item(path: tuple[Any, ...], index: int) -> Callable[[Any], Any]:
    def apply(document: Any) -> Any:
        def op(candidate: Any) -> None:
            required = get_node(candidate, path)["required"]
            del required[index]

        return mutate_copy(document, op)

    return apply


def local_mutations(schema: Any, path: tuple[Any, ...]) -> list[Mutation]:
    node = get_node(schema, path)
    mutations: list[Mutation] = []

    if path and isinstance(node, dict) and node:
        mutations.append(Mutation("replace_subschema_with_true_schema", path, replace_node(path, {})))

    if isinstance(node, dict):
        for key in list(node):
            mutations.append(Mutation("delete_keyword", path, delete_dict_key(path, key), keyword=key))

        for key in sorted(SCHEMA_ARRAY_KEYS):
            value = node.get(key)
            if isinstance(value, list) and len(value) > 1:
                for index in range(len(value)):
                    mutations.append(
                        Mutation("delete_schema_branch", path + (key,), delete_list_index(path + (key,), index), keyword=key)
                    )

        properties = node.get("properties")
        if isinstance(properties, dict):
            for prop in list(properties):
                mutations.append(
                    Mutation(
                        "delete_property",
                        path + ("properties",),
                        delete_dict_key(path + ("properties",), prop),
                        keyword=prop,
                    )
                )

        required = node.get("required")
        if isinstance(required, list):
            for index, prop in enumerate(list(required)):
                mutations.append(
                    Mutation("delete_required_item", path, remove_required_item(path, index), keyword=str(prop))
                )

        defs = node.get("$defs")
        if isinstance(defs, dict):
            for name in list(defs):
                mutations.append(
                    Mutation("delete_def", path + ("$defs",), delete_dict_key(path + ("$defs",), name), keyword=name)
                )

    elif isinstance(node, list) and len(node) > 1:
        for index in range(len(node)):
            mutations.append(Mutation("delete_list_item", path, delete_list_index(path, index), keyword=str(index)))

    return mutations


def child_schema_paths(schema: Any, path: tuple[Any, ...]) -> list[tuple[Any, ...]]:
    node = get_node(schema, path)
    children: list[tuple[Any, ...]] = []
    if isinstance(node, dict):
        for key in sorted(SCHEMA_CHILD_KEYS):
            value = node.get(key)
            if isinstance(value, (dict, list, bool)):
                children.append(path + (key,))
        for key in sorted(SCHEMA_ARRAY_KEYS):
            value = node.get(key)
            if isinstance(value, list):
                children.extend(path + (key, index) for index, child in enumerate(value) if isinstance(child, (dict, list, bool)))
        for key in sorted(SCHEMA_MAP_KEYS):
            value = node.get(key)
            if isinstance(value, dict):
                children.extend(
                    path + (key, name) for name, child in value.items() if isinstance(child, (dict, list, bool))
                )
    elif isinstance(node, list):
        children.extend(path + (index,) for index, child in enumerate(node) if isinstance(child, (dict, list, bool)))
    return children


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_result_rows(path: Path) -> list[dict[str, Any]]:
    by_test: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("test_id") or f"{row.get('schema_id')}::{row.get('test_index')}"
            by_test[str(key)] = row
    return list(by_test.values())


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def accepted_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return None


def select_cases(args: argparse.Namespace) -> list[Case]:
    results_path = Path(args.results_jsonl)
    if not results_path.is_absolute():
        results_path = ROOT / results_path
    rows = [
        row
        for row in load_result_rows(results_path)
        if row.get("framework_id") == "outlines" and row.get("result_available", True)
    ]
    rows.sort(key=lambda row: (str(row.get("schema_id", "")), int(row.get("test_index", 0)), str(row.get("test_id", ""))))

    wanted: set[str]
    if args.failure_type == "both":
        wanted = {"UNDER", "OVER"}
    else:
        wanted = {args.failure_type.upper()}

    payload_cache: dict[str, dict[str, Any]] = {}

    def payload_for(schema_id: str) -> dict[str, Any]:
        if schema_id not in payload_cache:
            payload_cache[schema_id] = load_json(DATA_ROOT / schema_id)
        return payload_cache[schema_id]

    def classify_source_row(row: dict[str, Any]) -> tuple[str, str] | None:
        accepted = accepted_bool(row.get("accepted"))
        if accepted is None:
            return None
        schema_id = str(row["schema_id"])
        payload = payload_for(schema_id)
        test = payload["tests"][int(row["test_index"])]
        validation = validate_instance(payload["schema"], test["data"])
        if not validation.schema_valid:
            return None
        expected_validity = "VALID" if validation.instance_valid else "INVALID"
        if expected_validity == "INVALID" and accepted is True:
            return "UNDER", expected_validity
        if expected_validity == "VALID" and accepted is False:
            return "OVER", expected_validity
        return None

    selected_rows: list[tuple[str, dict[str, Any], str]] = []
    if args.mode == "all_tests":
        for row in rows:
            classification = classify_source_row(row)
            if classification is None:
                continue
            failure_type, expected_validity = classification
            if failure_type in wanted:
                selected_rows.append((failure_type, row, expected_validity))
    else:
        seen: set[tuple[str, str]] = set()
        for row in rows:
            schema_id = str(row.get("schema_id"))
            classification = classify_source_row(row)
            if classification is None:
                continue
            failure_type, expected_validity = classification
            if failure_type in wanted and (schema_id, failure_type) not in seen:
                selected_rows.append((failure_type, row, expected_validity))
                seen.add((schema_id, failure_type))

    if args.max_schemas is not None:
        counts: Counter[str] = Counter()
        limited: list[tuple[str, dict[str, Any], str]] = []
        for failure_type, row, expected_validity in selected_rows:
            if counts[failure_type] >= args.max_schemas:
                continue
            limited.append((failure_type, row, expected_validity))
            counts[failure_type] += 1
        selected_rows = limited

    cases: list[Case] = []
    for failure_type, row, expected_validity in selected_rows:
        schema_id = str(row["schema_id"])
        schema_path = DATA_ROOT / schema_id
        payload = payload_for(schema_id)
        test_index = int(row["test_index"])
        test = payload["tests"][test_index]
        accepted = accepted_bool(row.get("accepted"))
        if accepted is None:
            continue
        cases.append(
            Case(
                schema_id=schema_id,
                schema_path=schema_path,
                test_id=str(row["test_id"]),
                test_index=test_index,
                failure_type=failure_type,
                instance=test["data"],
                original_expected_validity=expected_validity,
                original_outlines_accepted=accepted,
            )
        )
    return cases


def validate_instance(schema: Any, instance: Any) -> ValidationResult:
    try:
        validator_cls = validator_for(schema, default=Draft202012Validator)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
    except Exception as exc:
        return ValidationResult(False, None, type(exc).__name__, str(exc))

    error = next(validator.iter_errors(instance), None)
    if error is None:
        return ValidationResult(True, True)
    return ValidationResult(
        True,
        False,
        validator_error_keyword=str(error.validator),
        validator_error_path=path_text(tuple(error.path)),
        validator_error_schema_path=path_text(tuple(error.schema_path)),
        error_message=str(error.message),
    )


def run_outlines_acceptance_inprocess(engine: Any, schema: Any, instance: Any, debug: bool = False) -> tuple[str, str, str]:
    try:
        engine.compile_grammar(schema)
    except Exception as exc:
        return "COMPILE_ERROR", type(exc).__name__, str(exc)

    try:
        engine.reset()
        instance_text = json.dumps(instance, indent=None, ensure_ascii=False)
        tokens = engine.tokenizer.encode(instance_text, add_special_tokens=False)
        for token in tokens:
            engine.compute_mask()
            ok = engine.commit_token(token)
            if debug:
                engine.log_single(f"token={engine.tokenizer.decode([token])!r} ok={ok}")
            if not ok:
                return "REJECT", "", ""
        return "ACCEPT", "", ""
    except Exception as exc:
        return "RUNTIME_ERROR", type(exc).__name__, str(exc)


def outlines_acceptance_child(schema: Any, instance: Any, debug: bool, conn: Any) -> None:
    try:
        if _OUTLINES_ENGINE is None:
            raise RuntimeError("Outlines engine was not initialized before fork")
        conn.send(run_outlines_acceptance_inprocess(_OUTLINES_ENGINE, schema, instance, debug=debug))
    except BaseException as exc:
        conn.send(("RUNTIME_ERROR", type(exc).__name__, str(exc)))
    finally:
        conn.close()


def run_outlines_acceptance_subprocess(schema: Any, instance: Any, timeout: float, debug: bool = False) -> tuple[str, str, str]:
    ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=outlines_acceptance_child, args=(schema, instance, debug, child_conn))
    proc.start()
    child_conn.close()
    proc.join(max(timeout, 0.1))
    if proc.is_alive():
        proc.terminate()
        proc.join(2)
        if proc.is_alive():
            proc.kill()
            proc.join(2)
        parent_conn.close()
        return "TIMEOUT", "TimeoutError", f"outlines evaluation exceeded {timeout:.3f}s"
    if parent_conn.poll():
        try:
            result = parent_conn.recv()
            parent_conn.close()
            return result
        except EOFError:
            parent_conn.close()
            if proc.exitcode and proc.exitcode < 0:
                return "RUNTIME_ERROR", "ProcessPipeEOF", f"outlines child terminated by signal {-proc.exitcode}"
            return "RUNTIME_ERROR", "ProcessPipeEOF", f"outlines child closed pipe without result rc={proc.exitcode}"
    parent_conn.close()
    if proc.exitcode and proc.exitcode < 0:
        return "RUNTIME_ERROR", "ProcessTerminated", f"outlines child terminated by signal {-proc.exitcode}"
    return "RUNTIME_ERROR", "ProcessTerminated", f"outlines child exited without result rc={proc.exitcode}"


def classify_case(
    engine: Any,
    schema: Any,
    instance: Any,
    timeout: float,
    exec_mode: str,
    debug: bool = False,
) -> Classification:
    validation = validate_instance(schema, instance)
    if not validation.schema_valid:
        return Classification("RUNTIME_ERROR", "INVALID_SCHEMA", "NOT_RUN", validation.error_type, validation.error_message)

    if exec_mode == "inprocess":
        outlines_result, error_type, error_message = run_outlines_acceptance_inprocess(engine, schema, instance, debug=debug)
    else:
        outlines_result, error_type, error_message = run_outlines_acceptance_subprocess(
            schema,
            instance,
            timeout=timeout,
            debug=debug,
        )
    if outlines_result in {"COMPILE_ERROR", "RUNTIME_ERROR", "TIMEOUT"}:
        return Classification(
            outlines_result,
            "VALID" if validation.instance_valid else "INVALID",
            outlines_result,
            error_type,
            error_message,
            validation.validator_error_keyword,
            validation.validator_error_path,
            validation.validator_error_schema_path,
        )

    if validation.instance_valid and outlines_result == "ACCEPT":
        status = "OK_VALID"
    elif validation.instance_valid is False and outlines_result == "REJECT":
        status = "OK_INVALID"
    elif validation.instance_valid is False and outlines_result == "ACCEPT":
        status = "UNDER"
    elif validation.instance_valid and outlines_result == "REJECT":
        status = "OVER"
    else:
        status = "RUNTIME_ERROR"

    return Classification(
        status,
        "VALID" if validation.instance_valid else "INVALID",
        outlines_result,
        validator_error_keyword=validation.validator_error_keyword,
        validator_error_path=validation.validator_error_path,
        validator_error_schema_path=validation.validator_error_schema_path,
        error_message=validation.error_message,
    )


class Deadline:
    def __init__(self, seconds: float):
        self.end = time.monotonic() + seconds

    def remaining(self) -> float:
        return self.end - time.monotonic()

    def check(self) -> None:
        if self.remaining() <= 0:
            raise CaseTimeout("case timeout")


class Minimizer:
    def __init__(
        self,
        engine: Any,
        case: Case,
        output_dir: Path,
        deadline: Deadline,
        exec_mode: str,
        debug: bool = False,
    ):
        self.engine = engine
        self.case = case
        self.output_dir = output_dir
        self.deadline = deadline
        self.exec_mode = exec_mode
        self.debug = debug
        self.num_mutations_tried = 0
        self.num_mutations_kept = 0
        self.attempt_log = output_dir / "logs" / "hdd_attempts.jsonl"
        self.best_schema: Any | None = None
        self.initial_classification: Classification | None = None
        self.best_classification: Classification | None = None

    def classify(self, schema: Any) -> Classification:
        self.deadline.check()
        timeout = max(0.1, self.deadline.remaining())
        return classify_case(
            self.engine,
            schema,
            self.case.instance,
            timeout=timeout,
            exec_mode=self.exec_mode,
            debug=self.debug,
        )

    def preserves_failure(self, schema: Any) -> tuple[bool, Classification]:
        result = self.classify(schema)
        return result.status == self.case.failure_type, result

    def log_attempt(self, mutation: Mutation, kept: bool, result: Classification) -> None:
        write_jsonl(
            self.attempt_log,
            {
                "schema_id": self.case.schema_id,
                "test_id": self.case.test_id,
                "test_index": self.case.test_index,
                "failure_type": self.case.failure_type,
                "mutation_type": mutation.mutation_type,
                "path": path_text(mutation.path),
                "keyword": mutation.keyword,
                "kept": kept,
                "result": result.status,
                "validator_status": result.validator_status,
                "outlines_result": result.outlines_result,
                "error_type": result.error_type,
                "error_message": result.error_message[:500],
            },
        )

    def try_reduce_node(self, schema: Any, path: tuple[Any, ...]) -> Any | None:
        self.deadline.check()
        for mutation in local_mutations(schema, path):
            self.deadline.check()
            self.num_mutations_tried += 1
            try:
                candidate = mutation.apply(schema)
                kept, result = self.preserves_failure(candidate)
            except CaseTimeout:
                raise
            except Exception as exc:
                result = Classification("RUNTIME_ERROR", "UNKNOWN", "NOT_RUN", type(exc).__name__, str(exc))
                kept = False
            self.log_attempt(mutation, kept, result)
            if kept:
                self.num_mutations_kept += 1
                self.best_classification = result
                return candidate

        for child in child_schema_paths(schema, path):
            reduced = self.try_reduce_node(schema, child)
            if reduced is not None:
                return reduced
        return None

    def minimize(self, schema: Any) -> tuple[Any, Classification, Classification, str, str, str]:
        self.best_schema = deepcopy(schema)
        initial = self.classify(schema)
        self.initial_classification = initial
        self.best_classification = initial
        if initial.status != self.case.failure_type:
            if initial.status == "TIMEOUT":
                return schema, initial, initial, "timeout", initial.error_type, initial.error_message
            if initial.status == "COMPILE_ERROR":
                return schema, initial, initial, "compile_error", initial.error_type, initial.error_message
            if initial.status == "RUNTIME_ERROR":
                return schema, initial, initial, "runtime_error", initial.error_type, initial.error_message
            return schema, initial, initial, "failed_initial_not_reproduced", initial.error_type, initial.error_message

        current = deepcopy(schema)
        while True:
            self.deadline.check()
            candidate = self.try_reduce_node(current, ())
            if candidate is None:
                break
            current = candidate
            self.best_schema = deepcopy(current)
        final = self.classify(current)
        return current, initial, final, "success", final.error_type, final.error_message


def build_engine(args: argparse.Namespace) -> Any:
    global _OUTLINES_ENGINE

    from transformers import AutoTokenizer
    from maskbench.runner import get_engine

    runner_args = argparse.Namespace(
        xgr=False,
        xgr_compliant=False,
        xgr_cpp=False,
        llg=False,
        outlines=True,
        llamacpp=False,
        multi=False,
        tokenizer=args.tokenizer,
        debug=args.debug,
    )
    engine = get_engine(runner_args)
    engine.tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    engine.init()
    _OUTLINES_ENGINE = engine
    return engine


def output_schema_path(output_dir: Path, case: Case) -> Path:
    subdir = "under" if case.failure_type == "UNDER" else "over"
    name = f"{case.failure_type}__{safe_name(case.schema_id)}__test_{safe_name(case.test_id)}.json"
    return output_dir / "minimized_schemas" / subdir / name


def has_pattern(schema: Any, pattern: tuple[str, ...]) -> bool:
    def visit(value: Any, index: int) -> bool:
        if index >= len(pattern):
            return True
        if isinstance(value, dict):
            for key, child in value.items():
                next_index = index + 1 if key == pattern[index] else index
                if next_index >= len(pattern):
                    return True
                if visit(child, next_index):
                    return True
        elif isinstance(value, list):
            return any(visit(child, index) for child in value)
        return False

    return visit(schema, 0)


def summarize_outputs(output_dir: Path, case_rows: list[dict[str, Any]]) -> None:
    summaries_dir = output_dir / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    saved_rows = [
        row
        for row in case_rows
        if row["hdd_status"] in {"success", "timeout"} and row["minimized_schema_path"]
    ]
    schemas_by_type: dict[str, list[tuple[dict[str, Any], Any]]] = defaultdict(list)
    for row in saved_rows:
        schema = load_json(resolve_stored_path(row["minimized_schema_path"]))
        schemas_by_type[row["failure_type"]].append((row, schema))

    operator_rows: list[dict[str, Any]] = []
    for failure_type, entries in sorted(schemas_by_type.items()):
        denominator = len(entries) or 1
        for keyword in KEYWORDS:
            present = [(row, schema) for row, schema in entries if keyword in set(iter_keywords(schema))]
            if not present:
                continue
            avg_reduction = sum(float(row["reduction_ratio"]) for row, _ in present) / len(present)
            operator_rows.append(
                {
                    "failure_type": failure_type,
                    "keyword": keyword,
                    "count_schemas": len(present),
                    "percentage": len(present) / denominator,
                    "avg_reduction_ratio": avg_reduction,
                }
            )

    write_csv(
        summaries_dir / "hdd_operator_summary.csv",
        ["failure_type", "keyword", "count_schemas", "percentage", "avg_reduction_ratio"],
        operator_rows,
    )

    pattern_rows: list[dict[str, Any]] = []
    for failure_type, entries in sorted(schemas_by_type.items()):
        denominator = len(entries) or 1
        for pattern in NESTED_PATTERNS:
            count = sum(1 for _, schema in entries if has_pattern(schema, pattern))
            if count:
                pattern_rows.append(
                    {
                        "failure_type": failure_type,
                        "pattern": " -> ".join(pattern),
                        "count_schemas": count,
                        "percentage": count / denominator,
                    }
                )

    write_csv(
        summaries_dir / "hdd_nested_patterns_summary.csv",
        ["failure_type", "pattern", "count_schemas", "percentage"],
        pattern_rows,
    )
    write_report(output_dir, case_rows, operator_rows, pattern_rows)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_report(
    output_dir: Path,
    case_rows: list[dict[str, Any]],
    operator_rows: list[dict[str, Any]],
    pattern_rows: list[dict[str, Any]],
) -> None:
    status_counts = Counter(row["hdd_status"] for row in case_rows)
    failure_counts = Counter(row["failure_type"] for row in case_rows)
    success_rows = [row for row in case_rows if row["hdd_status"] == "success"]
    saved_rows = [
        row
        for row in case_rows
        if row["hdd_status"] in {"success", "timeout"} and row["minimized_schema_path"]
    ]
    avg_original = sum(int(row["original_schema_size_chars"]) for row in case_rows) / max(len(case_rows), 1)
    avg_minimized = sum(int(row["minimized_schema_size_chars"]) for row in saved_rows) / max(len(saved_rows), 1)
    avg_reduction = sum(float(row["reduction_ratio"]) for row in saved_rows) / max(len(saved_rows), 1)

    def top_table(rows: list[dict[str, Any]], group_key: str, value_key: str, failure_type: str) -> list[str]:
        selected = [row for row in rows if row["failure_type"] == failure_type]
        selected.sort(key=lambda row: int(row["count_schemas"]), reverse=True)
        return [f"- {row[group_key]}: {row['count_schemas']} ({float(row['percentage']):.1%})" for row in selected[:10]]

    examples = saved_rows[:5]
    lines = [
        "# HDD Minimization Report",
        "",
        "- dataset: Github_medium",
        "- framework: outlines",
        f"- UNDER candidate cases processed: {failure_counts['UNDER']}",
        f"- OVER candidate cases processed: {failure_counts['OVER']}",
        f"- total cases processed: {len(case_rows)}",
        f"- successful minimizations: {status_counts['success']}",
        f"- failures: {len(case_rows) - status_counts['success'] - status_counts['timeout']}",
        f"- timeouts: {status_counts['timeout']}",
        f"- average original schema size chars: {avg_original:.1f}",
        f"- average minimized schema size chars: {avg_minimized:.1f}",
        f"- average reduction ratio: {avg_reduction:.3f}",
        "",
        "## Top UNDER Keywords",
        *top_table(operator_rows, "keyword", "count_schemas", "UNDER"),
        "",
        "## Top OVER Keywords",
        *top_table(operator_rows, "keyword", "count_schemas", "OVER"),
        "",
        "## Top UNDER Nested Patterns",
        *top_table(pattern_rows, "pattern", "count_schemas", "UNDER"),
        "",
        "## Top OVER Nested Patterns",
        *top_table(pattern_rows, "pattern", "count_schemas", "OVER"),
        "",
        "## Examples",
    ]
    for row in examples:
        lines.append(f"- {row['failure_type']} {row['schema_id']} test {row['test_index']}: {row['minimized_schema_path']}")
    lines.extend(
        [
            "",
            "## Interpretation Note",
            "",
            "HDD reduces schemas while preserving the same mismatch. Operators that remain in minimized schemas are candidate structures for follow-up analysis; they are not automatically proven root causes.",
        ]
    )
    (output_dir / "hdd_minimization_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def case_row(
    case: Case,
    original_schema: Any,
    minimized_schema: Any,
    minimized_path: Path | None,
    status: str,
    original_classification: Classification,
    final_classification: Classification,
    minimizer: Minimizer,
    timeout: bool,
    error_type: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    original_size = json_size(original_schema)
    minimized_size = json_size(minimized_schema)
    reduction = 1.0 - (minimized_size / original_size if original_size else 1.0)
    return {
        "schema_id": case.schema_id,
        "test_id": case.test_id,
        "test_index": case.test_index,
        "failure_type": case.failure_type,
        "hdd_status": status,
        "original_schema_path": stored_path(case.schema_path),
        "minimized_schema_path": "" if minimized_path is None else stored_path(minimized_path),
        "original_schema_size_chars": original_size,
        "minimized_schema_size_chars": minimized_size,
        "reduction_ratio": reduction,
        "original_keyword_count": keyword_count(original_schema),
        "minimized_keyword_count": keyword_count(minimized_schema),
        "original_expected_validity": original_classification.validator_status,
        "minimized_expected_validity": final_classification.validator_status,
        "outlines_result_on_original": original_classification.outlines_result,
        "outlines_result_on_minimized": final_classification.outlines_result,
        "num_mutations_tried": minimizer.num_mutations_tried,
        "num_mutations_kept": minimizer.num_mutations_kept,
        "timeout": timeout,
        "error_type": error_type,
        "error_message": error_message[:1000],
    }


def run_case(engine: Any, case: Case, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    payload = load_json(case.schema_path)
    original_schema = payload["schema"]
    deadline = Deadline(args.timeout_per_case)
    minimizer = Minimizer(engine, case, output_dir, deadline, exec_mode=args.outlines_exec_mode, debug=args.debug)
    minimized_schema = deepcopy(original_schema)
    minimized_path: Path | None = None
    original_classification = Classification("RUNTIME_ERROR", "UNKNOWN", "NOT_RUN")
    final_classification = original_classification
    status = "runtime_error"
    error_type = ""
    error_message = ""
    timed_out = False

    try:
        (
            minimized_schema,
            original_classification,
            final_classification,
            status,
            error_type,
            error_message,
        ) = minimizer.minimize(original_schema)
        timed_out = status == "timeout"
        if status == "success":
            minimized_path = output_schema_path(output_dir, case)
            write_json(minimized_path, minimized_schema)
    except CaseTimeout as exc:
        timed_out = True
        status = "timeout"
        error_type = type(exc).__name__
        error_message = str(exc)
        minimized_schema = minimizer.best_schema if minimizer.best_schema is not None else minimized_schema
        if minimizer.initial_classification is not None:
            original_classification = minimizer.initial_classification
        if minimizer.best_classification is not None:
            final_classification = minimizer.best_classification
        minimized_path = output_schema_path(output_dir, case)
        write_json(minimized_path, minimized_schema)
    except Exception as exc:
        status = "runtime_error"
        error_type = type(exc).__name__
        error_message = str(exc)

    return case_row(
        case,
        original_schema,
        minimized_schema,
        minimized_path,
        status,
        original_classification,
        final_classification,
        minimizer,
        timed_out,
        error_type,
        error_message,
    )


def fallback_case_row(case: Case, status: str, error_type: str, error_message: str) -> dict[str, Any]:
    payload = load_json(case.schema_path)
    original_schema = payload["schema"]
    validation = validate_instance(original_schema, case.instance)
    if validation.schema_valid:
        validator_status = "VALID" if validation.instance_valid else "INVALID"
    else:
        validator_status = "INVALID_SCHEMA"
    outlines_result = "TIMEOUT" if status == "timeout" else "NOT_RUN"
    classification = Classification(
        status.upper() if status != "timeout" else "TIMEOUT",
        validator_status,
        outlines_result,
        error_type,
        error_message,
        validation.validator_error_keyword,
        validation.validator_error_path,
        validation.validator_error_schema_path,
    )
    return case_row(
        case,
        original_schema,
        original_schema,
        None,
        status,
        classification,
        classification,
        MutationStats(),
        status == "timeout",
        error_type,
        error_message,
    )


def isolated_case_worker(case: Case, args_dict: dict[str, Any], output_dir_text: str, conn: Any) -> None:
    try:
        args = argparse.Namespace(**args_dict)
        output_dir = Path(output_dir_text)
        engine = build_engine(args)
        row = run_case(engine, case, args, output_dir)
        conn.send(("row", row))
    except BaseException as exc:
        conn.send(("error", type(exc).__name__, str(exc)))
    finally:
        conn.close()


def run_case_isolated(case: Case, args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    args_dict = vars(args).copy()
    args_dict["outlines_exec_mode"] = "inprocess"
    proc = ctx.Process(target=isolated_case_worker, args=(case, args_dict, str(output_dir), child_conn))
    proc.start()
    child_conn.close()

    timeout = max(args.timeout_per_case + args.case_timeout_grace_seconds, args.timeout_per_case)
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join(5)
        parent_conn.close()
        return fallback_case_row(
            case,
            "timeout",
            "CaseWorkerTimeout",
            f"isolated case exceeded {timeout:.3f}s",
        )

    try:
        if parent_conn.poll():
            message = parent_conn.recv()
            parent_conn.close()
            kind = message[0]
            if kind == "row":
                return message[1]
            return fallback_case_row(case, "runtime_error", str(message[1]), str(message[2]))
    except EOFError:
        parent_conn.close()

    if proc.exitcode and proc.exitcode < 0:
        return fallback_case_row(
            case,
            "runtime_error",
            "ProcessTerminated",
            f"isolated case worker terminated by signal {-proc.exitcode}",
        )
    return fallback_case_row(
        case,
        "runtime_error",
        "ProcessTerminated",
        f"isolated case worker exited without result rc={proc.exitcode}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimize Outlines UNDER/OVER mismatches with greedy HDD.")
    parser.add_argument("--dataset", default="Github_medium", choices=["Github_medium"])
    parser.add_argument("--framework", default="outlines", choices=["outlines"])
    parser.add_argument("--failure-type", default="both", choices=["under", "over", "both"])
    parser.add_argument("--mode", default="one_case_per_schema", choices=["one_case_per_schema", "all_tests"])
    parser.add_argument("--max-schemas", type=int, default=None)
    parser.add_argument("--timeout-per-case", type=float, default=120.0)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--results-jsonl",
        default=str(DEFAULT_RESULTS / "outlines" / "Github_medium" / "per_test_results.jsonl"),
    )
    parser.add_argument("--tokenizer", default="unsloth/Meta-Llama-3.1-8B-Instruct")
    parser.add_argument(
        "--outlines-exec-mode",
        default="subprocess",
        choices=["subprocess", "inprocess"],
        help="Use subprocess for hard timeouts and memory isolation, or inprocess for faster but less robust runs.",
    )
    parser.add_argument(
        "--case-exec-mode",
        default="same-process",
        choices=["same-process", "isolated-process"],
        help="Run each HDD case in the main process or in an isolated worker process.",
    )
    parser.add_argument(
        "--case-timeout-grace-seconds",
        type=float,
        default=60.0,
        help="Extra parent-side timeout for isolated workers, on top of --timeout-per-case.",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite summary CSV/log files in output-dir.")
    return parser.parse_args()


def reset_output_dir(output_dir: Path) -> None:
    try:
        shutil.rmtree(output_dir)
    except OSError:
        stale_dir = output_dir.with_name(f"{output_dir.name}_stale_nfs_{int(time.time())}")
        output_dir.rename(stale_dir)
        print(f"Moved busy output dir to {stale_dir}", file=sys.stderr)


def write_csv_header(path: Path, fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    if args.overwrite and output_dir.exists():
        reset_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (output_dir / "summaries").mkdir(parents=True, exist_ok=True)
    (output_dir / "minimized_schemas" / "under").mkdir(parents=True, exist_ok=True)
    (output_dir / "minimized_schemas" / "over").mkdir(parents=True, exist_ok=True)

    case_csv = output_dir / "hdd_minimized_cases.csv"
    attempts_jsonl = output_dir / "logs" / "hdd_attempts.jsonl"

    cases = select_cases(args)
    print(f"Selected {len(cases)} cases", file=sys.stderr)
    engine = None
    if args.case_exec_mode == "same-process":
        engine = build_engine(args)
    elif args.outlines_exec_mode != "inprocess":
        print("Using inprocess Outlines evaluation inside isolated case workers.", file=sys.stderr)

    fieldnames = [
        "schema_id",
        "test_id",
        "test_index",
        "failure_type",
        "hdd_status",
        "original_schema_path",
        "minimized_schema_path",
        "original_schema_size_chars",
        "minimized_schema_size_chars",
        "reduction_ratio",
        "original_keyword_count",
        "minimized_keyword_count",
        "original_expected_validity",
        "minimized_expected_validity",
        "outlines_result_on_original",
        "outlines_result_on_minimized",
        "num_mutations_tried",
        "num_mutations_kept",
        "timeout",
        "error_type",
        "error_message",
    ]

    rows: list[dict[str, Any]] = []
    write_csv_header(case_csv, fieldnames)
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case.failure_type} {case.schema_id} test={case.test_index}", file=sys.stderr)
        if args.case_exec_mode == "isolated-process":
            row = run_case_isolated(case, args, output_dir)
        else:
            row = run_case(engine, case, args, output_dir)
        rows.append(row)
        append_csv_row(case_csv, fieldnames, row)

    summarize_outputs(output_dir, rows)
    print(f"Wrote HDD outputs under {output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
