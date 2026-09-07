// Shared live-overlay contour renderer for Water (cam1) and Road (road1).
// Replaces the duplicated inline live-canvas IIFEs that previously lived in
// frontend/sea-speed/index.html and frontend/sea-speed/road/index.html.
//
// Both pages call SeaSpeedOverlayCanvas.init({...}) once and wire the returned
// instance into their worker-control handler via setWorkerActive(active).
//
// Correctness notes vs the old duplicated code:
//  - contentRect centers vertically with (r.height-ch)/2 (the Water copy had a
//    "/h" typo that pushed contours to the top edge).
//  - renderForVideoFrame has a robust fallback: when the HLS stream exposes no
//    wall-clock (no #EXT-X-PROGRAM-DATE-TIME, so getMediaMs() is null), it draws
//    the most recent buffered envelope instead of clearing the canvas every
//    frame. Contours therefore stay visible regardless of stream metadata.
(function () {
  "use strict";

  var LIVE_BUFFER_MS = 15000;
  var LIVE_NEAR_MAX_AGE_MS = 2000;
  var MAX_GAP_MS = 500;

  function init(opts) {
    var cameraId = opts.cameraId;
    var video = document.getElementById(opts.videoId);
    var canvas = document.getElementById(opts.canvasId);
    var wrap = document.getElementById(opts.wrapId);
    var liveUrl = opts.liveUrl;
    var livePollUrl = opts.livePollUrl;
    var isWater = !!opts.isWater;

    var liveGen = null;
    var lastFrameNo = -1;
    var polling = false;
    var liveBuffer = [];
    var lagSamples = [];
    var lagCompensationMs = 0;
    var minLiveCaptureMs = 0;
    var workerServiceActive = null;

    function sourceSize() {
      var w = Number(window.__frameW || 1920);
      var h = Number(window.__frameH || 1080);
      return [w, h];
    }

    function contentRect(env) {
      var dims = env
        ? [Number(env.frame_width) || 1920, Number(env.frame_height) || 1080]
        : sourceSize();
      var w = dims[0];
      var h = dims[1];
      var r = wrap
        ? wrap.getBoundingClientRect()
        : canvas
        ? canvas.getBoundingClientRect()
        : { width: 1920, height: 1080 };
      var scale = Math.min(r.width / w, r.height / h);
      var cw = w * scale;
      var ch = h * scale;
      return {
        x: (r.width - cw) / 2,
        y: (r.height - ch) / 2,
        w: cw,
        h: ch,
        rw: r.width,
        rh: r.height
      };
    }

    function canvasContext() {
      if (!canvas) return null;
      var r = canvas.getBoundingClientRect();
      var d = window.devicePixelRatio || 1;
      var w = Math.max(1, Math.round(r.width * d));
      var h = Math.max(1, Math.round(r.height * d));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        canvas.style.width = r.width + "px";
        canvas.style.height = r.height + "px";
      }
      var c = canvas.getContext("2d");
      c.setTransform(d, 0, 0, d, 0, 0);
      return { c: c, r: r };
    }

    function clearLive() {
      var ctx = canvasContext();
      if (ctx) ctx.c.clearRect(0, 0, ctx.r.width, ctx.r.height);
    }

    function drawLive(env) {
      if (!env || !Array.isArray(env.detections)) return;
      var ctx = canvasContext();
      if (!ctx) return;
      var c = ctx.c;
      var r = ctx.r;
      var cr = contentRect(env);
      c.clearRect(0, 0, r.width, r.height);
      c.font = "600 10px Inter,system-ui,sans-serif";
      env.detections.forEach(function (d) {
        var x1 = Number(d.x1_norm || 0) * cr.w + cr.x;
        var y1 = Number(d.y1_norm || 0) * cr.h + cr.y;
        var x2 = Number(d.x2_norm || 0) * cr.w + cr.x;
        var y2 = Number(d.y2_norm || 0) * cr.h + cr.y;
        var w = x2 - x1;
        var h = y2 - y1;
        if (w <= 0 || h <= 0) return;
        c.strokeStyle = "#5eead4";
        c.lineWidth = 2;
        c.strokeRect(x1, y1, w, h);
        var label =
          (d.class_name || (isWater ? "vessel" : "obj")) +
          " #" +
          (d.track_id != null ? d.track_id : "-") +
          (d.passage_id ? " " + d.passage_id : "") +
          (d.speed_kmh != null ? " " + Number(d.speed_kmh).toFixed(1) + "km/h" : "");
        var tw = c.measureText(label).width + 8;
        c.fillStyle = "#010d15cc";
        c.fillRect(x1, Math.max(0, y1 - 14), tw, 14);
        c.fillStyle = "#edfaff";
        c.fillText(label, x1 + 4, y1 - 4);
      });
    }

    function interpolate(a, b, t) {
      if (!a || a.generation !== b.generation) return b;
      var prior = new Map(
        (a.detections || [])
          .filter(function (d) {
            return d.track_id != null;
          })
          .map(function (d) {
            return [String(d.track_id), d];
          })
      );
      return Object.assign({}, b, {
        detections: (b.detections || []).map(function (d) {
          if (d.track_id == null) return d;
          var p = prior.get(String(d.track_id));
          if (!p) return d;
          var out = Object.assign({}, d);
          ["x1_norm", "y1_norm", "x2_norm", "y2_norm"].forEach(function (k) {
            out[k] = Number(p[k] || 0) + (Number(d[k] || 0) - Number(p[k] || 0)) * t;
          });
          return out;
        })
      });
    }

    function getCaptureMs(env) {
      var v = env.capture_time_unix_ms;
      if (Number.isFinite(v)) return Number(v);
      if (Number.isFinite(env.observed_mono)) return Math.round(Number(env.observed_mono) * 1000);
      return null;
    }

    function pruneBuffer(nowMs) {
      var cutoff = nowMs - LIVE_BUFFER_MS;
      liveBuffer = liveBuffer.filter(function (e) {
        var t = getCaptureMs(e);
        return t != null && t >= cutoff;
      });
      if (liveBuffer.length > 120) liveBuffer = liveBuffer.slice(-120);
    }

    function accept(env) {
      if (workerServiceActive === false) {
        clearLive();
        return;
      }
      if (!env || env.camera_id !== cameraId) return;
      var captureMs = getCaptureMs(env);
      if (minLiveCaptureMs && captureMs != null && captureMs < minLiveCaptureMs) return;
      var gen = Number(env.generation);
      var frame = Number(env.frame_no);
      if (!Number.isFinite(gen) || !Number.isFinite(frame)) return;
      if (liveGen !== null && gen < liveGen) return;
      if (liveGen === null || gen > liveGen) {
        liveBuffer = [];
        lastFrameNo = -1;
        liveGen = gen;
        lagSamples = [];
        lagCompensationMs = 0;
      }
      if (frame <= lastFrameNo) return;
      lastFrameNo = frame;
      pruneBuffer(Date.now());
      liveBuffer.push(env);
      liveBuffer.sort(function (a, b) {
        return (getCaptureMs(a) || 0) - (getCaptureMs(b) || 0);
      });
      if (liveBuffer.length > 120) liveBuffer = liveBuffer.slice(-120);
    }

    function getMediaMs() {
      try {
        var hls = window.waterHls || window.hls;
        if (hls && hls.media === video && hls.playingDate) {
          return hls.playingDate.getTime();
        }
        if (video && typeof video.getStartDate === "function") {
          var d = video.getStartDate();
          if (d) return d.getTime() + video.currentTime * 1000;
        }
      } catch (_) {}
      return null;
    }

    function updateLag(mediaMs) {
      if (liveBuffer.length < 5 || mediaMs == null) return;
      var latest = Math.max.apply(
        null,
        liveBuffer.map(function (e) {
          return getCaptureMs(e) || 0;
        })
      );
      if (!latest) return;
      var delta = mediaMs - latest;
      if (!Number.isFinite(delta) || delta < -200 || delta > 6000) return;
      lagSamples.push(delta);
      if (lagSamples.length > 30) lagSamples.shift();
      if (lagSamples.length >= 20) {
        lagCompensationMs = SeaSpeedLiveSync.clampLag(SeaSpeedLiveSync.median(lagSamples));
      }
    }

    function closestEarlierEnvelope(compMs) {
      return SeaSpeedLiveSync.closestEarlierEnvelope(compMs, {
        liveBuffer: liveBuffer,
        getCaptureMs: getCaptureMs
      });
    }

    function bracketForMedia(mediaMs) {
      return SeaSpeedLiveSync.bracketForMedia(mediaMs, {
        liveBuffer: liveBuffer,
        getCaptureMs: getCaptureMs,
        lagCompensationMs: lagCompensationMs,
        maxGapMs: MAX_GAP_MS
      });
    }

    function renderForVideoFrame() {
      if (workerServiceActive === false) {
        clearLive();
        return;
      }
      var raw = getMediaMs();
      if (raw == null) {
        // Robust fallback: no HLS wall-clock (stream lacks PROGRAM-DATE-TIME).
        // Draw the most recent envelope so contours stay visible.
        var latest = liveBuffer.length ? liveBuffer[liveBuffer.length - 1] : null;
        if (latest) drawLive(latest);
        else clearLive();
        return;
      }
      updateLag(raw);
      var mediaMs = raw - lagCompensationMs;
      var br = bracketForMedia(raw);
      if (!br) {
        var near = closestEarlierEnvelope(mediaMs);
        var nearCapture = near ? getCaptureMs(near) : null;
        if (
          near &&
          nearCapture != null &&
          nearCapture >= mediaMs - LIVE_NEAR_MAX_AGE_MS &&
          nearCapture <= mediaMs
        ) {
          drawLive(near);
        } else {
          clearLive();
        }
        return;
      }
      drawLive(interpolate(br.lo, br.hi, br.t));
    }

    var _rvcbActive = false;
    function scheduleRender() {
      if (_rvcbActive) return;
      _rvcbActive = true;
      var cb = function () {
        _rvcbActive = false;
        renderForVideoFrame();
        var v = video;
        if (v && v.readyState >= 2 && !v.paused) {
          if (typeof v.requestVideoFrameCallback === "function") v.requestVideoFrameCallback(cb);
          else requestAnimationFrame(scheduleRender);
        } else {
          requestAnimationFrame(scheduleRender);
        }
      };
      if (video && typeof video.requestVideoFrameCallback === "function") {
        video.requestVideoFrameCallback(cb);
      } else {
        requestAnimationFrame(cb);
      }
    }

    (function startLoop() {
      scheduleRender();
      setInterval(function () {
        pruneBuffer(Date.now());
        renderForVideoFrame();
      }, 1000);
    })();

    setInterval(function () {
      if (workerServiceActive === false) {
        clearLive();
        return;
      }
      if (polling) return;
      var raw = getMediaMs();
      var need = liveBuffer.length === 0 || raw == null || !bracketForMedia(raw);
      if (!need) return;
      polling = true;
      var controller = new AbortController();
      var timer = setTimeout(function () {
        controller.abort();
      }, 1500);
      fetch(livePollUrl, {
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (d) {
          var env = (d.items || [])[d.items.length - 1];
          if (env) accept(env);
        })
        .catch(function () {})
        .then(function () {
          clearTimeout(timer);
          polling = false;
        });
    }, 500);

    window.addEventListener("resize", function () {
      renderForVideoFrame();
    });

    try {
      var es = new EventSource(liveUrl);
      es.onmessage = function (e) {
        try {
          accept(JSON.parse(e.data));
        } catch (_) {}
      };
      es.onerror = function () {};
    } catch (_) {}

    return {
      accept: accept,
      drawLive: drawLive,
      renderForVideoFrame: renderForVideoFrame,
      clear: clearLive,
      setWorkerActive: function (v) {
        workerServiceActive = v;
        if (v === false) {
          minLiveCaptureMs = Date.now();
          liveBuffer = [];
          liveGen = null;
          lastFrameNo = -1;
          lagSamples = [];
          lagCompensationMs = 0;
          clearLive();
        }
      },
      reset: function () {
        minLiveCaptureMs = Date.now();
        liveBuffer = [];
        liveGen = null;
        lastFrameNo = -1;
        lagSamples = [];
        lagCompensationMs = 0;
        clearLive();
      }
    };
  }

  window.SeaSpeedOverlayCanvas = { init: init };
})();
