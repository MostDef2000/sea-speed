#!/usr/bin/env python3
"""Validate the canonical API dependency lock (issue #579).

The API + test + CI-tooling dependency graph is pinned in
``api/requirements-api.txt`` and resolved by the ``resolve`` job of
``.github/workflows/resolve-runtime-lock.yml`` into the hash-locked
``api/requirements-api.lock.txt``. This stdlib-only validator is the local
and CI gate that the committed lock actually covers the pinned input:

- the lock exists, is non-empty and starts with the ``# sea-speed-api-lock-v1``
  marker (same prepend pattern as the worker runtime lock);
- every ``name==version`` pin from the requirements input is covered by the
  lock (name present, version identical);
- every locked package entry carries at least one ``--hash=sha256:`` digest,
  so installs verify artifact integrity;
- every non-comment, non-empty requirements line is an exact ``name==version``
  pin — no wildcard/specifier versions, no duplicate names — and the lock
  itself carries no option lines (``-r``, ``--index-url``, ...) and no
  unrecognized lines: pip would honor option lines, so a lock containing
  them is not a pure pin list and is rejected fail-closed.

Exit 0 = valid; exit 1 with one clear stderr line otherwise. The observable
CLI surface (exit codes + stderr) is pinned by ``tests/test_api_dependency_lock.py``.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LOCK_MARKER = "# sea-speed-api-lock-v1"
DEFAULT_REQUIREMENTS = Path("api/requirements-api.txt")
DEFAULT_LOCK = Path("api/requirements-api.lock.txt")

# Exact pin: PEP 508 name followed by `==` and an exact non-empty version
# token. No wildcard/specifier syntax (`foo==1.0*` is a specifier, not a
# pin) — the admitted contract is exact pins only.
_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._-]*)$")
# A locked entry line: `name==version` optionally continued with a backslash.
_LOCK_ENTRY_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^ \t\\]+)\s*\\?\s*$")
_HASH_MARKER = "--hash=sha256:"


class LockValidationError(ValueError):
    """One clear failure reason, printed to stderr by main()."""


def _normalize_name(name: str) -> str:
    """PEP 503 name normalization so requirements/lock spellings compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirements(path: Path) -> dict[str, str]:
    """Return {normalized name: pinned version}; reject non-pin lines and duplicates."""
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN_RE.match(line)
        if not match:
            raise LockValidationError(
                f"malformed requirements line in {path}: {line!r} "
                "(expected exactly name==version)"
            )
        name = _normalize_name(match.group(1))
        if name in pins:
            raise LockValidationError(
                f"duplicate requirements pin {name} in {path}: "
                f"{pins[name]} and {match.group(2)}"
            )
        pins[name] = match.group(2)
    return pins


def _store_entry(
    entries: dict[str, tuple[str, int]],
    path: Path,
    entry: tuple[str, str, int],
) -> None:
    """Finalize one parsed lock entry; a duplicate name is a contract violation."""
    name, version, hash_count = entry
    if name in entries:
        raise LockValidationError(f"duplicate lock entry for {name} in {path}")
    entries[name] = (version, hash_count)


def parse_lock(path: Path) -> dict[str, tuple[str, int]]:
    """Parse a uv --generate-hashes lock into {normalized name: (version, hash count)}.

    Handles the uv format: ``name==version \\`` continuation lines followed by
    indented ``--hash=sha256:...`` and ``# via ...`` lines. Comment lines
    (``#`` headers and indented ``# via ...`` provenance) are skipped; option
    lines (``-r``, ``--index-url``, indented ``--extra-index-url``, ...) and
    any other unrecognized line are REJECTED fail-closed — pip would honor
    option lines, so a lock carrying them is not a pure pin list.
    """
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise LockValidationError(f"lock file is missing or empty: {path}")
    lines = text.splitlines()
    if lines[0].strip() != LOCK_MARKER:
        raise LockValidationError(
            f"lock file must start with the marker line {LOCK_MARKER!r}: {path}"
        )
    entries: dict[str, tuple[str, int]] = {}
    current: tuple[str, str, int] | None = None
    for raw in lines[1:]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue  # blank lines, uv header comments, indented "# via ..." provenance
        entry = _LOCK_ENTRY_RE.match(raw)
        if entry:
            if current is not None:
                _store_entry(entries, path, current)
            current = (_normalize_name(entry.group(1)), entry.group(2), 0)
        elif (
            raw.startswith((" ", "\t"))
            and current is not None
            and stripped.startswith(_HASH_MARKER)
        ):
            current = (current[0], current[1], current[2] + 1)
        else:
            # Option lines (-r, --index-url, indented --extra-index-url, ...)
            # and any other unrecognized line: pip would honor option lines,
            # so a lock carrying them is not a pure pin list — reject.
            raise LockValidationError(f"unrecognized lock line in {path}: {raw!r}")
    if current is not None:
        _store_entry(entries, path, current)
    return entries


def validate(requirements_path: Path, lock_path: Path) -> None:
    """Raise LockValidationError with one clear message on the first failure."""
    if not requirements_path.is_file():
        raise LockValidationError(f"requirements file is missing: {requirements_path}")
    if not lock_path.is_file() or not lock_path.read_text(encoding="utf-8").strip():
        raise LockValidationError(f"lock file is missing or empty: {lock_path}")
    pins = parse_requirements(requirements_path)
    entries = parse_lock(lock_path)
    for name, version in pins.items():
        locked = entries.get(name)
        if locked is None:
            raise LockValidationError(
                f"requirements pin {name}=={version} is not covered by the lock "
                f"({lock_path}): name absent"
            )
        locked_version, hash_count = locked
        if locked_version != version:
            raise LockValidationError(
                f"requirements pin {name}=={version} is not covered by the lock "
                f"({lock_path}): locked version is {locked_version}"
            )
    for name, (_version, hash_count) in entries.items():
        if hash_count == 0:
            raise LockValidationError(
                f"locked package {name} in {lock_path} has zero --hash=sha256: lines"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that the API lock covers the pinned requirements "
        "with the marker and per-package sha256 hashes."
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help="pinned requirements input (default: api/requirements-api.txt)",
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=DEFAULT_LOCK,
        help="hash-pinned lock file (default: api/requirements-api.lock.txt)",
    )
    args = parser.parse_args()
    try:
        validate(args.requirements, args.lock)
    except LockValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        f"API dependency lock valid: {args.lock} covers {args.requirements} "
        f"({LOCK_MARKER})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
