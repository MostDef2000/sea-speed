"""Executed + structural twins for the protected-operator frontend contract
(issue #398 wave 4).

The raw source-text pins this file carried are retired in place: every
BEHAVIORAL pin became an execution of the page's real inline scripts under
the html shim (tests/support/frontend_html.py) — the water and road operator
pages boot against programmable API responses and the scenarios drive the
recorded handlers (HLS media events, worker toggle, stream toggle, refresh
intervals, registry scope controls) exactly like an operator would:

- one HLS player per operator page, attached to the page's main video element
  and published as window.hls (=== window.waterHls on water), loading the
  protected media path through the recorded MEDIA_ATTACHED handler;
- the worker toggle POSTs the page-scoped worker control endpoints and flips
  the overlay's worker state without touching the live stream;
- the fallback overlay snapshot lands on the overlay <img> only while
  playback is NOT advancing, is deduped per URL, and is re-applied after a
  reconnect cycle clears the dedup guard;
- the objects registry binds its camera/domain scope from ?scope, the
  same-origin referrer and the domain filter, syncs the scope into the URL,
  and issues real same-origin PATCH/DELETE writes;
- the playback watchdogs grant a startup grace (issue #656): a connect that
  is still buffering within the ~15s startup budget is never killed (the old
  1s road / 2.5s water watchdogs killed hls.js during its normal live-sync
  startup), the budget timeout reconnects exactly once, and the strict stall
  detection stays armed after playback has started.

Structural pins without an executable surface (data-layout markers, header
order, grid-template-areas, media queries, static link wiring, the stream
retry-ladder literal — the executed twins prove only its first 1000 ms rung)
stay source scans (SS) — CSS and markup have no AST to execute. The overlay/live-sync
module pins are covered by the wave-1 executed tests (test_live_overlay_sync,
test_road_overlay_sync, test_water_live_sync_guard) and are referenced, not
duplicated; the session watchdog/storage contract is executed in
tests/test_auth_session_frontend_contract.py. The full pin→twin mapping
lives in specs/398-wave4.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import frontend_html, frontend_node  # noqa: E402

WATER_PAGE = ROOT / "frontend/sea-speed/index.html"
ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"
OBJECTS_PAGE = ROOT / "frontend/sea-speed/objects/index.html"
CAMERAS_PAGE = ROOT / "frontend/sea-speed/cameras/index.html"
ROOT_PAGE = ROOT / "frontend/root/index.html"

WATER = WATER_PAGE.read_text(encoding="utf-8-sig")
ROAD = ROAD_PAGE.read_text(encoding="utf-8-sig")
OBJECTS = OBJECTS_PAGE.read_text(encoding="utf-8-sig")
CAMERAS = CAMERAS_PAGE.read_text(encoding="utf-8-sig")
ROOT_SOURCE = ROOT_PAGE.read_text(encoding="utf-8-sig")

WATER_HLS_URL = "/sea-speed/media/cam1/index.m3u8"
ROAD_HLS_URL = "/sea-speed/media/road1/index.m3u8"

# Pinned hls.js CDN artifact (issue #575): the production-proven 1.5.7
# release, loaded with Subresource Integrity on every operator page.
HLS_PINNED_SRC = "https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"
HLS_SRI_INTEGRITY = "sha384-1B+J55elPxu+trIhW7QThjZg3evX8C5P6zjB82Xnn46RKPAXpL+vkanRSjCidsJv"

# Boot responses: the worker control GET must answer ok:true so the page
# renders the trusted worker state instead of the control-error path.
WATER_WORKER_RESPONSE = {"match": "/worker/control", "json": {"ok": True, "active": True}}
ROAD_WORKER_RESPONSE = {
    "match": "/worker/control",
    "json": {"ok": True, "active": True, "target": "road1"},
}

SCENARIO_PREAMBLE = """
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  const settle = () => new Promise((r) => setImmediate(r));
  await settle();
"""

# Scenario-local virtual clock for the startup-grace twins (issue #656): the
# shim's setTimeout records but never fires, and the pages' stall math reads
# performance.now() (road) / Date.now() (water) — both real clocks under
# node — so "advance simulated time" is inexpressible without a scenario
# override. It is installed AFTER boot (the auto-connect already ran), so
# only the watchdog/reconnect timers the scenario drives go through it;
# advance(ms) fires the page's own timers in deadline order up to now+ms.
# The clock starts at 1e6 ms (never 0) because the pages treat a 0 progress
# timestamp as "no progress yet" (lastPlaybackProgressAt>0 guards).
VIRTUAL_CLOCK = """
  let __vnow = 1e6;
  const __pending = [];
  let __seq = 0;
  globalThis.setTimeout = (fn, ms) => { const id = ++__seq; __pending.push({ id, at: __vnow + Number(ms), fn }); return id; };
  globalThis.clearTimeout = (id) => { const i = __pending.findIndex((t) => t.id === id); if (i >= 0) __pending.splice(i, 1); };
  performance.now = () => __vnow;
  Date.now = () => __vnow;
  const advance = async (ms) => {
    const target = __vnow + ms;
    for (;;) {
      const due = __pending.filter((t) => t.at <= target).sort((a, b) => a.at - b.at || a.id - b.id);
      if (!due.length) break;
      for (const t of due) {
        const i = __pending.indexOf(t);
        if (i >= 0) __pending.splice(i, 1);
        __vnow = t.at;
        await t.fn();
      }
    }
    __vnow = target;
  };
"""

# Executed water stream twin: the auto-connect timer is drained, then the
# recorded MEDIA_ATTACHED handler must loadSource the protected media path.
# One Hls instance only, attached to waterMainVideo only, published as
# window.hls === window.waterHls; the main video carries the playback
# listeners and the waiting→watchdog→retry ladder is driven end to end; the
# stream toggle tears the stream down and re-creates it.
WATER_HLS_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const bootUrls = __record.fetch.map((c) => c.url);
  for (const endpoint of ["/sea-speed/api/cam1/state", "/sea-speed/api/cam1/roi", "/sea-speed/api/worker/control"]) {
    assert(bootUrls.includes(endpoint), "the operator page must wire " + endpoint + " at boot");
  }
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "the water page must create exactly one HLS instance; got " + instances.length);
  const inst = instances[0];
  assert(
    inst.attached.length === 1 && inst.attached[0].id === "waterMainVideo",
    "HLS must attach to waterMainVideo only: " + JSON.stringify(inst.attached.map((e) => e && e.id))
  );
  assert(window.hls === inst && window.waterHls === inst, "the live instance must be published as window.hls and window.waterHls");
  for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  assert(
    JSON.stringify(inst.sources) === JSON.stringify(["/sea-speed/media/cam1/index.m3u8"]),
    "MEDIA_ATTACHED must loadSource the protected water HLS path; got " + JSON.stringify(inst.sources)
  );
  const videoListeners = __record.elements.waterMainVideo.__listeners;
  for (const type of ["timeupdate", "waiting", "stalled"]) {
    assert((videoListeners[type] || []).length >= 1, "waterMainVideo must register a " + type + " playback listener");
  }
  let before = __record.timeouts.length;
  videoListeners.waiting[0]();
  await settle();
  let scheduled = __record.timeouts.slice(before);
  assert(scheduled.length === 1 && scheduled[0][1] === 2500, "waiting must schedule the 2500 ms playback watchdog");
  before = __record.timeouts.length;
  scheduled[0][0]();
  await settle();
  scheduled = __record.timeouts.slice(before);
  assert(scheduled.length === 1 && scheduled[0][1] === 1000, "a stalled watchdog must schedule the first stream retry (1000 ms)");
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(inst.destroyed === true && window.hls === null, "the stream toggle must tear the stream down");
  assert(__record.elements.debugLog.textContent.includes("HLS disconnected"), "stopping the stream must be logged");
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(__record.hlsInstances.length === 2, "re-toggling the stream must create a fresh HLS instance");
  assert(window.hls === __record.hlsInstances[1] && window.waterHls === window.hls, "the fresh instance must be republished as window.hls/waterHls");
  console.log("###" + JSON.stringify({ sources: inst.sources, instances: __record.hlsInstances.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water worker twin: the boot control state reaches the overlay, and
# the recorded toggle handler POSTs the worker start/stop endpoints and flips
# the overlay state WITHOUT touching the live stream.
WATER_WORKER_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  assert(__record.workerActive.includes(true), "the boot worker state must reach the overlay");
  assert(__record.elements.workerStatus.textContent === "online", "an active worker must render online: " + __record.elements.workerStatus.textContent);
  assert(__record.overlayInits.length === 1 && __record.overlayInits[0].cameraId === "cam1", "the overlay module must init for cam1");
  assert(__record.overlayInits[0].videoId === "waterMainVideo" && __record.overlayInits[0].isWater === true, "the overlay must bind the water video");
  assert(typeof window.clearWaterLiveOverlay === "undefined", "the retired global clear hook must stay absent");
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const inst = __record.hlsInstances[__record.hlsInstances.length - 1];
  const workerPosts = () => __record.fetch.filter((c) => (c.options.method || "GET") === "POST" && c.url.includes("/worker/control"));
  assert(workerPosts().length === 0, "boot must only GET the worker control state");
  __responses.length = 0;
  __setResponse("/worker/control/stop", { ok: true, active: false });
  await __record.elements.workerControlBtn.onclick();
  await settle();
  let posts = workerPosts();
  assert(posts.length === 1 && posts[0].url === "/sea-speed/api/worker/control/stop", "the stop toggle must POST the worker stop endpoint: " + JSON.stringify(posts.map((p) => p.url)));
  assert(__record.elements.debugLog.textContent.includes("AI worker stopped; live HLS unchanged"), "stopping must log the media-independence note");
  assert(__record.workerActive[__record.workerActive.length - 1] === false, "the overlay must be told the worker stopped");
  assert(inst.destroyed === false && window.hls === inst, "the worker toggle must not touch the live stream");
  assert(!__record.elements.debugLog.textContent.includes("HLS disconnected"), "the worker toggle must not disconnect the stream");
  __responses.length = 0;
  __setResponse("/worker/control/start", { ok: true, active: true });
  await __record.elements.workerControlBtn.onclick();
  await settle();
  posts = workerPosts();
  assert(posts.length === 2 && posts[1].url === "/sea-speed/api/worker/control/start", "the start toggle must POST the worker start endpoint");
  assert(__record.elements.debugLog.textContent.includes("AI worker started"), "starting must be logged");
  assert(__record.workerActive[__record.workerActive.length - 1] === true, "the overlay must be told the worker restarted");
  console.log("###" + JSON.stringify({ workerActive: __record.workerActive }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water fallback-overlay twin: the boot snapshot lands on the
# overlay <img> while playback is not advancing, an unchanged URL is never
# re-applied (dedup guard), a new URL is applied, and ADVANCING playback
# gates the fallback off entirely. The src spy is installed at scenario
# start, capturing the boot-time assignment into the current value.
WATER_FALLBACK_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const overlayImg = __record.elements.overlayImg;
  let currentSrc = String(overlayImg.src || "");
  const sets = [];
  Object.defineProperty(overlayImg, "src", {
    get: () => currentSrc,
    set: (v) => { currentSrc = String(v); sets.push(currentSrc); },
    configurable: true,
  });
  assert(currentSrc.includes("/sea-speed/api/cam1/overlay/snap-1.png"), "the boot fallback snapshot must land on overlayImg.src while playback is not advancing: " + currentSrc);
  const refresh = __record.intervals.find(([, ms]) => ms === 1500);
  assert(refresh, "the 1500 ms state refresh interval is missing");
  __responses.length = 0;
  __setResponse("/cam1/state", { last_overlay_url: "/sea-speed/api/cam1/overlay/snap-1.png" });
  await refresh[0]();
  assert(sets.length === 0, "an unchanged fallback URL must not re-assign overlayImg.src");
  let seq = 1;
  __responses.length = 0;
  __setResponse("/cam1/state", () => ({ last_overlay_url: "/sea-speed/api/cam1/overlay/snap-" + (++seq) + ".png" }));
  await refresh[0]();
  assert(sets.length === 1 && sets[0].includes("snap-2.png"), "a new fallback URL must update overlayImg.src: " + JSON.stringify(sets));
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const video = __record.elements.waterMainVideo;
  video.paused = false;
  video.currentTime = 5;
  for (const fn of video.__listeners.timeupdate || []) fn();
  await refresh[0]();
  assert(sets.length === 1, "advancing playback must gate the fallback overlay off");
  console.log("###" + JSON.stringify({ sets: sets.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water crossings-summary + recent-passages twin: the boot summary
# fetch carries the VLZ date window and populates the KPI/row elements; five
# passages render at most three event cards and a status-less passage falls
# back to the "tracking" badge.
WATER_STATS_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  assert(String(__record.elements.cxStatsIn.textContent) === "2", "the IN kpi must render the summary totals");
  assert(String(__record.elements.cxStatsOut.textContent) === "1", "the OUT kpi must render the summary totals");
  assert(String(__record.elements.cxStatsTotal.textContent) === "3", "the total kpi must sum the directions");
  assert(__record.elements.cxStatsRows.innerHTML.includes("vessel"), "the summary rows must break down by class");
  const summaryFetch = __record.fetch.find((c) => c.url.startsWith("/sea-speed/api/analytics/cam1/crossings/summary"));
  assert(summaryFetch, "the crossings summary must be fetched at boot");
  assert(summaryFetch.url.includes("date_from=") && summaryFetch.url.includes("date_to="), "the summary must be queried with the VLZ date window: " + summaryFetch.url);
  const cards = __record.elements.eventsList.__children || [];
  assert(cards.length === 3, "recent passages must render at most 3 cards; got " + cards.length);
  for (const card of cards) assert(card.className === "event-card", "passage cards must use the event-card markup");
  const statusBadge = cards[1].__children[0].__children[1].__children[2];
  assert(statusBadge.textContent === "tracking", "a passage without status must fall back to tracking: " + String(statusBadge.textContent));
  console.log("###" + JSON.stringify({ cards: cards.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road stream twin (drain_timeouts=True: the auto-connect timer
# runs attachHls before the scenario). The permanent protected HLS URL must
# be loaded and attached to roadMainVideo only — no preview session is
# started or stopped anymore (issue #637); the manifest, media-error and
# network-error paths arm the recorded watchdog/recovery/retry timers; the
# stream toggle tears the instance down without any API call.
ROAD_HLS_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const starts = __record.fetch.filter((c) => c.url.includes("/cameras/") && (c.options.method || "GET") === "POST");
  assert(starts.length === 0, "connect must not call any camera preview endpoint: " + JSON.stringify(starts.map((s) => s.url)));
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "the road page must create exactly one HLS instance; got " + instances.length);
  const inst = instances[0];
  assert(
    inst.attached.length === 1 && inst.attached[0].id === "roadMainVideo",
    "HLS must attach to roadMainVideo only: " + JSON.stringify(inst.attached.map((e) => e && e.id))
  );
  assert(
    JSON.stringify(inst.sources) === JSON.stringify(["/sea-speed/media/road1/index.m3u8"]),
    "the permanent HLS URL must be loaded: " + JSON.stringify(inst.sources)
  );
  assert(window.hls === inst, "the live instance must be published as window.hls");
  let before = __record.timeouts.length;
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  let scheduled = __record.timeouts.slice(before);
  assert(scheduled.length === 1 && scheduled[0][1] === 1000, "manifest-parsed must arm the 1000 ms playback watchdog");
  // The media-recovery cooldown is wall-clock; pre-age it so the branch is
  // deterministic under the harness (the branch wiring is what is pinned).
  lastMediaRecoveryAt = -1e9;
  before = __record.timeouts.length;
  for (const handler of inst.handlers.hlsError || []) await handler({}, { fatal: true, type: "mediaError", details: "bufferStalled" });
  scheduled = __record.timeouts.slice(before);
  assert(scheduled.length === 1 && scheduled[0][1] === 3500, "a fatal media error must schedule the 3500 ms recovery check");
  assert(__record.elements.debugLog.textContent.includes("HLS media recovery"), "the media recovery must be logged");
  before = __record.timeouts.length;
  for (const handler of inst.handlers.hlsError || []) await handler({}, { fatal: true, type: "networkError", details: "manifestLoadError" });
  scheduled = __record.timeouts.slice(before);
  assert(scheduled.length === 1 && scheduled[0][1] === 1000, "a fatal network error must schedule the first stream retry (1000 ms)");
  assert(__record.elements.debugLog.textContent.includes("HLS network recovery"), "the network recovery must be logged");
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(!__record.fetch.some((c) => (c.options.method || "GET") === "POST" && c.url.includes("/cameras")), "disconnect must not call any camera endpoint");
  assert(inst.destroyed === true && window.hls === null, "disconnect must tear the HLS instance down");
  assert(__record.elements.debugLog.textContent.includes("Road HLS stopped; AI worker state unchanged"), "disconnect must log worker independence");
  console.log("###" + JSON.stringify({ sources: inst.sources }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road Chrome-lie twin: Chrome reports canPlayType('application/
# vnd.apple.mpegurl') === 'maybe' while being unable to demux native HLS
# (prod incident 2026-11-12: the native-first branch stalled forever at
# readyState 0). The hls.js branch must win FIRST whenever MSE is available,
# with the worker disabled (the site CSP has no worker-src, so hls.js blob:
# workers are blocked), and the native path must stay a no-MSE fallback only.
ROAD_CHROME_LIE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "boot must connect exactly once; got " + instances.length);
  __canPlayType = "maybe";
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(instances[0].destroyed === true && window.hls === null, "the stop toggle must tear the boot instance down");
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(instances.length === 2, "the reconnect must stay on the hls.js branch even when canPlayType lies; got " + instances.length);
  assert(
    instances[1].config && instances[1].config.enableWorker === false,
    "road hls.js must run with enableWorker:false (CSP blocks blob: workers); got " + JSON.stringify(instances[1].config)
  );
  assert(
    JSON.stringify(instances[1].sources) === JSON.stringify(["/sea-speed/media/road1/index.m3u8"]),
    "the reconnect must load the protected road HLS path; got " + JSON.stringify(instances[1].sources)
  );
  assert(!__record.elements.roadMainVideo.src, "the native src must never be set while MSE is available; got " + __record.elements.roadMainVideo.src);
  console.log("###" + JSON.stringify({ configs: instances.map((i) => i.config) }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road no-MSE twin: with MSE unavailable the native path is the only
# fallback left and must set video.src directly (never create an Hls instance).
ROAD_NO_MSE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "boot must connect exactly once; got " + instances.length);
  __hlsSupported = false;
  __canPlayType = "maybe";
  await __record.elements.streamControlBtn.onclick();
  await settle();
  await __record.elements.streamControlBtn.onclick();
  await settle();
  assert(instances.length === 1, "no new Hls instance may be created when MSE is unavailable; got " + instances.length);
  assert(instances[0].destroyed === true && window.hls === null, "the hls.js instance must stay torn down on the native fallback");
  assert(
    __record.elements.roadMainVideo.src === "/sea-speed/media/road1/index.m3u8",
    "the no-MSE fallback must set the native video src; got " + JSON.stringify(__record.elements.roadMainVideo.src)
  );
  console.log("###" + JSON.stringify({ nativeSrc: __record.elements.roadMainVideo.src }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road startup-grace twin (issue #656): after MANIFEST_PARSED the
# video may legitimately sit at readyState 0 while hls.js live-syncs its
# first segments (~5-8s on the 2s-segment playlist); the old 1s polling
# watchdog killed the instance ~1s after MANIFEST_PARSED, forever. Within
# the ~15s startup budget no reconnect may happen — the virtual clock
# (VIRTUAL_CLOCK) advances simulated time well past the old kill point.
ROAD_STARTUP_GRACE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  const inst = __record.hlsInstances[0];
  assert(__record.hlsInstances.length === 1, "boot must connect exactly once; got " + __record.hlsInstances.length);
  assert(window.hls === inst, "the boot instance must be the attached one");
  const video = __record.elements.roadMainVideo;
  video.readyState = 0;
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(10000);
  assert(streamGeneration === 1, "startup grace: no reconnect may happen ~10s into startup (past the old 1s kill and the 2500 ms stall grace); streamGeneration went 1 -> " + streamGeneration);
  assert(__record.hlsInstances.length === 1, "startup grace: the original instance must stay attached; got " + __record.hlsInstances.length + " instances");
  assert(window.hls === inst, "startup grace: window.hls must still be the boot instance");
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length, status: __record.elements.streamStatus.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road startup-timeout twin (issue #656): playback that never
# starts must still reconnect — but only the startup-budget timeout may
# trigger it: no reconnect before the ~15s budget elapses, exactly one
# reconnect after it (the old watchdog reconnected at ~2s).
ROAD_STARTUP_TIMEOUT_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  const inst = __record.hlsInstances[0];
  const video = __record.elements.roadMainVideo;
  video.readyState = 0;
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(14000);
  assert(streamGeneration === 1, "startup timeout: no reconnect may be scheduled before the ~15s startup budget elapses; streamGeneration went 1 -> " + streamGeneration);
  await advance(6000);
  assert(streamGeneration === 2, "startup timeout: the budget timeout must lead to exactly one reconnect; streamGeneration = " + streamGeneration);
  assert(__record.hlsInstances.length === 2, "startup timeout: exactly one reconnect must create exactly one fresh instance; got " + __record.hlsInstances.length);
  assert(window.hls === __record.hlsInstances[1], "the startup-timeout reconnect must attach a fresh instance");
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road post-start stall twin (issue #656 regression guard): once
# playback has started (readyState>=2, playing), a stall with no progress
# for past the 2500 ms grace must still schedule a reconnect — the strict
# stall detection survives the startup-grace change.
ROAD_POST_START_STALL_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  const inst = __record.hlsInstances[0];
  const video = __record.elements.roadMainVideo;
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  video.readyState = 2;
  video.paused = false;
  video.currentTime = 1;
  for (const fn of video.__listeners.playing || []) fn();
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(3000);
  assert(__record.elements.streamStatus.textContent === "retrying", "post-start stall: a stalled watchdog must schedule a reconnect; status = " + __record.elements.streamStatus.textContent);
  await advance(1000);
  assert(streamGeneration === 2 && __record.hlsInstances.length === 2, "post-start stall: the scheduled reconnect must run; generation=" + streamGeneration + " instances=" + __record.hlsInstances.length);
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road worker twin: the road-scoped control endpoints only, the
# trusted target guard, and a toggle that never touches the live stream.
ROAD_WORKER_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  assert(__record.elements.workerStatus.textContent === "online", "an active road worker must render online: " + __record.elements.workerStatus.textContent);
  assert(__record.workerActive[0] === true, "the boot worker state must reach the overlay");
  assert(__record.overlayInits.length === 1 && __record.overlayInits[0].cameraId === "road1" && __record.overlayInits[0].isWater === false, "the overlay module must init for road1");
  const workerPosts = () => __record.fetch.filter((c) => (c.options.method || "GET") === "POST" && c.url.includes("/worker/control"));
  assert(workerPosts().length === 0, "boot must only GET the worker control state");
  __responses.length = 0;
  __setResponse("/worker/control/road1/stop", { ok: true, active: false, target: "road1" });
  await __record.elements.workerControlBtn.onclick();
  await settle();
  let posts = workerPosts();
  assert(posts.length === 1 && posts[0].url === "/sea-speed/api/worker/control/road1/stop", "the stop toggle must POST the road-scoped stop endpoint: " + JSON.stringify(posts.map((p) => p.url)));
  assert(__record.elements.debugLog.textContent.includes("Road AI worker stopped; live HLS unchanged"), "stopping must log the media-independence note");
  assert(__record.workerActive[__record.workerActive.length - 1] === false, "the overlay must be told the worker stopped");
  const inst = __record.hlsInstances[__record.hlsInstances.length - 1];
  assert(inst && inst.destroyed === false && window.hls === inst, "the worker toggle must not touch the live stream");
  assert(!__record.elements.debugLog.textContent.includes("Road HLS stopped"), "the worker toggle must not stop the stream");
  assert(!__record.fetch.some((c) => c.url.includes("/api/cameras")), "the worker toggle must not touch the camera API");
  __responses.length = 0;
  __setResponse("/worker/control/road1/start", { ok: true, active: true, target: "road1" });
  await __record.elements.workerControlBtn.onclick();
  await settle();
  posts = workerPosts();
  assert(posts.length === 2 && posts[1].url === "/sea-speed/api/worker/control/road1/start", "the start toggle must POST the road-scoped start endpoint");
  assert(__record.elements.debugLog.textContent.includes("Road AI worker started; live HLS unchanged"), "starting must log the media-independence note");
  for (const unscoped of ["/sea-speed/api/worker/control/start", "/sea-speed/api/worker/control/stop"]) {
    assert(!__record.fetch.some((c) => c.url === unscoped), "the unscoped worker endpoint " + unscoped + " must never be called");
  }
  console.log("###" + JSON.stringify({ workerActive: __record.workerActive }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road worker target guard: a control payload naming another camera
# must fail closed (control error, no toggle possible).
ROAD_WORKER_TARGET_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  assert(__record.elements.workerStatus.textContent === "control error", "a foreign worker target must fail closed: " + __record.elements.workerStatus.textContent);
  assert(__record.workerActive.length === 0, "a foreign target must not reach the overlay");
  await __record.elements.workerControlBtn.onclick();
  await settle();
  assert(
    !__record.fetch.some((c) => (c.options.method || "GET") === "POST" && c.url.includes("/worker/control")),
    "the toggle must refuse to POST without a trusted worker state"
  );
  console.log("###" + JSON.stringify({ guarded: true }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road fallback-overlay twin: the boot snapshot lands with the
# revision buster, an unchanged URL is never re-applied, advancing playback
# gates the fallback off, and a reconnect cycle (connect → clearFallbackOverlay
# → disconnect) resets the dedup guard so the SAME snapshot is re-applied.
ROAD_FALLBACK_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  const overlayImg = __record.elements.overlayImg;
  let currentSrc = String(overlayImg.src || "");
  const sets = [];
  Object.defineProperty(overlayImg, "src", {
    get: () => currentSrc,
    set: (v) => { currentSrc = String(v); sets.push(currentSrc); },
    configurable: true,
  });
  assert(currentSrc.endsWith("/sea-speed/api/analytics/road1/overlay/snap.png?v=7"), "the boot fallback must land on overlayImg.src with the revision buster: " + currentSrc);
  const refresh = __record.intervals.find(([, ms]) => ms === 3000);
  assert(refresh, "the 3000 ms road refresh interval is missing");
  const seedState = (state) => {
    __responses.length = 0;
    __setResponse("/analytics/road1/state", state);
    __setResponse("/analytics/road1/events", { events: [] });
  };
  await refresh[0]();
  await refresh[0]();
  assert(sets.length === 0, "an unchanged fallback URL must not re-assign overlayImg.src");
  const video = __record.elements.roadMainVideo;
  video.paused = false;
  video.currentTime = 5;
  for (const fn of video.__listeners.timeupdate || []) fn();
  seedState(() => ({ last_overlay_url: "/sea-speed/api/analytics/road1/overlay/snap.png", overlay_rev: 8 }));
  await refresh[0]();
  assert(sets.length === 0, "advancing playback must gate the fallback overlay off");
  video.paused = true;
  for (const [fn] of __record.timeouts.splice(0)) await fn();
  await settle();
  await __record.elements.streamControlBtn.onclick();
  await settle();
  seedState({ last_overlay_url: "/sea-speed/api/analytics/road1/overlay/snap.png", overlay_rev: 7 });
  await refresh[0]();
  assert(sets.length === 1 && sets[0].endsWith("snap.png?v=7"), "after a reconnect cycle the same snapshot must be re-applied (dedup guard reset): " + JSON.stringify(sets));
  console.log("###" + JSON.stringify({ sets: sets.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed road crossings + recent-events twin: the state payload populates
# the crossing KPIs/rows and five events render at most three cards with the
# speed placeholder for unmeasured events.
ROAD_STATS_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  assert(String(__record.elements.cxStatsIn.textContent) === "2", "the IN kpi must render the state crossings");
  assert(String(__record.elements.cxStatsOut.textContent) === "1", "the OUT kpi must render the state crossings");
  assert(String(__record.elements.cxStatsTotal.textContent) === "3", "the total kpi must sum the directions");
  assert(__record.elements.cxStatsRows.innerHTML.includes("car"), "the crossing rows must break down by class");
  const grid = __record.elements.eventsList.innerHTML;
  const cards = grid.split('class="event-card"').length - 1;
  assert(cards === 3, "recent events must render at most 3 cards; got " + cards);
  assert(grid.includes("speed --"), "an event without a measured speed must render the placeholder");
  console.log("###" + JSON.stringify({ cards }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed objects-registry twin (water default scope): the boot query carries
# the water camera/domain, the scope drives the filter controls, the page
# title and the URL; switching the domain filter re-queries the road scope;
# the operator write paths issue real same-origin PATCH/DELETE requests.
OBJECTS_SCOPE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  await settle();
  const objectsFetches = () => __record.fetch.filter((c) => c.url.startsWith("/sea-speed/api/objects?"));
  assert(objectsFetches().length >= 1, "the registry must load at boot");
  assert(objectsFetches()[0].url.includes("camera_id=cam1") && objectsFetches()[0].url.includes("domain=water"), "the default scope must query the water camera: " + objectsFetches()[0].url);
  assert(__record.elements.cameraInput.value === "cam1" && __record.elements.domainInput.value === "water", "the scope must drive the filter controls");
  assert(document.title.includes("Water"), "the water scope must title the page: " + document.title);
  assert(__record.history.some((args) => args.join(" ").includes("scope=water")), "the scope must be synced into the URL");
  assert((__record.elements.objectsGrid.innerHTML || "").includes("obj-1"), "the registry response must render into the grid");
  __record.elements.domainInput.value = "road";
  for (const fn of __record.elements.domainInput.__listeners.change || []) await fn();
  await settle();
  await settle();
  const roadFetch = objectsFetches()[objectsFetches().length - 1];
  assert(roadFetch.url.includes("camera_id=road1") && roadFetch.url.includes("domain=road"), "switching the domain must re-query the road scope: " + roadFetch.url);
  assert(__record.history.some((args) => args.join(" ").includes("scope=road")), "the switched scope must be synced into the URL");
  await openObject("obj-9");
  await settle();
  assert(typeof currentObject !== "undefined" && currentObject && currentObject.object_id === "obj-9", "openObject must load the object detail");
  let before = __record.fetch.length;
  for (const fn of __record.elements.editForm.__listeners.submit || []) await fn({ preventDefault() {} });
  await settle();
  await settle();
  const patch = __record.fetch.slice(before).find((c) => (c.options.method || "GET") === "PATCH");
  assert(patch && patch.url.endsWith("/sea-speed/api/objects/obj-9"), "saving the edit form must PATCH the object detail endpoint");
  assert(patch.options.credentials === "same-origin", "the PATCH must stay same-origin");
  assert(JSON.parse(patch.options.body).class_name === "car", "the PATCH must carry the edited fields");
  await openObject("obj-9");
  await settle();
  before = __record.fetch.length;
  for (const fn of __record.elements.deleteBtn.__listeners.click || []) await fn();
  await settle();
  await settle();
  const del = __record.fetch.slice(before).find((c) => (c.options.method || "GET") === "DELETE");
  assert(del && del.url.endsWith("/sea-speed/api/objects/obj-9"), "the delete action must DELETE the object detail endpoint");
  console.log("###" + JSON.stringify({ writes: 2 }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed objects-registry scope twins: ?scope=road and a same-origin road
# referrer must both bind the road registry scope.
OBJECTS_ROAD_SCOPE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  await settle();
  assert(typeof registryScopeKey !== "undefined" && registryScopeKey === "road", "the road scope binding must be active: " + String(registryScopeKey));
  const fetchUrl = (__record.fetch.find((c) => c.url.startsWith("/sea-speed/api/objects?")) || {}).url || "";
  assert(fetchUrl.includes("camera_id=road1") && fetchUrl.includes("domain=road"), "the road scope must query road1/road: " + fetchUrl);
  assert(__record.elements.cameraInput.value === "road1" && __record.elements.domainInput.value === "road", "the road scope must drive the filter controls");
  assert(document.title.includes("Road"), "the road scope must title the page: " + document.title);
  console.log("###" + JSON.stringify({ url: fetchUrl }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

WATER_STATE_FALLBACK_RESPONSE = {
    "match": "/cam1/state",
    "json": {"last_overlay_url": "/sea-speed/api/cam1/overlay/snap-1.png"},
}
WATER_SUMMARY_RESPONSE = {
    "match": "/crossings/summary",
    "json": {
        "totals": {"left_to_right": 2, "right_to_right": 0, "right_to_left": 1},
        "by_class": {"vessel": {"left_to_right": 2, "right_to_left": 1}},
    },
}
WATER_PASSAGES_RESPONSE = {
    "match": "/cam1/passages",
    "json": {
        "passages": [
            {"passage_id": "p1", "class_name": "vessel", "started_at": "2026-10-29T01:00:00Z", "direction": "left_to_right", "status": "new", "speed_status": "measured", "speed_kmh": 12.5},
            {"passage_id": "p2", "class_name": "vessel", "started_at": "2026-10-29T01:01:00Z", "direction": "right_to_left"},
            {"passage_id": "p3", "class_name": "vessel", "started_at": "2026-10-29T01:02:00Z", "direction": "left_to_right", "status": "reviewed", "speed_status": "measuring"},
            {"passage_id": "p4", "class_name": "vessel", "started_at": "2026-10-29T01:03:00Z", "direction": "right_to_left", "status": "new", "speed_status": "incomplete"},
            {"passage_id": "p5", "class_name": "vessel", "started_at": "2026-10-29T01:04:00Z", "direction": "left_to_right", "status": "new", "speed_status": "measured", "speed_kmh": 9.0},
        ]
    },
}
ROAD_STATE_STATS_RESPONSE = {
    "match": "/analytics/road1/state",
    "json": {
        "crossings": {
            "left_to_right": 2,
            "right_to_left": 1,
            "by_class": {"car": {"left_to_right": 2, "right_to_left": 1}},
        },
        "frame_width": 1920,
        "frame_height": 1080,
    },
}
ROAD_EVENTS_RESPONSE = {
    "match": "/analytics/road1/events",
    "json": {
        "events": [
            {"event_id": "e1", "created_at": "2026-10-29T01:00:00Z", "object_type": "car", "speed_kmh": 57.3},
            {"event_id": "e2", "created_at": "2026-10-29T01:01:00Z", "object_type": "car"},
            {"event_id": "e3", "created_at": "2026-10-29T01:02:00Z", "object_type": "truck", "speed_kmh": 41.0},
            {"event_id": "e4", "created_at": "2026-10-29T01:03:00Z", "object_type": "car", "speed_kmh": 48.8},
            {"event_id": "e5", "created_at": "2026-10-29T01:04:00Z", "object_type": "car", "speed_kmh": 39.2},
        ]
    },
}
ROAD_STATE_FALLBACK_RESPONSE = {
    "match": "/analytics/road1/state",
    "json": {"last_overlay_url": "/sea-speed/api/analytics/road1/overlay/snap.png", "overlay_rev": 7},
}
OBJECTS_DETAIL_RESPONSE = {
    "match": "/sea-speed/api/objects/obj-9",
    "json": {
        "object": {
            "object_id": "obj-9",
            "class_name": "car",
            "speed_kmh": 42.5,
            "status": "new",
            "comment": "",
            "original_event": {},
            "snapshot_url": None,
        }
    },
}
OBJECTS_LIST_RESPONSE = {
    "match": "/sea-speed/api/objects",
    "json": {
        "objects": [
            {
                "object_id": "obj-1",
                "class_name": "vessel",
                "camera_id": "cam1",
                "domain": "water",
                "speed_kmh": 12.5,
                "status": "new",
                "detected_at": "2026-10-29T01:00:00Z",
                "track_id": 7,
            }
        ],
        "total": 1,
        "count": 1,
    },
}


# Executed water worker-off twin: the site CSP has no worker-src, so hls.js
# blob: workers are blocked at the edge (prod incident 2026-11-12); the water
# Hls config must ship enableWorker:false.
WATER_ENABLEWORKER_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + """
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const instances = __record.hlsInstances;
  assert(instances.length === 1, "the water page must create exactly one HLS instance; got " + instances.length);
  assert(
    instances[0].config && instances[0].config.enableWorker === false,
    "water hls.js must run with enableWorker:false (CSP blocks blob: workers); got " + JSON.stringify(instances[0].config)
  );
  console.log("###" + JSON.stringify({ configs: instances.map((i) => i.config) }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water startup-grace twin (issue #656): MANIFEST_PARSED →
# attemptVideoPlay → the video fires `waiting` with an empty buffer while
# hls.js live-syncs its first segments; the old 2500 ms watchdog reconnected
# at ~2.5s, forever. Within the ~15s startup budget no reconnect may happen
# — the virtual clock (VIRTUAL_CLOCK) advances simulated time past the old
# kill point.
WATER_STARTUP_GRACE_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const inst = __record.hlsInstances[0];
  assert(__record.hlsInstances.length === 1, "boot must connect exactly once; got " + __record.hlsInstances.length);
  assert(window.hls === inst && window.waterHls === inst, "the boot instance must be the attached one");
  for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  await settle();
  const video = __record.elements.waterMainVideo;
  video.paused = false;
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(5000);
  assert(streamGeneration === 1, "startup grace: no reconnect may happen ~5s into startup (past the old 2500 ms kill); streamGeneration went 1 -> " + streamGeneration);
  assert(__record.hlsInstances.length === 1, "startup grace: the original instance must stay attached; got " + __record.hlsInstances.length + " instances");
  assert(window.hls === inst, "startup grace: window.hls must still be the boot instance");
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length, status: __record.elements.streamStatus.textContent }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water startup-timeout twin (issue #656): playback that never
# starts must still reconnect — but only the startup-budget timeout may
# trigger it: no reconnect before the ~15s budget elapses, exactly one
# reconnect after it (the old watchdog reconnected at ~2.5s).
WATER_STARTUP_TIMEOUT_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const inst = __record.hlsInstances[0];
  for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  await settle();
  const video = __record.elements.waterMainVideo;
  video.paused = false;
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(14000);
  assert(streamGeneration === 1, "startup timeout: no reconnect may be scheduled before the ~15s startup budget elapses; streamGeneration went 1 -> " + streamGeneration);
  await advance(6000);
  assert(streamGeneration === 2, "startup timeout: the budget timeout must lead to exactly one reconnect; streamGeneration = " + streamGeneration);
  assert(__record.hlsInstances.length === 2, "startup timeout: exactly one reconnect must create exactly one fresh instance; got " + __record.hlsInstances.length);
  assert(window.hls === __record.hlsInstances[1], "the startup-timeout reconnect must attach a fresh instance");
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

# Executed water post-start stall twin (issue #656 regression guard): once
# playback has started (playing), a `waiting` stall with no progress for
# past the 2500 ms grace must still schedule a reconnect — the strict stall
# detection survives the startup-grace change.
WATER_POST_START_STALL_SCENARIO = (
    ";(async () => {\n"
    + SCENARIO_PREAMBLE
    + VIRTUAL_CLOCK
    + """
  __record.timeouts.splice(0).forEach(([fn]) => fn());
  await settle();
  const inst = __record.hlsInstances[0];
  for (const handler of inst.handlers.hlsMediaAttached || []) await handler();
  for (const handler of inst.handlers.hlsManifestParsed || []) await handler();
  await settle();
  const video = __record.elements.waterMainVideo;
  video.paused = false;
  video.currentTime = 1;
  for (const fn of video.__listeners.playing || []) fn();
  await advance(100);
  for (const fn of video.__listeners.waiting || []) fn();
  await advance(2500);
  assert(String(__record.elements.streamStatus.textContent).startsWith("reconnecting"), "post-start stall: a stalled watchdog must schedule a reconnect; status = " + __record.elements.streamStatus.textContent);
  await advance(1000);
  assert(streamGeneration === 2 && __record.hlsInstances.length === 2, "post-start stall: the scheduled reconnect must run; generation=" + streamGeneration + " instances=" + __record.hlsInstances.length);
  console.log("###" + JSON.stringify({ generation: streamGeneration, instances: __record.hlsInstances.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""
)

class WaterStreamContractTests(unittest.TestCase):
    """Executed water operator twins (stream, worker, fallback, cards)."""

    def test_water_uses_one_hls_player_bound_to_main_video(self) -> None:
        evidence = frontend_html.run_inline_scripts(source=WATER_PAGE, scenario=WATER_HLS_SCENARIO)
        self.assertEqual(evidence["sources"], [WATER_HLS_URL])
        self.assertEqual(evidence["instances"], 2)  # initial + post-toggle reconnect

    def test_water_hls_runs_with_worker_disabled(self) -> None:
        evidence = frontend_html.run_inline_scripts(source=WATER_PAGE, scenario=WATER_ENABLEWORKER_SCENARIO)
        self.assertIs(
            evidence["configs"][0].get("enableWorker"), False,
            "water hls.js must run with enableWorker:false (CSP blocks blob: workers)",
        )

    def test_water_startup_grace_survives_hls_live_sync_startup(self) -> None:
        # Issue #656: the 2500 ms waiting watchdog reconnected at ~2.5s while
        # hls.js was still live-syncing its first segments; within the ~15s
        # startup budget no reconnect may happen.
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=WATER_STARTUP_GRACE_SCENARIO, responses=[]
        )
        self.assertEqual(evidence["generation"], 1, "no reconnect within the startup budget")
        self.assertEqual(evidence["instances"], 1, "the boot instance must stay attached")

    def test_water_startup_timeout_reconnects_exactly_once_after_budget(self) -> None:
        # Issue #656: a startup that never reaches playback must still
        # reconnect — exactly once, and only after the ~15s budget elapses.
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=WATER_STARTUP_TIMEOUT_SCENARIO, responses=[]
        )
        self.assertEqual(evidence["generation"], 2, "exactly one reconnect after the startup budget")
        self.assertEqual(evidence["instances"], 2, "the reconnect must create exactly one fresh instance")

    def test_water_post_start_stall_watchdog_still_reconnects(self) -> None:
        # Issue #656 regression guard: after playback started, a `waiting`
        # stall with no progress for past the 2500 ms grace must still
        # schedule a reconnect.
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=WATER_POST_START_STALL_SCENARIO, responses=[]
        )
        self.assertEqual(evidence["generation"], 2, "the post-start stall must reconnect")
        self.assertEqual(evidence["instances"], 2, "the post-start stall reconnect must create a fresh instance")

    def test_water_worker_lifecycle_only_controls_ai_overlay(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=WATER_WORKER_SCENARIO, responses=[WATER_WORKER_RESPONSE]
        )
        self.assertEqual(evidence["workerActive"], [True, False, True])

    def test_water_overlay_snapshot_is_bounded_fallback_only(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE, scenario=WATER_FALLBACK_SCENARIO, responses=[WATER_STATE_FALLBACK_RESPONSE]
        )
        self.assertEqual(evidence["sets"], 1)

    def test_water_crossings_and_recent_passages_use_existing_sources(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=WATER_PAGE,
            scenario=WATER_STATS_SCENARIO,
            responses=[WATER_SUMMARY_RESPONSE, WATER_PASSAGES_RESPONSE],
        )
        self.assertEqual(evidence["cards"], 3)


class RoadStreamContractTests(unittest.TestCase):
    """Executed road operator twins (stream, worker, fallback, cards)."""

    def test_road_uses_one_hls_player_bound_to_main_video(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_HLS_SCENARIO,
            responses=[],
            drain_timeouts=True,
        )
        self.assertEqual(evidence["sources"], [ROAD_HLS_URL])

    def test_road_stays_on_hlsjs_when_chrome_lies_about_native_hls(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=ROAD_CHROME_LIE_SCENARIO, responses=[], drain_timeouts=True
        )
        self.assertIs(
            evidence["configs"][1].get("enableWorker"), False,
            "road hls.js must run with enableWorker:false even when canPlayType lies",
        )

    def test_road_native_src_is_the_no_mse_fallback_only(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=ROAD_NO_MSE_SCENARIO, responses=[], drain_timeouts=True
        )
        self.assertEqual(evidence["nativeSrc"], ROAD_HLS_URL)

    def test_road_startup_grace_survives_hls_live_sync_startup(self) -> None:
        # Issue #656: the 1s polling watchdog killed the instance ~1s after
        # MANIFEST_PARSED while hls.js was still live-syncing its first
        # segments; within the ~15s startup budget no reconnect may happen.
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=ROAD_STARTUP_GRACE_SCENARIO, responses=[], drain_timeouts=True
        )
        self.assertEqual(evidence["generation"], 1, "no reconnect within the startup budget")
        self.assertEqual(evidence["instances"], 1, "the boot instance must stay attached")

    def test_road_startup_timeout_reconnects_exactly_once_after_budget(self) -> None:
        # Issue #656: a startup that never reaches playback must still
        # reconnect — exactly once, and only after the ~15s budget elapses.
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=ROAD_STARTUP_TIMEOUT_SCENARIO, responses=[], drain_timeouts=True
        )
        self.assertEqual(evidence["generation"], 2, "exactly one reconnect after the startup budget")
        self.assertEqual(evidence["instances"], 2, "the reconnect must create exactly one fresh instance")

    def test_road_post_start_stall_watchdog_still_reconnects(self) -> None:
        # Issue #656 regression guard: after playback started, a stall with
        # no progress for past the 2500 ms grace must still schedule a
        # reconnect.
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE, scenario=ROAD_POST_START_STALL_SCENARIO, responses=[], drain_timeouts=True
        )
        self.assertEqual(evidence["generation"], 2, "the post-start stall must reconnect")
        self.assertEqual(evidence["instances"], 2, "the post-start stall reconnect must create a fresh instance")

    def test_road_worker_control_is_road_scoped_and_media_independent(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_WORKER_SCENARIO,
            responses=[ROAD_WORKER_RESPONSE],
            drain_timeouts=True,
        )
        self.assertEqual(evidence["workerActive"], [True, False, True])

    def test_road_worker_control_rejects_foreign_target(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_WORKER_TARGET_SCENARIO,
            responses=[{"match": "/worker/control", "json": {"ok": True, "active": True, "target": "road2"}}],
        )
        self.assertTrue(evidence["guarded"])

    def test_road_overlay_snapshot_is_bounded_fallback_only(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_FALLBACK_SCENARIO,
            # The boot refresh() awaits BOTH state and events; without an
            # events reply the Promise.all rejects and renderState (which
            # applies the fallback overlay) never runs.
            responses=[ROAD_STATE_FALLBACK_RESPONSE, ROAD_EVENTS_RESPONSE],
        )
        self.assertEqual(evidence["sets"], 1)

    def test_road_crossings_and_recent_events_are_independent_cards(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=ROAD_PAGE,
            scenario=ROAD_STATS_SCENARIO,
            responses=[ROAD_STATE_STATS_RESPONSE, ROAD_EVENTS_RESPONSE],
        )
        self.assertEqual(evidence["cards"], 3)


class ObjectsRegistryExecutedTests(unittest.TestCase):
    """Executed objects-registry twins (scope binding + operator writes)."""

    def test_objects_registry_is_domain_scoped_with_operator_writes(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=OBJECTS_PAGE,
            scenario=OBJECTS_SCOPE_SCENARIO,
            responses=[OBJECTS_DETAIL_RESPONSE, OBJECTS_LIST_RESPONSE],
        )
        self.assertEqual(evidence["writes"], 2)

    def test_objects_road_scope_comes_from_the_url(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=OBJECTS_PAGE,
            scenario=OBJECTS_ROAD_SCOPE_SCENARIO,
            responses=[OBJECTS_LIST_RESPONSE],
            location_overrides={"search": "?scope=road"},
        )
        self.assertTrue(evidence["url"].startswith("/sea-speed/api/objects"))

    def test_objects_scope_is_inferred_from_same_origin_road_referrer(self) -> None:
        evidence = frontend_html.run_inline_scripts(
            source=OBJECTS_PAGE,
            scenario=OBJECTS_ROAD_SCOPE_SCENARIO,
            responses=[OBJECTS_LIST_RESPONSE],
            referrer="http://localhost/sea-speed/road/",
        )
        self.assertTrue(evidence["url"].startswith("/sea-speed/api/objects"))


class OverlayWorkerGateTests(unittest.TestCase):
    def test_overlay_render_stops_while_worker_is_inactive(self) -> None:
        # Executed twin (real overlay-canvas.js via the wave-1 node harness):
        # after setWorkerActive(false) the render loop must clear the canvas
        # instead of drawing, and late envelopes must be dropped.
        calls = frontend_node.overlay_render_calls(
            {"isWater": False},
            [frontend_node.envelope(-300, page="road")],
            raw_offset_ms=0.0,
            extra_scenario=(
                "overlay.setWorkerActive(false);"
                "overlay.accept({ id: 'post-disable', camera_id: 'road1', domain: 'road',"
                " generation: 1, frame_no: 99, capture_time_unix_ms: NOW + 250,"
                " frame_width: 1920, frame_height: 1080,"
                " detections: [{ track_id: 6, class_name: 'car', x1_norm: 0.4, y1_norm: 0.4,"
                " x2_norm: 0.5, y2_norm: 0.5 }] });"
                "overlay.renderForVideoFrame();"
            ),
        )
        self.assertEqual(len(calls["strokeRect"]), 1, "a disabled worker must not draw envelopes")
        self.assertGreaterEqual(calls["clearRect"], 2, "a disabled worker must clear the canvas instead")


def unique_ids(text: str) -> list[str]:
    return re.findall(r'\bid="([^"]+)"', text)


class WaterStructuralTests(unittest.TestCase):
    """SS twins: static water markup/CSS contract (no executable surface)."""

    def test_water_operator_matches_069_dashboard_layout(self) -> None:
        for marker in (
            'data-layout="single-row-header"', 'data-layout="water-operator-workspace"',
            'data-layout="primary-camera"', 'data-layout="right-information-rail"',
            'data-layout="crossing-stats"', 'data-layout="recent-passages"',
            'data-layout="under-camera-controls"', 'data-layout="collapsible-state"',
            'data-layout="collapsible-log"', 'id="waterMainVideo"', 'id="liveOverlayCanvas"',
            'id="roiCanvas"', 'id="speedLinesCanvas"', 'id="stateJson"', 'id="debugLog"',
        ):
            self.assertIn(marker, WATER)
        self.assertNotRegex(WATER, r'<(?:section|article|div)\b[^>]*data-layout="clean-live"')
        self.assertNotIn("Чистый поток", WATER)
        self.assertNotIn('id="cxSummary"', WATER)
        self.assertEqual(WATER.count('id="waterMainVideo"'), 1)
        self.assertNotIn('class="stream-probe"', WATER)
        ids = unique_ids(WATER)
        self.assertEqual(len(ids), len(set(ids)), "water page ids must be unique")

    def test_water_header_begins_with_clickable_lighthouse_and_compact_status(self) -> None:
        header = WATER[WATER.index('<header class="operator-header" data-layout="single-row-header">'):WATER.index("</header>")]
        self.assertLess(header.index('class="project-home"'), header.index('class="brand-inline"'))
        self.assertLess(header.index('class="brand-inline"'), header.index('class="header-links"'))
        self.assertIn('data-layout="compact-status"', header)
        self.assertIn('class="session-bar"', header)
        self.assertIn(".operator-header{display:flex;align-items:center;", WATER)

    def test_water_controls_stay_under_camera_and_mobile_order_is_explicit(self) -> None:
        for marker in (
            'id="roiEditBtn"', 'id="roiUndoBtn"', 'id="roiClearBtn"', 'id="roiSaveBtn"',
            'id="speedLineABtn"', 'id="speedLineBBtn"', 'id="speedLinesSaveBtn"',
            'id="cxEditBtn"', 'id="cxUndoBtn"', 'id="cxSaveBtn"', 'id="cxOffBtn"',
            'id="speedFactorInput"', 'id="speedSaveBtn"',
        ):
            self.assertEqual(WATER.count(marker), 1, marker)
        self.assertIn('grid-template-areas:"camera right" "controls right"', WATER)
        self.assertIn('grid-template-areas:"camera" "right" "controls"', WATER)
        self.assertIn("@media(max-width:430px)", WATER)

    def test_water_navigation_links_and_history_cards_are_wired(self) -> None:
        # SS: static anchor wiring. The session/watchdog behavior behind these
        # headers is executed in tests/test_auth_session_frontend_contract.py.
        for marker in (
            'href="/sea-speed/objects/">Реестр объектов</a>',
            'href="/sea-speed/cameras/">Камеры</a>',
            'href="/sea-speed/road/">Дорога</a>',
            'href="/sea-speed/objects/?scope=water&view=crossings">История</a>',
            'href="/sea-speed/objects/?scope=water">Все проходы</a>',
            'id="cxStatsIn"', 'id="cxStatsOut"', 'id="cxStatsTotal"', 'id="cxStatsRows"',
            "Последнее пересечение:",
        ):
            self.assertIn(marker, WATER)
        anchors = re.findall(r"<a\b[^>]*>", WATER)
        self.assertTrue(
            any('href="/outpost.goauthentik.io/sign_out"' in anchor for anchor in anchors),
            "the provider logout link must stay an anchor attribute",
        )
        self.assertNotIn('id="connectBtn"', WATER)
        self.assertNotIn('id="disconnectBtn"', WATER)
        self.assertNotIn('id="video"', WATER)

    def test_water_and_road_navigation_is_reciprocal_without_false_water_active_state(self) -> None:
        water_to_road = '<a class="objects-link road-link" href="/sea-speed/road/">Дорога</a>'
        road_to_water = '<a class="objects-link road-link active" href="/sea-speed/">Вода</a>'
        self.assertIn(water_to_road, WATER)
        self.assertEqual(WATER.count(water_to_road), 1)
        self.assertNotIn('<a class="objects-link road-link active" href="/sea-speed/road/">Дорога</a>', WATER)
        self.assertIn(road_to_water, ROAD)
        self.assertEqual(ROAD.count(road_to_water), 1)
        self.assertIn(".objects-link.active{", ROAD)


class RoadStructuralTests(unittest.TestCase):
    """SS twins: static road markup/CSS contract (no executable surface)."""

    def test_road_page_matches_water_parity_layout_and_controls(self) -> None:
        for marker in (
            'data-layout="single-row-header"', 'data-layout="compact-status"',
            'data-layout="road-operator-workspace"', 'data-layout="primary-camera"',
            'data-layout="right-information-rail"', 'data-layout="crossing-stats"',
            'data-layout="recent-events"', 'data-layout="under-camera-controls"',
            'data-layout="collapsible-state"', 'data-layout="collapsible-log"',
            'id="roadMainVideo"', 'id="overlayImg"', 'id="liveOverlayCanvas"',
            'id="roiCanvas"', 'id="speedLinesCanvas"', 'id="crossingCanvas"',
            'id="stateJson"', 'id="debugLog"', 'id="eventsList"',
        ):
            self.assertIn(marker, ROAD)
        for marker in (
            'id="roiEditBtn"', 'id="roiUndoBtn"', 'id="roiClearBtn"', 'id="roiSaveBtn"',
            'id="speedLineABtn"', 'id="speedLineBBtn"', 'id="speedLinesSaveBtn"',
            'id="cxEditBtn"', 'id="cxUndoBtn"', 'id="cxSaveBtn"', 'id="cxOffBtn"',
            'id="speedFactorInput"', 'id="speedSaveBtn"',
        ):
            self.assertEqual(ROAD.count(marker), 1, marker)
        self.assertNotIn('data-layout="clean-live"', ROAD)
        self.assertNotIn("Чистый поток", ROAD)
        self.assertNotIn("cleanPreviewVideo", ROAD)
        self.assertEqual(ROAD.count('id="roadMainVideo"'), 1)
        self.assertNotIn('id="video"', ROAD)
        self.assertIn('grid-template-areas:"camera right" "controls right"', ROAD)
        self.assertIn('grid-template-areas:"camera" "right" "controls"', ROAD)
        ids = unique_ids(ROAD)
        self.assertEqual(len(ids), len(set(ids)), "road page ids must be unique")

    def test_road_header_begins_with_lighthouse_and_compact_status(self) -> None:
        header = ROAD[ROAD.index('<header class="operator-header" data-layout="single-row-header">'):ROAD.index("</header>")]
        self.assertLess(header.index('class="project-home"'), header.index('class="brand-inline"'))
        self.assertLess(header.index('class="brand-inline"'), header.index('class="header-links"'))
        self.assertIn('data-layout="compact-status"', header)
        self.assertIn('class="session-bar"', header)
        self.assertIn(".operator-header{display:flex;align-items:center;", ROAD)

    def test_road_page_stays_on_protected_generic_analytics_api(self) -> None:
        # SS: the resolved endpoint wiring is executed in
        # RoadStreamContractTests; this scan keeps credential-bearing rtsp
        # URLs and the retired clean-live wiring out of the page text.
        self.assertNotRegex(ROAD, r"rtsp://[^\s\"']+:")
        self.assertNotIn('data-layout="clean-live"', ROAD)
        self.assertNotIn("Чистый поток", ROAD)
        for marker in (
            'href="/sea-speed/objects/?scope=road&view=crossings">История</a>',
            'href="/sea-speed/objects/?scope=road">Все события</a>',
            'href="/sea-speed/objects/">Реестр объектов</a>',
            'id="cxStatsIn"', 'id="cxStatsOut"', 'id="cxStatsTotal"', 'id="cxStatsRows"',
            "Последнее пересечение:",
        ):
            self.assertIn(marker, ROAD)


class CrossPageStructuralTests(unittest.TestCase):
    """SS twins: responsive baseline shared by the protected pages."""

    def test_all_pages_keep_mobile_baseline(self) -> None:
        for page, name in ((OBJECTS, "objects"), (CAMERAS, "cameras"), (ROAD, "road")):
            self.assertIn("@media(max-width:760px)", page, name)
            self.assertIn("viewport-fit=cover", page, name)
        self.assertIn("@media(max-width:700px)", WATER)
        self.assertIn("@media(max-width:430px)", WATER)
        self.assertIn("viewport-fit=cover", WATER)
        self.assertIn('href="/sea-speed/"', ROOT_SOURCE)


def strip_comments(text: str) -> str:
    """Comment-stripped page source for SS scans: HTML <!-- -->, JS /* */ and
    JS // comments are removed so a commented-out literal can never satisfy a
    structural pin. The (?<!:) guard keeps URL scheme separators (https://)
    intact; over-stripping is harmless here because the pinned literals carry
    no comment syntax themselves."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(?<!:)//.*$", "", text)


class StreamRetryLadderStructuralTests(unittest.TestCase):
    """SS twin: the stream retry ladder literal is live code on BOTH operator
    pages. The executed stream twins prove only the first 1000 ms rung (the
    full 8-second ladder would make them wall-clock slow) and the constant has
    no executable surface under the record-but-never-fire timers, so the full
    literal is pinned on comment-stripped source: commenting the ladder out or
    shortening it must fail the scan on both pages."""

    def test_water_and_road_pages_carry_the_full_stream_retry_ladder(self) -> None:
        # Issue #626: the ladder literal moved from the inline script blocks
        # into the shipped external .js files, so the scanned live-code text
        # is the page HTML plus the page's connected local external scripts.
        for page_path, name in ((WATER_PAGE, "water"), (ROAD_PAGE, "road")):
            html = page_path.read_text(encoding="utf-8-sig")
            self.assertIn(
                "STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]",
                strip_comments(html + "".join(frontend_html.external_local_scripts(page_path, html))),
                f"{name} page must keep the full stream retry ladder as live code",
            )


def script_tags(text: str) -> list[dict[str, str]]:
    """Attribute maps for every opening <script ...> tag (SS extraction:
    markup has no AST to execute, so the CDN supply-chain contract is pinned
    through structured attribute lookups on comment-stripped source — a
    commented-out tag can never satisfy it)."""
    return [
        dict(re.findall(r'\b([a-zA-Z-]+)="([^"]*)"', tag))
        for tag in re.findall(r"<script\b[^>]*>", text)
    ]


class HlsScriptPinTests(unittest.TestCase):
    """SS twin: the hls.js supply-chain contract on all three operator pages
    (issue #575, audit #534 P2-07). The executed stream twins above prove the
    player wiring; this pin freezes the CDN artifact itself — every page must
    load the exact production-proven 1.5.7 hls.min.js with its sha384
    Subresource Integrity and a CORS-anonymous request, and the floating
    @latest tag must stay gone."""

    def test_each_operator_page_loads_the_pinned_hls_artifact_with_sri(self) -> None:
        for page, name in ((WATER, "water"), (CAMERAS, "cameras"), (ROAD, "road")):
            with self.subTest(page=name):
                hls_tags = [
                    attrs for attrs in script_tags(strip_comments(page))
                    if "hls.js" in attrs.get("src", "")
                ]
                self.assertEqual(
                    len(hls_tags), 1,
                    f"the {name} page must load hls.js exactly once; got {len(hls_tags)}",
                )
                attrs = hls_tags[0]
                self.assertEqual(
                    attrs.get("src"), HLS_PINNED_SRC,
                    f"the {name} page must pin the exact hls.js 1.5.7 artifact",
                )
                self.assertEqual(
                    attrs.get("integrity"), HLS_SRI_INTEGRITY,
                    f"the {name} page hls.js tag must carry the exact sha384 integrity",
                )
                self.assertEqual(
                    attrs.get("crossorigin"), "anonymous",
                    f"the {name} page hls.js tag must request CORS-anonymous for SRI",
                )

    def test_no_page_loads_hls_from_a_moving_latest_tag(self) -> None:
        for page, name in ((WATER, "water"), (CAMERAS, "cameras"), (ROAD, "road")):
            with self.subTest(page=name):
                for attrs in script_tags(strip_comments(page)):
                    if "hls.js" in attrs.get("src", ""):
                        self.assertNotIn(
                            "@latest", attrs["src"],
                            f"the {name} page must never load hls.js from the floating @latest tag",
                        )


    def test_every_operator_hls_config_disables_the_worker(self) -> None:
        """The site CSP has no worker-src, so hls.js blob: workers are blocked
        at the edge; every shipped new Hls() config must carry enableWorker:false
        (prod incident 2026-11-12: the road page black-screened in Chrome)."""
        for page, name in ((WATER_PAGE, "water"), (CAMERAS_PAGE, "cameras"), (ROAD_PAGE, "road")):
            with self.subTest(page=name):
                self.assertIn(
                    "new Hls({enableWorker:false,",
                    frontend_html.page_live_source(page),
                    f"the {name} page hls.js config must disable the worker (CSP blocks blob: workers)",
                )


class StreamReconnectSemanticsStructuralTests(unittest.TestCase):
    """SS twin: the water page's stream reconnect retries forever with a
    capped delay (issue #633). The executed stream twins prove only the first
    1000 ms rung and never reach the exhaustion boundary, so the reconnect
    semantics are pinned on comment-stripped live code: the delay index must
    be capped at the last ladder rung, and the terminal exhaustion branch
    (which used to give up after the ladder ran out) must stay gone. The road
    page's symmetric forever-retry cap is pinned too."""

    def _live_source(self, page_path: Path, html: str) -> str:
        return strip_comments(
            page_path.read_text(encoding="utf-8-sig")
            + "".join(frontend_html.external_local_scripts(page_path, html))
        )

    def test_water_reconnect_caps_the_delay_index_at_the_last_ladder_rung(self) -> None:
        live = self._live_source(WATER_PAGE, WATER)
        self.assertIn(
            "STREAM_RETRY_DELAYS_MS[Math.min(reconnectAttempt,STREAM_RETRY_DELAYS_MS.length-1)]",
            live,
            "water scheduleStreamReconnect must cap the delay index at the last ladder rung",
        )

    def test_water_reconnect_has_no_terminal_exhaustion(self) -> None:
        live = self._live_source(WATER_PAGE, WATER)
        self.assertNotIn(
            "HLS reconnect exhausted", live,
            "water scheduleStreamReconnect must not give up after the ladder is exhausted",
        )
        self.assertNotIn(
            "reconnectAttempt>=STREAM_RETRY_DELAYS_MS.length", live,
            "water scheduleStreamReconnect must not treat ladder exhaustion as terminal",
        )

    def test_road_reconnect_keeps_the_capped_forever_retry(self) -> None:
        live = self._live_source(ROAD_PAGE, ROAD)
        self.assertIn(
            "STREAM_RETRY_DELAYS_MS[Math.min(reconnectAttempt,STREAM_RETRY_DELAYS_MS.length-1)]",
            live,
            "road scheduleReconnect must keep the capped forever-retry delay",
        )


if __name__ == "__main__":
    unittest.main()
