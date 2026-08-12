#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

BEGIN = "# SEA-SPEED-CAM1-DIRECT-H264-BEGIN"
END = "# SEA-SPEED-CAM1-DIRECT-H264-END"
CAM1_PREFIX = "/cams/hls/cam1/"
GENERIC_PREFIX = "/cams/hls/"
UPSTREAM = "http://127.0.0.1:18889/cam1/"


class ConfigError(RuntimeError):
    pass


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    in_comment = False
    for i in range(open_index, len(text)):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "#":
            in_comment = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _blocks(text: str, keyword: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for m in re.finditer(rf"(?m)^\s*{re.escape(keyword)}\b[^{{;]*{{", text):
        open_index = text.find("{", m.start(), m.end())
        close_index = _matching_brace(text, open_index)
        if close_index < 0:
            raise ConfigError(f"unbalanced {keyword} block")
        out.append((m.start(), open_index, close_index))
    return out


def _location_blocks(server_text: str) -> list[tuple[str, int, int, int]]:
    out = []
    pattern = re.compile(r"(?m)^\s*location\s+([^\{]+)\{")
    for m in pattern.finditer(server_text):
        spec = m.group(1).strip()
        open_index = server_text.find("{", m.start(), m.end())
        close_index = _matching_brace(server_text, open_index)
        if close_index < 0:
            raise ConfigError("unbalanced location block")
        out.append((spec, m.start(), open_index, close_index))
    return out


def _location_uri(spec: str) -> str:
    parts = spec.split()
    if not parts:
        return ""
    if parts[0] in {"=", "^~", "~", "~*"}:
        return parts[1] if len(parts) > 1 else ""
    return parts[0]


def _server_for_host(text: str, host: str) -> tuple[int, int, int]:
    host_matches = []
    target_matches = []
    host_re = re.compile(rf"(?m)^\s*server_name\s+[^;]*\b{re.escape(host)}\b[^;]*;")
    for block in _blocks(text, "server"):
        _, open_index, close_index = block
        body = text[open_index + 1 : close_index]
        if not host_re.search(body):
            continue
        host_matches.append(block)
        if any(_location_uri(spec) == GENERIC_PREFIX for spec, *_ in _location_blocks(body)):
            target_matches.append(block)
    if len(target_matches) != 1:
        raise ConfigError(
            f"expected exactly one server block for {host} containing {GENERIC_PREFIX}, "
            f"found {len(target_matches)} among {len(host_matches)} host blocks"
        )
    return target_matches[0]


def _generic_location(server_text: str) -> tuple[int, int, int]:
    matches = []
    for spec, start, open_index, close_index in _location_blocks(server_text):
        if _location_uri(spec) == GENERIC_PREFIX:
            matches.append((start, open_index, close_index))
    if len(matches) != 1:
        raise ConfigError(
            f"expected exactly one existing {GENERIC_PREFIX} location in target server, found {len(matches)}"
        )
    return matches[0]


def _extract_auth(generic_body: str) -> list[str]:
    auth_lines = []
    for line in generic_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("auth_basic ") or stripped.startswith("auth_basic_user_file "):
            if not stripped.endswith(";"):
                raise ConfigError("malformed nginx auth directive")
            auth_lines.append(stripped)
    return auth_lines


def _indent_at(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    return re.match(r"[ \t]*", text[line_start:index]).group(0)  # type: ignore[union-attr]


def render(text: str, host: str = "mostdef.ru") -> str:
    if (BEGIN in text) != (END in text):
        raise ConfigError("managed Camera 1 marker block is incomplete")

    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]

    generic_start, generic_open, generic_close = _generic_location(server_text)
    generic_body = server_text[generic_open + 1 : generic_close]
    auth_lines = _extract_auth(generic_body)

    cam1_blocks = [
        (spec, start, open_index, close_index)
        for spec, start, open_index, close_index in _location_blocks(server_text)
        if _location_uri(spec) == CAM1_PREFIX
    ]
    if len(cam1_blocks) > 1:
        raise ConfigError(f"multiple existing Camera 1 locations found: {len(cam1_blocks)}")
    if cam1_blocks:
        _spec, cam_start, cam_open, cam_close = cam1_blocks[0]
        auth_lines.extend(_extract_auth(server_text[cam_open + 1 : cam_close]))
        remove_start = server_start + cam_start
        remove_end = server_start + cam_close + 1
        while remove_end < len(text) and text[remove_end] in " \t":
            remove_end += 1
        if remove_end < len(text) and text[remove_end] == "\n":
            remove_end += 1
        marker_begin = text.rfind(BEGIN, server_start, remove_start)
        marker_end = text.find(END, remove_end, server_close)
        if marker_begin >= 0 and marker_end >= 0:
            remove_start = marker_begin
            remove_end = marker_end + len(END)
            while remove_end < len(text) and text[remove_end] in " \t":
                remove_end += 1
            if remove_end < len(text) and text[remove_end] == "\n":
                remove_end += 1
        text = text[:remove_start] + text[remove_end:]
    elif BEGIN in server_text:
        begin = text.index(BEGIN, server_start, server_close)
        end_marker = text.index(END, begin, server_close) + len(END)
        while end_marker < len(text) and text[end_marker] in " \t":
            end_marker += 1
        if end_marker < len(text) and text[end_marker] == "\n":
            end_marker += 1
        text = text[:begin] + text[end_marker:]

    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    generic_start, _, _ = _generic_location(server_text)
    insert_at = server_start + generic_start
    indent = _indent_at(text, insert_at)
    inner = indent + "    "

    auth_lines = list(dict.fromkeys(auth_lines))
    lines = [
        indent + BEGIN,
        indent + f"location ^~ {CAM1_PREFIX} {{",
        inner + f"proxy_pass {UPSTREAM};",
        inner + "proxy_http_version 1.1;",
        inner + "proxy_buffering off;",
        inner + "proxy_cache off;",
        inner + "proxy_hide_header Cache-Control;",
        inner + "proxy_hide_header Expires;",
        inner + 'add_header Cache-Control "no-store, no-cache, must-revalidate" always;',
        inner + 'add_header Pragma "no-cache" always;',
        inner + "expires -1;",
    ]
    lines.extend(inner + line for line in auth_lines)
    lines += [indent + "}", indent + END, ""]
    block = "\n".join(lines)
    return text[:insert_at] + block + text[insert_at:]


def verify(text: str, host: str = "mostdef.ru") -> None:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    if server_text.count(BEGIN) != 1 or server_text.count(END) != 1:
        raise ConfigError("managed Camera 1 block missing or duplicated")
    if f"location ^~ {CAM1_PREFIX} {{" not in server_text:
        raise ConfigError("exact Camera 1 ^~ location missing")
    if f"proxy_pass {UPSTREAM};" not in server_text:
        raise ConfigError("Camera 1 direct H264 upstream missing")
    for required in ("proxy_cache off;", "proxy_buffering off;", "Cache-Control"):
        if required not in server_text:
            raise ConfigError(f"required directive missing: {required}")
    managed = server_text.split(BEGIN, 1)[1].split(END, 1)[0]
    if "127.0.0.1:8888" in managed or "mediamtx" in managed.lower():
        raise ConfigError("managed Camera 1 block still references MediaMTX")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "verify"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    parser.add_argument("--host", default="mostdef.ru")
    args = parser.parse_args()

    source = Path(args.config)
    text = source.read_text(encoding="utf-8")
    if args.command == "verify":
        verify(text, args.host)
        print("CAM1_DIRECT_H264_CONFIG=PASS")
        return 0

    if not args.output:
        parser.error("render requires --output")
    rendered = render(text, args.host)
    verify(rendered, args.host)
    Path(args.output).write_text(rendered, encoding="utf-8")
    print("CAM1_DIRECT_H264_RENDER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
