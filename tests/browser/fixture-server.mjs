// Local fixture server for the #684 browser JS gate.
//
// Serves the six shipped operator pages, their shipped scripts, a local hls.js
// stub (no internet at test time) and deterministic API JSON. Every response
// carries the production Sea Speed CSP as a real header, so the browser really
// enforces the policy shipped by scripts/operations/nginx_sea_speed_auth.py.
//
// Harness deviation, deliberate and narrow: the shipped HTML references
// https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js with a `integrity`
// SRI digest. A synthetic stub can never satisfy that digest, and a blocked
// script would defeat the point of the gate, so this server strips only the
// `integrity`/`crossorigin` attributes of that one tag. Every other byte of the
// shipped HTML/JS is served untouched. The spec still asserts (a) the DOM keeps
// the absolute CDN URL, (b) the stub executed, and (c) no real CDN request is
// ever made.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// tests/browser/ -> repository root
const REPO_ROOT = path.resolve(HERE, "..", "..");
const FRONTEND_ROOT = path.join(REPO_ROOT, "frontend");
const SEA_SPEED_ROOT = path.join(FRONTEND_ROOT, "sea-speed");

export const FIXTURE_PORT = 8131;

export const HLS_CDN_URL = "https://cdn.jsdelivr.net/npm/hls.js@1.7.4/dist/hls.min.js";
export const HLS_STUB_PATH = "/cdn/hls.min.js";

// Byte-identical to the production policy in
// scripts/operations/nginx_sea_speed_auth.py (lines 82-87).
export const CONTENT_SECURITY_POLICY =
  "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; " +
  "connect-src 'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'";

// Minimal hls.js stand-in: supports the members the shipped pages touch
// (isSupported, Events, ErrorTypes, on/loadSource/attachMedia/destroy/startLoad/
// recoverMediaError) but never plays, never fires events and never requests
// media, so no page falls back to a ReferenceError and no stream traffic leaks
// into the assertions.
export const HLS_STUB_SOURCE = `/* local hls.js stub for the #684 browser JS gate */
(function () {
  "use strict";
  function HlsStub() {}
  HlsStub.isSupported = function () { return true; };
  HlsStub.Events = {
    MEDIA_ATTACHED: "hlsMediaAttached",
    MANIFEST_PARSED: "hlsManifestParsed",
    LEVEL_LOADED: "hlsLevelLoaded",
    FRAG_CHANGED: "hlsFragChanged",
    ERROR: "hlsError"
  };
  HlsStub.ErrorTypes = {
    NETWORK_ERROR: "networkError",
    MEDIA_ERROR: "mediaError",
    OTHER_ERROR: "otherError"
  };
  HlsStub.prototype.on = function () { return this; };
  HlsStub.prototype.loadSource = function () { return this; };
  HlsStub.prototype.attachMedia = function () { return this; };
  HlsStub.prototype.startLoad = function () { return this; };
  HlsStub.prototype.recoverMediaError = function () { return this; };
  HlsStub.prototype.destroy = function () {};
  HlsStub.prototype.latency = 0;
  window.Hls = HlsStub;
})();
`;

const PAGE_FILES = new Map([
  ["/", path.join(FRONTEND_ROOT, "root", "index.html")],
  ["/sea-speed/", path.join(SEA_SPEED_ROOT, "index.html")],
  ["/sea-speed/objects/", path.join(SEA_SPEED_ROOT, "objects", "index.html")],
  ["/sea-speed/cameras/", path.join(SEA_SPEED_ROOT, "cameras", "index.html")],
  ["/sea-speed/road/", path.join(SEA_SPEED_ROOT, "road", "index.html")],
  ["/sea-speed/unavailable.html", path.join(SEA_SPEED_ROOT, "unavailable.html")],
]);

const SESSION_BODY = { ok: true, username: "operator", role: "operator" };

// Shape-rich empty payload: every page boots against real endpoints, so the
// fallback carries the empty arrays/objects their renderers read instead of
// forcing a page to throw on `undefined.map` / `undefined.textContent`.
const EMPTY_API_BODY = {
  ok: true,
  active: false,
  items: [],
  events: [],
  objects: [],
  passages: [],
  total: 0,
  count: 0,
  enabled: false,
  by_class: {},
  totals: { left_to_right: 0, right_to_left: 0 },
  crossings: { left_to_right: 0, right_to_left: 0, by_class: {} },
  worker_online: false,
};

const CDN_SCRIPT_TAG =
  /<script\b[^>]*\bsrc="https:\/\/cdn\.jsdelivr\.net\/npm\/hls\.js@1\.7\.4\/dist\/hls\.min\.js"[^>]*><\/script>/gi;

function contentTypeFor(filePath) {
  switch (path.extname(filePath)) {
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
    case ".mjs":
      return "application/javascript; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".json":
      return "application/json; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    default:
      return "application/octet-stream";
  }
}

function send(res, status, body, contentType) {
  if (res.headersSent) return;
  res.writeHead(status, {
    "Content-Type": contentType,
    "Cache-Control": "no-store",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
  });
  res.end(body);
}

function sendText(res, status, text) {
  send(res, status, text, "text/plain; charset=utf-8");
}

function sendJson(res, status, value) {
  send(res, status, JSON.stringify(value), "application/json; charset=utf-8");
}

function insidePath(root, relative) {
  const resolved = path.resolve(root, relative);
  if (resolved !== root && !resolved.startsWith(root + path.sep)) return null;
  return resolved;
}

function resolveStaticPath(pathname) {
  if (PAGE_FILES.has(pathname)) return PAGE_FILES.get(pathname);
  if (pathname === "/login-popup.js") return insidePath(SEA_SPEED_ROOT, "login-popup.js");
  // Issue #685: the operator pages link the shared stylesheet from the same
  // static root as the modules — same insidePath containment guard as .js.
  if (
    pathname.startsWith("/sea-speed/") &&
    (pathname.endsWith(".js") || pathname.endsWith(".css"))
  ) {
    return insidePath(SEA_SPEED_ROOT, pathname.slice("/sea-speed/".length));
  }
  return null;
}

function stripCdnIntegrity(html, pathname) {
  if (!html.includes("cdn.jsdelivr.net")) return html;
  let rewritten = 0;
  const body = html.replace(CDN_SCRIPT_TAG, (tag) => {
    if (!/\bintegrity=/.test(tag) && !/\bcrossorigin=/.test(tag)) return tag;
    rewritten += 1;
    return `<script src="${HLS_CDN_URL}"></script>`;
  });
  if (rewritten === 0) {
    // Fail loudly: silently serving SRI-protected markup would make the CDN
    // script unloadable and the gate meaningless.
    throw new Error(`fixture: hls.js CDN tag with integrity/crossorigin not found in ${pathname}`);
  }
  return body;
}

// Water and Road overlay-canvas.js open `new EventSource(liveUrl)` against
// /sea-speed/api/**/live/stream. Answering that path with JSON makes Chromium
// log "EventSource's response has a MIME type ... not text/event-stream", so
// the stream is answered properly and held open without events.
function handleEventStream(req, res) {
  if (res.headersSent) return;
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-store",
    Connection: "keep-alive",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
  });
  res.write(": sea-speed fixture event stream\n\n");
  const keepAlive = setInterval(() => {
    try {
      res.write(": keepalive\n\n");
    } catch {
      /* client went away */
    }
  }, 15_000);
  const cleanup = () => clearInterval(keepAlive);
  req.on("close", cleanup);
  res.on("close", cleanup);
  res.on("error", cleanup);
}

function handleApi(req, res, pathname) {
  if (pathname === "/sea-speed/api/session") return sendJson(res, 200, SESSION_BODY);
  if (pathname === "/sea-speed/api/worker/control") return sendJson(res, 200, { ok: true, active: false });
  if (pathname === "/sea-speed/api/worker/control/road1") {
    return sendJson(res, 200, { ok: true, target: "road1", active: false });
  }
  if (pathname.endsWith("/live/stream")) return handleEventStream(req, res);
  return sendJson(res, 200, EMPTY_API_BODY);
}

function createHandler() {
  return async function handle(req, res) {
    try {
      req.resume();
      const url = new URL(req.url ?? "/", `http://127.0.0.1:${FIXTURE_PORT}`);
      let pathname;
      try {
        pathname = decodeURIComponent(url.pathname);
      } catch {
        return sendText(res, 400, "bad request path");
      }

      if (pathname.startsWith("/sea-speed/api/")) return handleApi(req, res, pathname);
      if (pathname.startsWith("/sea-speed/media/")) {
        return sendText(res, 404, "media fixture is out of scope");
      }
      if (pathname === HLS_STUB_PATH) {
        return send(res, 200, HLS_STUB_SOURCE, "application/javascript; charset=utf-8");
      }

      const filePath = resolveStaticPath(pathname);
      if (!filePath) return sendText(res, 404, `not found: ${pathname}`);

      const body = await readFile(filePath);
      if (path.extname(filePath) === ".html") {
        return send(res, 200, stripCdnIntegrity(body.toString("utf8"), pathname), contentTypeFor(filePath));
      }
      return send(res, 200, body, contentTypeFor(filePath));
    } catch (error) {
      if (error && error.code === "ENOENT") return sendText(res, 404, "not found");
      return sendText(res, 500, `fixture error: ${error?.message ?? error}`);
    }
  };
}

export async function startFixtureServer({ port = FIXTURE_PORT } = {}) {
  const server = createServer(createHandler());
  await new Promise((resolve, reject) => {
    const onError = (error) => {
      server.off("listening", onListening);
      reject(error);
    };
    const onListening = () => {
      server.off("error", onError);
      resolve();
    };
    server.once("error", onError);
    server.once("listening", onListening);
    server.listen(port, "127.0.0.1");
  });

  const address = server.address();
  const boundPort = address && typeof address === "object" ? address.port : port;
  return {
    url: `http://127.0.0.1:${boundPort}`,
    port: boundPort,
    csp: CONTENT_SECURITY_POLICY,
    close: () =>
      new Promise((resolve, reject) => {
        server.closeAllConnections?.();
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  };
}
