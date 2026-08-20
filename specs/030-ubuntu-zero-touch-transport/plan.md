# Implementation Plan: Ubuntu Zero-Touch Production Transport

- Feature: 030-ubuntu-zero-touch-transport
- Issue: #234
- Source authorization: OUTCOME APPROVED
- Production impact: CONTROL_PLANE
- Security impact: REQUIRED
- Risk profile: REQUIRED

## Architecture

Keep GitHub-hosted Actions as the only workflow executor. Keep the public GitHub repository as source transport on GitHub Free. Add a source-protection verifier to all production entrypoints. Replace the Ubuntu manual fallback with strict SSH ProxyJump through the existing VPS to a dedicated Worker deploy identity that is constrained by OpenSSH forced-command restrictions and one root-owned validation gate.

The gate is transport enforcement, not policy authority. Standing production authority remains only the trusted `production` environment delegation intersected with repository policy. The gate adds a second target-side blast-radius boundary: only exact first-parent source and a matching deterministic Ubuntu artifact digest can reach the existing `deploy-authorized.sh` transaction.

## Decisions

1. Repository remains public while GitHub Free is the control plane; private visibility is production deny.
2. `main` protection is independent admin state and is verified before production evaluation/transport.
3. No self-hosted runner is installed on VPS/Worker.
4. VPS is used as SSH ProxyJump only; no ZeroTier Central API token is introduced.
5. Worker automated identity is `sea-speed-deploy`, separate from operator `seaspeedadmin`.
6. OpenSSH `restrict` + forced command limits the deploy key before sudo.
7. Sudo admits only the root-owned zero-touch gate; the gate validates all request arguments and exact source/artifact before invoking the canonical deployment transaction.
8. The steady-state workflow has no recurring one-command fallback. Missing zero-touch configuration fails closed and requires administrative bootstrap.
9. Historical Change Contracts remain immutable; improved runtime capability may satisfy an old `ONE_COMMAND_FALLBACK` release through current protected workflow dispatch.

## Risk profile

Risk profile: REQUIRED

| Risk | Trigger | Mitigation | Evidence |
|---|---|---|---|
| R-030-001 source bypass | public repository + autonomous production | protected main hard gate, required checks, exact-main Quality and standing policy | source-protection verifier + admin settings evidence |
| R-030-002 deploy key becomes shell | new production SSH credential | dedicated account, `restrict`, forced command, no PTY/forwarding, exact sudo gate | bootstrap/gate tests + runtime negative probe |
| R-030-003 VPS jump becomes authority | ProxyJump reuses VPS credential | policy runs before transport; Worker requires separate credential; VPS command not used for Ubuntu mutation | workflow source/tests |
| R-030-004 replay/old release | forced key can request main-history SHA | SHA must be first-parent main; Issue/hash syntax; deterministic artifact equality; canonical target transaction validates exact source and Quality; use only policy-allowed workflow secret | gate + workflow evidence |
| R-030-005 artifact spoofing | request includes caller-provided digest | Worker independently rebuilds deterministic Ubuntu artifact and compares digest | gate test/source |
| R-030-006 secret leakage | new private key/known-host data | private key generated/handled only by operator/admin and stored as environment secret; bootstrap accepts public key only | bootstrap source + settings evidence |
| R-030-007 root escalation beyond deploy | passwordless sudo exception | one root-owned gate path only; strict argument parser; no `NOPASSWD: ALL` | sudoers inspection + tests |
| R-030-008 lockout | bad bootstrap key/host state | fingerprint check, strict host key, bounded `--remove`, operator access remains separate | bootstrap evidence |

Risk verdict: CONCERNS until branch protection, Worker credential and negative runtime probe are independently verified; source implementation may merge with those post-merge activation gates outstanding.

## Test design

- Unit: pure source-protection state validator for public/private, protected/unprotected and required contexts.
- Static security: workflow markers/order; no manual fallback; no insecure host-key setting; ProxyJump and dedicated identity present.
- Static gate: exact `SSH_ORIGINAL_COMMAND` regex, no `eval`, SHA/Issue/hash validation, first-parent proof, artifact recomputation, only canonical deploy transaction.
- Bootstrap: dedicated account/restrict/forced command, exact sudo boundary, no private-key generation, removal path.
- Regression: existing autonomous policy, delivery-contract convergence, quality architecture, exact artifacts and VPS privilege-boundary tests remain green.
- Integration: PR Validation + aggregate Quality on exact head, then exact-main Quality after merge.
- Runtime negative: arbitrary command/PTY/forward request denied by dedicated Worker key.
- Runtime positive: Issue #231 exact release dispatched through current protected workflow, `runtime_verified` manifest + execution audit, Authentik 30-day stage verification.

## Correct-course check

Correct-course Trigger: PRODUCTION_LEARNING

The prior one-command deployment exposed two production facts: the GitHub runner lacked Worker transport, and Authentik blueprint mode `0600` blocked container reconciliation. #233 corrected the blueprint permission defect. #234 addresses the transport defect without weakening the human-controlled authority boundary. Public GitHub Free constraints changed the selected architecture from potential self-hosted/private designs to protected public main plus GitHub-hosted ProxyJump.

No product detection/tracking/calibration/speed semantics change. No standing delegation widening. No new ZeroTier control-plane dependency.

## Deployment transaction audit

### ADMISSION

- Source: authorized Scope #234, exact main base, significant security/control-plane change.
- Production runtime for the source PR: NONE/CONTROL_PLANE.
- Activation: separately requires public protected main, valid standing delegation, Worker deploy key/host key and existing VPS credentials.
- Failure disposition: deny activation and keep existing manual/operator access unchanged.

### PRE-MUTATION

- Verify branch/ruleset settings and required checks.
- Verify standing delegation remains present and unchanged.
- Generate dedicated Ed25519 key outside Git; verify public-key fingerprint independently.
- Verify Worker SSH host key independently.
- Inspect existing VPS jump credential availability without exposing values.
- Failure disposition: no Worker access-boundary changes.

### MUTATION

- One-time Worker bootstrap installs dedicated account, root-owned gate, restricted authorized key and one gate-only sudoers rule.
- GitHub admin stores Worker private key + known-host data in `production` environment.
- No application service/runtime mutation occurs during transport bootstrap.
- Failure disposition: stop before test deployment; use bootstrap `--remove` if partial boundary exists.

### VERIFICATION

- Validate account locked, gate root-owned/mode, authorized key restriction, sudoers via `visudo`.
- Negative SSH probe proves arbitrary command/PTY/forwarding does not yield execution.
- Protected workflow verifies public/protected source and sees transport credentials.
- Failure disposition: remove/repair boundary before any release execution.

### STATE-COMMIT

- Administrative state is considered committed only after settings + Worker boundary + negative probe pass.
- Repository state remains the merged exact-main source commit; no runtime active-source marker changes during bootstrap.
- Failure disposition: do not mark zero-touch active.

### HOUSEKEEPING

- Remove temporary public-key files/checkouts created only for bootstrap where safe.
- Preserve operator `seaspeedadmin` access and existing application runtime state.
- Ensure no private key appears on Worker except where independently intended (target design requires none).

### EVIDENCE

- GitHub Connector: public repository, protected main, required checks, exact-main Quality.
- Worker sanitized bootstrap output: deploy-user, public-key fingerprint, host-key fingerprint, boundary state.
- Read-only negative-probe result.
- Positive Issue #231 workflow: policy decision, release manifest v3, deployment manifest, execution audit, Authentik runtime acceptance.

### ROLLBACK

- Transport boundary rollback: run bootstrap `--remove`, remove GitHub Worker deployment secrets, leave operator access/runtime untouched.
- Release rollback remains owned by existing canonical Ubuntu transaction and standing `rollback` authority.
- A failed positive deployment uses the target transaction's bounded rollback; transport bootstrap is not used to bypass application rollback.

## Rollout order

1. Merge #234 source after exact PR checks.
2. Confirm exact-main Quality.
3. Human/admin configures main protection and verifies required checks.
4. Human/admin provisions Worker key/known-host state and runs one bootstrap.
5. Verify restricted transport negative probes.
6. Dispatch exact #231 release through current protected Ubuntu workflow.
7. Verify Authentik `days=30`, runtime manifest and typed audit.
8. Close #231/#234 when their acceptance evidence is complete; use #229 acceptance linkage as applicable.
