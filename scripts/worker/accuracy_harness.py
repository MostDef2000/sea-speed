#!/usr/bin/env python3
"""Offline accuracy harness for predeclared pass/non-pass cases.

Reads a UTF-8 JSON array of ``{id, truth, outcome}`` records, scores the
closed confusion-matrix contract and writes a deterministic JSON report.
Stdlib only: no network, no git query, and no clock, hostname, cwd, output
path or input iteration order is recorded in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CONTRACT_ID = "sea_speed_accuracy_report_v1"
FIELDS = {"id", "truth", "outcome"}
TRUTHS = {"pass", "non_pass"}
OUTCOMES = {"pass", "non_pass", "unknown"}
MICRO = 1_000_000


class InputError(ValueError):
    """The pairs file does not satisfy the closed input contract."""


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise InputError("record contains a duplicated JSON object key")
    return dict(pairs)


def load_rows(path: Path) -> list[dict[str, str]]:
    """Validate the whole input before any report file is touched."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read pairs file: {exc}") from exc
    try:
        data = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"pairs file is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise InputError("pairs file must contain a JSON array")
    if not data:
        raise InputError("no cases: pairs file is empty")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, record in enumerate(data):
        if not isinstance(record, dict):
            raise InputError(f"case {index}: record must be a JSON object")
        missing = sorted(FIELDS - set(record))
        extra = sorted(set(record) - FIELDS)
        if missing or extra:
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unexpected " + ", ".join(extra))
            raise InputError(f"case {index}: " + "; ".join(details))
        if any(not isinstance(record[name], str) for name in FIELDS):
            raise InputError(f"case {index}: id, truth and outcome must be strings")
        case_id = record["id"]
        if not case_id.strip():
            raise InputError(f"case {index}: id must be nonblank")
        if case_id in seen:
            raise InputError(f"case {index}: duplicate id {case_id!r}")
        try:
            case_id.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise InputError(f"case {index}: id is not UTF-8 encodable") from exc
        seen.add(case_id)
        if record["truth"] not in TRUTHS:
            raise InputError(f"case {index}: unknown truth {record['truth']!r}")
        if record["outcome"] not in OUTCOMES:
            raise InputError(f"case {index}: unknown outcome {record['outcome']!r}")
        rows.append({"id": case_id, "truth": record["truth"], "outcome": record["outcome"]})
    return rows


def confusion_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {cell: 0 for cell in "ABCDEF"}
    for row in rows:
        if row["truth"] == "pass":
            counts[{"pass": "A", "non_pass": "B", "unknown": "C"}[row["outcome"]]] += 1
        else:
            counts[{"pass": "D", "non_pass": "E", "unknown": "F"}[row["outcome"]]] += 1
    return counts


def rounded_rate(numerator: int, denominator: int) -> float | None:
    """Exact fraction to 6 decimals, nearest with ties to even; null if 0/0."""
    if denominator == 0:
        return None
    whole, remainder = divmod(numerator * MICRO, denominator)
    if remainder * 2 > denominator or (remainder * 2 == denominator and whole % 2):
        whole += 1
    return whole / MICRO


def dataset_fingerprint(rows: list[dict[str, str]]) -> str:
    """SHA256 of canonical JSON of the validated rows sorted by id."""
    ordered = sorted(rows, key=lambda row: row["id"])
    canonical = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_report(rows: list[dict[str, str]]) -> dict[str, object]:
    counts = confusion_counts(rows)
    return {
        "contract": CONTRACT_ID,
        "counts": counts,
        "dataset_sha256": dataset_fingerprint(rows),
        "rates": {
            "false_pass_rate_on_violation": rounded_rate(
                counts["D"], counts["D"] + counts["E"] + counts["F"]
            ),
            "recognized_accuracy": rounded_rate(
                counts["A"] + counts["E"], counts["A"] + counts["B"] + counts["D"] + counts["E"]
            ),
            "unknown_fraction": rounded_rate(counts["C"] + counts["F"], len(rows)),
        },
    }


def serialize(report: dict[str, object]) -> bytes:
    text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    return text.encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline accuracy harness (no network, no mutation).")
    parser.add_argument("--pairs", type=Path, required=True, help="UTF-8 JSON array of {id, truth, outcome}")
    parser.add_argument("--output", type=Path, required=True, help="deterministic JSON report path")
    args = parser.parse_args(argv)
    try:
        rows = load_rows(args.pairs)
    except InputError as exc:
        print(f"invalid pairs input: {exc}", file=sys.stderr)
        return 2
    payload = serialize(build_report(rows))
    try:
        args.output.write_bytes(payload)
    except OSError as exc:
        print(f"cannot write report: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
