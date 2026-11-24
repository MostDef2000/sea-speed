"""Issue #696 — durable crossing delivery through the existing worker outbox.

The production side landed with the code worker (``worker/worker_outbox.py``
``enqueue_crossing``/``_post_crossing``, ``worker/worker_crossings.py``
``update_crossing_counts(detections, now=None, accept=None)`` +
``set_crossing_accept``, ``worker/ubuntu_worker_entrypoint.py``
``_crossing_payload``/``accept_crossing``/``_bind_crossing_acceptance()``);
these tests pin the OUTCOMES of ``specs/696-durable-crossing-outbox/spec.md``
(AC-001..AC-005), never the mechanism beyond what an observable requires.

Sections (one class each):

* ``CrossingCrashReplayOracleTests`` — the issue's primary AC (AC-003): real
  crossing detection driven through the Ubuntu binding inside a CHILD process
  with the barrier placed BEFORE the first network send (never before the
  enqueue), two distinct accepted crossings, a SIGKILL while the rows are
  durable and nothing has been sent, then a fresh publisher on the SAME
  database with NO new detections. A real local HTTP receiving stub observes
  zero requests across the kill and then exactly those two requests, in the
  original order, with the original ids/timestamps, the crossing route, the
  metadata-only form and no JPEG — and the rows are still present while each
  request is in flight, disappearing only after the acknowledgement.
* ``CrossingFailClosedSeamTests`` — AC-001/AC-002: a falsy acceptance return
  and a disk/SQLite failure at the real entrypoint seam both commit NOTHING
  (no counter, no track-side advance, no ``last_cross``, no returned event,
  no in-memory list append, no silent post), the failure is surfaced on
  stdout, and the next frame retries the very same geometry and commits once.
* ``CrossingTerminalAndFifoTests`` — AC-004: a permanent 400 on a crossing is
  retained as ``terminal_error`` and never re-posted while the next row still
  delivers; one shared ``id``-ordered FIFO means a retrying head never lets a
  later row overtake it; the road wire stays byte-identical (409 terminal,
  any other 4xx retried, multipart snapshot unchanged).
* ``CrossingRollbackIsolationTests`` — AC-005: the pre-#696 reader
  (``status='pending'``) cannot see crossing rows, a rollback publisher never
  posts them to ``/events`` (they are neither selected nor dispatched), and
  they remain for forward recovery on the new binary.
* ``CrossingScopeGuardTests`` — the working tree touches only the admitted
  #696 surface (``tests/``, the three worker files, ``specs/696-.../``), with
  ``api/``, ``deploy/``, ``.github/`` and lockfiles forbidden; the predicate
  itself is also fed synthetic offenders so the guard is proven to bite.

Environment: the battery is stdlib-only (``scripts/run_tests.py``), so
``requests``/``numpy`` may be absent — both are needed to IMPORT the worker
transport chain, so ``ensure_worker_imports()`` stubs only the names that are
genuinely missing (repo precedent:
``tests/test_worker_crossings_module.py:_import_worker_pair``) and never
replaces a real module with a stub. Every publisher in this file runs against
an injected transport at the module's guarded ``requests`` seam, exactly as
``tests/test_worker_outbox_delivery.py`` does, so behaviour is identical with
and without the third-party client installed.

RED spot-check (what fails on base ``172e938b43ad791bcc968e1ea9795e10c98be9ab``,
before the production change; measured by running this file against a
``git archive`` of the base — observed: ``8 failed, 2 passed``):

* Crash replay — the base tree has neither the wiring block nor the acceptance
  hook: the child dies with ``AttributeError: module 'worker_crossings' has
  no attribute '_crossing_accept'`` at the binding check (rc=1), the
  crash-window marker is never written and the parent fails fast with the
  child log. (Without that check the run would go no better: base
  ``update_crossing_counts`` has no acceptance callback, so both crossings
  would land in the killed process's ``_crossing_pending_posts`` RAM list and
  be lost with it.)
* Fail-closed seam — ``AttributeError: module 'worker_crossings' has no
  attribute 'set_crossing_accept'`` (both arms) and the entrypoint has no
  ``_bind_crossing_acceptance`` to bind: nothing can fail closed because the
  seam does not exist.
* Terminal/FIFO — ``AttributeError: 'WorkerOutbox' object has no attribute
  'enqueue_crossing'``, so no crossing row can ever be terminal or retried.
  The road-409/4xx/byte-identical arm of that class is a deliberate
  regression pin: it is GREEN on base and must stay green afterwards (it
  proves the road wire did not change).
* Rollback isolation — same missing ``enqueue_crossing``: AttributeError.
* Scope guard — deliberately NOT a production-code oracle (it only reads
  ``git status``): the two tree tests fail on the archive only because it has
  no ``.git`` (``CalledProcessError ... exit status 128``), while the
  synthetic predicate test passes on base and on the change alike — it
  proves the forbidden paths are rejected without touching the tree.
"""

from __future__ import annotations

import contextlib
import http.client
import http.server
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
# Issue #696 admission base: the scope guard diffs COMMITTED changes against
# this exact commit, so a clean working tree can never make it vacuous.
BASE_SHA = "172e938b43ad791bcc968e1ea9795e10c98be9ab"
for _root in (str(ROOT), str(WORKER_DIR)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

API_TOKEN = "test-token-0000000000"
SNAPSHOT_BYTES = b"\xff\xd8\x00\xff\xe0jpeg-payload\xff\xd9"
ROAD_EVENT_URL = "http://stub.invalid/api/analytics/road1/events"
STATE_URL = "http://stub.invalid/api/analytics/state"
# Literal route expectation (issue #696): the crossings URL is SEA_SPEED_API_URL
# with its LAST path segment replaced by "crossings" — same derivation as
# worker_transport.post_crossing. Never derived from the module under test.
CROSSINGS_URL = "http://stub.invalid/api/analytics/crossings"
CAMERA_ID = "cam1"
ANALYTICS_PROFILE = "water-v1"
# Vertical line at x=100 (frame coordinates), the geometry the fixtures below
# cross. side_of_line is negative right of the line, positive left of it.
VERTICAL_LINE = [(100, 0), (100, 576)]

# Track 7 starts LEFT of the line, track 9 starts RIGHT; FRAME_CROSSED swaps
# them, so both tracks cross inside one frame — two distinct accepted crossings
# with two distinct track ids (distinct event ids even in the same instant).
FRAME_SEEN = [
    {
        "track_id": 7,
        "bbox_xyxy": (30, 100, 70, 140),
        "object_type": "car",
        "class_name": "car",
        "confidence": 0.91,
        "speed_kmh": 42.0,
    },
    {
        "track_id": 9,
        "bbox_xyxy": (130, 100, 170, 140),
        "object_type": "truck",
        "class_name": "truck",
        "confidence": 0.87,
        "speed_kmh": 31.0,
    },
]
FRAME_CROSSED = [
    dict(FRAME_SEEN[0], bbox_xyxy=(130, 100, 170, 140)),
    dict(FRAME_SEEN[1], bbox_xyxy=(30, 100, 70, 140)),
]


def ensure_worker_imports() -> None:
    """Make the worker import chain importable in a bare battery environment.

    ``worker/worker_transport.py`` imports ``requests`` unconditionally and
    ``worker/worker_media.py`` imports ``numpy``; neither is declared by the
    stdlib-only battery. Only genuinely MISSING names are stubbed, and a real
    module is never replaced — a real ``numpy`` must stay real for the suites
    that gate their oracles on it (tests/test_700_ingest_frame_conformance).
    """
    for name in ("numpy", "requests"):
        if name in sys.modules:
            continue
        try:
            available = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            sys.modules[name] = mock.MagicMock(name=name)


ensure_worker_imports()


# ---------------------------------------------------------------------------
# fixtures and small helpers
# ---------------------------------------------------------------------------


def _wait_for(predicate, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return False


def load_outbox_module():
    """Import worker/worker_outbox.py by its runtime name (requests guarded)."""
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))
    import worker_outbox

    return worker_outbox


def load_worker_crossings():
    """Import worker/worker_crossings.py by its runtime name (worker/ on path)."""
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))
    import worker_crossings

    return worker_crossings


def load_entrypoint():
    """Load the Ubuntu entrypoint the provenance way, with the REAL binding.

    Only the heavy runtime worker module is stubbed (it pulls cv2/av/
    ultralytics and is irrelevant to the crossing contour); the entrypoint's
    module-level ``_bind_crossing_acceptance()`` then imports the REAL
    ``worker_crossings`` and binds ``entrypoint.accept_crossing`` into it.
    ``mock.patch.dict(sys.modules, ...)`` is deliberately NOT used here: it
    restores the whole dict on exit and would evict the freshly imported
    worker_crossings module from ``sys.modules``.
    """
    ensure_worker_imports()
    runtime_worker = types.ModuleType("hls_motion_yolo_worker_events")
    runtime_worker.start_media_reader = lambda av_module=None: None
    runtime_worker.post_state = lambda metadata, overlay_path: True
    runtime_worker.post_event = lambda metadata, snapshot_path: True
    spec = importlib.util.spec_from_file_location(
        "ubuntu_worker_entrypoint_696_oracle", ROOT / "worker" / "ubuntu_worker_entrypoint.py"
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get("hls_motion_yolo_worker_events")
    sys.modules["hls_motion_yolo_worker_events"] = runtime_worker
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("hls_motion_yolo_worker_events", None)
        else:
            sys.modules["hls_motion_yolo_worker_events"] = previous
    return module


def _crossing_metadata(event_id: str) -> str:
    """A crossing metadata JSON string (byte-verbatim is asserted end to end)."""
    return json.dumps(
        {
            "event_id": event_id,
            "camera_id": CAMERA_ID,
            "class_name": "car",
            "direction": "left_to_right",
            "confidence": 0.9,
        },
        ensure_ascii=False,
    )


def _road_metadata(event_id: str) -> str:
    return json.dumps(
        {"event_id": event_id, "camera_id": "road1", "class_name": "car", "confidence": 0.9},
        ensure_ascii=False,
    )


def _call_event_id(call: dict):
    """event_id of one recorded transport call, or None when unparsable."""
    metadata = call["data"].get("metadata")
    if not isinstance(metadata, str):
        return None
    try:
        payload = json.loads(metadata)
    except ValueError:
        return None
    return payload.get("event_id") if isinstance(payload, dict) else None


def _read_rows(db_path) -> list[tuple]:
    """(event_id, metadata, snapshot_bytes, status) for every row, id order."""
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        return conn.execute(
            "SELECT event_id, metadata, snapshot_bytes, status FROM outbox_events ORDER BY id"
        ).fetchall()


class _FakeClock:
    """time-surface stand-in: every monotonic read jumps past any 60s backoff."""

    def __init__(self) -> None:
        self._mono = 1_000_000.0

    def monotonic(self) -> float:
        self._mono += 1_000.0
        return self._mono

    def time(self) -> float:
        return 1_700_000_000.0

    def gmtime(self, t=None):
        import time as _time

        return _time.gmtime(self.time() if t is None else t)

    def strftime(self, fmt, t=None):
        import time as _time

        return _time.strftime(fmt, t if t is not None else self.gmtime())


class _StubResponse:
    def __init__(self, status_code: int, body=None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class _RecordingTransport:
    """requests-shaped stub injected at the module's guarded ``requests`` seam.

    Records the route, headers, form payload and file parts exactly as the
    production call hands them over; ``responder(index, metadata)`` returns a
    _StubResponse or raises (a raise mirrors a transport-level connection
    error).
    """

    def __init__(self, responder) -> None:
        self._responder = responder
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        with self._lock:
            index = len(self.calls)
            self.calls.append(
                {
                    "url": url,
                    "headers": dict(headers or {}),
                    "data": dict(data or {}),
                    "files": files,
                    "timeout": timeout,
                }
            )
        return self._responder(index, dict(data or {}))


class _HttpResponse:
    """The three response attributes worker_outbox reads (status/text/json)."""

    def __init__(self, status_code: int, raw: bytes) -> None:
        self.status_code = status_code
        self.raw = raw
        self.text = raw.decode("utf-8", "replace")

    def json(self):
        return json.loads(self.text)


def _encode_body(data, files):
    """requests-shaped encoding: urlencoded form, or multipart with files."""
    if not files:
        return urlencode(data or {}).encode("utf-8"), {
            "Content-Type": "application/x-www-form-urlencoded"
        }
    boundary = "----SeaSpeedBoundary696"
    chunks = []
    for name, spec in files.items():
        filename, content, content_type = spec
        chunks.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                f'; filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
            ).encode("utf-8")
            + bytes(content)
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


class _HttpTransport:
    """Real HTTP POST client at the ``requests`` seam (stdlib http.client).

    http.client never consults the ambient proxy environment, so a local
    receiving stub is reached deterministically, and the battery needs no
    third-party HTTP client (CI installs the API lock only). ``before_send``
    is the crash-replay barrier hook: it runs BEFORE the socket work, so the
    enqueue path is never blocked.
    """

    def __init__(self, before_send=None) -> None:
        self._before_send = before_send

    def post(self, url, headers=None, data=None, files=None, timeout=None):
        if self._before_send is not None:
            self._before_send()
        body, extra = _encode_body(data, files)
        request_headers = dict(headers or {})
        request_headers.update(extra)
        parsed = urlsplit(url)
        connection = http.client.HTTPConnection(
            parsed.hostname, parsed.port or 80, timeout=timeout or 10
        )
        try:
            target = parsed.path or "/"
            if parsed.query:
                target = f"{target}?{parsed.query}"
            connection.request("POST", target, body=body, headers=request_headers)
            response = connection.getresponse()
            return _HttpResponse(response.status, response.read())
        finally:
            connection.close()


class _CrossingReceivingHandler(http.server.BaseHTTPRequestHandler):
    """The real receiving stub: records every POST, then acknowledges it."""

    def do_POST(self) -> None:  # noqa: N802 - http.server's fixed hook name
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        metadata = None
        if content_type.startswith("application/x-www-form-urlencoded"):
            values = parse_qs(body.decode("utf-8", "replace")).get("metadata")
            if values:
                metadata = values[0]
        event_id = None
        if metadata is not None:
            try:
                payload = json.loads(metadata)
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                event_id = payload.get("event_id")
        entry = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "content_type": content_type,
            "body": body,
            "metadata": metadata,
            "event_id": event_id,
            "multipart": content_type.startswith("multipart/form-data"),
            # The row must still exist while the request is in flight: the
            # publisher deletes only AFTER this acknowledgement is sent.
            "row_status_at_receipt": self.server.row_status(event_id) if event_id else None,
        }
        self.server.record(entry)
        if event_id is None:
            self._respond(400, "unrecognised crossing request")
        else:
            self._respond(200, json.dumps({"ok": True, "event_id": event_id}))

    def _respond(self, status: int, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        pass


class _ReceivingServer:
    """Local HTTP endpoint both processes can reach (the crash-replay oracle)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._received: list[dict] = []
        self._lock = threading.Lock()
        self._httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), _CrossingReceivingHandler
        )
        self._httpd.record = self._record
        self._httpd.row_status = self._row_status
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="696-receiving-stub", daemon=True
        )
        self._thread.start()

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    @property
    def state_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/analytics/state"

    @property
    def crossings_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/analytics/crossings"

    def _record(self, entry: dict) -> None:
        with self._lock:
            self._received.append(entry)

    def _row_status(self, event_id: str):
        try:
            with contextlib.closing(
                sqlite3.connect(str(self.db_path), timeout=30.0)
            ) as conn:
                row = conn.execute(
                    "SELECT status FROM outbox_events WHERE event_id = ?", (event_id,)
                ).fetchone()
            return row[0] if row else None
        except sqlite3.Error as exc:
            return f"row-status-read-failed: {type(exc).__name__}: {exc}"

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._received)

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5.0)


def _old_binary_head_row(self):
    """The pre-#696 publisher selector (base 172e938): ``status='pending'`` only.

    Used to emulate a rollback binary against the current code: crossing rows
    are never selected, so they can neither be dispatched nor posted anywhere.
    """
    with self._lock:
        row = self._conn.execute(
            "SELECT id, event_id, metadata, snapshot_bytes, attempts, retries,"
            " status FROM outbox_events WHERE status = ? ORDER BY id LIMIT 1",
            ("pending",),
        ).fetchone()
    return row or None


class _FailingInsertConnection:
    """Delegating sqlite3-connection proxy: INSERTs into outbox_events fail.

    Stands in for a full disk / SQLite write failure at the durable-acceptance
    seam (AC-002) without touching schema init or the SELECT paths, so the
    publisher keeps running exactly as it would on a real disk-full.
    """

    def __init__(self, real) -> None:
        self._real = real

    def execute(self, sql, *args, **kwargs):
        if isinstance(sql, str) and sql.lstrip().upper().startswith("INSERT INTO OUTBOX_EVENTS"):
            raise sqlite3.OperationalError("database or disk is full")
        return self._real.execute(sql, *args, **kwargs)

    def __enter__(self):
        return self._real.__enter__()

    def __exit__(self, *exc):
        return self._real.__exit__(*exc)

    def commit(self):
        return self._real.commit()

    def close(self):
        return self._real.close()


# ---------------------------------------------------------------------------
# the producer child (crash-replay oracle): real detection through the
# Ubuntu binding, killed before the first network send
# ---------------------------------------------------------------------------

CHILD_SCRIPT = r'''
"""Producer child for the #696 crash-replay oracle (driven by the test module)."""
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path

repo = Path(sys.argv[1])
notify_path = Path(sys.argv[3])
parked_path = Path(sys.argv[4])
report_path = Path(sys.argv[5])

sys.path.insert(0, str(repo / "worker"))

# Load the test module: it owns the shared HTTP transport (both processes send
# identical bytes) and ensure_worker_imports() for the bare battery.
oracle_spec = importlib.util.spec_from_file_location(
    "test_696_durable_crossing_outbox", str(repo / "tests" / "test_696_durable_crossing_outbox.py")
)
oracle = importlib.util.module_from_spec(oracle_spec)
oracle_spec.loader.exec_module(oracle)

import worker_outbox  # noqa: E402  repo-local worker/ (sys.path set above)


def park_before_first_send():
    """The barrier: park the publisher BEFORE the first network send.

    The enqueue path is never blocked - both crossing rows are committed to
    SQLite before this hook can run - so the parent's SIGKILL lands exactly in
    the crash window: rows durable, nothing sent.
    """
    parked_path.write_text("parked before the first network send\n", encoding="utf-8")
    threading.Event().wait()  # never set: only the kill ends this


worker_outbox.requests = oracle._HttpTransport(before_send=park_before_first_send)

# Ubuntu wiring, for real: stub ONLY the heavy runtime worker module (the
# provenance convention), then exec the entrypoint so its module-level
# _bind_crossing_acceptance() binds entrypoint.accept_crossing into the real
# worker_crossings module.
runtime_worker = types.ModuleType("hls_motion_yolo_worker_events")
runtime_worker.start_media_reader = lambda av_module=None: None
runtime_worker.post_state = lambda metadata, overlay_path: True
runtime_worker.post_event = lambda metadata, snapshot_path: True
sys.modules["hls_motion_yolo_worker_events"] = runtime_worker

entry_spec = importlib.util.spec_from_file_location(
    "ubuntu_worker_entrypoint_696_child", str(repo / "worker" / "ubuntu_worker_entrypoint.py")
)
entrypoint = importlib.util.module_from_spec(entry_spec)
entry_spec.loader.exec_module(entrypoint)

import worker_crossings  # noqa: E402  repo-local worker/ (sys.path set above)

if worker_crossings._crossing_accept is not entrypoint.accept_crossing:
    raise SystemExit(
        "crossing acceptance seam is NOT bound: " + repr(worker_crossings._crossing_accept)
    )

# Configuration input (the line normally comes from the crossing-line API);
# the detection math below is the production code.
worker_crossings.fetch_crossing_line_config = lambda: {
    "enabled": True,
    "line": [(100, 0), (100, 576)],
}

first = worker_crossings.update_crossing_counts(oracle.FRAME_SEEN, now=100.0)
if first:
    raise SystemExit("frame 1 must not report crossings: " + repr(first))
second = worker_crossings.update_crossing_counts(oracle.FRAME_CROSSED, now=101.0)
if len(second) != 2:
    raise SystemExit("frame 2 must report exactly two crossings: " + repr(second))
if len({c["track_id"] for c in second}) != 2:
    raise SystemExit("the two crossings must be distinct: " + repr(second))

summary = worker_crossings.crossing_overlay_summary()
report = {
    "crossings": second,
    "counts": {
        "left_to_right": summary["left_to_right"],
        "right_to_left": summary["right_to_left"],
    },
    "ram_list_len": len(worker_crossings._crossing_pending_posts),
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
# Notify the parent only AFTER the second detection returned (both rows are
# committed by then), then stay alive so the parent can SIGKILL this process
# without any graceful outbox close.
notify_path.write_text("two crossings accepted\n", encoding="utf-8")
threading.Event().wait()
'''


# ---------------------------------------------------------------------------
# 1. crash-replay oracle (the issue's primary acceptance criterion)
# ---------------------------------------------------------------------------


class CrossingCrashReplayOracleTests(unittest.TestCase):
    """AC-003: a kill before the HTTP send replays both rows on restart."""

    def _kill_quietly(self, proc) -> None:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            proc.kill()
            proc.wait(timeout=15)

    def test_child_killed_before_any_send_replays_both_crossings_in_order(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        workdir = Path(tmp.name)
        db_path = workdir / "road-worker-outbox.sqlite3"
        report_path = workdir / "child-report.json"
        notify_path = workdir / "detections-done.marker"
        parked_path = workdir / "send-parked.marker"
        child_log_path = workdir / "child.log"
        script_path = workdir / "producer_child.py"
        script_path.write_text(CHILD_SCRIPT, encoding="utf-8")

        server = _ReceivingServer(db_path)
        self.addCleanup(server.stop)

        child_env = dict(os.environ)
        child_env.update(
            {
                "SEA_SPEED_OUTBOX_DB": str(db_path),
                "SEA_SPEED_API_URL": server.state_url,
                "SEA_SPEED_API_TOKEN": API_TOKEN,
                "CAMERA_ID": CAMERA_ID,
                "ANALYTICS_PROFILE": ANALYTICS_PROFILE,
            }
        )
        child_env.pop("SEA_SPEED_EVENT_API_URL", None)

        with open(child_log_path, "w", encoding="utf-8") as child_log:
            child = subprocess.Popen(
                [
                    sys.executable,
                    str(script_path),
                    str(ROOT),
                    str(db_path),
                    str(notify_path),
                    str(parked_path),
                    str(report_path),
                ],
                cwd=str(workdir),
                env=child_env,
                stdout=child_log,
                stderr=subprocess.STDOUT,
            )
        self.addCleanup(self._kill_quietly, child)

        def child_died() -> str:
            if child.poll() is None:
                return ""
            return f"\nproducer child exited early rc={child.returncode}:\n{child_log_path.read_text(encoding='utf-8')}"

        # Wait for BOTH sides of the crash window: the second detection
        # returned (notification) and the publisher parked at the pre-send
        # barrier.
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if notify_path.is_file() and parked_path.is_file():
                break
            died = child_died()
            if died:
                self.fail(died)
            time.sleep(0.02)
        else:
            self.fail(
                "timed out waiting for the child's crash window"
                + child_died()
                + f"\nlog:\n{child_log_path.read_text(encoding='utf-8')}"
            )

        # (a) ZERO requests reached the receiving stub before the kill.
        self.assertEqual(
            server.snapshot(),
            [],
            "the barrier sits before the first network send: nothing may be sent yet",
        )

        report = json.loads(report_path.read_text(encoding="utf-8"))
        crossings = report["crossings"]
        self.assertEqual(len(crossings), 2, report)
        self.assertEqual(
            [c["track_id"] for c in crossings], [7, 9], "two distinct accepted crossings"
        )
        self.assertEqual(
            report["counts"],
            {"left_to_right": 1, "right_to_left": 1},
            "both crossings were counted after durable acceptance",
        )
        self.assertEqual(
            report["ram_list_len"],
            0,
            "a bound callback must never fall back to the in-memory crossing list",
        )

        # Literal event-id expectation from the issue text:
        # crossing:<camera_id>:<created_at>:<track_id>:<direction>
        expected_ids = [
            f"crossing:{CAMERA_ID}:{c['created_at']}:{c['track_id']}:{c['direction']}"
            for c in crossings
        ]
        self.assertEqual(len(set(expected_ids)), 2, expected_ids)

        rows = _read_rows(db_path)
        self.assertEqual(len(rows), 2, "both crossings must be committed before the kill")
        self.assertEqual([row[0] for row in rows], expected_ids, "original ids, original order")
        for row in rows:
            self.assertEqual(row[2], b"", "crossing rows carry an empty snapshot BLOB")
            self.assertEqual(row[3], "crossing_pending")
        stored_metadata = [row[1] for row in rows]
        for metadata, crossing in zip(stored_metadata, crossings):
            payload = json.loads(metadata)
            self.assertEqual(payload["event_id"], expected_ids[crossings.index(crossing)])
            self.assertEqual(payload["created_at"], crossing["created_at"], "original timestamp")
            self.assertEqual(payload["track_id"], crossing["track_id"])
            self.assertEqual(payload["direction"], crossing["direction"])
            self.assertEqual(payload["camera_id"], CAMERA_ID)
            self.assertEqual(payload["analytics_profile"], ANALYTICS_PROFILE)
            self.assertEqual(payload["domain"], "water")

        # (b) kill WITHOUT a graceful close: no outbox.close(), no flush, the
        # rows must survive untouched in the database file.
        child.kill()
        child.wait(timeout=15)
        self.assertEqual(child.returncode, -9, "the child must die from SIGKILL")
        self.assertEqual(
            server.snapshot(),
            [],
            "the kill must land while the rows are durable and unsent",
        )
        self.assertEqual(len(_read_rows(db_path)), 2, "the killed child kept both rows")

        # (c) fresh publisher on the SAME database, NO new detections: only the
        # two surviving rows are replayed.
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        captured = io.StringIO()
        with (
            contextlib.redirect_stdout(captured),
            mock.patch.dict(
                os.environ,
                {"SEA_SPEED_API_URL": server.state_url, "SEA_SPEED_API_TOKEN": API_TOKEN},
                clear=False,
            ),
            mock.patch.object(mod, "requests", _HttpTransport()),
        ):
            outbox.start()
            delivered = _wait_for(
                lambda: len(server.snapshot()) >= 2 and outbox.pending_count() == 0,
                timeout=20.0,
            )
        stdout = captured.getvalue()
        self.assertTrue(
            delivered,
            f"rows were not replayed; received={server.snapshot()} stdout={stdout}",
        )

        received = server.snapshot()
        self.assertEqual(
            len(received),
            2,
            f"exactly the two surviving rows, no more: {received}; stdout={stdout}",
        )
        self.assertEqual(
            [entry["event_id"] for entry in received],
            expected_ids,
            "original ids in original order",
        )
        for entry, expected_meta in zip(received, stored_metadata):
            self.assertEqual(entry["path"], "/api/analytics/crossings", "crossing route")
            self.assertEqual(entry["auth"], f"Bearer {API_TOKEN}")
            self.assertEqual(
                entry["metadata"],
                expected_meta,
                "byte-identical metadata (original created_at and identity)",
            )
            self.assertFalse(entry["multipart"], "crossings carry no JPEG and no file part")
            self.assertEqual(
                entry["row_status_at_receipt"],
                "crossing_pending",
                "the row is still present while the request is in flight: it "
                "disappears only after a valid acknowledgement",
            )

        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0],
                0,
                "both rows disappear only after their acknowledgement",
            )

        self.assertIn(f"POST crossing ok event_id={expected_ids[0]}", stdout)
        self.assertIn(f"POST crossing ok event_id={expected_ids[1]}", stdout)
        self.assertNotIn(
            "POST event ok id=",
            stdout,
            "crossing confirmations must not reuse the road success log line",
        )


# ---------------------------------------------------------------------------
# 2. fail-closed acceptance seam (durable BEFORE counted)
# ---------------------------------------------------------------------------


class CrossingFailClosedSeamTests(unittest.TestCase):
    """AC-001/AC-002: persistence failure never counts, advances or posts."""

    def setUp(self) -> None:
        self.crossings = load_worker_crossings()
        self.crossings.reset_crossing_counts()
        self._saved_vlz_date = self.crossings._crossing_vlz_date
        patcher = mock.patch.object(
            self.crossings,
            "fetch_crossing_line_config",
            lambda: {"enabled": True, "line": VERTICAL_LINE},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.crossings.set_crossing_accept, None)
        self.addCleanup(self._restore_state)

    def _restore_state(self) -> None:
        self.crossings._crossing_vlz_date = self._saved_vlz_date
        self.crossings.reset_crossing_counts()
        self.crossings.set_crossing_accept(None)

    def _assert_nothing_committed(self) -> None:
        summary = self.crossings.crossing_overlay_summary()
        self.assertEqual(summary["left_to_right"], 0, "no counter may move without acceptance")
        self.assertEqual(summary["right_to_left"], 0, "no counter may move without acceptance")
        self.assertEqual(
            self.crossings._crossing_track_sides[7]["side"],
            1,
            "the previous side must be kept so the next frame retries",
        )
        self.assertEqual(
            self.crossings._crossing_track_sides[9]["side"],
            -1,
            "the previous side must be kept so the next frame retries",
        )
        self.assertEqual(
            self.crossings._crossing_pending_posts,
            [],
            "no RAM append and therefore no silent post on a failed acceptance",
        )

    def test_falsy_accept_return_commits_nothing_and_the_next_frame_retries(self) -> None:
        update = self.crossings.update_crossing_counts
        # frame 1: both tracks are first seen — no crossing yet.
        self.assertEqual(update(FRAME_SEEN, now=100.0), [])

        # frame 2: both crossings fire, the Ubuntu seam rejects them (falsy).
        self.crossings.set_crossing_accept(lambda crossing: False)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            rejected = update(FRAME_CROSSED, now=101.0)

        self.assertEqual(rejected, [], "a rejected crossing is never returned as accepted")
        self.assertIn(
            "crossing accept failed track_id=7 direction=left_to_right reason=rejected",
            captured.getvalue(),
        )
        self.assertIn(
            "crossing accept failed track_id=9 direction=right_to_left reason=rejected",
            captured.getvalue(),
        )
        self._assert_nothing_committed()

        # frame 3: the very same geometry retries and commits exactly once.
        self.crossings.set_crossing_accept(lambda crossing: True)
        accepted = update(FRAME_CROSSED, now=102.0)
        self.assertEqual([c["track_id"] for c in accepted], [7, 9])
        summary = self.crossings.crossing_overlay_summary()
        self.assertEqual(
            (summary["left_to_right"], summary["right_to_left"]),
            (1, 1),
            "the retried crossing counts exactly once",
        )
        self.assertEqual(
            self.crossings._crossing_pending_posts,
            [],
            "a bound callback never falls back to the in-memory list",
        )

    def test_disk_failure_at_the_real_entrypoint_seam_commits_nothing_then_retries(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "road-worker-outbox.sqlite3"

        entrypoint = load_entrypoint()
        self.assertIs(
            self.crossings._crossing_accept,
            entrypoint.accept_crossing,
            "the Ubuntu wiring block must bind the real acceptance seam",
        )

        with mock.patch.dict(os.environ, {"SEA_SPEED_OUTBOX_DB": str(db_path)}, clear=False):
            # Ambient delivery settings must not let the publisher reach a
            # real endpoint while the seam is under test.
            os.environ.pop("SEA_SPEED_API_URL", None)
            os.environ.pop("SEA_SPEED_EVENT_API_URL", None)
            outbox = entrypoint._ensure_outbox()
            self.addCleanup(entrypoint._close_outbox)

            # frame 1: sides established through the real bound seam.
            self.assertEqual(self.crossings.update_crossing_counts(FRAME_SEEN, now=100.0), [])

            # disk full at the durable INSERT: accept_crossing raises, so
            # update_crossing_counts must commit nothing at all.
            real_conn = outbox._conn
            outbox._conn = _FailingInsertConnection(real_conn)
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                rejected = self.crossings.update_crossing_counts(FRAME_CROSSED, now=101.0)
            outbox._conn = real_conn

            self.assertEqual(rejected, [], "nothing may be accepted that was not persisted")
            self.assertIn(
                "crossing accept failed track_id=7 direction=left_to_right"
                " reason=OperationalError",
                captured.getvalue(),
            )
            self._assert_nothing_committed()
            with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0],
                    0,
                    "a failed enqueue leaves no partial row",
                )

            # disk is back: the very next frame retries the same geometry and
            # commits both rows durably.
            accepted = self.crossings.update_crossing_counts(FRAME_CROSSED, now=102.0)
            self.assertEqual([c["track_id"] for c in accepted], [7, 9])
            summary = self.crossings.crossing_overlay_summary()
            self.assertEqual(
                (summary["left_to_right"], summary["right_to_left"]), (1, 1)
            )
            rows = _read_rows(db_path)
            self.assertEqual(len(rows), 2, "the retried acceptance persists both rows")
            for row, crossing in zip(rows, accepted):
                self.assertEqual(row[2], b"", "crossing rows carry an empty snapshot BLOB")
                self.assertEqual(row[3], "crossing_pending")
                payload = json.loads(row[1])
                expected_id = (
                    f"crossing:{CAMERA_ID}:{crossing['created_at']}:"
                    f"{crossing['track_id']}:{crossing['direction']}"
                )
                self.assertEqual(row[0], expected_id)
                self.assertEqual(payload["created_at"], crossing["created_at"])
            self.assertEqual(
                self.crossings._crossing_pending_posts,
                [],
                "even a successful Ubuntu acceptance never uses the RAM list",
            )


# ---------------------------------------------------------------------------
# 3. terminal rejection + one shared FIFO + unchanged road wire
# ---------------------------------------------------------------------------


class _OutboxTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db_path = self.tmp / "road-worker-outbox.sqlite3"
        self.snapshot = self.tmp / "event.jpg"
        self.snapshot.write_bytes(SNAPSHOT_BYTES)
        self.mod = load_outbox_module()
        self.outbox = self.mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(self.outbox.close)
        self.env = {
            "SEA_SPEED_EVENT_API_URL": ROAD_EVENT_URL,
            "SEA_SPEED_API_URL": STATE_URL,
            "SEA_SPEED_API_TOKEN": API_TOKEN,
        }

    def drive(self, stub, actions) -> dict:
        """Run the real publisher thread under the fake clock + stub transport."""
        summary: dict = {}
        with (
            mock.patch.dict(os.environ, self.env, clear=False),
            mock.patch.object(self.mod, "requests", stub),
            mock.patch.object(self.mod, "time", _FakeClock()),
        ):
            self.outbox.start()
            try:
                actions(self.outbox, stub, summary)
            finally:
                self.outbox.close()
        return summary


class CrossingTerminalAndFifoTests(_OutboxTestBase):
    """AC-004: terminal vs retry classification and the shared id-ordered FIFO."""

    def test_crossing_400_is_terminal_retained_and_the_next_row_still_delivers(self) -> None:
        def responder(index: int, data: dict):
            event_id = json.loads(data["metadata"])["event_id"]
            if event_id == "crossing:rejected":
                return _StubResponse(400, text="direction is not allowed")
            return _StubResponse(200, {"ok": True, "event_id": event_id})

        stub = _RecordingTransport(responder)
        rejected_meta = _crossing_metadata("crossing:rejected")
        self.outbox.enqueue_crossing("crossing:rejected", rejected_meta)
        self.outbox.enqueue_crossing(
            "crossing:accepted", _crossing_metadata("crossing:accepted")
        )

        captured = io.StringIO()

        def actions(live, live_stub, summary):
            # rejected -> terminal (still counted), accepted -> deleted
            self.assertTrue(_wait_for(lambda: live.pending_count() == 1))
            time.sleep(0.3)  # settle: the terminal row must never be re-picked
            summary.update(live.snapshot())

        with contextlib.redirect_stdout(captured):
            summary = self.drive(stub, actions)
        stdout = captured.getvalue()

        rejected_calls = [c for c in stub.calls if _call_event_id(c) == "crossing:rejected"]
        self.assertEqual(len(rejected_calls), 1, "a terminal 400 crossing is never retried")
        self.assertIn(
            "crossing:accepted",
            [_call_event_id(c) for c in stub.calls],
            "a terminal head row must not block the next row",
        )
        for call in stub.calls:
            self.assertEqual(call["url"], CROSSINGS_URL, "crossings never reach /events")
        self.assertIn(
            "outbox crossing accept_error event_id=crossing:rejected", stdout
        )
        self.assertNotIn(
            "outbox accept_error event_id=crossing:rejected",
            stdout,
            "the road accept-error line must not be reused for crossings",
        )
        self.assertIn("POST crossing ok event_id=crossing:accepted", stdout)
        self.assertNotIn(
            "POST event ok id=",
            stdout,
            "the road success line must not be reused for crossings",
        )

        rows = {row[0]: row for row in _read_rows(self.db_path)}
        self.assertNotIn("crossing:accepted", rows, "the confirmed row is deleted")
        self.assertIn("crossing:rejected", rows, "the terminal row is retained")
        self.assertEqual(rows["crossing:rejected"][3], "terminal_error")
        self.assertEqual(rows["crossing:rejected"][1], rejected_meta, "metadata kept verbatim")
        self.assertEqual(summary["accept_errors"], 1)
        self.assertEqual(
            summary["pending"], 1, "the terminal row stays in the table as unconfirmed"
        )

    def test_retrying_crossing_head_never_lets_a_later_row_overtake_it(self) -> None:
        attempts: dict = {"crossing:head": 0, "evt-road": 0}
        # Status observed at the moment each row reaches the transport (the
        # publisher thread must not assert, so the observations are recorded
        # here and asserted in the test body).
        status_at_send: dict = {}

        def responder(index: int, data: dict):
            event_id = json.loads(data["metadata"])["event_id"]
            attempts[event_id] += 1
            with contextlib.closing(sqlite3.connect(str(self.db_path))) as conn:
                row = conn.execute(
                    "SELECT status FROM outbox_events WHERE event_id = ?", (event_id,)
                ).fetchone()
            status_at_send[event_id] = row[0] if row else None
            if event_id == "crossing:head":
                if attempts["crossing:head"] == 1:
                    return _StubResponse(503, text="upstream unavailable")
                return _StubResponse(200, {"ok": True, "event_id": event_id})
            return _StubResponse(
                200, {"ok": True, "event": {"event_id": event_id}, "duplicate": False}
            )

        stub = _RecordingTransport(responder)
        head_meta = _crossing_metadata("crossing:head")
        road_meta = _road_metadata("evt-road")
        self.outbox.enqueue_crossing("crossing:head", head_meta)
        self.outbox.enqueue("evt-road", road_meta, self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 0))
            summary.update(live.snapshot())

        self.drive(stub, actions)

        self.assertEqual(
            [_call_event_id(c) for c in stub.calls],
            ["crossing:head", "crossing:head", "evt-road"],
            "one id-ordered FIFO: the later road row waits out the head's retry",
        )
        self.assertEqual(
            [c["url"] for c in stub.calls],
            [CROSSINGS_URL, CROSSINGS_URL, ROAD_EVENT_URL],
            "each row is routed by its own stored status",
        )
        self.assertEqual(
            attempts,
            {"crossing:head": 2, "evt-road": 1},
            "the head is retried exactly once, the road row exactly once",
        )
        self.assertEqual(
            status_at_send["crossing:head"],
            "crossing_pending",
            "a retrying crossing keeps its own status (dispatch stays status-driven)",
        )
        self.assertEqual(
            status_at_send["evt-road"],
            "pending",
            "the road row status literal is untouched by #696",
        )
        road_calls = [c for c in stub.calls if _call_event_id(c) == "evt-road"]
        self.assertEqual(road_calls[0]["data"]["metadata"], road_meta, "byte-identical road row")
        self.assertEqual(
            road_calls[0]["files"],
            {"snapshot": ("event.jpg", SNAPSHOT_BYTES, "image/jpeg")},
            "the road multipart snapshot is unchanged",
        )
        self.assertEqual(stub.calls[0]["data"]["metadata"], head_meta, "byte-identical crossing")

    def test_road_409_terminal_other_4xx_retry_with_byte_identical_payload(self) -> None:
        attempts: dict = {"evt-conflict": 0, "evt-client": 0}

        def responder(index: int, data: dict):
            event_id = json.loads(data["metadata"])["event_id"]
            attempts[event_id] += 1
            if event_id == "evt-conflict":
                return _StubResponse(409, text="event_id accepted with different content")
            if attempts["evt-client"] == 1:
                return _StubResponse(400, text="bad request")
            return _StubResponse(
                200, {"ok": True, "event": {"event_id": event_id}, "duplicate": False}
            )

        stub = _RecordingTransport(responder)
        conflict_meta = _road_metadata("evt-conflict")
        client_meta = _road_metadata("evt-client")
        self.outbox.enqueue("evt-conflict", conflict_meta, self.snapshot)
        self.outbox.enqueue("evt-client", client_meta, self.snapshot)

        def actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: live.pending_count() == 1))
            time.sleep(0.3)  # settle: the terminal row must never be re-picked
            summary.update(live.snapshot())

        summary = self.drive(stub, actions)

        conflict_calls = [c for c in stub.calls if _call_event_id(c) == "evt-conflict"]
        client_calls = [c for c in stub.calls if _call_event_id(c) == "evt-client"]
        self.assertEqual(len(conflict_calls), 1, "road 409 stays terminal")
        self.assertEqual(len(client_calls), 2, "any other road 4xx retries")
        for call in client_calls:
            self.assertEqual(call["url"], ROAD_EVENT_URL, "road route unchanged")
            self.assertEqual(
                call["data"]["metadata"], client_meta, "byte-identical road metadata"
            )
            self.assertEqual(
                call["files"],
                {"snapshot": ("event.jpg", SNAPSHOT_BYTES, "image/jpeg")},
                "road snapshot bytes unchanged",
            )
            self.assertEqual(call["headers"]["Authorization"], f"Bearer {API_TOKEN}")
        rows = {row[0]: row for row in _read_rows(self.db_path)}
        self.assertNotIn("evt-client", rows, "the retried road row confirms and deletes")
        self.assertEqual(rows["evt-conflict"][3], "terminal_error")
        self.assertEqual(summary["accept_errors"], 1)
        self.assertEqual(summary["send_errors"], 1)
        self.assertEqual(summary["pending"], 1, "the terminal road row stays unconfirmed")


# ---------------------------------------------------------------------------
# 4. rollback isolation (the pre-#696 selector)
# ---------------------------------------------------------------------------


class CrossingRollbackIsolationTests(_OutboxTestBase):
    """AC-005: an old binary leaves crossing rows untouched for forward recovery."""

    def test_old_reader_never_sees_or_posts_crossing_rows_then_forward_recovers(self) -> None:
        id_a = f"crossing:{CAMERA_ID}:2026-11-24T00:00:00+00:00:7:left_to_right"
        id_b = f"crossing:{CAMERA_ID}:2026-11-24T00:00:01+00:00:9:right_to_left"
        meta_a = _crossing_metadata(id_a)
        meta_b = _crossing_metadata(id_b)
        road_meta = _road_metadata("evt-road")
        self.outbox.enqueue_crossing(id_a, meta_a)
        self.outbox.enqueue_crossing(id_b, meta_b)
        self.outbox.enqueue("evt-road", road_meta, self.snapshot)

        # (1) The old reader's literal query: pre-#696 selected status='pending'
        # only, so crossing rows are invisible to it.
        with contextlib.closing(sqlite3.connect(str(self.db_path))) as conn:
            old_visible = [
                row[0]
                for row in conn.execute(
                    "SELECT event_id FROM outbox_events WHERE status = 'pending' ORDER BY id"
                )
            ]
        self.assertEqual(
            old_visible,
            ["evt-road"],
            "crossing rows must be invisible to the pre-#696 selector",
        )

        def ok_responder(index: int, data: dict):
            event_id = json.loads(data["metadata"])["event_id"]
            if event_id.startswith("crossing:"):
                return _StubResponse(200, {"ok": True, "event_id": event_id})
            return _StubResponse(
                200, {"ok": True, "event": {"event_id": event_id}, "duplicate": False}
            )

        # (2) Rollback delivery: the REAL publisher running with the old
        # binary's selector restored (it selected 'pending' rows only and
        # dispatched every one of them through the road wire).
        stub = _RecordingTransport(ok_responder)

        def rollback_actions(live, live_stub, summary):
            self.assertTrue(_wait_for(lambda: len(live_stub.calls) >= 1))
            time.sleep(0.3)  # settle: a crossing row must never be picked up

        with mock.patch.object(self.mod.WorkerOutbox, "_head_row", _old_binary_head_row):
            self.drive(stub, rollback_actions)
        self.assertEqual(
            [_call_event_id(c) for c in stub.calls],
            ["evt-road"],
            "a rollback publisher delivers only the road row",
        )
        for call in stub.calls:
            self.assertEqual(call["url"], ROAD_EVENT_URL, "the old binary only knows /events")
            self.assertNotIn(
                "crossing:",
                call["data"]["metadata"],
                "no crossing metadata may ever reach the road /events endpoint",
            )
        rows = {row[0]: row for row in _read_rows(self.db_path)}
        self.assertEqual(
            sorted(rows),
            sorted([id_a, id_b]),
            "crossing rows survive the rollback untouched",
        )
        self.assertEqual(rows[id_a][1], meta_a, "metadata byte-identical after rollback")
        self.assertEqual(rows[id_b][1], meta_b, "metadata byte-identical after rollback")
        self.assertEqual(rows[id_a][3], "crossing_pending")
        self.assertEqual(rows[id_b][3], "crossing_pending")

        # (3) Forward recovery: a fresh publisher on the new binary drains the
        # surviving rows to the crossing endpoint, in one id-ordered FIFO.
        recovered = self.mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(recovered.close)
        self.outbox = recovered
        stub_2 = _RecordingTransport(ok_responder)
        self.drive(
            stub_2,
            lambda live, live_stub, summary: self.assertTrue(
                _wait_for(lambda: live.pending_count() == 0)
            ),
        )
        self.assertEqual(
            [_call_event_id(c) for c in stub_2.calls],
            [id_a, id_b],
            "forward recovery delivers both rows in their original order",
        )
        for call, expected_meta in zip(stub_2.calls, [meta_a, meta_b]):
            self.assertEqual(call["url"], CROSSINGS_URL)
            self.assertEqual(call["data"]["metadata"], expected_meta, "byte-identical")
            self.assertIsNone(call["files"], "crossings carry no file part")
        with contextlib.closing(sqlite3.connect(str(self.db_path))) as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM outbox_events").fetchone()[0],
                0,
                "forward recovery confirms and deletes both rows",
            )
        for call in stub.calls + stub_2.calls:
            if call["url"] == ROAD_EVENT_URL:
                self.assertNotIn("crossing:", call["data"]["metadata"])


# ---------------------------------------------------------------------------
# 5. scope guard — only the admitted #696 surface
# ---------------------------------------------------------------------------


class CrossingScopeGuardTests(unittest.TestCase):
    """No API/deploy/workflow/lockfile change; only the admitted paths.

    The guard covers COMMITTED changes (diff against ``BASE_SHA``) AND
    uncommitted/untracked working-tree changes: after the #696 commit the
    working tree is clean, so a status-only guard would pass vacuously even
    if ``api/``, ``deploy/``, ``.github/`` or a lockfile had been committed.
    The committed side fails closed — if that ``git diff`` cannot run
    (missing base object, shallow clone, bad repo) the test errors instead of
    silently falling back to ``git status`` alone.
    """

    ALLOWED_CHANGE_PREFIXES = (
        "tests/",
        "worker/worker_outbox.py",
        "worker/worker_crossings.py",
        "worker/ubuntu_worker_entrypoint.py",
        "specs/696-durable-crossing-outbox/",
    )
    FORBIDDEN_PREFIXES = ("api/", "deploy/", ".github/", ".gitlab")

    @classmethod
    def _offenders(cls, paths: list[str]) -> list[str]:
        return [
            path
            for path in paths
            if not any(path.startswith(prefix) for prefix in cls.ALLOWED_CHANGE_PREFIXES)
        ]

    @staticmethod
    def _changed_paths() -> list[str]:
        """Sorted union of COMMITTED (vs ``BASE_SHA``) and uncommitted paths.

        The committed side is mandatory: a clean working tree must not make
        the guard vacuous after the #696 commit. It fails CLOSED — a failing
        ``git diff`` raises with diagnostics and is never replaced by the
        status-only view (a guard that cannot see committed changes must not
        pass).
        """
        try:
            committed = subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--name-only", BASE_SHA, "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise AssertionError(
                "scope guard cannot see COMMITTED changes: "
                f"`git diff --name-only {BASE_SHA} HEAD` failed with rc="
                f"{exc.returncode} ({detail or 'no output'}) — shallow clone or "
                "missing base object? Failing closed: falling back to "
                "`git status` alone would let committed out-of-scope paths pass."
            ) from exc
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        paths: set[str] = set()
        for line in committed.stdout.splitlines():
            if line.strip():
                paths.add(line.strip().strip('"'))
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.add(path.strip().strip('"'))
        return sorted(paths)

    def test_working_tree_touches_only_the_696_surface_and_tests(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope changes (issue #696 surface only — committed or uncommitted): {offenders}",
        )

    def test_no_api_deploy_workflow_or_lockfile_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES),
                    f"forbidden path changed: {path}",
                )
                self.assertFalse(
                    path.endswith(".lock") or path.endswith(".lock.txt"),
                    f"lockfile changed: {path}",
                )
                self.assertNotIn("package-lock.json", path)
                self.assertNotIn("runtime-lock.json", path)

    def test_scope_predicate_rejects_every_forbidden_path(self) -> None:
        """The guard itself must bite: feed it synthetic offenders.

        Proves the decision logic rejects the forbidden surface without
        touching the working tree (a working-tree guard cannot be exercised
        against a forbidden path from inside the admitted scope).
        """
        forbidden = [
            "api/app/analytics.py",
            "deploy/vps/deploy.sh",
            "deploy/worker/ubuntu/worker.env.example",
            ".github/workflows/quality-integration.yml",
            ".gitlab-ci.yml",
            "package-lock.json",
            "runtime-lock.json",
            "api/requirements-api.lock.txt",
        ]
        for path in forbidden:
            with self.subTest(path=path):
                self.assertTrue(self._offenders([path]), f"{path} must be rejected")
        admitted = [
            "tests/test_696_durable_crossing_outbox.py",
            "worker/worker_outbox.py",
            "worker/worker_crossings.py",
            "worker/ubuntu_worker_entrypoint.py",
            "specs/696-durable-crossing-outbox/spec.md",
        ]
        self.assertEqual(self._offenders(admitted), [], "the admitted surface must pass")


if __name__ == "__main__":
    unittest.main()
