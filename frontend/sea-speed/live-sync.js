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

// Bracket mediaMs inside the live buffer after lag compensation.
// Returns {lo, hi, t} for interpolation or null.
// Both envelopes of a valid pair must share one generation and the gap
// must be within maxGapMs.
function ssBracketForMedia(mediaMs, opts) {
  const buf = opts.liveBuffer;
  const capture = opts.getCaptureMs;
  const comp = mediaMs - opts.lagCompensationMs;
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

window.SeaSpeedLiveSync = {
  median: ssMedian,
  clampLag: ssClampLag,
  bracketForMedia: ssBracketForMedia,
  closestEarlierEnvelope: ssClosestEarlierEnvelope
};
