#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit

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
DEFAULT_AUTHENTIK_UPSTREAM = "http://127.0.0.1:9000"
DEFAULT_SEA_SPEED_INCLUDE_ROOT = Path("/etc/nginx/snippets")
FALLBACK_URI = "/sea-speed-unavailable.html"
FALLBACK_ROOT = "/var/www/mostdef.ru"
FALLBACK_BEGIN = "# SEA-SPEED-FALLBACK-V1-BEGIN"
FALLBACK_END = "# SEA-SPEED-FALLBACK-V1-END"
MATERIALIZED_INCLUDE_BEGIN = "# SEA-SPEED-INCLUDE-MATERIALIZED-BEGIN"
MATERIALIZED_INCLUDE_END = "# SEA-SPEED-INCLUDE-MATERIALIZED-END"
WORKER_BEGIN = "# SEA-SPEED-WORKER-PRIVATE-V1-BEGIN"
WORKER_END = "# SEA-SPEED-WORKER-PRIVATE-V1-END"
WORKER_BROWSER_CONTROL_PREFIX = "/api/worker/control"
WORKER_BROWSER_CONTROL_PATHS = (
    "/api/worker/control",
    "/api/worker/control/start",
    "/api/worker/control/stop",
    "/api/worker/control/road1",
    "/api/worker/control/road1/start",
    "/api/worker/control/road1/stop",
)
WORKER_PRIVATE_ENDPOINTS = (
    ("/api/cam1/state", "POST"),
    ("/api/cam1/events", "POST"),
    ("/api/cam1/passages", "POST"),
    ("/api/cam1/roi", "GET"),
    ("/api/cam1/speed-config", "GET"),
    ("/api/cam1/speed-lines", "GET"),
    ("/api/analytics/road1/state", "POST"),
    ("/api/analytics/road1/events", "POST"),
    ("/api/analytics/road1/roi", "GET"),
    ("/api/analytics/road1/speed-config", "GET"),
    ("/api/analytics/road1/speed-lines", "GET"),
)
RFC1918_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
INCLUDE_DIRECTIVE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)include[ \t]+(?P<path>[^; \t\r\n]+)[ \t]*;[ \t]*(?:#.*)?$"
)
SEA_SPEED_INCLUDE_NAME_RE = re.compile(r"^sea-speed-[A-Za-z0-9._-]+\.conf$")


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
            if ch == "\n": in_comment = False
            continue
        if quote:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == quote: quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == "#":
            in_comment = True
            continue
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: return i
    return -1


def _blocks(text: str, keyword: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for match in re.finditer(rf"(?m)^\s*{re.escape(keyword)}\b[^{{;]*{{", text):
        open_index = text.find("{", match.start(), match.end())
        close_index = _matching_brace(text, open_index)
        if close_index < 0: raise ConfigError(f"unbalanced {keyword} block")
        out.append((match.start(), open_index, close_index))
    return out


def _location_blocks(server_text: str) -> list[tuple[str, int, int, int]]:
    out = []
    pattern = re.compile(r"(?m)^\s*location\s+([^\{]+)\{")
    for match in pattern.finditer(server_text):
        spec = match.group(1).strip()
        open_index = server_text.find("{", match.start(), match.end())
        close_index = _matching_brace(server_text, open_index)
        if close_index < 0: raise ConfigError("unbalanced location block")
        out.append((spec, match.start(), open_index, close_index))
    return out


def _location_uri(spec: str) -> str:
    parts = spec.split()
    if not parts: return ""
    if parts[0] in {"=", "^~", "~", "~*"}: return parts[1] if len(parts) > 1 else ""
    return parts[0]


def _is_target_host_server(body: str, host: str) -> bool:
    names: list[str] = []
    for match in re.finditer(r"(?m)^\s*server_name\s+([^;]+);", body): names.extend(match.group(1).split())
    tls_re = re.compile(r"(?m)^\s*listen\s+[^;]*\b443\b[^;]*;")
    return host in names and bool(tls_re.search(body))


def _server_for_host(text: str, host: str) -> tuple[int, int, int]:
    matches = []
    for block in _blocks(text, "server"):
        _, open_index, close_index = block
        body = text[open_index + 1 : close_index]
        if _is_target_host_server(body, host): matches.append(block)
    if len(matches) != 1: raise ConfigError(f"expected exactly one TLS server block for {host}, found {len(matches)}")
    return matches[0]


def _is_sea_speed_include_path(raw: str) -> bool:
    name = raw.rsplit("/", 1)[-1]
    return name.startswith("sea-speed-") and name.endswith(".conf")


def verify_source_layout(text: str, host: str = "mostdef.ru") -> None:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    for spec, _start, _open_index, _close_index in _location_blocks(server_text):
        uri = _location_uri(spec)
        if uri == SEA_SPEED_PREFIX or uri.startswith(SEA_SPEED_PREFIX + "/"): return
    if any(_is_sea_speed_include_path(match.group("path")) for match in INCLUDE_DIRECTIVE_RE.finditer(server_text)): return
    raise ConfigError(f"target TLS server for {host} has no /sea-speed locations or direct Sea Speed snippet include")


def materialize_sea_speed_includes(text: str, host: str = "mostdef.ru", include_root: str | Path = DEFAULT_SEA_SPEED_INCLUDE_ROOT) -> str:
    verify_source_layout(text, host)
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    try: root = Path(include_root).resolve(strict=True)
    except OSError as exc: raise ConfigError(f"Sea Speed include root is unavailable: {include_root}") from exc
    if not root.is_dir(): raise ConfigError(f"Sea Speed include root is not a directory: {root}")
    replacements: list[tuple[int, int, str]] = []
    for match in INCLUDE_DIRECTIVE_RE.finditer(server_text):
        raw = match.group("path")
        if not _is_sea_speed_include_path(raw): continue
        if any(char in raw for char in "*?["): raise ConfigError(f"wildcard Sea Speed include is not allowed: {raw}")
        include_path = Path(raw)
        if not include_path.is_absolute(): raise ConfigError(f"Sea Speed include must use an absolute path: {raw}")
        if not SEA_SPEED_INCLUDE_NAME_RE.fullmatch(include_path.name): raise ConfigError(f"invalid Sea Speed include name: {raw}")
        if include_path.is_symlink(): raise ConfigError(f"Sea Speed include must be a regular non-symlink file: {raw}")
        try: resolved = include_path.resolve(strict=True)
        except OSError as exc: raise ConfigError(f"Sea Speed include is unavailable: {raw}") from exc
        if resolved.parent != root: raise ConfigError(f"Sea Speed include is outside approved root {root}: {raw}")
        if not resolved.is_file(): raise ConfigError(f"Sea Speed include is not a regular file: {raw}")
        body = resolved.read_text(encoding="utf-8")
        if re.search(r"(?m)^[ \t]*include[ \t]+[^;]+;", body): raise ConfigError(f"nested include is not allowed in Sea Speed snippet: {raw}")
        indent = match.group("indent")
        normalized = body.rstrip("\r\n")
        replacement = f"{indent}{MATERIALIZED_INCLUDE_BEGIN} {raw}\n{normalized}\n{indent}{MATERIALIZED_INCLUDE_END} {raw}"
        replacements.append((match.start(), match.end(), replacement))
    if not replacements: return text
    for start, end, replacement in reversed(replacements): server_text = server_text[:start] + replacement + server_text[end:]
    rendered = text[:server_start] + server_text + text[server_close + 1 :]
    verify_source_layout(rendered, host)
    return rendered


def _strip_marked_sections(text: str, begin: str, end: str) -> str:
    while begin in text or end in text:
        if (begin in text) != (end in text): raise ConfigError(f"incomplete managed marker pair: {begin}")
        start = text.index(begin)
        finish = text.index(end, start) + len(end)
        line_start = text.rfind("\n", 0, start) + 1
        while finish < len(text) and text[finish] in " \t": finish += 1
        if finish < len(text) and text[finish] == "\r": finish += 1
        if finish < len(text) and text[finish] == "\n": finish += 1
        while finish < len(text) and text[finish] in "\r\n": finish += 1
        text = text[:line_start] + text[finish:]
    return text


def _indent_at(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    match = re.match(r"[ \t]*", text[line_start:index])
    return match.group(0) if match else ""


def _remove_location(text: str, server_start: int, start: int, close_index: int) -> str:
    remove_start = server_start + start
    remove_end = server_start + close_index + 1
    while remove_end < len(text) and text[remove_end] in " \t": remove_end += 1
    if remove_end < len(text) and text[remove_end] == "\n": remove_end += 1
    return text[:remove_start] + text[remove_end:]


def _strip_legacy_locations(text: str, host: str) -> str:
    while True:
        server_start, _, server_close = _server_for_host(text, host)
        server_text = text[server_start : server_close + 1]
        matches = []
        for spec, start, _open_index, close_index in _location_blocks(server_text):
            uri = _location_uri(spec)
            if uri == LEGACY_CAMS_PREFIX or uri.startswith(LEGACY_CAMS_PREFIX + "/"): matches.append((start, close_index))
        if not matches: return text
        start, close_index = matches[-1]
        text = _remove_location(text, server_start, start, close_index)


def _strip_basic_auth(body: str) -> str:
    body = re.sub(r"(?m)^[ \t]*auth_basic(?:_user_file)?\s+[^;]*;[ \t]*(?:\n|$)", "", body)
    body = re.sub(r"auth_basic(?:_user_file)?\s+[^;]*;[ \t]*", "", body)
    return body.lstrip("\n")


def _auth_location_snippet(indent: str) -> str:
    inner = indent + "    "
    lines = [inner + LOCATION_BEGIN, inner + f"auth_request {AUTH_URI};", inner + "error_page 401 = @goauthentik_proxy_signin;", inner + f"error_page 500 =503 {FALLBACK_URI};", inner + "auth_request_set $auth_cookie $upstream_http_set_cookie;", inner + "add_header Set-Cookie $auth_cookie;", inner + "auth_request_set $authentik_username $upstream_http_x_authentik_username;", inner + "auth_request_set $authentik_groups $upstream_http_x_authentik_groups;", inner + "auth_request_set $authentik_entitlements $upstream_http_x_authentik_entitlements;", inner + "auth_request_set $authentik_email $upstream_http_x_authentik_email;", inner + "auth_request_set $authentik_name $upstream_http_x_authentik_name;", inner + "auth_request_set $authentik_uid $upstream_http_x_authentik_uid;", inner + "proxy_set_header X-authentik-username $authentik_username;", inner + "proxy_set_header X-authentik-groups $authentik_groups;", inner + "proxy_set_header X-authentik-entitlements $authentik_entitlements;", inner + "proxy_set_header X-authentik-email $authentik_email;", inner + "proxy_set_header X-authentik-name $authentik_name;", inner + "proxy_set_header X-authentik-uid $authentik_uid;", inner + LOCATION_END]
    return "\n" + "\n".join(lines) + "\n"


def _fallback_block(indent: str) -> str:
    inner = indent + "    "
    lines = [indent + FALLBACK_BEGIN, indent + f"location = {FALLBACK_URI} {{", inner + "internal;", inner + f"root {FALLBACK_ROOT};", inner + 'add_header Cache-Control "no-store" always;', inner + 'add_header Retry-After "30" always;', indent + "}", indent + FALLBACK_END, ""]
    return "\n".join(lines)


def _inject_location_auth(text: str, host: str) -> str:
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    targets = []
    for spec, start, open_index, close_index in _location_blocks(server_text):
        uri = _location_uri(spec)
        if uri == SEA_SPEED_PREFIX or uri.startswith(SEA_SPEED_PREFIX + "/"): targets.append((start, open_index, close_index))
    if not targets: raise ConfigError("no /sea-speed location found in target server")
    for start, open_index, close_index in reversed(targets):
        global_open = server_start + open_index
        global_close = server_start + close_index
        body = _strip_basic_auth(text[global_open + 1 : global_close])
        indent = _indent_at(text, server_start + start)
        replacement = _auth_location_snippet(indent) + body
        text = text[: global_open + 1] + replacement + text[global_close:]
    return text


def _authentik_upstream(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme != "http": raise ConfigError("Authentik upstream must use private HTTP behind VPS TLS")
    if parsed.username or parsed.password: raise ConfigError("Authentik upstream must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment: raise ConfigError("Authentik upstream must be an origin without path/query/fragment")
    if not parsed.hostname or parsed.port is None: raise ConfigError("Authentik upstream must be literal IPv4:port")
    try: address = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc: raise ConfigError("Authentik upstream host must be a literal IPv4") from exc
    if address.version != 4: raise ConfigError("Authentik upstream must use IPv4")
    if not address.is_loopback and not any(address in network for network in RFC1918_NETWORKS): raise ConfigError("Authentik upstream must be loopback or RFC1918 private IPv4")
    if not 1024 <= parsed.port <= 65535: raise ConfigError("Authentik upstream port must be 1024..65535")
    return f"http://{address}:{parsed.port}"


def _global_block(indent: str, authentik_upstream: str, host: str) -> str:
    inner = indent + "    "
    origin = _authentik_upstream(authentik_upstream)
    lines = [indent + GLOBAL_BEGIN, indent + f"if ($host = www.{host}) {{", inner + f"return 308 https://{host}$request_uri;", indent + "}", indent + "location = /cams {", inner + "return 404;", indent + "}", indent + "location ^~ /cams/ {", inner + "return 404;", indent + "}", indent + f"location ^~ {OUTPOST_PREFIX} {{", inner + f"proxy_pass {origin}{OUTPOST_PREFIX};", inner + "proxy_set_header Host $host;", inner + "proxy_set_header X-Original-URL $scheme://$http_host$request_uri;", inner + "add_header Set-Cookie $auth_cookie;", inner + "auth_request_set $auth_cookie $upstream_http_set_cookie;", inner + "proxy_pass_request_body off;", inner + 'proxy_set_header Content-Length "";', indent + "}", indent + "location @goauthentik_proxy_signin {", inner + "internal;", inner + "add_header Set-Cookie $auth_cookie;", inner + "return 302 /outpost.goauthentik.io/start?rd=$scheme://$http_host$request_uri;", indent + "}", indent + GLOBAL_END, ""]
    return "\n".join(lines)


def _private_ipv4(value: str, *, with_port: bool = False) -> tuple[str, int | None]:
    raw = value.strip(); port = None; host = raw
    if with_port:
        if raw.count(":") != 1: raise ConfigError("worker private listen must be IPv4:port")
        host, raw_port = raw.rsplit(":", 1)
        try: port = int(raw_port)
        except ValueError as exc: raise ConfigError("worker private listen port is invalid") from exc
        if port < 1024 or port > 65535: raise ConfigError("worker private listen port must be 1024..65535")
    try: address = ipaddress.ip_address(host)
    except ValueError as exc: raise ConfigError("worker private address must be a literal IPv4") from exc
    if address.version != 4 or not any(address in network for network in RFC1918_NETWORKS): raise ConfigError("worker private address must be a non-loopback RFC1918 IPv4")
    return str(address), port


def _api_origin(server_text: str) -> str:
    matches = []
    for spec, _start, open_index, close_index in _location_blocks(server_text):
        if _location_uri(spec) != "/sea-speed/api/": continue
        body = server_text[open_index + 1 : close_index]
        proxy = re.findall(r"(?m)^\s*proxy_pass\s+(https?://[^;]+);", body)
        if len(proxy) != 1: raise ConfigError("expected one proxy_pass in /sea-speed/api/ location")
        parsed = urlsplit(proxy[0])
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}: raise ConfigError("Sea Speed API upstream must remain loopback for private worker ingress")
        if parsed.username or parsed.password or not parsed.port: raise ConfigError("Sea Speed API upstream must be credential-free loopback host:port")
        host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
        matches.append(f"{parsed.scheme}://{host}:{parsed.port}")
    if len(matches) != 1: raise ConfigError(f"expected exactly one /sea-speed/api/ location, found {len(matches)}")
    return matches[0]


def _worker_private_block(listen: str, peer: str, api_origin: str) -> str:
    listen_ip, listen_port = _private_ipv4(listen, with_port=True)
    peer_ip, _ = _private_ipv4(peer)
    endpoints = WORKER_PRIVATE_ENDPOINTS
    if any(path in WORKER_BROWSER_CONTROL_PATHS or path.startswith(WORKER_BROWSER_CONTROL_PREFIX + "/") for path, _method in endpoints):
        raise ConfigError("browser worker-control endpoints must never be exposed on private worker ingress")
    lines = [WORKER_BEGIN, "server {", f"    listen {listen_ip}:{listen_port};", "    server_name sea-speed-worker-private;", f"    allow {peer_ip};", "    deny all;", "    client_max_body_size 25m;"]
    for path, method in endpoints:
        lines += [f"    location = {path} {{", f"        limit_except {method} {{ deny all; }}", f"        proxy_pass {api_origin}{path};", "        proxy_set_header Host $host;", "        proxy_set_header Authorization $http_authorization;", "        proxy_set_header X-Forwarded-For $remote_addr;", "    }"]
    lines += ["    location / { return 404; }", "}", WORKER_END, ""]
    return "\n".join(lines)


def render(text: str, host: str = "mostdef.ru", worker_private_listen: str | None = None, worker_private_peer: str | None = None, authentik_upstream: str = DEFAULT_AUTHENTIK_UPSTREAM) -> str:
    origin = _authentik_upstream(authentik_upstream)
    if (worker_private_listen is None) != (worker_private_peer is None): raise ConfigError("worker private listen and peer must be supplied together")
    want_worker = worker_private_listen is not None
    has_worker = WORKER_BEGIN in text or WORKER_END in text
    if GLOBAL_BEGIN in text and GLOBAL_END in text and has_worker == want_worker and FALLBACK_BEGIN in text and FALLBACK_END in text:
        try:
            verify(text, host, worker_private_listen=worker_private_listen, worker_private_peer=worker_private_peer, authentik_upstream=origin)
            return text
        except ConfigError: pass
    text = _strip_marked_sections(text, GLOBAL_BEGIN, GLOBAL_END)
    text = _strip_marked_sections(text, WORKER_BEGIN, WORKER_END)
    text = _strip_marked_sections(text, LOCATION_BEGIN, LOCATION_END)
    text = _strip_marked_sections(text, FALLBACK_BEGIN, FALLBACK_END)
    if OLD_CAM1_BEGIN in text or OLD_CAM1_END in text: text = _strip_marked_sections(text, OLD_CAM1_BEGIN, OLD_CAM1_END)
    text = _strip_legacy_locations(text, host)
    text = _inject_location_auth(text, host)
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    sea_locations = [(start, spec) for spec, start, _open_index, _close_index in _location_blocks(server_text) if (_location_uri(spec) == SEA_SPEED_PREFIX or _location_uri(spec).startswith(SEA_SPEED_PREFIX + "/"))]
    if not sea_locations: raise ConfigError("no /sea-speed location after auth injection")
    insert_at = server_start + min(start for start, _spec in sea_locations)
    indent = _indent_at(text, insert_at)
    text = text[:insert_at] + _global_block(indent, origin, host) + _fallback_block(indent) + text[insert_at:]
    if worker_private_listen and worker_private_peer:
        server_start, _, server_close = _server_for_host(text, host)
        server_text = text[server_start : server_close + 1]
        api_origin = _api_origin(server_text)
        insert_worker_at = server_close + 1
        text = text[:insert_worker_at] + "\n" + _worker_private_block(worker_private_listen, worker_private_peer, api_origin) + text[insert_worker_at:]
    verify(text, host, worker_private_listen=worker_private_listen, worker_private_peer=worker_private_peer, authentik_upstream=origin)
    return text


def verify(text: str, host: str = "mostdef.ru", worker_private_listen: str | None = None, worker_private_peer: str | None = None, authentik_upstream: str = DEFAULT_AUTHENTIK_UPSTREAM) -> None:
    origin = _authentik_upstream(authentik_upstream)
    server_start, _, server_close = _server_for_host(text, host)
    server_text = text[server_start : server_close + 1]
    if server_text.count(GLOBAL_BEGIN) != 1 or server_text.count(GLOBAL_END) != 1: raise ConfigError("global Sea Speed Auth v1 block missing or duplicated")
    if server_text.count(FALLBACK_BEGIN) != 1 or server_text.count(FALLBACK_END) != 1: raise ConfigError("fallback Sea Speed outage page block missing or duplicated")
    canonical_if = f"if ($host = www.{host}) {{"; canonical_return = f"return 308 https://{host}$request_uri;"
    if server_text.count(canonical_if) != 1 or server_text.count(canonical_return) != 1: raise ConfigError("canonical www host redirect missing or duplicated")
    if f"proxy_pass {origin}{OUTPOST_PREFIX};" not in server_text: raise ConfigError("embedded Authentik outpost proxy missing or wrong private origin")
    if "location @goauthentik_proxy_signin" not in server_text: raise ConfigError("Authentik signin location missing")
    fallback_expected = f"location = {FALLBACK_URI} {{"
    if fallback_expected not in server_text: raise ConfigError("fallback Sea Speed outage location missing")
    if "internal;" not in server_text or f"root {FALLBACK_ROOT};" not in server_text: raise ConfigError("fallback outage location must be internal with VPS-local root")
    if 'add_header Cache-Control "no-store" always;' not in server_text: raise ConfigError("fallback outage location must use Cache-Control no-store")
    if 'add_header Retry-After "30" always;' not in server_text: raise ConfigError("fallback outage location must set Retry-After")
    sea_count = cams_count = outpost_count = 0
    for spec, _start, open_index, close_index in _location_blocks(server_text):
        uri = _location_uri(spec); body = server_text[open_index + 1 : close_index]
        if uri == FALLBACK_URI:
            if "internal;" not in body: raise ConfigError("fallback outage location must be internal")
            continue
        if uri == OUTPOST_PREFIX:
            outpost_count += 1
            if f"proxy_pass {origin}{OUTPOST_PREFIX};" not in body: raise ConfigError("root Authentik outpost proxy uses wrong private origin")
            if "auth_request " in body or "error_page 401" in body: raise ConfigError("root Authentik outpost must not recursively require auth")
        if uri.startswith(SEA_SPEED_PREFIX + OUTPOST_PREFIX): raise ConfigError("prefixed Authentik outpost location is not allowed")
        if uri == SEA_SPEED_PREFIX or uri.startswith(SEA_SPEED_PREFIX + "/"):
            sea_count += 1
            required = (f"auth_request {AUTH_URI};", "error_page 401 = @goauthentik_proxy_signin;", f"error_page 500 =503 {FALLBACK_URI};", "proxy_set_header X-authentik-username $authentik_username;", "proxy_set_header X-authentik-groups $authentik_groups;", "proxy_set_header X-authentik-email $authentik_email;", "proxy_set_header X-authentik-uid $authentik_uid;")
            for marker in required:
                if marker not in body: raise ConfigError(f"unprotected Sea Speed location {spec}: missing {marker}")
            if "auth_basic " in body or "auth_basic_user_file " in body: raise ConfigError(f"legacy Basic Auth remains in Sea Speed location {spec}")
        if uri == LEGACY_CAMS_PREFIX or uri.startswith(LEGACY_CAMS_PREFIX + "/"):
            cams_count += 1
            if "return 404;" not in body or "proxy_pass" in body: raise ConfigError(f"legacy cams location is not retired: {spec}")
    if outpost_count != 1: raise ConfigError(f"expected exactly one root Authentik outpost location, found {outpost_count}")
    if sea_count < 1: raise ConfigError("no protected Sea Speed locations found")
    if cams_count != 2: raise ConfigError(f"expected exactly two deny-only /cams locations, found {cams_count}")
    if "/cams/hls/cam1/" in server_text: raise ConfigError("legacy Camera 1 browser path remains in nginx server")
    if worker_private_listen or worker_private_peer:
        if not worker_private_listen or not worker_private_peer: raise ConfigError("worker private listen and peer must be supplied together")
        expected = _worker_private_block(worker_private_listen, worker_private_peer, _api_origin(server_text)).strip()
        if expected not in text: raise ConfigError("private worker ingress block missing or does not match expected addresses")
    elif WORKER_BEGIN in text or WORKER_END in text:
        if text.count(WORKER_BEGIN) != 1 or text.count(WORKER_END) != 1: raise ConfigError("private worker ingress markers are incomplete")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "verify", "materialize", "source-check"))
    parser.add_argument("--config", required=True); parser.add_argument("--output"); parser.add_argument("--host", default="mostdef.ru")
    parser.add_argument("--include-root", default=str(DEFAULT_SEA_SPEED_INCLUDE_ROOT)); parser.add_argument("--worker-private-listen"); parser.add_argument("--worker-private-peer"); parser.add_argument("--authentik-upstream", default=DEFAULT_AUTHENTIK_UPSTREAM)
    args = parser.parse_args(); source = Path(args.config); text = source.read_text(encoding="utf-8")
    if args.command == "source-check": verify_source_layout(text, args.host); print("SEA_SPEED_AUTH_SOURCE_LAYOUT=PASS"); return 0
    if args.command == "materialize":
        if not args.output: parser.error("materialize requires --output")
        materialized = materialize_sea_speed_includes(text, args.host, include_root=args.include_root); Path(args.output).write_text(materialized, encoding="utf-8"); print("SEA_SPEED_AUTH_INCLUDE_MATERIALIZE=PASS"); return 0
    if args.command == "verify":
        verify(text, args.host, worker_private_listen=args.worker_private_listen, worker_private_peer=args.worker_private_peer, authentik_upstream=args.authentik_upstream); print("SEA_SPEED_AUTH_CONFIG=PASS"); return 0
    if not args.output: parser.error("render requires --output")
    rendered = render(text, args.host, worker_private_listen=args.worker_private_listen, worker_private_peer=args.worker_private_peer, authentik_upstream=args.authentik_upstream)
    Path(args.output).write_text(rendered, encoding="utf-8"); print("SEA_SPEED_AUTH_RENDER=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main())