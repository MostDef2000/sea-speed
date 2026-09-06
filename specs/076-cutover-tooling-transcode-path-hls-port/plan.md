# Implementation Plan: Cutover tooling transcode path and HLS port

- Specification: specs/076-cutover-tooling-transcode-path-hls-port/spec.md
- Issue: #335 (follow-up)
- Status: Source implementation

## Architecture

The #335 cutover moved Camera 1 HEVC->H264 transcode from VPS to the Ubuntu Worker. Two tooling defects were worked around by hand on the hosts and must be corrected in repository source:

1. `scripts/operations/mediamtx_path_config.py` mode `ubuntu-transcode-reader` (invoked by `deploy/worker/ubuntu/camera1-h264-transcode.sh prepare`) only added the least-privilege reader+publish rule for `cam1-h264` but did not create the `paths: cam1-h264:` publisher block. The Worker MediaMTX therefore had no `cam1-h264` path for ffmpeg to publish into.
2. `deploy/vps/camera-source-switch.sh` defaulted its HLS check to `:8888`, restarted MediaMTX before freeing `:18889`, and did not pin `0640 root:mediamtx` on the live config.

The fix reuses the existing, unit-tested `set_path_source` helper for the publisher path and adjusts the VPS script's argument handling and `activate`/`install_candidate` ordering. No runtime host is mutated; the already-deployed manual edits remain the live state until a future re-run uses the corrected tooling.

## Decisions

- D-001: Create the `cam1-h264` publisher path with `set_path_source(text, path, "publisher", source_on_demand=False)` inside `render_ubuntu_transcode_reader`, reusing the proven helper instead of hand-writing YAML.
- D-002: Derive `hls_check_url` from `--hls-address` when provided, supporting both `:port` and `host:port` forms, overriding the MediaMTX-default `:8888` check.
- D-003: In `activate`, disable the retired external units (`sea-speed-camera1-h264.service`, `sea-speed-camera1-hls-http.service`) before `install_candidate` restarts MediaMTX, removing the `:18889` bind conflict.
- D-004: In `install_candidate`, pin the live config to `root:mediamtx` / `0640` after install and before restart, so the `mediamtx` user can read the credential-bearing config.
- D-005: VPS contour is in policy scope because the change touches `deploy/vps/**`; the PR declares `VPS deployment: REQUIRED` and `Production safety envelope: REQUIRED`. Ubuntu Worker/relay update remains NOT REQUIRED.

## Affected contours

- VPS runtime: in policy scope (change touches `deploy/vps/**`); this PR performs no deployment, but the contour is declared REQUIRED per policy.
- VPS execution capability: CONNECTOR.
- Operator actions expected: 0.
- Ubuntu Worker/relay: NOT REQUIRED — source-only tooling change; no deployment.
- Frontend/API/storage: unchanged.
- nginx/Auth topology: unchanged.
- MediaMTX on hosts: unchanged by this PR (live config already carries the manual edits).

## Validation

Source validation uses the existing Python unit suite for the renderer plus `bash -n` and `scripts/ci/validate_repo.py`. The extended test `tests/test_vps_transcode_to_ubuntu.py::test_ubuntu_transcode_reader_renders_combined_cam1_h264_rule` asserts the `cam1-h264` publisher path, `source: "publisher"`, and `sourceOnDemand: no`. The VPS script is validated statically (`bash -n`) and by review of the argument-derivation and ordering change. PR Validation and aggregate Quality must pass on one exact head; before merge refresh current `main`, exact PR head, changed-file scope, review submissions and unresolved threads; merge only with expected-head protection. Exact-main Quality must pass before any new production decision.

## Risk profile

- Risk profile: NOT REQUIRED

This is a VPS-contour tooling change with no runtime deployment, so security-boundary and operational risk are low but explicit. Risk is bounded by reusing the existing unit-tested `set_path_source` helper, preserving the fail-closed `ConfigError` path, keeping the existing `validate_config_security` (no world-access) contract, and not mutating any host.

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `render_ubuntu_transcode_reader` output contains `cam1-h264:`, `source: "publisher"`, `sourceOnDemand: no`
- TEST-002 | Covers: AC-002 | Level: static | Priority: P0 | Evidence: `bash -n deploy/vps/camera-source-switch.sh` passes
- TEST-003 | Covers: AC-003 | Level: static | Priority: P0 | Evidence: `scripts/ci/validate_repo.py` passes on changed tree
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `python3 -m unittest tests/test_vps_transcode_to_ubuntu.py` passes (6 tests)
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: PR Change Contract declares VPS REQUIRED, Ubuntu NOT REQUIRED, operator actions 0

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE (tooling defect correction discovered during #335 cutover)
- Issue impact: Issue #335 remains DONE; this follow-up records the two hand-worked defects as repository-source fixes.
- Specification impact: binds the Worker transcode candidate to contain the `cam1-h264` publisher path and the VPS activate to verify the configured HLS port with secure perms and correct ordering.
- Plan impact: preserves the existing cutover architecture; adds deterministic renderer coverage and VPS-script hardening.
- Tasks impact: records T1-T6 as completed source work and T7 (PR) as the remaining step.
- Authorization impact: this follow-up is a separate bounded source task admitted under its own `OUTCOME APPROVED`; it does not widen #335 and grants no production authority.
- Follow-up: open PR with Change Contract (VPS REQUIRED per policy, Ubuntu NOT REQUIRED); after merge, no host action is required because the live configs already carry equivalent manual edits.

## Runtime feedback

- During the #335 VPS cutover the operator had to insert `cam1-h264: source: publisher` by hand on the Worker because `ubuntu-transcode-reader` omitted the path block.
- During the #335 VPS `activate` the operator hit "canonical VPS-local HLS did not become available" (`:8888` default), a `:18889` bind conflict (external units still up), and `permission denied` on `/etc/mediamtx/mediamtx.yml` (wrong perms) — all three are addressed here.
- The live hosts already carry the equivalent manual edits; this PR makes the repository tooling correct so a future re-run needs no hand edits.
- No production deployment is triggered; standing delegation and policy evaluation are unchanged.
