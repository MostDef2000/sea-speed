#!/usr/bin/env python3
"""Render narrowly-scoped MediaMTX configuration candidates safely.

The Ubuntu mode reads the credential-bearing camera URL from a protected env
file and never prints it. The VPS mode accepts only a credential-free RFC1918
relay URL. All output files are written mode 0600 because an Ubuntu candidate
can contain camera credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import NamedTuple, Sequence
from urllib.parse import urlsplit


RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
READER_MARKER_CAM1 = "# Sea Speed least-privilege reader for canonical cam1"
READER_MARKER_CAM1_H264 = "# Sea Speed least-privilege reader for canonical cam1-h264"
API_RULE_MARKER = "# Sea Speed loopback API observation rule for the freshness watchdog"
LOOPBACK_API_ADDRESS = "127.0.0.1:9997"
LOOPBACK_IP = "127.0.0.1"
RTSP_TRANSPORTS = {"automatic", "udp", "multicast", "tcp"}


def reader_marker(path_name: str) -> str:
    """Return the least-privilege reader-rule marker for a MediaMTX path.

    cam1 keeps its historical marker so already-deployed configs remain
    recognizable; every other path (e.g. cam1-h264) gets a path-specific marker.
    """
    if path_name == "cam1":
        return READER_MARKER_CAM1
    return f"# Sea Speed least-privilege reader for canonical {path_name}"


class ConfigError(ValueError):
    """Raised when a bounded MediaMTX transformation cannot be proven safe."""


def _split_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _ensure_newline(line: str) -> str:
    return line if line.endswith("\n") else line + "\n"


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _is_rfc1918_ipv4(address: ipaddress._BaseAddress) -> bool:
    return address.version == 4 and any(address in network for network in RFC1918_NETWORKS)


def _find_top_level(lines: list[str], key: str) -> list[int]:
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    return [index for index, line in enumerate(lines) if pattern.match(line)]


def set_top_level_scalar(text: str, key: str, value: str, *, quote: bool) -> str:
    lines = _split_lines(text)
    matches = _find_top_level(lines, key)
    if len(matches) > 1:
        raise ConfigError(f"duplicate top-level MediaMTX key: {key}")
    rendered = f"{key}: {_yaml_string(value) if quote else value}\n"
    if matches:
        lines[matches[0]] = rendered
        return "".join(lines)

    paths = _find_top_level(lines, "paths")
    if len(paths) != 1:
        raise ConfigError("MediaMTX config must contain exactly one top-level paths block")
    lines.insert(paths[0], rendered)
    return "".join(lines)


def get_top_level_scalar(text: str, key: str) -> str | None:
    lines = _split_lines(text)
    matches = _find_top_level(lines, key)
    if len(matches) > 1:
        raise ConfigError(f"duplicate top-level MediaMTX key: {key}")
    if not matches:
        return None
    raw = lines[matches[0]].split(":", 1)[1].strip()
    if not raw or raw.startswith("#"):
        return ""
    raw = raw.split(" #", 1)[0].strip()
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid quoted top-level field: {key}") from exc
        return str(value)
    return raw


def _paths_bounds(lines: list[str]) -> tuple[int, int]:
    matches = _find_top_level(lines, "paths")
    if len(matches) != 1:
        raise ConfigError("MediaMTX config must contain exactly one top-level paths block")
    start = matches[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        if not stripped or line.lstrip().startswith("#"):
            continue
        if line[0] not in " \t":
            end = index
            break
    return start, end


def _path_ranges(lines: list[str], paths_start: int, paths_end: int) -> dict[str, tuple[int, int]]:
    header_re = re.compile(r"^  ([^#\s][^:]*):\s*(?:#.*)?(?:\n)?$")
    starts: list[tuple[str, int]] = []
    for index in range(paths_start + 1, paths_end):
        match = header_re.match(lines[index])
        if match:
            name = match.group(1).strip()
            if name in {existing for existing, _ in starts}:
                raise ConfigError(f"duplicate MediaMTX path: {name}")
            starts.append((name, index))
    ranges: dict[str, tuple[int, int]] = {}
    for position, (name, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else paths_end
        ranges[name] = (start, end)
    return ranges


def set_path_source(
    text: str,
    path_name: str,
    source: str,
    *,
    source_on_demand: bool = True,
    rtsp_transport: str | None = None,
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", path_name):
        raise ConfigError("MediaMTX path name must be a simple literal name")
    if rtsp_transport is not None and rtsp_transport not in RTSP_TRANSPORTS:
        raise ConfigError("unsupported MediaMTX RTSP source transport")
    lines = _split_lines(text)
    paths_start, paths_end = _paths_bounds(lines)
    ranges = _path_ranges(lines, paths_start, paths_end)
    source_line = f"    source: {_yaml_string(source)}\n"
    demand_line = f"    sourceOnDemand: {'yes' if source_on_demand else 'no'}\n"
    transport_line = f"    rtspTransport: {rtsp_transport}\n" if rtsp_transport is not None else None
    managed = "source|sourceOnDemand"
    if rtsp_transport is not None:
        managed += "|rtspTransport"
    field_re = re.compile(rf"^    ({managed})\s*:")

    if path_name in ranges:
        start, end = ranges[path_name]
        kept = [line for line in lines[start + 1 : end] if not field_re.match(line)]
        replacement = [_ensure_newline(lines[start]), source_line, demand_line]
        if transport_line is not None:
            replacement.append(transport_line)
        lines[start:end] = [*replacement, *kept]
        return "".join(lines)

    insertion = paths_end
    block = [f"  {path_name}:\n", source_line, demand_line]
    if transport_line is not None:
        block.append(transport_line)
    if insertion > 0 and lines[insertion - 1].strip():
        block.insert(0, "\n")
    lines[insertion:insertion] = block
    return "".join(lines)


def remove_path(text: str, path_name: str) -> str:
    lines = _split_lines(text)
    paths_start, paths_end = _paths_bounds(lines)
    ranges = _path_ranges(lines, paths_start, paths_end)
    if path_name not in ranges:
        raise ConfigError(f"MediaMTX path is not present: {path_name}")
    start, end = ranges[path_name]
    del lines[start:end]
    return "".join(lines)


def get_path_field(text: str, path_name: str, field: str) -> str | None:
    lines = _split_lines(text)
    paths_start, paths_end = _paths_bounds(lines)
    ranges = _path_ranges(lines, paths_start, paths_end)
    if path_name not in ranges:
        return None
    start, end = ranges[path_name]
    pattern = re.compile(rf"^    {re.escape(field)}\s*:\s*(.*?)\s*(?:\n)?$")
    found: list[str] = []
    for line in lines[start + 1 : end]:
        match = pattern.match(line)
        if match:
            found.append(match.group(1).strip())
    if len(found) > 1:
        raise ConfigError(f"duplicate field {field} in MediaMTX path {path_name}")
    if not found:
        return None
    raw = found[0]
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid quoted field {field} in MediaMTX path {path_name}") from exc
        return str(value)
    return raw.split(" #", 1)[0].strip()


def validate_reader_ip(value: str) -> None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ConfigError("reader IP must be a literal RFC1918 IPv4 address") from exc
    if not _is_rfc1918_ipv4(address):
        raise ConfigError("reader IP must be a literal RFC1918 IPv4 address")


def validate_peer_reader_ip(value: str) -> None:
    """Validate a literal IPv4 reader peer that is allowed to be public (e.g. VPS)."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ConfigError("reader IP must be a literal IPv4 address") from exc
    if address.version != 4:
        raise ConfigError("reader IP must be a literal IPv4 address")
    if address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved:
        raise ConfigError("reader IP must not be loopback, link-local, multicast or reserved")


def _reader_ip_list(value: str | list[str]) -> list[str]:
    """Normalize repeatable/comma-separated --reader-ip input (issue #372).

    The live Ubuntu worker cam1 reader rule legitimately carries more than one
    VPS reader IP, so the CLI accepts either repeated `--reader-ip` flags or
    one comma-separated value. Order is preserved exactly as given (stable
    documented order for the rendered `ips: [...]` list) and duplicates fail
    closed instead of silently reordering.
    """
    raw_values = [value] if isinstance(value, str) else list(value)
    ips: list[str] = []
    for raw in raw_values:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if part in ips:
                raise ConfigError(f"duplicate reader IP is not allowed: {part}")
            ips.append(part)
    if not ips:
        raise ConfigError("at least one reader IP is required")
    return ips


def reader_scope_token(count: int) -> str:
    """Deterministic reader-scope evidence token; single-IP stays historical."""
    if count == 1:
        return "single-rfc1918-ip"
    return f"multi-rfc1918-ip-count-{count}"


def _auth_internal_users_bounds(lines: list[str]) -> tuple[int, int]:
    matches = _find_top_level(lines, "authInternalUsers")
    if len(matches) != 1:
        raise ConfigError("MediaMTX config must contain exactly one top-level authInternalUsers block")
    start = matches[0]
    if not re.match(r"^authInternalUsers\s*:\s*(?:#.*)?(?:\n)?$", lines[start]):
        raise ConfigError("authInternalUsers must use a block sequence")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if line[0] not in " \t":
            end = index
            break
    return start, end


def _reader_rule_lines(
    path_name: str,
    reader_ips: list[str],
    publisher_ips: list[str] | None = None,
) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", path_name):
        raise ConfigError("MediaMTX path name must be a simple literal name")
    for ip in reader_ips:
        validate_peer_reader_ip(ip)
    if publisher_ips is not None:
        for ip in publisher_ips:
            validate_reader_ip(ip)
    permissions: list[str] = ["      - action: read\n", f"        path: {_yaml_string(path_name)}\n"]
    if publisher_ips:
        permissions += ["      - action: publish\n", f"        path: {_yaml_string(path_name)}\n"]
    ips = list(reader_ips) + list(publisher_ips or [])
    return [
        f"  {reader_marker(path_name)}\n",
        "  - user: any\n",
        "    pass:\n",
        f"    ips: [{', '.join(_yaml_string(ip) for ip in ips)}]\n",
        "    permissions:\n",
        *permissions,
    ]


def _parse_rule_block(lines: list[str], marker_index: int, end: int) -> tuple[set[str], set[str]]:
    ips: set[str] = set()
    actions: set[str] = set()
    in_ips = False
    in_permissions = False
    for line in lines[marker_index + 1 : end]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# Sea Speed least-privilege reader for canonical"):
            break
        if stripped.startswith("ips:"):
            in_ips = True
            in_permissions = False
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("["):
                inner = value[1:-1] if value.endswith("]") else value[1:]
                for part in inner.split(","):
                    part = part.strip().strip('"').strip("'")
                    if part:
                        ips.add(part)
                in_ips = False
            continue
        if in_ips and stripped.startswith("- "):
            item = stripped[2:].strip().strip('"').strip("'")
            if item:
                ips.add(item)
            continue
        if stripped.startswith("permissions:"):
            in_permissions = True
            in_ips = False
            continue
        if in_permissions and stripped.startswith("- action:"):
            actions.add(stripped.split(":", 1)[1].strip())
            continue
        if in_permissions and (
            stripped.startswith("ips:")
            or stripped.startswith("user:")
            or stripped.startswith("pass:")
        ):
            in_permissions = False
    return ips, actions


def verify_internal_reader_rule(
    text: str,
    path_name: str,
    reader_ip: str | list[str],
    publisher_ips: list[str] | None = None,
) -> None:
    method = get_top_level_scalar(text, "authMethod")
    if method not in (None, "internal"):
        raise ConfigError("MediaMTX authMethod must be internal for bounded reader authorization")
    reader_ips = [reader_ip] if isinstance(reader_ip, str) else list(reader_ip)
    for ip in reader_ips:
        validate_peer_reader_ip(ip)
    if publisher_ips is not None:
        for ip in publisher_ips:
            validate_reader_ip(ip)
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    marker = reader_marker(path_name)
    markers = [index for index in range(start + 1, end) if lines[index].strip() == marker]
    if len(markers) != 1:
        raise ConfigError("exactly one Sea Speed reader authorization rule is required for the path")
    block_ips, block_actions = _parse_rule_block(lines, markers[0], end)
    if not set(reader_ips) <= block_ips:
        raise ConfigError("requested reader IPs are not a subset of the Sea Speed reader rule")
    if publisher_ips is not None and not set(publisher_ips) <= block_ips:
        raise ConfigError("requested publisher IPs are not a subset of the Sea Speed reader rule")
    if "read" not in block_actions:
        raise ConfigError("Sea Speed reader rule must grant read")
    if publisher_ips is not None and "publish" not in block_actions:
        raise ConfigError("Sea Speed reader rule must grant publish for the transcode publisher")


def ensure_internal_reader_rule(
    text: str,
    path_name: str,
    reader_ip: str | list[str],
    publisher_ips: list[str] | None = None,
) -> str:
    method = get_top_level_scalar(text, "authMethod")
    if method not in (None, "internal"):
        raise ConfigError("MediaMTX authMethod must be internal for bounded reader authorization")
    reader_ips = [reader_ip] if isinstance(reader_ip, str) else list(reader_ip)
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    expected = _reader_rule_lines(path_name, reader_ips, publisher_ips)
    marker = reader_marker(path_name)
    markers = [index for index in range(start + 1, end) if lines[index].strip() == marker]
    if markers:
        if len(markers) != 1 or lines[markers[0] : markers[0] + len(expected)] != expected:
            raise ConfigError("existing Sea Speed reader authorization rule does not match the requested rule")
        return text
    lines[end:end] = expected
    rendered = "".join(lines)
    verify_internal_reader_rule(rendered, path_name, reader_ip=reader_ip, publisher_ips=publisher_ips)
    return rendered


def _require_internal_auth_method(text: str, purpose: str) -> None:
    method = get_top_level_scalar(text, "authMethod")
    if method not in (None, "internal"):
        raise ConfigError(f"MediaMTX authMethod must be internal for bounded {purpose}")


def _api_rule_lines() -> list[str]:
    """Return the loopback-only API observation rule (docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md)."""
    return [
        f"  {API_RULE_MARKER}\n",
        "  - user: any\n",
        f"    ips: [{_yaml_string(LOOPBACK_IP)}]\n",
        "    permissions:\n",
        "      - action: api\n",
    ]


def verify_internal_api_rule(text: str) -> None:
    """Verify the rendered loopback API observation profile for the freshness watchdog."""
    _require_internal_auth_method(text, "API authorization")
    if get_top_level_scalar(text, "api") != "yes":
        raise ConfigError("MediaMTX api must be enabled for loopback freshness observation")
    if get_top_level_scalar(text, "apiAddress") != LOOPBACK_API_ADDRESS:
        raise ConfigError("MediaMTX apiAddress must bind the loopback watchdog endpoint")
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    markers = [index for index in range(start + 1, end) if lines[index].strip() == API_RULE_MARKER]
    if len(markers) != 1:
        raise ConfigError("exactly one Sea Speed loopback API authorization rule is required")
    block_ips, block_actions = _parse_rule_block(lines, markers[0], end)
    if LOOPBACK_IP not in block_ips:
        raise ConfigError("Sea Speed API rule must be restricted to the loopback source IP")
    if "api" not in block_actions:
        raise ConfigError("Sea Speed API rule must grant the api action")


def ensure_internal_api_rule(text: str) -> str:
    """Idempotently render the loopback API observation rule at the top of authInternalUsers."""
    _require_internal_auth_method(text, "API authorization")
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    expected = _api_rule_lines()
    markers = [index for index in range(start + 1, end) if lines[index].strip() == API_RULE_MARKER]
    if markers:
        if len(markers) != 1 or lines[markers[0] : markers[0] + len(expected)] != expected:
            raise ConfigError("existing Sea Speed loopback API rule does not match the requested rule")
        return text
    lines[start + 1 : start + 1] = expected
    rendered = "".join(lines)
    verify_internal_api_rule(rendered)
    return rendered


AUTH_ENTRY_RE = re.compile(r"^  - ")
AUTH_ENTRY_COMMENT_RE = re.compile(r"^  #")
AUTH_MARKER_PREFIX = "# Sea Speed "
# Issue #436: the only foreign (unmarked) rule the bounded sanitize may remove
# is an exact scope duplicate of the canonical loopback API rule.
CANONICAL_API_SCOPE_IPS = frozenset({LOOPBACK_IP})
CANONICAL_API_SCOPE_ACTIONS = frozenset({"api"})


def _scan_auth_entries(lines: list[str], start: int, end: int) -> list[dict[str, object]]:
    """Scan authInternalUsers sequence entries within [start + 1, end).

    Unlike the marker-anchored `_parse_rule_block` span (which merges
    following entries into one ips/actions set — the #436 blind spot), this
    scanner segments the block per entry:

    - an entry starts at a two-space-indented `  - ` sequence line;
    - the span ends at the next `  - ` entry line, the next two-space-indented
      comment (e.g. a canonical marker), or the block end;
    - `marked` is True only when the preceding non-blank line is a canonical
      "# Sea Speed " marker comment at two-space indent (rules owned by this
      renderer). Marked rules are never candidates for deletion.
    """
    entries: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for index in range(start + 1, end):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            continue
        if AUTH_ENTRY_COMMENT_RE.match(line):
            current = None
            continue
        if AUTH_ENTRY_RE.match(line):
            preceding = index - 1
            while preceding > start and not lines[preceding].strip():
                preceding -= 1
            marked = (
                preceding > start
                and AUTH_ENTRY_COMMENT_RE.match(lines[preceding]) is not None
                and lines[preceding].strip().startswith(AUTH_MARKER_PREFIX)
            )
            current = {"start": index, "end": index + 1, "marked": marked}
            entries.append(current)
            continue
        if current is not None:
            current["end"] = index + 1
    return entries


def _parse_auth_entry_fields(lines: list[str], entry: dict[str, object]) -> tuple[set[str], set[str], set[str], bool]:
    """Parse the ips/actions/paths scope of one authInternalUsers entry.

    Returns (ips, actions, paths, well_formed). `well_formed` is False when the
    entry carries content this bounded tool does not model (unknown fields,
    deeper nesting such as permission-level ips, or comments inside the entry);
    such entries are never deletable — fail closed.

    Issue #444: permission-level `path:` scalars are collected into `paths`
    (quote-stripped, comma-split) so a declared prune can match the exact
    (path, ips, actions) triple. An empty `path:` value is unmodeled.
    """
    ips: set[str] = set()
    actions: set[str] = set()
    paths: set[str] = set()
    well_formed = True
    in_ips = False
    in_permissions = False

    def reset() -> None:
        nonlocal in_ips, in_permissions, well_formed
        in_ips = False
        in_permissions = False
        well_formed = False

    for offset, line in enumerate(lines[entry["start"] : entry["end"]]):  # type: ignore[arg-type]
        stripped = line.strip()
        if not stripped:
            continue
        if offset == 0:
            # The `  - ` entry header line (guaranteed by the scanner). Only
            # the observed `- user:` shape is modeled; anything else fails
            # closed.
            if stripped[2:].strip().startswith("user:"):
                in_ips = False
                in_permissions = False
                continue
            reset()
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent < 4:
            # Anything at sequence-item indent inside an entry is unmodeled.
            reset()
            continue
        if indent == 4:
            if stripped.startswith("user:") or stripped.startswith("pass:"):
                in_ips = False
                in_permissions = False
                continue
            if stripped.startswith("ips:"):
                in_permissions = False
                value = stripped.split(":", 1)[1].strip()
                if value:
                    if value.startswith("["):
                        inner = value[1:-1] if value.endswith("]") else value[1:]
                        for part in inner.split(","):
                            part = part.strip().strip('"').strip("'")
                            if part:
                                ips.add(part)
                    else:
                        ips.add(value.strip('"').strip("'"))
                    in_ips = False
                else:
                    in_ips = True
                continue
            if stripped.startswith("permissions:"):
                in_permissions = True
                in_ips = False
                continue
            reset()
            continue
        # indent >= 6: nested content.
        if in_ips and stripped.startswith("- "):
            item = stripped[2:].strip().strip('"').strip("'")
            if item:
                ips.add(item)
            continue
        if in_permissions and stripped.startswith("- action:"):
            actions.add(stripped.split(":", 1)[1].strip())
            continue
        if in_permissions and stripped.startswith("path:"):
            value = stripped.split(":", 1)[1].strip()
            if not value:
                # A path block shape this bounded tool does not model.
                reset()
                continue
            if value.startswith("["):
                value = value[1:-1] if value.endswith("]") else value[1:]
            for part in value.split(","):
                part = part.strip().strip('"').strip("'")
                if part:
                    paths.add(part)
            continue
        reset()
    return ips, actions, paths, well_formed


def scan_foreign_auth_rules(text: str) -> list[str]:
    """Describe foreign (unmarked) authInternalUsers entries (issue #436).

    Foreign = an entry whose preceding non-blank line is not a canonical
    "# Sea Speed " marker comment. The canonical marked rules are never
    reported.
    """
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    descriptions: list[str] = []
    for entry in _scan_auth_entries(lines, start, end):
        if entry["marked"]:
            continue
        ips, actions, _paths, well_formed = _parse_auth_entry_fields(lines, entry)
        suffix = "" if well_formed else " (unmodeled fields)"
        descriptions.append(
            f"line {entry['start']}: ips={sorted(ips)} actions={sorted(actions)}{suffix}"
        )
    return descriptions


def count_foreign_auth_rules(text: str) -> int:
    """Count foreign (unmarked) authInternalUsers entries (issue #436).

    This is the explicit foreign-rule counter for verify-after; it does NOT
    use the marker-anchored span-merge parsing of verify_internal_api_rule.
    """
    return len(scan_foreign_auth_rules(text))


class DeclaredAuthPrune(NamedTuple):
    """Issue #444: one explicit opt-in prune declaration.

    `path` is a single MediaMTX path name; `ips` and `actions` are the exact
    scope the operator declares removable. A foreign unmarked rule is
    deletable under this declaration only when its parsed permission-path set
    equals {path}, its ips set equals set(ips) and its actions set equals
    set(actions) — partial matches stay fail-closed.
    """

    path: str
    ips: tuple[str, ...]
    actions: tuple[str, ...]


ALLOWED_DECLARED_PRUNE_ACTIONS = frozenset({"read", "publish", "api"})


def parse_declared_auth_prune(spec: str) -> DeclaredAuthPrune:
    """Parse one `--prune-declared` declaration (issue #444).

    Grammar (documented in the sanitize runbook): comma-separated tokens;
    each token is either `key=value` — starting the section for key
    path|ips|actions — or a bare value continuing the previous key. Exactly
    one `path=`, at least one ip (validated IPv4/IPv6) and at least one
    action (restricted to the renderer vocabulary read|publish|api) are
    required; anything else raises ConfigError.
    """
    error = f"invalid --prune-declared declaration {spec!r}"
    path: str | None = None
    ips: list[str] = []
    actions: list[str] = []
    section: str | None = None
    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            raise ConfigError(f"{error}: empty value")
        if "=" in token:
            key, value = (part.strip() for part in token.split("=", 1))
            if key not in ("path", "ips", "actions"):
                raise ConfigError(f"{error}: unknown key {key!r}")
            if key == "path" and path is not None:
                raise ConfigError(f"{error}: duplicate path key")
            if not value:
                raise ConfigError(f"{error}: empty value for key {key!r}")
            section = key
        else:
            if section is None:
                raise ConfigError(f"{error}: bare value {token!r} before any key=")
            if section == "path":
                raise ConfigError(f"{error}: path takes exactly one value")
            value = token
        if section == "path":
            path = value
        elif section == "ips":
            ips.append(value)
        else:
            actions.append(value)
    if path is None or not ips or not actions:
        raise ConfigError(f"{error}: path, ips and actions are all required")
    for address in ips:
        try:
            ipaddress.ip_address(address)
        except ValueError:
            raise ConfigError(f"{error}: invalid ip {address!r}") from None
    for action in actions:
        if action not in ALLOWED_DECLARED_PRUNE_ACTIONS:
            allowed = ", ".join(sorted(ALLOWED_DECLARED_PRUNE_ACTIONS))
            raise ConfigError(f"{error}: action {action!r} outside the allowed vocabulary ({allowed})")
    if any(character.isspace() for character in path):
        raise ConfigError(f"{error}: path {path!r} must not contain whitespace")
    return DeclaredAuthPrune(path=path, ips=tuple(ips), actions=tuple(actions))


def sanitize_foreign_auth_rules_declared(
    text: str, declared_prunes: Sequence[DeclaredAuthPrune]
) -> tuple[str, int, list[int]]:
    """Prune foreign unmarked auth rules: the canonical loopback-API scope
    always, plus any rule matching an explicitly declared (path, ips, actions)
    triple exactly (issue #444).

    Any other foreign rule fails the whole sanitize closed (ConfigError,
    report naming the offending scope) BEFORE any deletion — the input text is
    returned untouched on failure. Marked "# Sea Speed " rules are never
    parsed for deletion and are preserved byte-identically (post-condition
    asserted); a declaration never removes a marked rule even on an exact
    triple match. Returns (pruned text, total removed, per-declaration removed
    counts in declaration order). Without declarations the behavior is exactly
    the #436 default.
    """
    _require_internal_auth_method(text, "auth sanitization")
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    entries = _scan_auth_entries(lines, start, end)
    marked_spans_before = [
        "".join(lines[entry["start"] : entry["end"]])  # type: ignore[arg-type]
        for entry in entries
        if entry["marked"]
    ]
    foreign = [entry for entry in entries if not entry["marked"]]
    if not foreign:
        return text, 0, [0] * len(declared_prunes)
    deletable: list[dict[str, object]] = []
    per_declaration = [0] * len(declared_prunes)
    for entry in foreign:
        ips, actions, paths, well_formed = _parse_auth_entry_fields(lines, entry)
        api_scope = (
            well_formed and ips == CANONICAL_API_SCOPE_IPS and actions == CANONICAL_API_SCOPE_ACTIONS
        )
        matched = -1
        if well_formed and not api_scope:
            for position, declaration in enumerate(declared_prunes):
                if (
                    paths == {declaration.path}
                    and ips == set(declaration.ips)
                    and actions == set(declaration.actions)
                ):
                    matched = position
                    break
        if not api_scope and matched < 0:
            raise ConfigError(
                "foreign unmarked authInternalUsers rule is outside the canonical "
                "loopback-api scope and matches no declared prune "
                f"(line {entry['start']}, ips={sorted(ips)}, actions={sorted(actions)}, "
                f"paths={sorted(paths)})"
            )
        deletable.append(entry)
        if matched >= 0:
            per_declaration[matched] += 1
    keep = [True] * len(lines)
    for entry in deletable:
        for index in range(entry["start"], entry["end"]):  # type: ignore[arg-type]
            keep[index] = False
    pruned = "".join(line for index, line in enumerate(lines) if keep[index])
    pruned_lines = _split_lines(pruned)
    pruned_start, pruned_end = _auth_internal_users_bounds(pruned_lines)
    pruned_entries = _scan_auth_entries(pruned_lines, pruned_start, pruned_end)
    marked_spans_after = [
        "".join(pruned_lines[entry["start"] : entry["end"]])  # type: ignore[arg-type]
        for entry in pruned_entries
        if entry["marked"]
    ]
    if marked_spans_before != marked_spans_after:
        raise ConfigError("sanitize post-condition failed: marked auth rules changed")
    if count_foreign_auth_rules(pruned) != 0:
        raise ConfigError("sanitize post-condition failed: foreign auth rules remain")
    return pruned, len(deletable), per_declaration


def sanitize_foreign_auth_rules(text: str) -> tuple[str, int]:
    """Prune foreign unmarked auth rules scoped EXACTLY like the canonical
    loopback API rule (ips == {127.0.0.1}, actions == {"api"}, fully modeled).

    Any other foreign rule fails the whole sanitize closed (ConfigError,
    report naming the offending scope) BEFORE any deletion — the input text is
    returned untouched on failure. Marked "# Sea Speed " rules are never
    parsed for deletion and are preserved byte-identically (post-condition
    asserted). Issue #436; explicit opt-in declarations ride the #444
    `_declared` variant.
    """
    pruned, removed, _per_declaration = sanitize_foreign_auth_rules_declared(text, ())
    return pruned, removed


def _reader_rule_ips_in_order(lines: list[str], marker_index: int, end: int) -> list[str]:
    """Issue #437: ordered ips of a marker-anchored reader rule.

    Companion to `_parse_rule_block` (whose set result loses the live order
    and collapses duplicates): remediation must preserve the live rendering
    order and fail closed on duplicates, so this parser mirrors the same
    span/field grammar while keeping the sequence exactly as written.
    """
    ordered: list[str] = []
    in_ips = False
    for line in lines[marker_index + 1 : end]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# Sea Speed least-privilege reader for canonical"):
            break
        if stripped.startswith("ips:"):
            in_ips = True
            value = stripped.split(":", 1)[1].strip()
            if value.startswith("["):
                inner = value[1:-1] if value.endswith("]") else value[1:]
                for part in inner.split(","):
                    part = part.strip().strip('"').strip("'")
                    if part:
                        ordered.append(part)
                in_ips = False
            continue
        if in_ips and stripped.startswith("- "):
            item = stripped[2:].strip().strip('"').strip("'")
            if item:
                ordered.append(item)
            continue
        in_ips = False
    return ordered


# Issue #437: the relay profile is read-only; a drifted reader block granting
# publish cannot have its publisher role recovered from a flat live ips list.
READER_RULE_ALLOWED_ACTIONS = frozenset({"read", "publish"})


def remediate_internal_reader_rule(text: str, path_name: str) -> tuple[str, list[str], bool]:
    """Converge a drifted marker-anchored reader rule to the canonical block.

    Issue #437. The live scopes are preserved; the FORM is re-emitted through
    `_reader_rule_lines` (the exact renderer `ubuntu-relay` uses), so a
    remediated config is byte-identical to what `ensure_internal_reader_rule`
    considers canonical for those scopes. Every scope element is re-authorized
    BEFORE re-emission — the remediation NEVER canonizes an unauthorized scope:

    - ips: every live ip must pass `validate_peer_reader_ip` AND
      `validate_reader_ip` (the relay profile renders reader IPs as literal
      RFC1918 IPv4); non-IPv4, loopback, link-local, multicast, reserved,
      public and duplicate ips fail closed;
    - actions: must be a subset of {read, publish}; `publish` fails closed on
      the read-only relay profile;
    - the marked span must contain exactly this one bounded entry (no merged
      foreign rules, no unmodeled content) — anything else fails closed
      BEFORE any replacement.

    Returns (remediated_text, live_reader_ips, remediation_needed) where
    remediation_needed is False only when the re-emitted block was already
    byte-identical to the live one (idempotent no-op). Raises ConfigError
    without touching the input on any violation.
    """
    _require_internal_auth_method(text, "reader remediation")
    lines = _split_lines(text)
    start, end = _auth_internal_users_bounds(lines)
    marker = reader_marker(path_name)
    markers = [index for index in range(start + 1, end) if lines[index].strip() == marker]
    if len(markers) != 1:
        raise ConfigError("exactly one Sea Speed reader authorization rule is required for the path")
    marker_index = markers[0]
    span_end = end
    for index in range(marker_index + 1, end):
        if lines[index].strip().startswith("# Sea Speed least-privilege reader for canonical"):
            span_end = index
            break
    entries = _scan_auth_entries(lines, marker_index, span_end)
    if len(entries) != 1:
        raise ConfigError(
            "drifted Sea Speed reader rule span is not exactly one bounded entry; "
            "remediation refuses to canonize merged auth rules"
        )
    first_content = next(
        index for index in range(marker_index + 1, span_end) if lines[index].strip()
    )
    if first_content != entries[0]["start"]:  # type: ignore[comparison-overlap]
        raise ConfigError("unmodeled content between the Sea Speed reader marker and its rule")
    entry_end = entries[0]["end"]  # type: ignore[assignment]
    live_ips, live_actions = _parse_rule_block(lines, marker_index, entry_end)
    ordered_ips = _reader_rule_ips_in_order(lines, marker_index, entry_end)
    if not ordered_ips:
        raise ConfigError("drifted Sea Speed reader rule carries no reader IPs")
    if len(set(ordered_ips)) != len(ordered_ips):
        raise ConfigError(
            f"duplicate reader IP in the drifted Sea Speed reader rule: {sorted(set(ordered_ips))}"
        )
    if set(ordered_ips) != live_ips:
        raise ConfigError("drifted Sea Speed reader rule parse divergence; failing closed")
    if not live_actions <= READER_RULE_ALLOWED_ACTIONS:
        raise ConfigError(
            "drifted Sea Speed reader rule carries actions outside {read, publish}: "
            f"{sorted(live_actions)}"
        )
    if "publish" in live_actions:
        raise ConfigError(
            "drifted Sea Speed reader rule grants publish; the relay profile is "
            "read-only and publisher scopes cannot be recovered from the live rule"
        )
    for ip in ordered_ips:
        validate_peer_reader_ip(ip)
        validate_reader_ip(ip)
    canonical = _reader_rule_lines(path_name, ordered_ips)
    lines[marker_index:entry_end] = canonical
    rendered = "".join(lines)
    if ensure_internal_reader_rule(rendered, path_name, ordered_ips) != rendered:
        raise ConfigError("remediation post-condition failed: block is not canonical")
    verify_internal_reader_rule(rendered, path_name, ordered_ips)
    verify_internal_api_rule(rendered)
    return rendered, ordered_ips, rendered != text


def read_protected_env_value(path: Path, key: str) -> str:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ConfigError("protected source env file is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ConfigError("protected source env file must be a regular non-symlink file")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise ConfigError("protected source env file mode must be 0600")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError("protected source env file cannot be read") from exc

    prefix = key + "="
    values: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith(prefix):
            continue
        raw = stripped[len(prefix) :].strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
            raw = raw[1:-1]
        values.append(raw)
    if len(values) != 1 or not values[0]:
        raise ConfigError(f"protected env file must contain exactly one non-empty {key}")
    return values[0]


def validate_camera_source(source: str) -> None:
    try:
        parsed = urlsplit(source)
        host = parsed.hostname
    except (TypeError, ValueError) as exc:
        raise ConfigError("camera source is not a valid RTSP URL") from exc
    if parsed.scheme.lower() != "rtsp" or not host:
        raise ConfigError("camera source must use rtsp with a host")
    if parsed.username is None:
        raise ConfigError("camera source must contain protected userinfo")


def validate_private_relay_url(source: str, expected_path: str) -> None:
    try:
        parsed = urlsplit(source)
        host = parsed.hostname
    except (TypeError, ValueError) as exc:
        raise ConfigError("private relay source is not a valid RTSP URL") from exc
    if parsed.scheme.lower() != "rtsp" or not host:
        raise ConfigError("private relay source must use rtsp with a host")
    if parsed.username is not None or parsed.password is not None:
        raise ConfigError("private relay source must not contain userinfo")
    # NOTE: the relay URL path is intentionally NOT required to equal the
    # switched path. The Camera 1 cutover points the VPS HLS path `cam1` at a
    # distinct Ubuntu Worker transcode path `cam1-h264`; requiring path equality
    # would block the correct topology. Safety is provided by the rtsp + RFC1918
    # literal-IP checks below, and the rendered candidate is reviewed (SHA) before
    # activation.
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ConfigError("private relay source must use a literal RFC1918 IPv4 address") from exc
    if not _is_rfc1918_ipv4(address):
        raise ConfigError("private relay source IP must be RFC1918")


def validate_private_rtsp_address(address: str) -> None:
    if address.count(":") != 1:
        raise ConfigError("private RTSP listen address must be IPv4:port")
    host, port_text = address.rsplit(":", 1)
    try:
        ip = ipaddress.ip_address(host)
        port = int(port_text)
    except ValueError as exc:
        raise ConfigError("private RTSP listen address must be valid IPv4:port") from exc
    if not _is_rfc1918_ipv4(ip) or not (1 <= port <= 65535):
        raise ConfigError("private RTSP listen address must use RFC1918 IPv4 and valid port")


def verify_vps_relay_path(text: str, path_name: str, relay_url: str) -> None:
    validate_private_relay_url(relay_url, path_name)
    if get_path_field(text, path_name, "source") != relay_url:
        raise ConfigError("canonical path is not bound to the expected private relay")
    if get_path_field(text, path_name, "sourceOnDemand") != "yes":
        raise ConfigError("canonical private relay must use sourceOnDemand=yes")
    if get_path_field(text, path_name, "rtspTransport") != "tcp":
        raise ConfigError("canonical private relay must use rtspTransport=tcp")


def read_config(path: Path) -> str:
    try:
        info = os.lstat(path)
    except OSError as exc:
        raise ConfigError("MediaMTX config is unavailable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ConfigError("MediaMTX config must be a regular non-symlink file")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError("MediaMTX config cannot be read") from exc


def write_candidate(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ConfigError("candidate output must not be a symlink")
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(text, encoding="utf-8")
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_ubuntu_relay(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    source = read_protected_env_value(args.source_env_file, args.source_env_key)
    validate_camera_source(source)
    validate_private_rtsp_address(args.private_rtsp_address)
    reader_ips = _reader_ip_list(args.reader_ip)
    for ip in reader_ips:
        validate_reader_ip(ip)
    for key, value, quote in (
        ("rtsp", "yes", False),
        ("rtspAddress", args.private_rtsp_address, True),
        ("rtmp", "no", False),
        ("hls", "no", False),
        ("webrtc", "no", False),
        ("srt", "no", False),
        # The loopback REST API is the camera1-h264 freshness watchdog's only
        # liveness input (issue #407); without it the watchdog deterministically
        # false-positives STALE and restart-loops the transcode. Loopback-only.
        ("api", "yes", False),
        ("apiAddress", LOOPBACK_API_ADDRESS, True),
    ):
        text = set_top_level_scalar(text, key, value, quote=quote)
    text = set_path_source(text, args.path, source, source_on_demand=True, rtsp_transport="tcp")
    text = ensure_internal_reader_rule(text, args.path, reader_ips)
    text = ensure_internal_api_rule(text)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=ubuntu-relay path={args.path} source_scheme=rtsp "
        f"source_has_userinfo=YES reader_scope={reader_scope_token(len(reader_ips))} "
        f"reader_permission=read-only api=loopback-watchdog output_sha256={digest}"
    )
    return digest


def render_ubuntu_sanitize_auth(args: argparse.Namespace) -> str:
    """Issue #436: bounded foreign-unmarked-auth-rule sanitize candidate.

    Transaction shape (called by `camera-relay.sh sanitize`; installation only
    through the existing digest-bound `activate`):
      verify-before (marked loopback API rule intact on the live config)
      -> prune ONLY exact-scope foreign duplicates (else fail closed)
      -> explicit post-condition: foreign-rule count == 0 (dedicated scanner,
         not the legacy span-merge verify)
      -> verify-after (marked loopback API rule intact on the candidate)
      -> write the 0600 candidate and emit the digest evidence line.

    Issue #444: repeatable explicit opt-in `--prune-declared` declarations
    (path/ips/actions grammar) extend the removable set with unmarked rules
    matching a declared triple exactly; without declarations the behavior is
    byte-for-byte the #436 default. Each declaration gets a
    `DECLARED_PRUNED ... removed=N` evidence line.
    """
    declared_prunes = [parse_declared_auth_prune(spec) for spec in args.prune_declared]
    text = read_config(args.config)
    verify_internal_api_rule(text)
    pruned, removed, per_declaration = sanitize_foreign_auth_rules_declared(text, declared_prunes)
    remaining = count_foreign_auth_rules(pruned)
    if remaining != 0:
        raise ConfigError(f"foreign unmarked authInternalUsers rules remain after sanitize: {remaining}")
    verify_internal_api_rule(pruned)
    digest = write_candidate(args.output, pruned)
    for declaration, declaration_removed in zip(declared_prunes, per_declaration):
        print(
            f"DECLARED_PRUNED path={declaration.path} "
            f"ips={','.join(declaration.ips)} actions={','.join(declaration.actions)} "
            f"removed={declaration_removed}"
        )
    print(
        f"SANITIZED mode=ubuntu-sanitize-auth foreign_rules_removed={removed} "
        f"foreign_rules_remaining={remaining} api_rule=loopback-watchdog-intact "
        f"output_sha256={digest}"
    )
    return digest


def render_ubuntu_remediate_reader(args: argparse.Namespace) -> str:
    """Issue #437: bounded drifted-reader-rule remediation candidate.

    Transaction shape (called by `camera-relay.sh remediate`; installation only
    through the existing digest-bound `activate`):
      verify-before (marked loopback API rule intact on the live config)
      -> locate the drifted marked reader rule, extract its live ips/actions
         via `_parse_rule_block`, re-authorize every scope element
         (fail closed: non-IPv4/loopback/public/duplicate ips, actions outside
         {read, publish}, publish on the read-only relay profile)
      -> re-emit the canonical block via `_reader_rule_lines` preserving the
         live scopes and replace the drifted block
      -> verify-after (reader rule + marked loopback API rule on the result,
         plus byte-exact ensure_internal_reader_rule idempotency)
      -> write the 0600 candidate and emit the digest evidence line.
    """
    text = read_config(args.config)
    verify_internal_api_rule(text)
    remediated, reader_ips, needed = remediate_internal_reader_rule(text, args.path)
    digest = write_candidate(args.output, remediated)
    print(
        f"REMEDIATED mode=ubuntu-remediate-reader path={args.path} "
        f"remediation_needed={'YES' if needed else 'NO'} "
        f"reader_scope={reader_scope_token(len(reader_ips))} "
        f"reader_permission=read-only output_sha256={digest}"
    )
    return digest


def render_verify_reader_auth(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    reader_ips = _reader_ip_list(args.reader_ip)
    verify_internal_reader_rule(text, args.path, reader_ips)
    print(
        f"VERIFIED mode=reader-auth path={args.path} "
        f"reader_scope={reader_scope_token(len(reader_ips))} reader_permission=read-only"
    )
    return ""


def render_ubuntu_transcode_reader(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    validate_peer_reader_ip(args.reader_ip)
    validate_reader_ip(args.publisher_ip)
    # The Ubuntu ffmpeg transcode publishes H264 RTSP into this path, so the
    # Worker MediaMTX must expose it as a publisher path. Without this block the
    # transcode unit has nowhere to publish and the VPS relay stays empty.
    text = set_path_source(text, args.path, "publisher", source_on_demand=False)
    text = ensure_internal_reader_rule(
        text,
        args.path,
        args.reader_ip,
        publisher_ips=[args.publisher_ip],
    )
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=ubuntu-transcode-reader path={args.path} "
        f"reader_scope=rfc1918-vps-peer publisher_scope=rfc1918-ubuntu-peer "
        f"reader_permission=read+publish output_sha256={digest}"
    )
    return digest


def render_verify_vps_switch(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    verify_vps_relay_path(text, args.path, args.relay_url)
    print(f"VERIFIED mode=vps-switch path={args.path} rtsp_transport=tcp relay_userinfo=NO")
    return ""


def render_vps_switch(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    validate_private_relay_url(args.relay_url, args.path)
    text = set_path_source(
        text,
        args.path,
        args.relay_url,
        source_on_demand=True,
        rtsp_transport="tcp",
    )
    verify_vps_relay_path(text, args.path, args.relay_url)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=vps-switch path={args.path} relay_userinfo=NO "
        f"rtsp_transport=tcp output_sha256={digest}"
    )
    return digest


def render_vps_set_hls_address(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    text = set_top_level_scalar(text, "hlsAddress", args.hls_address, quote=True)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=vps-set-hls-address hls_address={args.hls_address} "
        f"output_sha256={digest}"
    )
    return digest


def render_vps_cleanup(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    verify_vps_relay_path(text, args.path, args.relay_url)
    text = remove_path(text, args.remove_path)
    verify_vps_relay_path(text, args.path, args.relay_url)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=vps-cleanup path={args.path} removed={args.remove_path} "
        f"rtsp_transport=tcp output_sha256={digest}"
    )
    return digest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ubuntu = sub.add_parser("ubuntu-relay")
    ubuntu.add_argument("--config", type=Path, required=True)
    ubuntu.add_argument("--source-env-file", type=Path, required=True)
    ubuntu.add_argument("--source-env-key", default="HLS_URL")
    ubuntu.add_argument("--private-rtsp-address", required=True)
    # Repeatable (and comma-separated) since issue #372: live worker reader
    # rules legitimately carry more than one VPS reader IP.
    ubuntu.add_argument("--reader-ip", required=True, action="append")
    ubuntu.add_argument("--path", default="cam1")
    ubuntu.add_argument("--output", type=Path, required=True)
    ubuntu.set_defaults(handler=render_ubuntu_relay)

    verify = sub.add_parser("verify-reader-auth")
    verify.add_argument("--config", type=Path, required=True)
    verify.add_argument("--reader-ip", required=True, action="append")
    verify.add_argument("--path", default="cam1")
    verify.set_defaults(handler=render_verify_reader_auth)

    sanitize = sub.add_parser(
        "ubuntu-sanitize-auth",
        help="prune ONLY foreign unmarked auth rules scoped exactly like the canonical loopback API rule, plus explicitly declared prunes (issues #436/#444)",
    )
    sanitize.add_argument("--config", type=Path, required=True)
    sanitize.add_argument("--output", type=Path, required=True)
    sanitize.add_argument(
        "--prune-declared",
        action="append",
        default=[],
        metavar="SPEC",
        help="explicit opt-in prune declaration path=NAME,ips=IP[,IP...],actions=ACTION[,ACTION...] (repeatable; #444)",
    )
    sanitize.set_defaults(handler=render_ubuntu_sanitize_auth)

    remediate = sub.add_parser(
        "ubuntu-remediate-reader",
        help="converge a drifted marked reader rule to the canonical read-only relay block, preserving its live authorized scope (issue #437)",
    )
    remediate.add_argument("--config", type=Path, required=True)
    remediate.add_argument("--path", default="cam1")
    remediate.add_argument("--output", type=Path, required=True)
    remediate.set_defaults(handler=render_ubuntu_remediate_reader)

    transcode = sub.add_parser("ubuntu-transcode-reader")
    transcode.add_argument("--config", type=Path, required=True)
    transcode.add_argument("--reader-ip", required=True)
    transcode.add_argument("--publisher-ip", required=True)
    transcode.add_argument("--path", default="cam1-h264")
    transcode.add_argument("--output", type=Path, required=True)
    transcode.set_defaults(handler=render_ubuntu_transcode_reader)

    verify_vps = sub.add_parser("verify-vps-switch")
    verify_vps.add_argument("--config", type=Path, required=True)
    verify_vps.add_argument("--relay-url", required=True)
    verify_vps.add_argument("--path", default="cam1")
    verify_vps.set_defaults(handler=render_verify_vps_switch)

    switch = sub.add_parser("vps-switch")
    switch.add_argument("--config", type=Path, required=True)
    switch.add_argument("--relay-url", required=True)
    switch.add_argument("--path", default="cam1")
    switch.add_argument("--output", type=Path, required=True)
    switch.set_defaults(handler=render_vps_switch)

    hlsaddr = sub.add_parser("vps-set-hls-address")
    hlsaddr.add_argument("--config", type=Path, required=True)
    hlsaddr.add_argument("--hls-address", required=True)
    hlsaddr.add_argument("--output", type=Path, required=True)
    hlsaddr.set_defaults(handler=render_vps_set_hls_address)

    cleanup = sub.add_parser("vps-cleanup")
    cleanup.add_argument("--config", type=Path, required=True)
    cleanup.add_argument("--relay-url", required=True)
    cleanup.add_argument("--path", default="cam1")
    cleanup.add_argument("--remove-path", default="cam1-new")
    cleanup.add_argument("--output", type=Path, required=True)
    cleanup.set_defaults(handler=render_vps_cleanup)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (ConfigError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())