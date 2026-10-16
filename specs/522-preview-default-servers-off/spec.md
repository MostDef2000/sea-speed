# Spec: #522 — preview relay: explicitly disable unused mediamtx default servers

- Issue: #522

Linked issue context: ИБ, P3, child of #402; :8892 attribution closed by
#454 AC-3.

## Product outcome

The camera preview relay's mediamtx process no longer exposes any listener
beyond the configured RTSP endpoint (`10.123.239.102:8555` on the ZeroTier
address). Today the renderer emits `rtmp/hls/webrtc/srt: false` but leaves
`api`, `metrics`, `pprof`, `playback` and `moq` to the installed binary's
version defaults — which is how the unconfigured built-in HTTP server
appeared on `*:8892` (all interfaces, ufw inactive). After this change the
rendered config pins every unused server off, matching the canonical disable
vocabulary already proven on the cam1 relay
(`MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: "Unused servers (`api`, `metrics`,
`pprof`, `playback`, RTMP, WebRTC, SRT and MoQ) are disabled"), and the
preview profile stops relying on version-specific defaults entirely.

## User scenarios

- Operator runs `camera-preview-relay.sh prepare` for a new/updated
  inventory: the rendered `mediamtx.yml` contains the five explicit disable
  toggles next to the existing `rtmp: false / hls: false / webrtc: false /
  srt: false`; digest outputs change accordingly; no other renderer behavior
  changes.
- Operator runs `activate`: the preview service restarts with the new config;
  the on-box `ss` probe no longer shows :8892 on the preview process; the
  RTSP preview bind stays alive.
- Road-worker analytics keep consuming previews over RTSP as before; no
  in-repo consumer of the disabled servers exists (catalog consumers are
  RTSP-only).

## Scope

- `scripts/operations/mediamtx_path_config.py`: `ubuntu-preview-relay`
  render skeleton gains `api: false`, `metrics: false`, `pprof: false`,
  `playback: false`, `moq: false` (nothing else; RTSP block untouched).
- `tests/test_mediamtx_preview_relay.py`: golden byte-config, legacy-parity
  oracle, re-render byte-identity, and the api-less negative pin are updated
  to the new skeleton; a positive per-toggle pin asserts all five explicit
  `false` values.
- `tests/test_camera_preview_gallery.py`: renderer-literal pins inspected —
  none pin the server skeleton bytes, so the file is unchanged.
- `docs/operations/CAMERA_PREVIEW_RELAY.md`: render contract updated
  (disable vocabulary) and the `:8892` disposition note updated.
- On-box application happens AFTER merge via the standing lane-A worker
  deploy (renderer lives in the `/opt/sea-speed-worker` install root) and
  ONE lane-B sysadmin prepare→activate tx (out of repo scope, audited on
  #522).

Out of scope: binding-scope narrowing of a kept server (rejected: zero
observed peers, in-repo consumers are RTSP-only); `verify-preview-auth`
changes (it verifies auth rules, not server toggles); any change to the
cam1 relay or other renderer profiles; relay runbook open questions 3-4;
ufw enablement on the box (separate decision surface).

## Requirements

- R-1: the preview renderer must emit explicit `api: false`,
  `metrics: false`, `pprof: false`, `playback: false`, `moq: false`.
- R-2: the renderer must not rely on any mediamtx version default for
  server enablement (all optional servers explicitly pinned).
- R-3: golden byte-config, legacy-parity and byte-identity tests stay
  synchronized with the renderer (no drift between spec pins and tests).
- R-4: preview RTSP behavior is unchanged: `rtsp: true`,
  `rtspTransports: [tcp]`, `rtspAddress`, path block byte-identical.
- R-5: `verify-preview-auth` and the auth rule block remain byte-identical
  (the toggles are top-level server switches, not auth entries).

## Acceptance criteria

- AC-001: renderer emits the five explicit disable toggles; golden and
  parity tests updated and green.
- AC-002: full battery green with accounted deltas; validate_sdd green;
  validate_repo green.
- AC-003: PR Change Contract exact-match; CI 8/8 on exact head.
- AC-004: on-box after prepare→activate: :8892 absent from the preview
  process listeners, :8555 alive, service active, digests recorded
  (runtime-manual, sysadmin session).

## Runtime feedback

- Box binary version is not recorded in the repo (`specs/406`): step 0 of
  the on-box tx records `mediamtx --version` + current digests before any
  mutation. Strict yml parsing of an unknown key (older binary) fails
  closed in `activate` (is-active gate + listener probe); rollback is the
  previous digest-bound candidates/activate.
- activate performs a scoped restart of the preview service only
  (`CAM1_RELAY_CHANGED=NO`, `AI_WORKER_CHANGED=NO`); short preview outage
  for road analytics is expected and scheduled.

## NFR assessment

- NFR-001 | Area: security | Target: rendered preview config contains zero version-default-dependent server toggles; all five canonical disable toggles present byte-explicit | Validation: positive per-toggle unit pin + golden byte-config test | Evidence: tests/test_mediamtx_preview_relay.py updated pins, CI on exact head | Status: PASS
- NFR-002 | Area: compatibility | Target: renderer output remains valid for the deployed mediamtx line (strict parser); activate canary fails closed on any unknown-key rejection | Validation: on-box prepare (fail-closed schema render) + activate is-active/listener gates precede any state commit | Evidence: lane-B tx evidence on #522 after activate | Status: CONCERNS
- NFR-003 | Area: maintainability | Target: preview and cam1 relay profiles share one canonical disable vocabulary, documented | Validation: runbook render-contract section updated in the same PR | Evidence: docs/operations/CAMERA_PREVIEW_RELAY.md diff | Status: PASS
