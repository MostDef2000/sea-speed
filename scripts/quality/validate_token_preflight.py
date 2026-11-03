#!/usr/bin/env python3
"""Validate the repo-owned token inventory and pre-flight its credentials (issue #583).

The token inventory (``data/contracts/token-inventory-v1.json``) is the single
repo-owned record of every GitHub credential the delivery pipeline depends on.
This stdlib-only validator is the local and CI gate over that record:

- offline mode (default) validates the inventory schema and evaluates the
  expiry/review dates as of today (or ``--today``). It performs NO network
  requests, reads NO credential environment variables and NO host files;
- probe mode (``--probe``) additionally reads the credential environment
  variable named by each ``api-zen`` entry's ``credential_pointer`` and
  performs ``GET https://api.github.com/zen`` with a Bearer header, a fixed
  User-Agent, a 10s timeout, redirects disabled and TLS verification.
  200 -> PROBE-OK; 401 -> PROBE-UNAUTHORIZED (no retry); 403 ->
  PROBE-FORBIDDEN (no retry); 5xx/network/timeout -> 3 attempts total with
  1s then 2s sleeps; any other status fails without retry. Response bodies,
  headers, raw exceptions and credential values are never printed.

Output is one line per finding (``<MARKER>: <token-name> <short safe detail>``)
with errors on stderr and info/warnings on stdout, followed by exactly
``TOKEN-PREFLIGHT PASS`` or ``TOKEN-PREFLIGHT FAIL``. Exit 0 = pass, 1 = fail,
2 = usage error. In probe mode a sanitized section is appended to
``GITHUB_STEP_SUMMARY`` on PASS and FAIL; an unwritable summary path is
``SUMMARY-WRITE-FAILED`` + exit 1. Credential-shaped strings are never echoed:
schema violations name the record index and field only, and any
credential-shaped string inside the inventory is rejected outright.

The observable CLI surface (exit codes, markers, module seams) is pinned by
``tests/test_token_preflight.py``; the runbook is
``docs/operations/TOKEN_PREFLIGHT.md``.
"""
from __future__ import annotations

import argparse
import contextlib
import email.message
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import IO, Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "sea-speed-token-inventory/v1"
WARNING_DAYS = 21
DEFAULT_INVENTORY = REPO_ROOT / "data" / "contracts" / "token-inventory-v1.json"
ZEN_URL = "https://api.github.com/zen"
USER_AGENT = "sea-speed-token-preflight/1.0"
PROBE_TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 3
RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0)

_ROOT_KEYS = {"schema", "tokens"}
_TOKEN_KEYS = {
    "name", "kind", "expiry_status", "expiry", "review_date",
    "probe", "credential_pointer", "expected_scopes", "note",
}
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KINDS = frozenset({"classic", "fine-grained"})
_EXPIRY_STATUSES = frozenset({"dated", "no-expiry", "unknown"})
_PROBES = frozenset({"none", "api-zen"})
_RESERVED_PROBE_ENV = frozenset({"GITHUB_TOKEN", "GH_TOKEN"})

# Credential-shaped strings must never appear in any inventory string field.
# Findings name the record index and field only — content is never echoed.
_CREDENTIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub classic token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b")),
    ("private key material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("JWT-shaped credential", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b")),
    ("Authorization header assignment", re.compile(r"(?i)\bauthorization\s*:")),
)


class InventoryError(ValueError):
    """One clear inventory failure reason, reported by main()."""


class Finding(NamedTuple):
    """One output line: severity routes the stream, the rest is sanitized."""

    severity: str  # "error" | "warn" | "info"
    marker: str
    name: str
    detail: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """object_pairs_hook that rejects duplicate JSON keys fail-closed."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("duplicate JSON key in inventory (key name withheld)")
        result[key] = value
    return result


def load_inventory(path: Path) -> dict[str, Any]:
    """Read and parse the inventory JSON, rejecting duplicate keys."""
    if not path.is_file():
        raise InventoryError(f"inventory file is missing: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InventoryError("inventory file is not valid UTF-8") from exc
    except OSError as exc:
        raise InventoryError(f"inventory file cannot be read: {exc.strerror}") from exc
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise InventoryError(f"inventory is not valid JSON (line {exc.lineno})") from exc
    if not isinstance(data, dict):
        raise InventoryError("inventory root must be a JSON object")
    return data


def _credential_findings(value: Any, path: str) -> list[tuple[str, str]]:
    """Return (field path, label) for every credential-shaped string below value."""
    hits: list[tuple[str, str]] = []
    if isinstance(value, str):
        for label, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(value):
                hits.append((path, label))
    elif isinstance(value, list):
        for offset, item in enumerate(value):
            hits.extend(_credential_findings(item, f"{path}[{offset}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            hits.extend(_credential_findings(item, f"{path}.{key}"))
    return hits


def _display_name(index: int, token: dict[str, Any]) -> str:
    """Safe name for output: the token name, or its index if unusable."""
    raw = token.get("name")
    if isinstance(raw, str) and _NAME_RE.fullmatch(raw) and not _credential_findings(raw, "name"):
        return raw
    return f"token[{index}]"


def _date_field_error(value: Any, field: str) -> str | None:
    """Null-or-strict-YYYY-MM-DD check; return the error detail or None."""
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        return f"{field} must be null or a strict YYYY-MM-DD string"
    try:
        date.fromisoformat(value)
    except ValueError:
        return f"{field} is not a valid calendar date (YYYY-MM-DD)"
    return None


def _none_pointer_error(pointer: Any) -> str | None:
    """probe: none pointers may be null, an env name, or an absolute POSIX path."""
    if pointer is None:
        return None
    if not isinstance(pointer, str):
        return "credential_pointer must be null or a string"
    if _ENV_NAME_RE.fullmatch(pointer):
        return None
    if not pointer.startswith("/"):
        return "credential_pointer must be null, an env var name, or an absolute POSIX path"
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in pointer):
        return "credential_pointer path must not contain whitespace or control characters"
    if ".." in pointer:
        return "credential_pointer path must not contain '..'"
    if "://" in pointer:
        return "credential_pointer path must not contain '://'"
    return None


def _validate_token(index: int, token: Any, seen_names: set[str]) -> list[Finding]:
    """Schema-validate one token record; collect every violation."""
    if not isinstance(token, dict):
        return [Finding("error", "SCHEMA-ERROR", f"token[{index}]", "token must be a JSON object")]
    display = _display_name(index, token)
    findings: list[Finding] = []
    for field_path, label in _credential_findings(token, f"token[{index}]"):
        findings.append(
            Finding("error", "SCHEMA-ERROR", display, f"{label} rejected in {field_path} (content withheld)")
        )
    if set(token.keys()) != _TOKEN_KEYS:
        findings.append(
            Finding("error", "SCHEMA-ERROR", display, f"token keys must be exactly {sorted(_TOKEN_KEYS)}")
        )
        return findings

    name = token["name"]
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        findings.append(
            Finding("error", "SCHEMA-ERROR", display, "name must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
        )
    elif name in seen_names:
        findings.append(Finding("error", "SCHEMA-ERROR", display, "duplicate token name"))
    else:
        seen_names.add(name)

    kind = token["kind"]
    if not isinstance(kind, str) or kind not in _KINDS:
        findings.append(Finding("error", "SCHEMA-ERROR", display, f"kind must be one of {sorted(_KINDS)}"))
    status = token["expiry_status"]
    if not isinstance(status, str) or status not in _EXPIRY_STATUSES:
        findings.append(
            Finding("error", "SCHEMA-ERROR", display, f"expiry_status must be one of {sorted(_EXPIRY_STATUSES)}")
        )
    probe = token["probe"]
    if not isinstance(probe, str) or probe not in _PROBES:
        findings.append(Finding("error", "SCHEMA-ERROR", display, f"probe must be one of {sorted(_PROBES)}"))

    for field in ("expiry", "review_date"):
        error = _date_field_error(token[field], field)
        if error is not None:
            findings.append(Finding("error", "SCHEMA-ERROR", display, error))

    if isinstance(status, str) and status in _EXPIRY_STATUSES:
        if status == "dated" and token["expiry"] is None:
            findings.append(Finding("error", "SCHEMA-ERROR", display, "expiry_status dated requires a non-null expiry"))
        if status != "dated" and token["expiry"] is not None:
            findings.append(Finding("error", "SCHEMA-ERROR", display, "expiry must be null unless expiry_status is dated"))
        if status == "no-expiry" and token["review_date"] is None:
            findings.append(
                Finding("error", "SCHEMA-ERROR", display, "expiry_status no-expiry requires a non-null review_date")
            )

    pointer = token["credential_pointer"]
    if probe == "api-zen":
        if not isinstance(pointer, str) or not _ENV_NAME_RE.fullmatch(pointer):
            findings.append(
                Finding(
                    "error", "SCHEMA-ERROR", display,
                    "probe api-zen requires credential_pointer to name an env var "
                    "(^[A-Z_][A-Z0-9_]*$)",
                )
            )
        elif pointer in _RESERVED_PROBE_ENV:
            findings.append(
                Finding("error", "SCHEMA-ERROR", display, f"probe api-zen must not read the reserved env var {pointer}")
            )
    else:
        error = _none_pointer_error(pointer)
        if error is not None:
            findings.append(Finding("error", "SCHEMA-ERROR", display, error))

    scopes = token["expected_scopes"]
    if scopes is not None:
        if not isinstance(scopes, list):
            findings.append(Finding("error", "SCHEMA-ERROR", display, "expected_scopes must be null or a list"))
        else:
            seen_scopes: set[str] = set()
            for offset, scope in enumerate(scopes):
                if not isinstance(scope, str) or not scope or not scope.isascii():
                    findings.append(
                        Finding("error", "SCHEMA-ERROR", display, f"expected_scopes[{offset}] must be a non-empty ASCII string")
                    )
                elif scope in seen_scopes:
                    findings.append(Finding("error", "SCHEMA-ERROR", display, f"expected_scopes[{offset}] is a duplicate"))
                else:
                    seen_scopes.add(scope)

    note = token["note"]
    if not isinstance(note, str) or not note.strip():
        findings.append(Finding("error", "SCHEMA-ERROR", display, "note must be a non-empty string"))
    elif len(note) > 1000:
        findings.append(Finding("error", "SCHEMA-ERROR", display, "note must be at most 1000 characters"))
    elif "\n" in note or "\r" in note:
        findings.append(Finding("error", "SCHEMA-ERROR", display, "note must be a single line"))

    return findings


def validate_inventory(data: dict[str, Any]) -> list[Finding]:
    """Validate the inventory schema; return every violation as a Finding."""
    findings: list[Finding] = []
    if set(data.keys()) != _ROOT_KEYS:
        findings.append(
            Finding("error", "SCHEMA-ERROR", "inventory", f"root keys must be exactly {sorted(_ROOT_KEYS)}")
        )
        return findings
    if data["schema"] != SCHEMA:
        findings.append(Finding("error", "SCHEMA-ERROR", "inventory", f"schema must be {SCHEMA!r}"))
    for field_path, label in _credential_findings(data.get("schema"), "schema"):
        findings.append(
            Finding("error", "SCHEMA-ERROR", "inventory", f"{label} rejected in {field_path} (content withheld)")
        )
    tokens = data["tokens"]
    if not isinstance(tokens, list) or not tokens:
        findings.append(Finding("error", "SCHEMA-ERROR", "inventory", "tokens must be a non-empty list"))
        return findings
    seen_names: set[str] = set()
    for index, token in enumerate(tokens):
        findings.extend(_validate_token(index, token, seen_names))
    return findings


def _as_date(value: Any) -> date | None:
    """Parse an already-schema-validated date field; None when absent."""
    if isinstance(value, str) and _DATE_RE.fullmatch(value):
        return date.fromisoformat(value)
    return None


def _ok_detail(token: dict[str, Any]) -> str:
    """Short safe detail for an OK date evaluation."""
    parts: list[str] = []
    if token.get("expiry_status") == "no-expiry":
        parts.append("no expiry")
    elif isinstance(token.get("expiry"), str):
        parts.append(f"expiry {token['expiry']}")
    if isinstance(token.get("review_date"), str):
        parts.append(f"review {token['review_date']}")
    return "; ".join(parts) if parts else "within thresholds"


def evaluate_dates(tokens: list[dict[str, Any]], today: date) -> list[Finding]:
    """Evaluate expiry/review dates; date failures never suppress probing."""
    threshold = today + timedelta(days=WARNING_DAYS)
    findings: list[Finding] = []
    for token in tokens:
        name = str(token.get("name", "token"))
        expiry = _as_date(token.get("expiry"))
        review = _as_date(token.get("review_date"))
        failed = False
        if expiry is not None:
            if expiry < today:
                findings.append(Finding("error", "EXPIRED", name, f"expiry {expiry.isoformat()} is in the past"))
                failed = True
            elif expiry <= threshold:
                findings.append(
                    Finding("error", "EXPIRY-DUE", name, f"expiry {expiry.isoformat()} is within {WARNING_DAYS} days")
                )
                failed = True
        if review is not None and review <= threshold:
            findings.append(
                Finding(
                    "error", "REVIEW-DUE", name,
                    f"review date {review.isoformat()} is due within {WARNING_DAYS} days (or overdue)",
                )
            )
            failed = True
        if token.get("expiry_status") == "unknown":
            findings.append(
                Finding("warn", "UNKNOWN-EXPIRY", name, "expiry unknown; owner lookup pending (non-failing)")
            )
            continue
        if not failed:
            findings.append(Finding("info", "OK", name, _ok_detail(token)))
    return findings


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: a 3xx must never forward the Bearer credential."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: email.message.Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


def _close_error_body(exc: urllib.error.HTTPError) -> None:
    """Close the error response body without reading or echoing it."""
    fp = getattr(exc, "fp", None)
    if fp is not None:
        with contextlib.suppress(Exception):
            fp.close()


def fetch_status(credential: str, timeout: float) -> int:
    """GET the zen endpoint with the Bearer credential; return the HTTP status.

    Network/timeout failures raise (the caller retries); HTTP statuses
    (including 3xx surfaced as HTTPError by the no-redirect handler) are
    returned as integers. The response body is never read or echoed.
    """
    request = urllib.request.Request(
        ZEN_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {credential}",
            "User-Agent": USER_AGENT,
            "Accept": "text/plain",
        },
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        _close_error_body(exc)
        return int(exc.code)


def probe_token(name: str, credential: str) -> Finding:
    """Probe one credential with retries; never echo the credential or errors."""
    status: int | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            status = fetch_status(credential, PROBE_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - transport failure; detail never echoed
            status = None
        if status == 200:
            return Finding("info", "PROBE-OK", name, f"GET {ZEN_URL} returned 200")
        if status == 401:
            return Finding("error", "PROBE-UNAUTHORIZED", name, f"GET {ZEN_URL} returned 401 (revoked or wrong secret)")
        if status == 403:
            return Finding("error", "PROBE-FORBIDDEN", name, f"GET {ZEN_URL} returned 403 (missing scope or blocked)")
        if status is not None and not 500 <= status < 600:
            return Finding("error", "PROBE-FAILED", name, f"GET {ZEN_URL} returned unexpected status {status}")
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAYS[attempt - 1])
    if status is None:
        return Finding("error", "PROBE-UNREACHABLE", name, f"GET {ZEN_URL} unreachable after {MAX_ATTEMPTS} attempts")
    return Finding(
        "error", "PROBE-SERVER-ERROR", name,
        f"GET {ZEN_URL} returned {status} after {MAX_ATTEMPTS} attempts",
    )


def _run_probes(tokens: list[dict[str, Any]]) -> list[Finding]:
    """Probe every api-zen entry; probe: none entries are reported, not probed."""
    findings: list[Finding] = []
    for token in tokens:
        name = str(token.get("name", "token"))
        if token.get("probe") != "api-zen":
            findings.append(
                Finding("info", "NOT-PROBED", name, "probe disabled in inventory; coverage is documented, not live")
            )
            continue
        pointer = token.get("credential_pointer")
        if not isinstance(pointer, str) or not pointer:
            findings.append(Finding("error", "MISSING-CREDENTIAL", name, "credential_pointer does not name an env var"))
            continue
        credential = os.environ.get(pointer, "")
        if not credential.strip():
            findings.append(
                Finding("error", "MISSING-CREDENTIAL", name, f"credential env {pointer} is unset or empty (zero requests made)")
            )
            continue
        if credential != credential.strip() or any(ord(char) < 32 or ord(char) == 127 for char in credential):
            findings.append(
                Finding(
                    "error", "INVALID-CREDENTIAL", name,
                    f"credential env {pointer} carries surrounding whitespace or control characters "
                    "(not normalized, not sent)",
                )
            )
            continue
        findings.append(probe_token(name, credential))
    return findings


def write_step_summary(path: Path, findings: list[Finding], passed: bool, today: date) -> Finding | None:
    """Append the sanitized step-summary section; return a Finding on failure."""
    outcome = "PASS" if passed else "FAIL"
    lines = [
        "",
        "## Token pre-flight",
        "",
        f"- Outcome: {outcome}",
        f"- Evaluated (UTC): {today.isoformat()}",
        f"- Expiry and review warning threshold: {WARNING_DAYS} days",
        "- Coverage: date evaluation runs for every inventory entry; only entries"
        " with probe: api-zen perform a live credential probe (probe: none entries"
        " are covered by documentation and out-of-band signals, not by CI).",
        "- Runbook: docs/operations/TOKEN_PREFLIGHT.md",
        "",
    ]
    for finding in findings:
        lines.append(f"- `{finding.marker}` {finding.name}: {finding.detail}")
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        return Finding("error", "SUMMARY-WRITE-FAILED", "step-summary", "could not append the pre-flight section to GITHUB_STEP_SUMMARY")
    return None


def _emit(findings: list[Finding]) -> None:
    """Print one line per finding; errors to stderr, info/warn to stdout."""
    for finding in findings:
        line = f"{finding.marker}: {finding.name} {finding.detail}"
        if finding.severity == "error":
            print(line, file=sys.stderr)
        else:
            print(line)


def _parse_today(value: str) -> date:
    """Argparse type for --today: strict YYYY-MM-DD."""
    if not _DATE_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("--today must be a strict YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--today is not a valid calendar date: {value}") from exc


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: exit 0 pass, 1 fail, 2 usage."""
    parser = argparse.ArgumentParser(
        description="Validate the token inventory schema and dates; --probe additionally "
        "performs the live /zen credential probe for api-zen entries."
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help="token inventory path (default: data/contracts/token-inventory-v1.json)",
    )
    parser.add_argument(
        "--today",
        type=_parse_today,
        default=None,
        help="evaluate dates as of this YYYY-MM-DD UTC date (offline mode only)",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="read credential env vars and probe api.github.com/zen for api-zen entries",
    )
    args = parser.parse_args(argv)
    raw_today: date | None = args.today
    if args.probe and raw_today is not None:
        parser.error("--today cannot be combined with --probe (probe mode always evaluates today's UTC date)")
    today = datetime.now(UTC).date() if raw_today is None else raw_today

    findings: list[Finding] = []
    data: dict[str, Any] | None = None
    try:
        data = load_inventory(args.inventory)
        findings.extend(validate_inventory(data))
    except InventoryError as exc:
        findings.append(Finding("error", "SCHEMA-ERROR", "inventory", str(exc)))

    if data is not None and not any(finding.marker == "SCHEMA-ERROR" for finding in findings):
        tokens: list[dict[str, Any]] = data["tokens"]
        findings.extend(evaluate_dates(tokens, today))
        if args.probe:
            findings.extend(_run_probes(tokens))

    passed = not any(finding.severity == "error" for finding in findings)
    if args.probe:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            failure = write_step_summary(Path(summary_path), findings, passed, today)
            if failure is not None:
                findings.append(failure)
                passed = False
    _emit(findings)
    print("TOKEN-PREFLIGHT PASS" if passed else "TOKEN-PREFLIGHT FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
