# Spec: Cross-repo GPU-box deploy lock for Ubuntu worker deploys (T8b)

- Issue: #460
- Specification: specs/460-cross-repo-lock/spec.md

## Product outcome

Ubuntu worker deploys run on the shared GPU box (`sea-speed-deploy@10.123.239.102`) together with `content` deploys. The content side already serializes its deploys through the cross-repo lock (content PR #14, merged 9d96373, proven live by drill run 38185426951); the sea-speed deploy path had no such gate, so a parallel deploy of the two repositories could interleave root mutations on the same host (updater install, protected-config backup, checkout swap, service restarts vs docker compose build/up).

This change (task T8b of issue #460) makes `deploy/worker/ubuntu/deploy-authorized.sh` adopt the IDENTICAL contract:

1. Non-blocking cross-repo lock on `/var/tmp/gpu-box-deploy.lock`, acquired BEFORE the first host mutation: `touch` (umask 000, self-heal) → `chmod 0666` belt-and-suspenders → `exec 8<` fail-closed → `flock -n 8` fail-closed (exit 6) with the byte-exact contention message `ERROR another GPU-box deploy is active (cross-repo lock: content/sea-speed)`.
2. Self-heal contract: `/var/tmp` persists across reboot (`/run` is tmpfs — the original lock died at every reboot) and has mode 1777 on a standard Ubuntu, so the deploy user creates the file itself — no root bootstrap. The file mode is umask-independent 0666: `flock` works through a read-only fd even on 0644, and 0666 lets the other repo's deploy user `touch` the file, refreshing mtime against `systemd-tmpfiles-clean`, which removes `/var/tmp` files inactive > 30 days. Every deploy touches the file; an idle period > 30 days is self-healed when the next deploy recreates it.
3. The repo-internal transaction lock (`/opt/sea-speed-worker/updater/deploy-authorized.lock`) moves fd 8 → 9 — the same fd layout as the content deploy-wrapper (8 = cross-repo, 9 = repo-internal); child scripts keep per-process descriptors and are unaffected.
4. `AGENTS.md` records the "Cross-repo GPU-box deploy lock" contract subsection, and five static CI assertions pin the contract (path, byte-exact contention message, command order, lock-before-first-mutation, fd layout) with RED authenticity proven by mutation.

## User scenarios

- US-1 (the incident direction): a content deploy holds the cross-repo lock → a parallel sea-speed deploy fails closed with exit 6 and the byte-identical contention message BEFORE any host mutation (no `install -d`, no backup, no checkout, no restart).
- US-2: the mirror direction — a sea-speed deploy holds the lock → a parallel content deploy fails closed with the same message (both repos share the same path, mode and diagnostics).
- US-3: no lock file (first deploy, or removed by tmpfiles-clean after > 30 idle days) → the deploy creates it (mode 0666, umask-independent) and acquires the lock; two sequential deploys both proceed.
- US-4: a stale root-owned 0644 lock file → `touch` fails with a non-fatal WARNING; `open+flock` still decides (read-only fd works on 0644) and the deploy proceeds.
- US-5: per-deploy `touch` keeps mtime fresh, and a foreign deploy user (the other repo) can refresh mtime on the 0666 file — `systemd-tmpfiles-clean`'s 30-day inactivity rule cannot reap an actively used lock.
- US-6: while a sea-speed deploy is active, its own repo-internal lock (fd 9) still rejects a second sea-speed deploy with the unchanged internal message and exit 6; the two locks are independent and additional.

## Scope

- `deploy/worker/ubuntu/deploy-authorized.sh`: ONLY the cross-repo lock block (BEGIN/END-marked, after the required-commands check, BEFORE the first `install -d`) and the internal updater lock renumber fd 8 → 9 (+ its comment); every other byte of the deploy transaction unchanged.
- `AGENTS.md`: the "Cross-repo GPU-box deploy lock" subsection under production runtime contours.
- `tests/test_ubuntu_worker_deploy_authorized.py`: EXTENDED with the `UbuntuWorkerGpuBoxDeployLockTests` class (5 static methods); the existing 14 methods are untouched.
- SDD trio `specs/460-cross-repo-lock/` and the durable progress file (outside the repo tree).
- OUT of scope: the content-side wrapper (already merged as content PR #14), child scripts `update-exact.sh`/`rollback-exact.sh` (the fd renumber affects only deploy-authorized.sh's own descriptors), rollback-code.sh (no rollback-path lock change in this task), `.github/workflows/**` (no workflow change), live box state (the lock file already exists from content deploys).

## Requirements

- R-1 (AC-1 fail-closed serialization): with any other holder of `/var/tmp/gpu-box-deploy.lock`, deploy-authorized.sh exits 6 with the byte-exact message `ERROR another GPU-box deploy is active (cross-repo lock: content/sea-speed)` BEFORE the first host mutation; the acquisition sequence (touch umask 000 → chmod 0666 → exec 8< → flock -n 8) is pinned in order.
- R-2 (AC-2 self-heal): an absent lock file is created umask-independent 0666 and the lock acquired; a stale root-owned 0644 file degrades to a non-fatal WARNING with `open+flock` as the single fail-closed decider; per-deploy touch refreshes mtime, and 0666 lets the other repo's deploy user refresh mtime too (systemd-tmpfiles-clean 30-day rule).
- R-3 (AC-3 unchanged internal semantics): the repo-internal transaction lock keeps its path, 0600 mode, contention message and exit 6, now on fd 9; acquisition order is cross-repo (fd 8) → internal (fd 9), identical to content — no inversion/deadlock; child scripts are byte-untouched.
- R-4 (AC-4 pinned contract): the lock contract is pinned by static CI assertions (path constant, byte-exact contention string, command order, lock-before-first-mutation, fd layout), and RED authenticity is proven by mutation (string and ordering mutations each fail the named test).

## Acceptance criteria

- AC-1: a foreign lock holder → fail-closed exit 6 before any host mutation, contention message byte-identical to content's.
- AC-2: absent/stale lock self-heals (0666 umask-independent, mtime refresh vs tmpfiles-clean 30d).
- AC-3: child script lock semantics unchanged (per-process fds); internal updater lock on fd 9, cross-repo lock on fd 8, cross-repo acquired first.
- AC-4: the contract is pinned by static tests, with RED authenticity proven.

## Runtime feedback

- RF-001: Operator actions expected: 1 (on-box install of the updated deploy-authorized.sh — copy + chmod over the forced-command path); the live two-sided proof arrives with the next real sea-speed deploy; the optional parallel-deploy drill is documented on issue #460. Orchestrator records the runtime acceptance.
- RF-002: Evidence: deploy logs carry the lock acquire/contention diagnostics (the contention diagnostic is byte-identical to content's); acceptance is recorded on issue #460 and in the delivery session log.

## NFR assessment

- NFR-001 | Area: security | Target: the gate only rejects concurrency — it adds no capability, no secret handling change and no widening of any sudo/exec boundary; contention fails closed (exit 6) BEFORE any host mutation with a byte-exact shared diagnostic; the lock file itself is an empty world-readable 0666 file whose only cross-user affordances are touch (mtime refresh) and flock through a read-only fd | Validation: static contract battery (path constant, byte-exact message, lock-before-first-mutation ordering pin) + behavioral harness foreign-holder scenarios b1/b2 (rc 6, zero host mutations) | Evidence: tests/test_ubuntu_worker_deploy_authorized.py — UbuntuWorkerGpuBoxDeployLockTests + harness transcript recorded in the durable progress file | Status: PASS
- NFR-002 | Area: reliability/operations | Target: deploys of content and sea-speed serialize on the shared GPU box in BOTH directions; a parallel deploy of the other repo is rejected fast (non-blocking) instead of interleaving host mutations or queueing behind an unknown-duration holder; no deadlock — the acquisition order is fixed (cross-repo fd 8 → internal fd 9), byte-identical to the content deploy-wrapper layout | Validation: harness b1/b2 (foreign holder → rc 6 + byte-identical diagnostic) + c1/c2 (two sequential acquisitions both proceed) + contract byte-identity normalization (CONTRACT_CMD_LINES_IDENTICAL) | Evidence: harness transcript + tests/test_ubuntu_worker_deploy_authorized.py 19/19 OK | Status: PASS
- NFR-003 | Area: compatibility | Target: single-deploy flow unchanged (lock absent/self-heals); the fd renumber is local to deploy-authorized.sh (per-process fds) so update-exact.sh/rollback-exact.sh semantics are untouched; the pre-lock region of the script is byte-unchanged; the contention diagnostic format matches content's exactly (variable names/local handler style differ by design) | Validation: focus suites (tests/test_ubuntu_worker_deploy_authorized.py 14+5=19 OK; update-exact suite 37 OK) + bash -n + the 4 contract command lines byte-identical to content's under the agreed normalization | Evidence: suite transcripts + CONTRACT_CMD_LINES_IDENTICAL recorded in the durable progress file | Status: PASS
