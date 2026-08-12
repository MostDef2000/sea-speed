#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

BEGIN = "# SEA-SPEED-CAM1-PROTECTED-H264-BEGIN"
END = "# SEA-SPEED-CAM1-PROTECTED-H264-END"
OLD_BEGIN = "# SEA-SPEED-CAM1-DIRECT-H264-BEGIN"
OLD_END = "# SEA-SPEED-CAM1-DIRECT-H264-END"
CAM1_PREFIX = "/sea-speed/media/cam1/"
LEGACY_CAM1_PREFIX = "/cams/hls/cam1/"
SEA_SPEED_PREFIX = "/sea-speed/"
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
    out = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(keyword)}\b[^{{;]*{{", text):
        open_index = text.find("{", match.start(), match.end())
        close_index = _matching_brace(text, open_index)
        if close_index < 0:
            raise ConfigError(f"unbalanced {keyword} block")
        out.append((match.start(), open_index, close_index))
    return out


def _location_blocks(server_text: str) -> list[tuple[str, int, int, int]]:
    out = []
    pattern = re.compile(r"(?m)^\s*location\s+([^\{]+)\{")
    for match in pattern.finditer(server_text):
        spec = match.group(1).strip()
        open_index = server_text.find("{", match.start(), match.end())
        close_index = _matching_brace(server_text, open_index)
        if close_index < 0:
            raise ConfigError("unbalanced location block")
        out.append((spec, match.start(), open_index, close_index))
    return out


def _location_uri(spec: str) -> str:
    parts = spec.split()
    if not parts:
        return ""
    if parts[0] in {"=", "^~", "~", "~*"}:
        return parts[1] if len(parts) > 1 else ""
    return parts[0]


def _server_for_host(text: str, host: str) -> tuple[int, int, int]:
    matches = []
    host_re = re.compile(rf"(?m)^\s*server_name\s+[^;]*\b{re.escape(host)}\b[^;]*;")
    tls_re = re.compile(r"(?m)^\s*listen\s+[^;]*\b443\b[^;]*;")
    for block in _blocks(text, "server"):
        _, open_index, close_index = block
        body = text[open_index + 1 : close_index]
        if host_re.search(body) and tls_re.search(body):
            matches.append(block)
    if len(matches) != 1:
        raise ConfigError(f"expected exactly one TLS server block for {host}, found {len(matches)}")
    return matches[0]


def _strip_marked_section(text: str, begin: str, end: str) -> str:
    while begin in text or end in text:
        if (begin in text) != (end in text):
            raise ConfigError(f"incomplete marker pair: {begin}")
        start = text.index(begin)
        finish = text.index(end, start) + len(end)
        line_start = text.rfind("\n", 0, start) + 1
        while finish < len(text) and text[finish] in " \t":
            finish += 1
        if finish < len(text) and text[finish] == "\r":
            finish += 1
        if finish < len(text) and text[finish] == "\n":
            finish += 1
        while finish < len(text) and text[finish] in "\r\n":
            finish += 1
        text = text[:line_start] + text[finish:]
    return text


def _remove_location(text: str, host: str, target_uri: str) -> str:
    while True:
        server_start, _, server_close = _server_for_host(text, host)
        server_text = text[server_start : server_close + 1]
        matches = [
            (start, close_index)
            for spec, start, _open, close_index in _location_blocks(server_text)
            if _location_uri(spec) == target_uri
        ]
        if not matches:
            return text
        if len(matches) > 1:
            raise ConfigError(f"multiple locations found for {target_uri}")
        start, close_index = matches[0]
        remove_start = server_start + start
        remove_end = server_start + close_index + 1
        while remove_end < len(text) and text[remove_end] in " \t":
            remove_end += 1
        if remove_end < len(text) and text[remove_end] == "\n":
            remove_end += 1
        text = text[:remove_start] + text[remove_end:]


def _indent_at(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    match = re.match(r"[ \t]*", text[line_start:index])
    return match.group(0) if match else ""


def render(text: str, host: str = "mostdef.ru") -> str:
    text = _strip_marked_section(text, BEGIN, END)
    if OLD_BEGIN in text or OLD_END in text:
        text = _strip_marked_section(text, OLD_BEGIN, OLD_END)
    text = _remove_location(text, host, CAM1_PREFIX)
    text = _remove_location(text, host, LEGACY_CAM1_PREFIX)

    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    targets = [
        start
        for spec, start, _open, _close in _location_blocks(server_text)
        if _location_uri(spec) == SEA_SPEED_PREFIX
    ]
    if len(targets) != 1:
        raise ConfigError(
            f"expected exactly one {SEA_SPEED_PREFIX} location for insertion, found {len(targets)}"
        )
    insert_at = server_start + targets[0]
    indent = _indent_at(text, insert_at)
    inner = indent + "    "
    block = "\n".join(
        [
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
            indent + "}",
            indent + END,
            "",
        ]
    )
    text = text[:insert_at] + block + text[insert_at:]
    verify(text, host)
    return text


def verify(text: str, host: str = "mostdef.ru") -> None:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    if server_text.count(BEGIN) != 1 or server_text.count(END) != 1:
        raise ConfigError("managed protected Camera 1 block missing or duplicated")
    if f"location ^~ {CAM1_PREFIX} {{" not in server_text:
        raise ConfigError("protected Camera 1 location missing")
    if f"proxy_pass {UPSTREAM};" not in server_text:
        raise ConfigError("Camera 1 H264 upstream missing")
    if LEGACY_CAM1_PREFIX in server_text:
        raise ConfigError("legacy public Camera 1 location remains")
    managed = server_text.split(BEGIN, 1)[1].split(END, 1)[0]
    for required in ("proxy_cache off;", "proxy_buffering off;", "Cache-Control"):
        if required not in managed:
            raise ConfigError(f"required Camera 1 directive missing: {required}")
    if "127.0.0.1:8888" in managed or "mediamtx" in managed.lower():
        raise ConfigError("protected Camera 1 block references MediaMTX")
    if "auth_basic " in managed or "auth_basic_user_file " in managed:
        raise ConfigError("legacy Basic Auth must not be embedded in Camera 1 media block")


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
        print("CAM1_PROTECTED_H264_CONFIG=PASS")
        return 0
    if not args.output:
        parser.error("render requires --output")
    rendered = render(text, args.host)
    Path(args.output).write_text(rendered, encoding="utf-8")
    print("CAM1_PROTECTED_H264_RENDER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
