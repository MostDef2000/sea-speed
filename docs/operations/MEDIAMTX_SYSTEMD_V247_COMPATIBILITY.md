# MediaMTX systemd v247 compatibility runner

## Purpose

Issue #87 already has a fail-closed MediaMTX v1.20.0 compatibility core in
`deploy/vps/mediamtx-compatibility-remediation.sh`. Production proved that its
sandbox contract reaches systemd before any candidate media work, but the VPS
systemd v247 rejects the newer `PrivateUsers=self` value. The intended sandbox
semantics for this bounded canary are preserved by the backward-compatible
boolean form `PrivateUsers=yes`.

This remediation intentionally does not rewrite the large audited core. The new
`deploy/vps/mediamtx-systemd-v247-runner.sh` verifies that core by the exact
Issue #87 SHA-256, creates a root-only deterministic copy under `/run`, proves
that the copy differs by exactly one substitution
`PrivateUsers=self` -> `PrivateUsers=yes`, and executes the copy. Because both
`prepare` and `activate` are launched through the same deterministic transform,
the core's existing `tool_sha256` marker binding still protects activation.

## Sandbox property preflight

Before `prepare` can execute the candidate, the launcher starts a bounded
transient `/usr/bin/true` unit as the existing MediaMTX service identity with the
same security-property family used by the candidate sandbox. This includes
`PrivateUsers=yes`, private tmp/device/IPC/network namespaces, strict filesystem
protection, namespace restrictions, capability removal, execution-path limits,
resource limits and the existing service UMask. A property parse or transient
unit failure returns `SYSTEMD_SANDBOX_PREFLIGHT=FAIL` before the MediaMTX
candidate core starts. Success returns `SYSTEMD_SANDBOX_PREFLIGHT=PASS`.

This preflight is compatibility evidence only. It is not runtime acceptance of
MediaMTX. The existing core must still prove the candidate version, active
configuration compatibility, two advancing RTSP frames and two advancing HLS
frames before it can publish a canary marker.

## Resumable final Camera 1 runner

`deploy/vps/camera1-final-cutover.sh` is a thin entry point for the final
compatibility `prepare`, `activate` and `status` calls. It never edits the active
MediaMTX YAML and never restarts a service itself.

The production HLS remediation from `mpegts` to `fmp4` was a separate protected
runtime action. A resumed final run is allowed to continue only when the active
configuration already contains exactly one top-level `hlsVariant: fmp4`. In
that case it reports:

```text
HLS_VARIANT_REMEDIATION=ALREADY_APPLIED
```

If the config still says `mpegts`, the runner reports
`HLS_VARIANT_REMEDIATION=REQUIRED` and stops. It does not repeat the production
configuration mutation. Other explicit variants are outside this bounded flow.

## Simplified completion flow

After this source is merged and separately approved for deployment, the Windows
side only needs to establish the already-proven SSH path, stage the exact merged
VPS files plus the approved official MediaMTX archive, and invoke the final
runner. The runner performs the fMP4 resume gate, systemd property preflight and
existing compatibility canary. Activation remains conditional on a successful
canary marker. Human visual acceptance of the new physical camera remains a
separate gate before the existing `camera-source-switch.sh prepare-cleanup` /
`activate-cleanup` path may retire `cam1-new`.

Repository integration of these runners is source state only. It does not by
itself authorize or prove VPS installation, service mutation or runtime
acceptance. VPS deployment remains required after merge; no Windows worker
update or release manifest is required for this bounded remediation.

No AI worker activation, Ubuntu mutation, nginx change, network change, camera
credential handling or automatic rollback is introduced by these runners.
