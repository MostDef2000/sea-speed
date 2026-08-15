# Tasks: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Delivery tasks

- [x] Confirm failed production evidence for `c73c6e048399ff5985918348c028d3f9a6a2ca89` and successful automatic restore.
- [x] Confirm failed production evidence for `e5d4d25b731328951c7a2178c244b99c5ad64372`, including zero AI successes and systemd start-limit blocking the first restore attempt.
- [x] Recover the previous exact Worker unit with `systemctl reset-failed` and verify exact old marker/unit/service identity.
- [x] Keep the remediation inside the already approved AI-inference-supervision and deployment-safety outcome.
- [x] Create correction branch from exact current `main`.
- [x] Preserve bounded AI child request writes, same-child startup validation, and replacement-child warm timeout semantics.
- [x] Pin the ByteTrack linear-assignment runtime dependency required by Ultralytics for the production Python interpreter.
- [x] Verify the tracker dependency version and import during canonical Worker preparation.
- [x] Disable Ultralytics service-time auto-install in the systemd unit.
- [x] Clear systemd failed/start-limit state before automatic restore restarts the previous exact Worker.
- [x] Preserve `model.track(... persist=True ...)`, ByteTrack selection, detection shape, vehicle allow-list, ROI filtering, speed semantics, API schemas, and frontend behavior.
- [x] Add focused source-contract coverage for dependency closure, immutable runtime, and reset-before-restart rollback ordering.
- [x] Open correction PR with exact Change Contract.
- [ ] Pass PR Validation, Quality integration, and Worker package gates.
- [ ] Merge exact green head and pass post-merge gates.
- [ ] Obtain fresh exact-SHA production authorization.
- [ ] Run one Worker exact activation and sustained UI/runtime acceptance.
- [ ] Deploy VPS/frontend on the same accepted SHA and close Issue #159 with production evidence.

## Completion gate

Source correction is complete only when the exact PR head is green and merged,
and the merged SHA has fresh post-merge gates. Production remains incomplete
until that same exact SHA passes Worker activation/runtime acceptance and the
Issue #159 VPS/frontend acceptance after fresh production authorization.
