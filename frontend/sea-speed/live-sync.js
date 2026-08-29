// Unified live-sync module for Road and Water overlays.
// Included by frontend/sea-speed/index.html and
// frontend/sea-speed/road/index.html BEFORE each page's main script.
// Per-page config (video element id, HLS globals, poll URL, buffer
// variable identity) remains in each HTML file; shared sync math lives
// here and receives page state explicitly so the module stays pure.

// Median of a numeric array.
function ssMedian(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) return 0;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

// Clamp lag compensation to 0..1200ms (Road previously clamped to 600ms).
function ssClampLag(medianLagMs) {
  return Math.max(0, Math.min(1200, medianLagMs));
}

function ssFiniteCaptureValues(opts) {
  const buf = opts.liveBuffer || [];
  const capture = opts.getCaptureMs;
  const values = [];
  for (let i = 0; i < buf.length; i++) {
    const value = Number(capture(buf[i]));
    if (Number.isFinite(value)) values.push(value);
  }
  return values;
}

function ssIsWaterBuffer(opts) {
  const buf = opts.liveBuffer || [];
  const latest = buf.length ? buf[buf.length - 1] : null;
  return Boolean(latest && latest.camera_id === "cam1" && latest.domain !== "road");
}

// Water and browser HLS do not share a trustworthy absolute capture clock:
// Water envelopes use worker_receive_utc while the player may expose HLS
// program date time (or no absolute media time at all).  What HLS does expose
// reliably is the current distance from the live edge.  Project that relative
// latency onto the Worker capture timeline instead of comparing unrelated
// absolute clocks.
function ssWaterPlaybackLatencyMs() {
  if (typeof window === "undefined") return null;
  try {
    const hls = window.waterHls;
    const hlsLatencySeconds = hls ? Number(hls.latency) : NaN;
    if (Number.isFinite(hlsLatencySeconds) && hlsLatencySeconds >= 0 && hlsLatencySeconds <= 30) {
      return hlsLatencySeconds * 1000;
    }
  } catch (_) {}
  try {
    if (typeof document === "undefined") return null;
    const video = document.getElementById("waterMainVideo");
    if (!video || !video.seekable || !video.seekable.length) return null;
    const edge = Number(video.seekable.end(video.seekable.length - 1));
    const current = Number(video.currentTime);
    const latencySeconds = edge - current;
    if (Number.isFinite(latencySeconds) && latencySeconds >= 0 && latencySeconds <= 30) {
      return latencySeconds * 1000;
    }
  } catch (_) {}
  return null;
}

function ssWaterTargetCaptureMs(opts) {
  const latencyMs = ssWaterPlaybackLatencyMs();
  if (!Number.isFinite(latencyMs)) return null;
  const captures = ssFiniteCaptureValues(opts);
  if (!captures.length) return null;
  return Math.max(...captures) - latencyMs;
}

function ssResolvedTargetMs(mediaMs, opts) {
  if (ssIsWaterBuffer(opts)) {
    const relativeTarget = ssWaterTargetCaptureMs(opts);
    if (Number.isFinite(relativeTarget)) return relativeTarget;
  }
  const absoluteMediaMs = Number(mediaMs);
  if (!Number.isFinite(absoluteMediaMs)) return null;
  return absoluteMediaMs - Number(opts.lagCompensationMs || 0);
}

// The Water page's legacy getMediaMs() treats an absent getStartDate() as
// unresolved and returns before the selector can use live-edge latency.  Keep
// the native value when available, but provide an invalid-Date sentinel on the
// Water video element so the selector is reached and can resolve the relative
// timeline.  If latency is unavailable the selector still fails closed.
function ssInstallWaterMediaTimeProbe() {
  if (typeof document === "undefined") return;
  const video = document.getElementById("waterMainVideo");
  if (!video || video.__seaSpeedMediaTimeProbeInstalled) return;
  const nativeGetStartDate = typeof video.getStartDate === "function" ? video.getStartDate.bind(video) : null;
  video.getStartDate = function () {
    if (nativeGetStartDate) {
      try {
        const value = nativeGetStartDate();
        if (value) return value;
      } catch (_) {}
    }
    return new Date(NaN);
  };
  video.__seaSpeedMediaTimeProbeInstalled = true;
}

// Bracket the resolved target inside the live buffer.
// Road preserves its existing absolute media-time behavior. Water first maps
// HLS live-edge latency onto the Worker capture timeline. Both envelopes of a
// valid pair must share one generation and the gap must be within maxGapMs.
function ssBracketForMedia(mediaMs, opts) {
  const buf = opts.liveBuffer;
  const capture = opts.getCaptureMs;
  const comp = ssResolvedTargetMs(mediaMs, opts);
  if (!Number.isFinite(comp)) return null;
  let lo = null, hi = null;
  for (let i = 0; i < buf.length; i++) {
    const t = capture(buf[i]);
    if (t == null) continue;
    if (t <= comp) lo = buf[i];
    else { hi = buf[i]; break; }
  }
  if (!lo || !hi) return null;
  if (lo.generation !== hi.generation) return null;
  const gap = Number(capture(hi)) - Number(capture(lo));
  if (!Number.isFinite(gap) || gap <= 0 || gap > (opts.maxGapMs || 500)) return null;
  const t = (comp - Number(capture(lo))) / gap;
  if (t < 0 || t > 1) return null;
  return { lo, hi, t };
}

// Latest envelope captured at or before compMs, or null.
function ssClosestEarlierEnvelope(compMs, opts) {
  const buf = opts.liveBuffer;
  const capture = opts.getCaptureMs;
  let lo = null;
  for (let i = 0; i < buf.length; i++) {
    const t = capture(buf[i]);
    if (t == null) continue;
    if (t <= compMs) lo = buf[i];
    else break;
  }
  return lo;
}

ssInstallWaterMediaTimeProbe();

window.SeaSpeedLiveSync = {
  median: ssMedian,
  clampLag: ssClampLag,
  bracketForMedia: ssBracketForMedia,
  closestEarlierEnvelope: ssClosestEarlierEnvelope,
  waterPlaybackLatencyMs: ssWaterPlaybackLatencyMs,
  waterTargetCaptureMs: ssWaterTargetCaptureMs,
  resolvedTargetMs: ssResolvedTargetMs
};
