# Tasks: legacy VPS camera-source-switch cleanup + fail-closed relay-identity config install

- Spec: specs/661-legacy-camera-switch-cleanup/spec.md

## Delivery tasks
- [x] Port `derive_relay_service_identity` verbatim from `deploy/worker/ubuntu/camera-relay.sh` (L208-276; `$relay_service` instead of `$service_name`) into both `deploy/worker/ubuntu/road1-h264-transcode.sh` and `deploy/worker/ubuntu/camera1-h264-transcode.sh`, with the 4-line caller block (derive || exit 9 → read → printf INSTALL_OWNER → printf MODE) after the id gate and before the backup
- [x] Add `--systemd-unit-dir PATH` (default `/etc/systemd/system`) to both scripts and `--watchdog-bin-dir PATH` (default `/usr/local/sbin`) to camera1 (usage + variable + case branch); retarget the unit install, config install (derived owner/group/mode) and camera1 watchdog installs; backup line unchanged
- [x] Add opt-in `ID_STUB`/`INSTALL_STUB` to tests/support/relay_shell.py (default OFF; install stub logs argv to `$INSTALL_LOG` and applies the mode for real) and the executed-twin battery tests/test_transcode_activate_permissions.py (one subclass per script × three scenarios, copy-tree harness with the real renderer bytes planted executable)
- [x] Capture RED-on-base evidence before the script edits (all six twins fail on base; scenario-c flag-free behavioral RED: base takes the backup then dies at the hardcoded real-/etc unit install) into the delivery record
- [x] Delete `deploy/vps/camera-source-switch.sh` and mark the four runbooks (CAMERA1_DIRECT_H264_CUTOVER, CAMERA1_LIVE_REPLACEMENT, MEDIAMTX_COMPATIBILITY_REMEDIATION, MEDIAMTX_SYSTEMD_V247_COMPATIBILITY) with removal notes (removed in #661, dead legacy VPS-mediamtx era, superseded by the road1-720p transcode path PR #660), keeping historical command shapes as record
- [x] Update tests/test_camera1_live_replacement.py: drop the deleted-script constant, syntax-check, source reads and VPS SP pins; pin the removal-note state ("REMOVED in #661" + retained historical command shapes) in the retire-section assertions
- [x] Write the SDD trio specs/661-legacy-camera-switch-cleanup/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [x] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the #661 PR
- [ ] Merge the #661 PR to main

## Completion gate
- Peer verification of the #661 diff complete
- CI green on the #661 PR
- PR merged to main
- No server-side execution in this chain: the ported contract takes effect on the next manual activation of either transcode script (explicitly not a gate for this PR)

## Requirements traceability
- AC-001 | Task: executed underivable-identity twins (flag-free) | Evidence: test_activate_underivable_identity_refuses_fail_closed_before_mutation, both subclasses in tests/test_transcode_activate_permissions.py (exit 9, derive error, config bytes+mode unchanged, no backup); behavioral RED on base quoted in the delivery record | Coverage: COVERED
- AC-002 | Task: executed derived-identity twins | Evidence: test_activate_non_root_relay_identity_evidences_and_installs_0640 and test_activate_root_relay_identity_keeps_0600_install, both subclasses (evidence lines, install-argv log `-o root -g mediamtx -m 0640`, installed modes 0640/0600) | Coverage: COVERED
- AC-003 | Task: redirect seams + unchanged backup | Evidence: (a)/(b) twins complete the full transaction through --systemd-unit-dir/--watchdog-bin-dir; defaults inspected in both scripts; backup line byte-identical; bash -n green | Coverage: COVERED
- AC-004 | Task: legacy deletion + removal notes + test updates | Evidence: git status shows D deploy/vps/camera-source-switch.sh; four runbooks carry "REMOVED in #661" notes; tests/test_camera1_live_replacement.py green with the new retire-section pins | Coverage: COVERED
- AC-005 | Task: RED-on-base evidence + full battery | Evidence: RED-pre-edit.txt (6/6 fail on base incl. the scenario-c behavioral quote) vs post-fix 6/6 OK; full unittest discover green; validate_sdd.py green | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
