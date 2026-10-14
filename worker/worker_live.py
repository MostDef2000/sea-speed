"""Sea Speed worker live-publisher module (issue #397, wave 7).

The live-publisher family moved VERBATIM (move-only refactor, byte-identical
bodies) from hls_motion_yolo_worker_events.py: the publish-thread state
(_LIVE_PUBLISH_QUEUE/_LIVE_PUBLISH_LOCK/_LIVE_PUBLISH_THREAD) and the three
publisher functions (_live_publisher_loop, _ensure_live_publisher,
post_live_envelope). The loop's network body (_post_live_envelope_sync) had
already moved to worker_transport in wave 5; this module imports it (import
chain live -> transport -> kernel stays acyclic).

queue/threading are allowed here by design: this module OWNS the publish
thread lifecycle - the bounded queue, its lock and the daemon thread are
created, started and drained here and nowhere else.

Object-identity coupling with the worker: _LIVE_PUBLISH_QUEUE and
_LIVE_PUBLISH_LOCK are defined here ONCE and re-exported BY IDENTITY (the
worker never rebinds them - every access is a method call on the same
Queue/Lock objects). _LIVE_PUBLISH_THREAD is the single rebinding name: it
is rebound ONLY inside _ensure_live_publisher (the only ast.Global naming
it), which moved WITH the literal so the pair is never split; the
no-rebinding/rebinder-coupling guards live in tests/test_worker_live_module.py.

Import policy (guarded by tests/test_worker_live_module.py): top-level
imports are limited to queue, threading and the repo siblings worker_kernel
(env_str) and worker_transport (_post_live_envelope_sync). NO cv2/numpy/
ultralytics/av, NO subprocess/socket, NO requests/json - network I/O stays
in worker_transport; the publisher only hands envelopes to the queue.
"""

import queue
import threading

from worker_kernel import env_str
from worker_transport import _post_live_envelope_sync


_LIVE_PUBLISH_QUEUE = queue.Queue(maxsize=1)
_LIVE_PUBLISH_LOCK = threading.Lock()
_LIVE_PUBLISH_THREAD = None


def _live_publisher_loop():
    while True:
        envelope = _LIVE_PUBLISH_QUEUE.get()
        try:
            _post_live_envelope_sync(envelope)
        finally:
            _LIVE_PUBLISH_QUEUE.task_done()


def _ensure_live_publisher():
    global _LIVE_PUBLISH_THREAD
    with _LIVE_PUBLISH_LOCK:
        if _LIVE_PUBLISH_THREAD is None or not _LIVE_PUBLISH_THREAD.is_alive():
            _LIVE_PUBLISH_THREAD = threading.Thread(
                target=_live_publisher_loop,
                name="road-live-publisher",
                daemon=True,
            )
            _LIVE_PUBLISH_THREAD.start()


def post_live_envelope(envelope):
    if not env_str("SEA_SPEED_LIVE_API_URL") and not env_str("SEA_SPEED_API_URL"):
        return False
    if not env_str("SEA_SPEED_API_TOKEN"):
        return False
    _ensure_live_publisher()
    try:
        _LIVE_PUBLISH_QUEUE.put_nowait(envelope)
    except queue.Full:
        try:
            _LIVE_PUBLISH_QUEUE.get_nowait()
            _LIVE_PUBLISH_QUEUE.task_done()
        except queue.Empty:
            pass
        _LIVE_PUBLISH_QUEUE.put_nowait(envelope)
    return True
