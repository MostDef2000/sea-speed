# Research: Camera Live Pipeline

- Specification: specs/001-camera-live-pipeline/spec.md
- Issue: #87
- Status: Accepted findings

## What was tested

The new camera was reachable by the Ubuntu host and the VPS could reach the Ubuntu private relay. The upstream media advanced, but the public browser experience remained black/buffering through several iterations.

A VPS compatibility path was then proven separately: the camera stream was converted to H.264 and exposed as fMP4 HLS. Local checks showed advancing frames and browser-compatible media characteristics.

## Misleading symptoms

The frontend initially reported play/recovery errors. Hls.js-first playback and bounded recovery were reasonable robustness changes, but they did not solve the product because the browser was still receiving the wrong media description.

## Decisive evidence

The browser eventually reported `manifestIncompatibleCodecsError` with `hvc1.1.6.L120.0`. This showed the public path was still advertising HEVC even though the compatible H.264 fallback existed and was healthy.

## Accepted conclusion

The simplest reliable design is to route Camera 1 directly to the proven H.264 compatibility output for browser delivery. VPS MediaMTX is not required in this path.

## General lesson

For future cameras, separate three concerns:

1. acquire the camera privately;
2. normalize media for the browser when needed;
3. expose a stable public camera identity.

Do not make the browser or frontend responsible for compensating for an incompatible camera codec.
