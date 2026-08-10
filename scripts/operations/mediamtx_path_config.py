#!/usr/bin/env python3
"""Render narrowly-scoped MediaMTX configuration candidates safely.

The Ubuntu mode reads the credential-bearing camera URL from a protected env
file and never prints it. The VPS mode accepts only a credential-free private
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
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """Raised when a bounded MediaMTX transformation cannot be proven safe."""


def _split_lines(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def _ensure_newline(line: str) -> str:
    return line if line.endswith("\n") else line + "\n"


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


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


def set_path_source(text: str, path_name: str, source: str, *, source_on_demand: bool = True) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", path_name):
        raise ConfigError("MediaMTX path name must be a simple literal name")
    lines = _split_lines(text)
    paths_start, paths_end = _paths_bounds(lines)
    ranges = _path_ranges(lines, paths_start, paths_end)
    source_line = f"    source: {_yaml_string(source)}\n"
    demand_line = f"    sourceOnDemand: {'yes' if source_on_demand else 'no'}\n"
    field_re = re.compile(r"^    (source|sourceOnDemand)\s*:")

    if path_name in ranges:
        start, end = ranges[path_name]
        kept = [line for line in lines[start + 1 : end] if not field_re.match(line)]
        lines[start:end] = [_ensure_newline(lines[start]), source_line, demand_line, *kept]
        return "".join(lines)

    insertion = paths_end
    block = [f"  {path_name}:\n", source_line, demand_line]
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
    if parsed.path.rstrip("/") != "/" + expected_path:
        raise ConfigError("private relay source path does not match the canonical path")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ConfigError("private relay source must use a literal private IP address") from exc
    if not address.is_private:
        raise ConfigError("private relay source IP must be private")


def validate_private_rtsp_address(address: str) -> None:
    if address.count(":") != 1:
        raise ConfigError("private RTSP listen address must be IPv4:port")
    host, port_text = address.rsplit(":", 1)
    try:
        ip = ipaddress.ip_address(host)
        port = int(port_text)
    except ValueError as exc:
        raise ConfigError("private RTSP listen address must be valid IPv4:port") from exc
    if ip.version != 4 or not ip.is_private or not (1 <= port <= 65535):
        raise ConfigError("private RTSP listen address must use a private IPv4 and valid port")


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
    for key, value, quote in (
        ("rtsp", "yes", False),
        ("rtspAddress", args.private_rtsp_address, True),
        ("rtmp", "no", False),
        ("hls", "no", False),
        ("webrtc", "no", False),
        ("srt", "no", False),
    ):
        text = set_top_level_scalar(text, key, value, quote=quote)
    text = set_path_source(text, args.path, source, source_on_demand=True)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=ubuntu-relay path={args.path} source_scheme=rtsp "
        f"source_has_userinfo=YES output_sha256={digest}"
    )
    return digest


def render_vps_switch(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    validate_private_relay_url(args.relay_url, args.path)
    text = set_path_source(text, args.path, args.relay_url, source_on_demand=True)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=vps-switch path={args.path} relay_userinfo=NO "
        f"output_sha256={digest}"
    )
    return digest


def render_vps_cleanup(args: argparse.Namespace) -> str:
    text = read_config(args.config)
    validate_private_relay_url(args.relay_url, args.path)
    current = get_path_field(text, args.path, "source")
    if current != args.relay_url:
        raise ConfigError("canonical path is not bound to the expected private relay")
    text = remove_path(text, args.remove_path)
    digest = write_candidate(args.output, text)
    print(
        f"RENDERED mode=vps-cleanup path={args.path} removed={args.remove_path} "
        f"output_sha256={digest}"
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
    ubuntu.add_argument("--path", default="cam1")
    ubuntu.add_argument("--output", type=Path, required=True)
    ubuntu.set_defaults(handler=render_ubuntu_relay)

    switch = sub.add_parser("vps-switch")
    switch.add_argument("--config", type=Path, required=True)
    switch.add_argument("--relay-url", required=True)
    switch.add_argument("--path", default="cam1")
    switch.add_argument("--output", type=Path, required=True)
    switch.set_defaults(handler=render_vps_switch)

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
