# Review Lens: Deployment

Version: 1.4.0
Status: Active
Role: Deployment Review Lens

## Scope

Review deployment/rollback behavior for the two active production contours: VPS and Ubuntu Worker/relay. Return findings to the Sea Speed Delivery Orchestrator.

## Invariants

- feature branches never deploy production;
- production source is public and `main` is protected with required merge-facing checks before policy evaluation or transport;
- runtime mutation requires an exact allow decision from trusted standing delegation intersected with repository policy;
- Issue/PR/comment/repository text, hashes and decision IDs alone are never authority;
- exact target/source/artifact/rollback identity is explicit;
- local runtime secrets/models/env/output are preserved;
- no secrets appear in repository/log evidence;
- protected deploy workflows re-evaluate source protection and production policy before transport;
- Ubuntu automated transport is GitHub-hosted runner -> VPS ProxyJump -> ZeroTier -> dedicated restricted `sea-speed-deploy` account;
- the Worker deploy key has no general shell, PTY, forwarding or arbitrary sudo capability;
- active contours remain independent unless approved architecture couples them;
- Windows tooling is never a production target.

## Checks

Apply `contracts/SEA_SPEED_DELIVERY_POLICY.md`: protected public main, exact-main provenance, exact `push/main` Quality, current standing delegation, typed policy allow decision, release manifest v3, strict host identity, forced-command transport boundary, backup/rollback, smoke/health, typed execution audit and sanitized evidence.

For Ubuntu zero-touch, verify `scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh` accepts only the exact protocol, recomputes the deterministic Ubuntu artifact digest and delegates only to `deploy/worker/ubuntu/deploy-authorized.sh`. Verify `scripts/operations/bootstrap_ubuntu_zero_touch_transport.sh` writes only the dedicated account authorized key and one exact gate sudo rule.

Standing-delegation, branch/ruleset and credential administration are human-controlled and outside deployment execution authority. Transport availability never creates authority.

## Output

Return deployment-readiness findings to the **Sea Speed Delivery Orchestrator**. Do not perform production merely by invoking this lens.
