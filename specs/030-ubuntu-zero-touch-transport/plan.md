# Implementation Plan: Ubuntu Zero-Touch Production Transport

- Feature: 030-ubuntu-zero-touch-transport
- Issue: #234
- Specification: `specs/030-ubuntu-zero-touch-transport/spec.md`
- Source authorization: OUTCOME APPROVED
- Production impact: CONTROL_PLANE
- Security impact: REQUIRED
- Risk profile: REQUIRED

## Architecture

Keep GitHub-hosted Actions as the only workflow executor. Keep the public GitHub repository as source transport on GitHub Free. Add a source-protection verifier to all production entrypoints. Replace the Ubuntu manual fallback with strict SSH ProxyJump through the existing VPS to a dedicated Worker deploy identity constrained by OpenSSH forced-command restrictions and one root-owned validation gate.

The gate is transport enforcement, not policy authority. Standing production authority remains only the trusted `production` environment delegation intersected with repository policy. The gate adds a target-side blast-radius boundary: only exact first-parent source and a matching deterministic Ubuntu artifact digest can reach the existing `deploy-authorized.sh` transaction.

## Decisions

1. Repository remains public while GitHub Free is the control plane; private visibility is production deny.
2. `main` protection is independent admin state and is verified before production evaluation/transport.
3. No self-hosted runner is installed on VPS/Worker.
4. VPS is used as SSH ProxyJump only; no ZeroTier Central API token is introduced.
5. Worker automated identity is `sea-speed-deploy`, separate from operator `seaspeedadmin`.
6. OpenSSH `restrict` + forced command limits the deploy key before sudo.
7. Sudo admits only the root-owned zero-touch gate; the gate validates request arguments and exact source/artifact before invoking the canonical deployment transaction.
8. Steady-state workflow has no recurring one-command fallback. Missing zero-touch configuration fails closed and requires administrative bootstrap.
9. Historical Change Contracts remain immutable; current protected workflow capability may satisfy an older `ONE_COMMAND_FALLBACK` release after independent activation.

## Affected contours

- Source PR impact: `CONTROL_PLANE`; no VPS or Ubuntu application mutation is performed by the source PR.
- VPS deployment: `NOT REQUIRED` for this source PR. Existing VPS is later reused only as SSH `ProxyJump` transport bridge.
- Ubuntu Worker/relay update: `NOT REQUIRED` for this source PR. One-time post-merge transport bootstrap changes only Worker SSH/deploy access boundary, not Water/Road/Auth runtime state.
- Runtime acceptance after activation: Ubuntu `CONNECTOR` path is exercised by retrying exact Issue #231; that later execution owns the Authentik runtime mutation and verification.
- Windows Worker: retired/not applicable.

## Validation

- Local/source: Python compile for new/modified Python, `bash -n` for shell entrypoints, workflow YAML parse, source-protection unit tests, zero-touch static security tests and existing policy/convergence/quality regressions.
- PR: `PR Validation / Repository validation` and aggregate `Quality integration gate / quality-integration` must both succeed on the exact PR head.
- Post-merge: exact-main Quality must succeed before independent activation.
- Administrative: Connector/settings evidence must show public protected `main`, required checks, unchanged standing delegation and production environment transport configuration.
- Runtime: negative SSH capability probes followed by exact #231 positive deployment with `runtime_verified`, typed audit and Authentik `days=30`.

## Runtime feedback

- Issue #231 proved current production Authentik still reports `hours=12`; the first bounded attempt rolled back successfully after an unreadable `0600` bind-mounted blueprint.
- PR #233/current main repaired that blueprint mode to `0644`.
- Subsequent autonomous execution reached standing policy `allow` but stopped with exit 42 because zero-touch Ubuntu SSH transport was not provisioned.
- Repository visibility is public again on GitHub Free, while `main` is currently unprotected; #234 therefore adds a fail-closed protected-source gate and defers activation until independent branch/ruleset administration.
- Existing VPS GitHub-hosted SSH capability is retained as transport-only ProxyJump; no new ZeroTier control-plane credential is introduced.

## Risk profile

- Risk profile: REQUIRED
- RISK-030-001 | Category: SEC | Probability: 3 | Impact: 5 | Score: 15 | Mitigation: require public protected main, exact required checks, exact-main Quality and standing policy before transport | Validation: source-protection unit tests plus independent branch/ruleset evidence | Residual risk: source-protection drift blocks deployment rather than mutating production | Owner: Delivery Orchestrator + repository administrator | Status: OPEN
- RISK-030-002 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: dedicated locked account, OpenSSH restrict, forced command, no PTY/forwarding and one exact sudo gate | Validation: bootstrap/gate tests plus installed negative SSH probe | Residual risk: dedicated key can request only validated deployment protocol | Owner: Delivery Orchestrator + Worker administrator | Status: OPEN
- RISK-030-003 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: policy executes before transport and Worker requires separate credential from VPS jump identity | Validation: workflow-order tests and runtime transport evidence | Residual risk: VPS compromise remains network-path risk but does not become policy authority | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-030-004 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: require first-parent main SHA, exact Issue/hash syntax, deterministic artifact equality and canonical target validation | Validation: gate tests and release evidence | Residual risk: historical main SHA remains requestable only through current policy-allowed workflow | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-030-005 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Worker independently rebuilds deterministic Ubuntu artifact and compares digest | Validation: artifact mismatch tests | Residual risk: deterministic builder correctness remains covered by existing artifact tests | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-030-006 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: private key generated/handled only by administrator and stored as environment secret; bootstrap accepts public key only | Validation: bootstrap source tests and protected-settings evidence | Residual risk: credential compromise requires independent rotation/removal | Owner: repository administrator | Status: OPEN
- RISK-030-007 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: one root-owned gate path only, strict parser and no broad NOPASSWD | Validation: sudoers/bootstrap static tests plus installed-boundary inspection | Residual risk: root gate defects remain bounded by exact source/artifact checks | Owner: Worker administrator | Status: OPEN
- RISK-030-008 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: fingerprint verification, strict host key, bounded `--remove`, preserve separate operator access | Validation: bootstrap removal test and runtime bootstrap evidence | Residual risk: bootstrap misconfiguration may block automation without blocking operator access | Owner: Worker administrator | Status: OPEN

## Test design

- TEST-030-001 | Covers: FR-001..FR-003 source protection public/protected/required-check fail-closed behavior | Level: unit | Priority: P0 | Evidence: `tests/test_production_source_protection.py`
- TEST-030-002 | Covers: FR-004..FR-006 GitHub-hosted runner and VPS ProxyJump transport ordering | Level: integration | Priority: P0 | Evidence: workflow policy and quality architecture tests
- TEST-030-003 | Covers: FR-007..FR-014 forced-command gate, strict request parser, first-parent and deterministic artifact verification | Level: unit | Priority: P0 | Evidence: `tests/test_ubuntu_zero_touch_transport.py`
- TEST-030-004 | Covers: FR-015..FR-018 strict SSH options, bootstrap boundary and removal path | Level: unit | Priority: P0 | Evidence: bootstrap/transport source tests
- TEST-030-005 | Covers: FR-019..FR-020 standing authority unchanged and repository prose non-authoritative | Level: integration | Priority: P0 | Evidence: autonomous policy and delivery convergence tests
- TEST-030-006 | Covers: AC-009 exact-head PR Validation and aggregate Quality followed by exact-main Quality | Level: end-to-end | Priority: P0 | Evidence: GitHub Actions run evidence
- TEST-030-007 | Covers: AC-010..AC-012 installed source protection and restricted Worker transport | Level: runtime-manual | Priority: P0 | Evidence: Connector/settings evidence plus installed negative SSH probes
- TEST-030-008 | Covers: AC-013..AC-014 exact #231 zero-touch deployment and Authentik 30-day verification | Level: runtime-manual | Priority: P0 | Evidence: protected deployment manifest, typed audit and runtime ORM/UI evidence

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #234 captures the transport defect exposed by #231 and preserves #231 as the product-runtime acceptance release.
- Specification impact: zero-touch design is narrowed to public GitHub Free, protected main, GitHub-hosted runner and VPS ProxyJump rather than private/self-hosted alternatives.
- Plan impact: adds protected-source hard gate, dedicated Worker identity, forced command, bounded bootstrap/removal and runtime negative probes.
- Tasks impact: source tasks and independent activation tasks are separated so repository writes cannot self-administer their own trust boundary.
- Authorization impact: source authorization remains the existing `OUTCOME APPROVED`; standing delegation remains unchanged and settings/credential administration remains independent.
- Follow-up: after source merge and exact-main Quality, complete T010-T018 and use #231 runtime evidence to close #231/#234 and satisfy #229 acceptance linkage where applicable.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the autonomous Ubuntu workflow had no provisioned Worker transport and therefore could only emit one-command fallback after policy allow.
- Production-learning adjacent-stage findings: Authentik blueprint mode 0600 was a separate mutation-stage defect already corrected by #233; source protection was also absent and must become a pre-transport hard gate before zero-touch activation.
- TX-030-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source or activation remains unapproved and production unchanged | Retry: retry only after exact admission evidence is valid | Rollback: not applicable because no mutation occurred | Evidence: Issue #234 scope, exact base, public repository and risk classification
- TX-030-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: existing operator access and application runtime remain unchanged | Retry: retry after protected-main, delegation, key and host-trust prerequisites are complete | Rollback: no mutation to roll back | Evidence: branch/ruleset, standing delegation, public-key fingerprint and host-key evidence
- TX-030-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: partial transport boundary may exist but application runtime is unchanged | Retry: remove or repair partial boundary before another bootstrap | Rollback: run bootstrap `--remove` and remove incomplete protected settings | Evidence: sanitized bootstrap result and installed file ownership/mode
- TX-030-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: zero-touch remains inactive and application runtime unchanged | Retry: repair boundary then rerun negative probes | Rollback: remove transport boundary if restrictions cannot be proven | Evidence: account lock, authorized-key restriction, sudoers validation and rejected shell/PTY/forward probes
- TX-030-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: zero-touch capability is not declared active until all settings and probes pass | Retry: recommit only after complete verified state | Rollback: remove Worker transport secrets/boundary while preserving operator access | Evidence: protected-main state, environment configuration presence and boundary PASS record
- TX-030-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified transport may remain active while temporary bootstrap material awaits cleanup | Retry: remove temporary public-key/checkouts without touching runtime | Rollback: transport removal is not required solely for harmless temporary cleanup residue | Evidence: absence of private key on Worker and preserved operator/runtime state
- TX-030-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: acceptance remains incomplete even if transport is installed | Retry: recollect sanitized evidence and rerun exact #231 protected deployment | Rollback: no evidence-only rollback; remove transport if verification cannot be reconstructed | Evidence: Connector source state, bootstrap fingerprints, negative probe, policy decision, release/deployment manifests and execution audit
- TX-030-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: operator access and application runtime remain available while zero-touch boundary is removed | Retry: bootstrap can be safely reattempted from clean boundary | Rollback: `bootstrap_ubuntu_zero_touch_transport.sh --remove`; application rollback remains canonical Ubuntu transaction | Evidence: removal output, absence of dedicated boundary and preserved operator access

## Rollout order

1. Merge #234 source after exact PR checks.
2. Confirm exact-main Quality.
3. Human/admin configures main protection and verifies required checks.
4. Human/admin provisions Worker key/known-host state and runs one bootstrap.
5. Verify restricted transport negative probes.
6. Dispatch exact #231 release through current protected Ubuntu workflow.
7. Verify Authentik `days=30`, runtime manifest and typed audit.
8. Close #231/#234 when acceptance evidence is complete; use #229 acceptance linkage as applicable.
