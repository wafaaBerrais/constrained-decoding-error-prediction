#!/usr/bin/env python3
"""Summarize schema/test/framework result statistics.

Reads extension_jsonschemabench/results/schema_test_framework_index.csv by
default and reports counts for executed results, correctness, under/over
constraint cases, compile errors, and useful examples.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
EXT_ROOT = ROOT / "extension_jsonschemabench"
DEFAULT_CSV = EXT_ROOT / "results" / "schema_test_framework_index.csv"
DEFAULT_REPORT = EXT_ROOT / "reports" / "constraint_stats_report.md"


def rel(path: Path | str) -> str:
    p = Path(path)
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(part: int, total: int) -> str:
    if total == 0:
        return "0.00%"
    return f"{(part / total) * 100:.2f}%"


def table(title: str, counts: Counter[str], total: int | None = None) -> list[str]:
    lines = [f"## {title}", ""]
    if not counts:
        return lines + ["No rows.", ""]
    if total is None:
        total = sum(counts.values())
    lines += ["| Value | Count | Share |", "| --- | ---: | ---: |"]
    for key, value in counts.most_common():
        lines.append(f"| `{key or '<empty>'}` | {value} | {pct(value, total)} |")
    lines.append("")
    return lines


def examples(title: str, rows: Iterable[dict[str, str]], limit: int) -> list[str]:
    selected = list(rows)[:limit]
    lines = [f"## {title}", ""]
    if not selected:
        return lines + ["No examples.", ""]

    lines += [
        "| framework | dataset | schema_id | test_id | expected | actual | constraint_case |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in selected:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row.get('framework', '')}`",
                    f"`{row.get('dataset_id', '')}`",
                    f"`{row.get('schema_id', '')}`",
                    f"`{row.get('test_id', '')}`",
                    f"`{row.get('expected_validity', '')}`",
                    f"`{row.get('actual_result', '')}`",
                    f"`{row.get('constraint_case', '')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def summarize(rows: list[dict[str, str]], framework: str | None, example_limit: int) -> str:
    if framework:
        rows = [row for row in rows if row.get("framework") == framework]

    executed = [row for row in rows if row.get("result_available") == "true"]
    unavailable = [row for row in rows if row.get("result_available") != "true"]
    problematic = [
        row
        for row in executed
        if row.get("constraint_case") in {"under_constraint", "over_constraint", "compile_error"}
        or row.get("actual_result") not in {"passed"}
    ]

    lines: list[str] = []
    lines.append("# Constraint Result Statistics")
    lines.append("")
    lines.append(f"- Source CSV: `{rel(DEFAULT_CSV)}`")
    if framework:
        lines.append(f"- Framework filter: `{framework}`")
    else:
        lines.append("- Framework filter: all frameworks")
    lines.append(f"- Rows scanned: {len(rows)}")
    lines.append(f"- Executed rows: {len(executed)} ({pct(len(executed), len(rows))})")
    lines.append(f"- Rows without real result: {len(unavailable)} ({pct(len(unavailable), len(rows))})")
    lines.append(f"- Problematic executed rows: {len(problematic)} ({pct(len(problematic), len(executed))})")
    lines.append("")

    lines += table("Frameworks", Counter(row.get("framework", "") for row in rows), len(rows))
    lines += table("Datasets", Counter(row.get("dataset_id", "") for row in executed), len(executed))
    lines += table("Expected Validity", Counter(row.get("expected_validity", "") for row in executed), len(executed))
    lines += table("Actual Results", Counter(row.get("actual_result", "") for row in executed), len(executed))
    lines += table("Constraint Cases", Counter(row.get("constraint_case", "") for row in executed), len(executed))

    by_framework: dict[str, Counter[str]] = defaultdict(Counter)
    for row in executed:
        by_framework[row.get("framework", "")][row.get("constraint_case", "")] += 1

    lines += ["## Constraint Cases By Framework", ""]
    if not by_framework:
        lines += ["No executed framework rows.", ""]
    else:
        lines += [
            "| framework | executed | correct | under_constraint | over_constraint | compile_error | unknown |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name in sorted(by_framework):
            counts = by_framework[name]
            total = sum(counts.values())
            lines.append(
                f"| `{name}` | {total} | {counts['correct']} | {counts['under_constraint']} | "
                f"{counts['over_constraint']} | {counts['compile_error']} | {counts['unknown']} |"
            )
        lines.append("")

    by_dataset: dict[str, Counter[str]] = defaultdict(Counter)
    for row in executed:
        by_dataset[row.get("dataset_id", "")][row.get("constraint_case", "")] += 1

    lines += ["## Constraint Cases By Dataset", ""]
    if not by_dataset:
        lines += ["No executed dataset rows.", ""]
    else:
        lines += [
            "| dataset | executed | correct | under_constraint | over_constraint | compile_error | unknown |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name in sorted(by_dataset):
            counts = by_dataset[name]
            total = sum(counts.values())
            lines.append(
                f"| `{name or '<empty>'}` | {total} | {counts['correct']} | {counts['under_constraint']} | "
                f"{counts['over_constraint']} | {counts['compile_error']} | {counts['unknown']} |"
            )
        lines.append("")

    cross = Counter(
        (
            row.get("expected_validity", ""),
            row.get("actual_result", ""),
            row.get("constraint_case", ""),
        )
        for row in executed
    )
    lines += ["## Expected vs Actual vs Constraint", ""]
    if not cross:
        lines += ["No executed rows.", ""]
    else:
        lines += ["| expected | actual_result | constraint_case | count |", "| --- | --- | --- | ---: |"]
        for (expected, actual, case), count in cross.most_common():
            lines.append(f"| `{expected}` | `{actual}` | `{case}` | {count} |")
        lines.append("")

    lines += examples(
        "Under-Constraint Examples",
        (row for row in executed if row.get("constraint_case") == "under_constraint"),
        example_limit,
    )
    lines += examples(
        "Over-Constraint Examples",
        (row for row in executed if row.get("constraint_case") == "over_constraint"),
        example_limit,
    )
    lines += examples(
        "Compile Error Examples",
        (row for row in executed if row.get("constraint_case") == "compile_error"),
        example_limit,
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize under/over-constraint statistics.")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to schema_test_framework_index.csv.")
    parser.add_argument("--framework", default=None, help="Optional exact framework name, for example XGrammar.")
    parser.add_argument("--examples", type=int, default=10, help="Number of examples per problem type.")
    parser.add_argument("--output", default=None, help="Optional Markdown report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    rows = load_rows(csv_path)
    report = summarize(rows, args.framework, args.examples)

    if args.output:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
    else:
        output = DEFAULT_REPORT

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {rel(output)}")


if __name__ == "__main__":
    main()
