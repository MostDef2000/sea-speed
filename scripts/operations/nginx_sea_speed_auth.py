#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import re
from urllib.parse import urlsplit
from pathlib import Path

GLOBAL_BEGIN = "# SEA-SPEED-AUTH-V1-BEGIN"
GLOBAL_END = "# SEA-SPEED-AUTH-V1-END"
LOCATION_BEGIN = "# SEA-SPEED-AUTH-V1-LOCATION-BEGIN"
LOCATION_END = "# SEA-SPEED-AUTH-V1-LOCATION-END"
OLD_CAM1_BEGIN = "# SEA-SPEED-CAM1-DIRECT-H264-BEGIN"
OLD_CAM1_END = "# SEA-SPEED-CAM1-DIRECT-H264-END"
AUTH_URI = "/outpost.goauthentik.io/auth/nginx"
OUTPOST_PREFIX = "/outpost.goauthentik.io"
SEA_SPEED_PREFIX = "/sea-speed"
LEGACY_CAMS_PREFIX = "/cams"
AUTHENTIK_UPSTREAM = "http://127.0.0.1:9000"
WORKER_BEGIN = "# SEA-SPEED-WORKER-PRIVATE-V1-BEGIN"
WORKER_END = "# SEA-SPEED-WORKER-PRIVATE-V1-END"


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


def _is_target_host_server(body: str, host: str) -> bool:
    host_re = re.compile(rf"(?m)^\s*server_name\s+[^;]*\b{re.escape(host)}\b[^;]*;")
    tls_re = re.compile(r"(?m)^\s*listen\s+[^;]*\b443\b[^;]*;")
    return bool(host_re.search(body) and tls_re.search(body))


def _server_for_host(text: str, host: str) -> tuple[int, int, int]:
    matches = []
    for block in _blocks(text, "server"):
        _, open_index, close_index = block
        body = text[open_index + 1 : close_index]
        if _is_target_host_server(body, host):
            matches.append(block)
    if len(matches) != 1:
        raise ConfigError(f"expected exactly one TLS server block for {host}, found {len(matches)}")
    return matches[0]


def _strip_marked_sections(text: str, begin: str, end: str) -> str:
    while begin in text or end in text:
        if (begin in text) != (end in text):
            raise ConfigError(f"incomplete managed marker pair: {begin}")
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


def _indent_at(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    match = re.match(r"[ \t]*", text[line_start:index])
    return match.group(0) if match else ""


def _remove_location(text: str, server_start: int, start: int, close_index: int) -> str:
    remove_start = server_start + start
    remove_end = server_start + close_index + 1
    while remove_end < len(text) and text[remove_end] in " \t":
        remove_end += 1
    if remove_end < len(text) and text[remove_end] == "\n":
        remove_end += 1
    return text[:remove_start] + text[remove_end:]


def _strip_legacy_locations(text: str, host: str) -> str:
    while True:
        server_start, _, server_close = _server_for_host(text, host)
        server_text = text[server_start : server_close + 1]
        matches = []
        for spec, start, _open_index, close_index in _location_blocks(server_text):
            uri = _location_uri(spec)
            if uri == LEGACY_CAMS_PREFIX or uri.startswith(LEGACY_CAMS_PREFIX + "/"):
                matches.append((start, close_index))
        if not matches:
            return text
        start, close_index = matches[-1]
        text = _remove_location(text, server_start, start, close_index)


def _strip_basic_auth(body: str) -> str:
    body = re.sub(
        r"(?m)^[ \t]*auth_basic(?:_user_file)?\s+[^;]*;[ \t]*(?:\n|$)",
        "",
        body,
    )
    body = re.sub(r"auth_basic(?:_user_file)?\s+[^;]*;[ \t]*", "", body)
    return body.lstrip("\n")


def _auth_location_snippet(indent: str) -> str:
    inner = indent + "    "
    lines = [
        inner + LOCATION_BEGIN,
        inner + f"auth_request {AUTH_URI};",
        inner + "error_page 401 = @goauthentik_proxy_signin;",
        inner + "auth_request_set $auth_cookie $upstream_http_set_cookie;",
        inner + "add_header Set-Cookie $auth_cookie;",
        inner + "auth_request_set $authentik_username $upstream_http_x_authentik_username;",
        inner + "auth_request_set $authentik_groups $upstream_http_x_authentik_groups;",
        inner + "auth_request_set $authentik_entitlements $upstream_http_x_authentik_entitlements;",
        inner + "auth_request_set $authentik_email $upstream_http_x_authentik_email;",
        inner + "auth_request_set $authentik_name $upstream_http_x_authentik_name;",
        inner + "auth_request_set $authentik_uid $upstream_http_x_authentik_uid;",
        inner + "proxy_set_header X-authentik-username $authentik_username;",
        inner + "proxy_set_header X-authentik-groups $authentik_groups;",
        inner + "proxy_set_header X-authentik-entitlements $authentik_entitlements;",
        inner + "proxy_set_header X-authentik-email $authentik_email;",
        inner + "proxy_set_header X-authentik-name $authentik_name;",
        inner + "proxy_set_header X-authentik-uid $authentik_uid;",
        inner + LOCATION_END,
    ]
    return "\n" + "\n".join(lines) + "\n"


def _inject_location_auth(text: str, host: str) -> str:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    targets = []
    for spec, start, open_index, close_index in _location_blocks(server_text):
        uri = _location_uri(spec)
        if uri == SEA_SPEED_PREFIX or uri.startswith(SEA_SPEED_PREFIX + "/"):
            targets.append((start, open_index, close_index))
    if not targets:
        raise ConfigError("no /sea-speed location found in target server")
    for start, open_index, close_index in reversed(targets):
        global_open = server_start + open_index
        global_close = server_start + close_index
        body = _strip_basic_auth(text[global_open + 1 : global_close])
        indent = _indent_at(text, server_start + start)
        replacement = _auth_location_snippet(indent) + body
        text = text[: global_open + 1] + replacement + text[global_close:]
    return text


def _global_block(indent: str) -> str:
    inner = indent + "    "
    lines = [
        indent + GLOBAL_BEGIN,
        indent + "location = /cams {",
        inner + "return 404;",
        indent + "}",
        indent + "location ^~ /cams/ {",
        inner + "return 404;",
        indent + "}",
        indent + f"location ^~ {OUTPOST_PREFIX} {{",
        inner + f"proxy_pass {AUTHENTIK_UPSTREAM}{OUTPOST_PREFIX};",
        inner + "proxy_set_header Host $host;",
        inner + "proxy_set_header X-Original-URL $scheme://$http_host$request_uri;",
        inner + "add_header Set-Cookie $auth_cookie;",
        inner + "auth_request_set $auth_cookie $upstream_http_set_cookie;",
        inner + "proxy_pass_request_body off;",
        inner + 'proxy_set_header Content-Length "";',
        indent + "}",
        indent + "location @goauthentik_proxy_signin {",
        inner + "internal;",
        inner + "add_header Set-Cookie $auth_cookie;",
        inner + "return 302 /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;",
        indent + "}",
        indent + GLOBAL_END,
        "",
    ]
    return "\n".join(lines)


def _private_ipv4(value: str, *, with_port: bool = False) -> tuple[str, int | None]:
    raw = value.strip()
    port = None
    host = raw
    if with_port:
        if raw.count(":") != 1:
            raise ConfigError("worker private listen must be IPv4:port")
        host, raw_port = raw.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ConfigError("worker private listen port is invalid") from exc
        if port < 1024 or port > 65535:
            raise ConfigError("worker private listen port must be 1024..65535")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ConfigError("worker private address must be a literal IPv4") from exc
    if address.version != 4 or not address.is_private or address.is_loopback:
        raise ConfigError("worker private address must be a non-loopback RFC1918 IPv4")
    return str(address), port


def _api_origin(server_text: str) -> str:
    matches = []
    for spec, _start, open_index, close_index in _location_blocks(server_text):
        if _location_uri(spec) != "/sea-speed/api/":
            continue
        body = server_text[open_index + 1 : close_index]
        proxy = re.findall(r"(?m)^\s*proxy_pass\s+(https?://[^;]+);", body)
        if len(proxy) != 1:
            raise ConfigError("expected one proxy_pass in /sea-speed/api/ location")
        parsed = urlsplit(proxy[0])
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigError(
                "Sea Speed API upstream must remain loopback for private worker ingress"
            )
        if parsed.username or parsed.password or not parsed.port:
            raise ConfigError(
                "Sea Speed API upstream must be credential-free loopback host:port"
            )
        host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
        matches.append(f"{parsed.scheme}://{host}:{parsed.port}")
    if len(matches) != 1:
        raise ConfigError(f"expected exactly one /sea-speed/api/ location, found {len(matches)}")
    return matches[0]


def _worker_private_block(listen: str, peer: str, api_origin: str) -> str:
    listen_ip, listen_port = _private_ipv4(listen, with_port=True)
    peer_ip, _ = _private_ipv4(peer)
    endpoints = [
        ("/api/cam1/state", "POST"),
        ("/api/cam1/events", "POST"),
        ("/api/cam1/roi", "GET"),
        ("/api/cam1/speed-config", "GET"),
        ("/api/cam1/speed-lines", "GET"),
    ]
    lines = [
        WORKER_BEGIN,
        "server {",
        f"    listen {listen_ip}:{listen_port};",
        "    server_name sea-speed-worker-private;",
        f"    allow {peer_ip};",
        "    deny all;",
        "    client_max_body_size 25m;",
    ]
    for path, method in endpoints:
        lines += [
            f"    location = {path} {{",
            f"        limit_except {method} {{ deny all; }}",
            f"        proxy_pass {api_origin}{path};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header Authorization $http_authorization;",
            "        proxy_set_header X-Forwarded-For $remote_addr;",
            "    }",
        ]
    lines += [
        "    location / { return 404; }",
        "}",
        WORKER_END,
        "",
    ]
    return "\n".join(lines)


def render(
    text: str,
    host: str = "mostdef.ru",
    worker_private_listen: str | None = None,
    worker_private_peer: str | None = None,
) -> str:
    text = _strip_marked_sections(text, GLOBAL_BEGIN, GLOBAL_END)
    text = _strip_marked_sections(text, WORKER_BEGIN, WORKER_END)
    text = _strip_marked_sections(text, LOCATION_BEGIN, LOCATION_END)
    if OLD_CAM1_BEGIN in text or OLD_CAM1_END in text:
        text = _strip_marked_sections(text, OLD_CAM1_BEGIN, OLD_CAM1_END)
    text = _strip_legacy_locations(text, host)
    text = _inject_location_auth(text, host)

    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    sea_locations = [
        (start, spec)
        for spec, start, _open_index, _close_index in _location_blocks(server_text)
        if (
            _location_uri(spec) == SEA_SPEED_PREFIX
            or _location_uri(spec).startswith(SEA_SPEED_PREFIX + "/")
        )
    ]
    if not sea_locations:
        raise ConfigError("no /sea-speed location after auth injection")
    insert_at = server_start + min(start for start, _spec in sea_locations)
    indent = _indent_at(text, insert_at)
    text = text[:insert_at] + _global_block(indent) + text[insert_at:]
    if (worker_private_listen is None) != (worker_private_peer is None):
        raise ConfigError("worker private listen and peer must be supplied together")
    if worker_private_listen and worker_private_peer:
        server_start, _, server_close = _server_for_host(text, host)
        server_text = text[server_start : server_close + 1]
        origin = _api_origin(server_text)
        insert_worker_at = server_close + 1
        text = (
            text[:insert_worker_at]
            + "\n"
            + _worker_private_block(worker_private_listen, worker_private_peer, origin)
            + text[insert_worker_at:]
        )
    verify(
        text,
        host,
        worker_private_listen=worker_private_listen,
        worker_private_peer=worker_private_peer,
    )
    return text


def verify(
    text: str,
    host: str = "mostdef.ru",
    worker_private_listen: str | None = None,
    worker_private_peer: str | None = None,
) -> None:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    if server_text.count(GLOBAL_BEGIN) != 1 or server_text.count(GLOBAL_END) != 1:
        raise ConfigError("global Sea Speed Auth v1 block missing or duplicated")
    if f"proxy_pass {AUTHENTIK_UPSTREAM}{OUTPOST_PREFIX};" not in server_text:
        raise ConfigError("embedded Authentik outpost proxy missing")
    if "location @goauthentik_proxy_signin" not in server_text:
        raise ConfigError("Authentik signin location missing")

    sea_count = 0
    cams_count = 0
    for spec, _start, open_index, close_index in _location_blocks(server_text):
        uri = _location_uri(spec)
        body = server_text[open_index + 1 : close_index]
        if uri == SEA_SPEED_PREFIX or uri.startswith(SEA_SPEED_PREFIX + "/"):
            sea_count += 1
            required = (
                f"auth_request {AUTH_URI};",
                "error_page 401 = @goauthentik_proxy_signin;",
                "proxy_set_header X-authentik-username $authentik_username;",
                "proxy_set_header X-authentik-groups $authentik_groups;",
                "proxy_set_header X-authentik-email $authentik_email;",
                "proxy_set_header X-authentik-uid $authentik_uid;",
            )
            for marker in required:
                if marker not in body:
                    raise ConfigError(
                        f"unprotected Sea Speed location {spec}: missing {marker}"
                    )
            if "auth_basic " in body or "auth_basic_user_file " in body:
                raise ConfigError(f"legacy Basic Auth remains in Sea Speed location {spec}")
        if uri == LEGACY_CAMS_PREFIX or uri.startswith(LEGACY_CAMS_PREFIX + "/"):
            cams_count += 1
            if "return 404;" not in body or "proxy_pass" in body:
                raise ConfigError(f"legacy cams location is not retired: {spec}")
    if sea_count < 1:
        raise ConfigError("no protected Sea Speed locations found")
    if cams_count != 2:
        raise ConfigError(f"expected exactly two deny-only /cams locations, found {cams_count}")
    if "/cams/hls/cam1/" in server_text:
        raise ConfigError("legacy Camera 1 browser path remains in nginx server")
    if worker_private_listen or worker_private_peer:
        if not worker_private_listen or not worker_private_peer:
            raise ConfigError("worker private listen and peer must be supplied together")
        expected = _worker_private_block(
            worker_private_listen,
            worker_private_peer,
            _api_origin(server_text),
        ).strip()
        if expected not in text:
            raise ConfigError(
                "private worker ingress block missing or does not match expected addresses"
            )
    elif WORKER_BEGIN in text or WORKER_END in text:
        if text.count(WORKER_BEGIN) != 1 or text.count(WORKER_END) != 1:
            raise ConfigError("private worker ingress markers are incomplete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "verify"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--output")
    parser.add_argument("--host", default="mostdef.ru")
    parser.add_argument("--worker-private-listen")
    parser.add_argument("--worker-private-peer")
    args = parser.parse_args()
    source = Path(args.config)
    text = source.read_text(encoding="utf-8")
    if args.command == "verify":
        verify(
            text,
            args.host,
            worker_private_listen=args.worker_private_listen,
            worker_private_peer=args.worker_private_peer,
        )
        print("SEA_SPEED_AUTH_CONFIG=PASS")
        return 0
    if not args.output:
        parser.error("render requires --output")
    rendered = render(
        text,
        args.host,
        worker_private_listen=args.worker_private_listen,
        worker_private_peer=args.worker_private_peer,
    )
    Path(args.output).write_text(rendered, encoding="utf-8")
    print("SEA_SPEED_AUTH_RENDER=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
