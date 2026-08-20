# Feature Specification: Ubuntu Zero-Touch Production Transport

- Feature: 030-ubuntu-zero-touch-transport
- Issue: #234
- Status: Source implementation
- Owner outcome: ordinary accepted Ubuntu Worker releases deploy, verify and audit with zero per-release operator commands while production authority remains bounded by protected public main and the standing delegation.

## Product outcome

Replace the current Ubuntu `ONE_COMMAND_FALLBACK` transport with a permanent restricted `CONNECTOR` path that works on GitHub Free without a self-hosted production runner. GitHub-hosted Actions uses the existing production VPS as an SSH ProxyJump, reaches the Ubuntu Worker over the existing ZeroTier route, authenticates as a dedicated `sea-speed-deploy` account, and can invoke only one forced deployment protocol.

The repository remains public because the current GitHub Free account needs public-repository branch protection, required checks and environments for the control-plane design. Public source is not trusted authority and is not a credential boundary. Production execution also requires protected main, exact-main Quality and a standing production-policy allow decision.

## User scenarios

### Scenario 1 - Ordinary Ubuntu release

Given an approved runtime-impacting release is merged through protected main and exact-main Quality succeeds, when standing policy allows Ubuntu deployment, then the protected workflow reaches the Worker through VPS ProxyJump, invokes the restricted forced command, receives a runtime-verified deployment manifest, builds a typed execution audit and requires no operator terminal action.

### Scenario 2 - Repository protection drifts

Given repository visibility becomes private on GitHub Free, main protection is removed, or required merge-facing checks are absent, when any production workflow attempts policy evaluation, then source-protection verification denies before transport and no runtime mutation occurs.

### Scenario 3 - Deploy key is used for an arbitrary command

Given the dedicated Worker deploy key is presented with a shell, PTY, forwarding request or command other than the exact protocol, when sshd applies the authorized key restrictions and forced command, then the request cannot obtain general execution and the gate rejects unsupported `SSH_ORIGINAL_COMMAND`.

### Scenario 4 - Request metadata is tampered

Given the forced command contains a malformed SHA, Issue or artifact hash, or the artifact digest differs from the deterministic exact Ubuntu artifact for that source, when the root gate evaluates the request, then it denies without invoking the canonical deployment transaction.

### Scenario 5 - Existing Authentik session release is retried

Given zero-touch transport is active, when the exact Issue #231 Ubuntu release is dispatched through the current protected workflow, then it may use the improved connector capability even though its historical Change Contract recorded `ONE_COMMAND_FALLBACK`, and the canonical target transaction applies/verifies the 30-day Authentik blueprint without another manual server command.

## Requirements

- FR-001: Production workflows MUST verify repository visibility is `public` and `main.protected=true` before production policy evaluation or runtime transport.
- FR-002: Source protection MUST require merge-facing contexts `Repository validation` and `quality-integration`; missing required contexts MUST deny.
- FR-003: Repository/ruleset settings MUST remain independently administered and MUST NOT become writable authority of the Delivery Orchestrator.
- FR-004: The Ubuntu workflow MUST run on a GitHub-hosted runner and MUST NOT install/use a self-hosted runner on production hosts.
- FR-005: Ubuntu transport MUST use the existing VPS as `ProxyJump` to fixed Worker endpoint `10.123.239.102:22`.
- FR-006: The VPS jump credential MUST remain transport-only; Ubuntu execution authority MUST still require standing policy allow and the dedicated Worker deploy credential.
- FR-007: The Worker deployment account MUST be `sea-speed-deploy`, MUST reject password authentication without being account-locked, and MUST admit only one authorized Ed25519 key using OpenSSH `restrict` plus forced command. On Linux the active account password field MUST NOT begin with `!`, because sshd rejects a locked account before public-key authentication.
- FR-008: The Worker deploy key MUST NOT provide interactive shell, PTY, forwarding, agent forwarding or arbitrary sudo.
- FR-009: The forced protocol MUST be exactly `sea-speed-ubuntu-deploy-v1 <sha> <issue> <artifact-sha256>`.
- FR-010: The root gate MUST require lowercase SHA40, positive Issue and lowercase SHA256 before mutation.
- FR-011: The root gate MUST prove the requested SHA is on current public main first-parent history.
- FR-012: The root gate MUST recompute the deterministic exact Ubuntu artifact digest for the requested SHA and require equality with the workflow-provided digest.
- FR-013: The root gate MUST invoke only `deploy/worker/ubuntu/deploy-authorized.sh` for product mutation and MUST validate the resulting deployment manifest.
- FR-014: Successful gate stdout MUST be the validated deployment manifest; diagnostic transaction output MUST remain on stderr so workflow JSON validation is deterministic.
- FR-015: The Ubuntu workflow MUST use strict host-key verification for both VPS jump and Worker, separate identities/known-host files, `RequestTTY no`, `ForwardAgent no` and `ClearAllForwardings yes`.
- FR-016: Missing Worker key/host-key or required VPS jump credential MUST fail closed before SSH. The steady-state workflow MUST NOT create a recurring one-command operator fallback.
- FR-017: One-time bootstrap MUST not create or print a private key. It accepts one Ed25519 public key, may require an independently verified fingerprint, installs the root-owned gate, restricted authorized key and one exact gate sudo rule, validates sudoers, and configures the deploy account with a non-locking invalid password marker so password authentication is impossible while public-key authentication remains available.
- FR-018: Bootstrap MUST support bounded transport-boundary removal without modifying application runtime state; removal MUST lock the dedicated deploy account after deleting its authorized key/sudo boundary.
- FR-019: Standing delegation permissions remain exactly the existing `deploy|rollback` intersection; this Outcome MUST NOT widen policy authority.
- FR-020: GitHub Issue/PR/comment/repository prose remains non-authoritative for production.

## Acceptance criteria

- AC-001: Connector evidence confirms repository visibility `public` and, after independent bootstrap, `main.protected=true`.
- AC-002: Source tests deny private visibility, unprotected main and missing required status contexts.
- AC-003: Workflow policy tests prove source protection runs before standing policy/transport in autonomous, VPS and Ubuntu workflows.
- AC-004: Ubuntu workflow source proves GitHub-hosted runner -> VPS ProxyJump -> `sea-speed-deploy@10.123.239.102`, strict host-key checks and zero operator fallback.
- AC-005: Gate tests prove arbitrary commands and malformed SHA/Issue/hash do not reach the root transaction.
- AC-006: Gate source proves first-parent validation and deterministic artifact digest recomputation before `deploy-authorized.sh`.
- AC-007: Bootstrap tests prove `restrict` + forced command, no `NOPASSWD: ALL`, root-owned gate, password authentication disabled without an active account lock, and no private-key generation/printing.
- AC-008: Exact changed-file list remains inside Issue #234 authorized Scope and PR Change Contract.
- AC-009: PR Validation and aggregate Quality succeed on one exact PR head; expected-head merge is followed by exact-main Quality success.
- AC-010: Post-merge repository/ruleset bootstrap establishes PR/check enforcement, force-push/delete disabled and no silent bypass/per-release reviewer requirement.
- AC-011: Production environment retains the standing delegation and receives only the dedicated Worker private key + independently verified Worker known-host data; no secret enters Git/chat.
- AC-012: A restricted transport probe authenticates by the dedicated key but cannot obtain shell/PTY/forwarding and rejects a non-protocol command.
- AC-013: Exact Issue #231 Ubuntu release retries through the new workflow with standing policy allow, reaches `runtime_verified`, produces typed execution audit and requires operator actions `0`.
- AC-014: Authentik runtime acceptance after the retry shows both managed login stages at `days=30`, enabling closure of #231 and supplying zero-touch production evidence for #234/#229.

## NFR assessment

- NFR-001 | Area: SECURITY | Target: no general remote execution surface; source protection + standing policy + dedicated forced-command key are independent gates | Validation: source-protection tests, workflow-policy tests, gate/bootstrap tests, runtime restricted-command probe | Evidence: `tests/test_production_source_protection.py`, `tests/test_ubuntu_zero_touch_transport.py`, production bootstrap/deployment evidence | Status: CONCERNS
- NFR-002 | Area: LEAST_PRIVILEGE | Target: Worker key can invoke only one root-owned validated gate; password login is impossible; VPS remains jump-only; no broad sudo or self-hosted runner | Validation: static tests + installed authorized_keys/sudoers/account-state evidence | Evidence: bootstrap output and read-only installed-boundary inspection | Status: CONCERNS
- NFR-003 | Area: FAIL_CLOSED | Target: private/unprotected source, missing checks, missing transport credentials, malformed request, non-main SHA or artifact mismatch produces no mutation | Validation: unit/static tests and protected workflow evidence | Evidence: tests + failed-negative workflow/probe evidence | Status: PASS
- NFR-004 | Area: OPERABILITY | Target: ordinary Ubuntu deployment requires zero operator commands after one bootstrap | Validation: full Issue #231 retry through Connector mode | Evidence: workflow execution summary + typed audit | Status: CONCERNS
- NFR-005 | Area: PROVENANCE | Target: exact source, Quality, Issue/PR, standing decision, deterministic artifact hash, target manifest and audit remain bound | Validation: existing v3 release/evidence validators plus root artifact recomputation | Evidence: protected workflow artifacts | Status: CONCERNS

## Runtime feedback

- Current main at admission: `9f529a0064ba8ac1a2e2069bf45679f04fa0bd13`.
- Repository is public again after a temporary private experiment; other repositories are outside this Outcome.
- Protected-main administration and both required merge-facing checks are now active.
- The first zero-touch bootstrap returned PASS with the expected deploy-key and Worker host-key fingerprints, but the first CONNECTOR retry failed during SSH authentication with `Permission denied (publickey)` before the forced command executed.
- Root cause is the bootstrap's `passwd -l sea-speed-deploy`: OpenSSH checks account accessibility independently of authentication type, and on Linux a leading `!` lock prevents public-key login too. No application runtime mutation occurred in this failed retry.
- The remediation keeps password authentication impossible using the non-locking invalid password marker `*NP*`, preserving the `restrict`/forced-command/sudo boundary while allowing the dedicated public key to authenticate.
- Issue #231 runtime remains at 12-hour Authentik sessions until the corrected zero-touch retry completes successfully.
