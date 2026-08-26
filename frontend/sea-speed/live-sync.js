// Unified live-sync module for Road and Water overlays
// This file is included by both frontend/sea-speed/index.html and
// frontend/sea-speed/road/index.html. Per-page config (video element id,
// HLS globals, poll URL) remains in each HTML file.

// Shared utility: median of numeric array
function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const n = s.length;
  if (n === 0) return 0;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

// Shared bracket-for-media logic (identical in Road and Water)
function bracketForMedia(mediaMs) {
  if (liveBuffer.length === 0) return null;
  const comp = mediaMs - lagCompensationMs;
  let lo = null, hi = null;
  for (let i = 0; i < liveBuffer.length; i++) {
    const t = liveBuffer[i].capture_time_unix_ms;
    if (t == null) continue;
    if (t <= comp) lo = liveBuffer[i];
    else { hi = liveBuffer[i]; break; }
  }
  if (!lo || !hi) return null;
  if (lo.generation !== hi.generation) return null;
  const gap = liveBuffer[hi === liveBuffer ? liveBuffer.length - 1 : hi].capture_time_unix_ms - liveBuffer[lo === liveBuffer ? 0 : lo].capture_time_unix_ms;
  // Note: gap calculation depends on exact buffer implementation;
  // per-page code provides the exact gap check.
  if (isNaN(gap) || gap <= 0 || gap > 500) return null;
  const t = (comp - liveBuffer[lo].capture_time_unix_ms) / gap;
  if (t < 0 || t > 1) return null;
  return { lo, hi, t };
}

// Clamp lag compensation to 0..1200ms (shared; Road previously used 600ms)
function clampLag(medianLagMs) {
  return Math.max(0, Math.min(1200, medianLagMs));
}

// Export for per-page use
window.SeaSpeedLiveSync = {
  median,
  bracketForMedia,
  clampLag
};