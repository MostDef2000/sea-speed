# MediaMTX Compatibility Remediation for Camera 1

Status: repository source only until merge, exact quality evidence, and a separate production approval.

## Why this exists

Issue #87 has already proven the new camera path through the Ubuntu relay. The remaining production failure is narrower than network reachability or authorization:

```text
new physical camera -> Ubuntu relay -> VPS host media probe = PASS
new physical camera -> Ubuntu relay -> VPS MediaMTX canonical source = FAIL
```

The bounded cross-host investigation classified the failure as `E_RTSP_HANDSHAKE_COMPATIBILITY` and the required action class as a MediaMTX version or compatibility change. The VPS service and an `ffprobe` process running as the same `mediamtx` user share the same network namespace and both can reach and decode the credential-free relay. Ubuntu observes the VPS reader and accepts it. The configured `sourceOnDemandStartTimeout` is longer than the observed direct time to first media. This excludes service-user networking, a separate service namespace, Ubuntu reader authorization, and the configured on-demand timeout as the confirmed blocker.

This remediation therefore does not widen relay access and does not change the Camera 1 source URL. It provides a fail-closed way to prove a candidate MediaMTX build against the real relay before the production executable is replaced.

The first official `v1.20.0` canary exposed a separate startup defect in the synthetic canary config. The candidate accepted the config, including the legacy unquoted YAML booleans `yes` and `no`, and opened the loopback RTSP and HLS listeners. It then enabled Media-over-QUIC from its default settings, attempted to generate `auto.key` and `auto.crt`, and exited because the non-root service identity could not write them. The canary now explicitly disables MoQ and every other unused server instead of relying on version-specific defaults.

## Components

- `deploy/vps/mediamtx-compatibility-remediation.sh` performs a loopback-only compatibility canary and, only after that canary succeeds, a digest-bound production binary replacement.
- `deploy/vps/camera-source-switch.sh` remains responsible for the existing canonical `cam1` config contract and the gated removal of `cam1-new`.
- `docs/operations/CAMERA1_LIVE_REPLACEMENT.md` remains the base live-source runbook; this document is the compatibility-remediation supplement for the confirmed source-pull blocker.

## Candidate provenance

The candidate must be an official `bluenviron/mediamtx` release for the VPS architecture. OpenCode must obtain the release archive and the corresponding upstream `checksums.sha256` from the official release, verify the archive checksum before invoking repository tooling, and record the exact release version and archive SHA-256 in sanitized rollout evidence.

The repository script independently requires the approved archive SHA-256 and refuses a mismatch. It extracts only the `mediamtx` executable, computes a separate binary SHA-256, and verifies the exact requested version inside a bounded transient systemd sandbox. Candidate code is never invoked directly as root.

Do not use a mutable package repository, an unverified mirror, a locally rebuilt binary, or a release artifact whose checksum has not been verified.

## Loopback-only compatibility canary

Preparation is intentionally not a production binary replacement.

Example shape:

```text
mediamtx-compatibility-remediation.sh prepare \
  --config /etc/mediamtx/mediamtx.yml \
  --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 \
  --candidate-archive <verified-official-release-archive> \
  --candidate-version <exact-version> \
  --expected-archive-sha256 <approved-upstream-sha256>
```

The script requires the existing production MediaMTX service to be active, the installed binary and config to be root-owned beneath protected canonical paths, and the config to remain readable only by root and its service group. It derives the existing non-root MediaMTX service identity and applies that exact user and group to every candidate transient unit.

The canary binds only to loopback:

```text
RTSP 127.0.0.1:18954
HLS  127.0.0.1:18888
```

Unused servers (`api`, `metrics`, `pprof`, `playback`, RTMP, WebRTC, SRT and MoQ) are disabled, RTSP listening is TCP-only, and the candidate pulls the same credential-free private Ubuntu relay with `sourceOnDemand: yes` and `rtspTransport: tcp`. MediaMTX `v1.20.0` explicitly supports these legacy YAML boolean literals; the startup failure was caused by the omitted MoQ disable, not boolean parsing.

The canary uses the `fmp4` HLS variant because the relay's proven H265 track is not supported by MediaMTX's MPEG-TS HLS variant. HLS probes use MediaMTX's same-origin `cookieCheck=1` playlist form so the intentional cookie-capability redirect cannot be mistaken for a media playlist. The configured base URL must remain loopback HTTP with no userinfo, query or fragment, and success still requires decoded frames rather than an HTTP status alone.

Before opening canary listeners, preparation copies the protected active production config to a root-controlled snapshot and verifies that the source and snapshot digests match. It also proves that canonical `cam1` uses the requested relay, `sourceOnDemand: yes` and `rtspTransport: tcp`, that the canonical HLS probe port matches the configured HLS listener, and that the effective HLS variant is `fmp4` or `lowLatency`. An explicit `mpegts` production HLS variant is rejected before binary replacement because the proven Camera 1 upstream video is H265 and MediaMTX MPEG-TS HLS supports H264 video only. It runs the candidate against those exact bytes, with no MediaMTX configuration overrides, as the production service identity in a transient systemd sandbox. The sandbox clears the inherited environment, uses private user, network, IPC, device and temporary namespaces, exposes the host filesystem read-only except for the dedicated runtime, and denies execution of every host binary except the candidate launcher and candidate itself. Configured hooks therefore cannot execute host commands, while version defaults such as MoQ are still exercised. The candidate must remain active across a bounded startup window before the unit is stopped and verified inactive. This is startup/resource compatibility; hooks and source traffic are not functionally exercised by the active-config phase.

The media canary uses the same filesystem, user-namespace, resource and execution restrictions in its own transient cgroup. It uses the host network only because it must expose loopback listeners and read the real relay; systemd egress policy denies every destination except loopback and the exact RFC1918 relay address. Every candidate process remains in the transient cgroup, `KillMode=control-group` applies, and cleanup verifies the unit is inactive before publishing a marker or deleting runtime files.

The supported service contract is deliberately narrow: the production unit must directly execute the expected binary and config as an explicit non-root identity, with no environment entries, environment files, drop-ins, supplementary groups, dynamic user, alternate root, PAM integration, lifecycle commands or alternate working directory. The loaded unit must not require `daemon-reload`. Preparation hashes the effective execution fields and protected unit fragment. The host must provide systemd 247 or newer and the namespace, cgroup and IP-accounting features required by the transient units; unsupported isolation is a clean stop before any production mutation.

A canary passes only when it produces actual video through both its local RTSP output and its local HLS output. Static config parsing, TCP reachability, or a process staying alive are not sufficient. Startup readiness is based on candidate process state and both loopback listeners instead of a fixed sleep. The production MediaMTX executable is not replaced and the production service is not restarted during this phase.

Successful preparation records a root-only marker bound to:

- candidate binary SHA-256;
- candidate version;
- verified release archive SHA-256;
- current installed MediaMTX binary SHA-256;
- current active MediaMTX config SHA-256;
- current supported systemd service-contract SHA-256;
- current compatibility-remediation tool SHA-256;
- exact credential-free relay URL and canonical loopback HLS URL;
- a successful sandboxed active-config compatibility proof.

If the installed binary, active config, supported service contract or remediation tool changes after the canary, activation refuses to continue and a new canary is required. The marker is written to a root-only temporary file and atomically renamed only after both media proofs pass.

If the sandboxed check or media canary fails, the raw candidate log is copied to the root-only compatibility diagnostics directory with mode `0600` before the temporary runtime is removed. Command output contains only a bounded failure category, sanitized reason code and protected log path; it does not dump the config, environment or raw log. Interruption and all failure exits stop the complete transient cgroup before removing the runtime directory.

## Production binary activation

Activation requires the exact candidate binary SHA-256 returned by successful preparation:

```text
mediamtx-compatibility-remediation.sh activate \
  --config /etc/mediamtx/mediamtx.yml \
  --relay-url rtsp://<ubuntu-private-ip>:8554/cam1 \
  --expected-candidate-sha256 <canary-approved-binary-sha256>
```

Activation does not edit the MediaMTX YAML. It:

1. revalidates the marker, relay/HLS contract, config, binary, service contract and tool identities;
2. creates and digest-verifies a root-only backup of the current MediaMTX executable;
3. atomically records a `prepared` durable activation phase;
4. preserves the installed executable owner, group and mode and rechecks every mutable boundary;
5. atomically replaces only the executable and records `binary_replaced`;
6. restarts only `mediamtx.service`;
7. verifies the service `MainPID` executable and SHA-256 through `/proc` without executing the installed candidate as root;
8. retries until actual advancing video is available from existing VPS-local canonical HLS at `http://127.0.0.1:8888/cam1/index.m3u8`;
9. records `complete` only after all runtime proof succeeds.

If service restart, running-process digest verification, or canonical HLS media fails after replacement, the script stops and reports the preserved binary backup. Interruption preserves the durable phase and removes only an unrenamed `.next` file. Re-running the same digest safely resumes `prepared` or `binary_replaced`, while a completed activation is revalidated without another restart. Automatic rollback remains prohibited; rollback is a separate governed decision.

The script never starts, stops, restarts or enables `sea-speed-worker.service`.

## One final Camera 1 completion scope

After this source is merged and a production approval covers the exact candidate artifact and final Issue #87 completion, the remaining work is designed to run as one OpenCode rollout scope rather than a chain of micro-diagnostics.

The scope should:

1. verify `sea-speed-worker.service` is inactive and `sea-speed-stream.service` is active;
2. verify the Ubuntu relay still produces advancing media from the VPS;
3. download one approved official MediaMTX candidate archive and its official checksum evidence;
4. prove the candidate can start from an unchanged active-config snapshot with its real defaults in the transient systemd sandbox, then run the loopback-only compatibility canary;
5. stop without production binary mutation if the canary fails;
6. if the canary passes, activate exactly the canary-approved binary digest;
7. prove canonical VPS-local HLS produces advancing media;
8. prove the existing unauthenticated public request still receives the expected Basic Auth challenge and that `/cams/hls/cam1/index.m3u8` is unchanged;
9. pause for human visual acceptance on `mostdef.ru` and require the exact text `CONFIRM_NEW_CAMERA` only when the new physical camera is visibly moving and the AI worker remains offline;
10. only after that confirmation, use the existing `camera-source-switch.sh prepare-cleanup` and `activate-cleanup` flow to retire `cam1-new`;
11. re-prove canonical HLS, public boundary, AI-worker-off state, secret safety and preserved backups.

If the failed pre-merge canary left the exact approved candidate binary in compatibility state, the post-merge rollout may reuse only that same digest after verifying its root ownership, mode and SHA-256. It must not select a second candidate, accept a conflicting marker, or activate a marker created by pre-fix source. The corrected merged `prepare` must create a new marker containing the active-config compatibility proof before activation is possible.

The post-merge Windows/VPS orchestration must be regenerated from the corrected merged source and its new tool digest. It must require `ACTIVE_CONFIG_COMPATIBILITY=PASS` together with both media proofs, and on failure it may propagate only `CANARY_FAILURE_CATEGORY`, `CANARY_FAILURE_REASON` and the protected `CANARY_FAILURE_LOG` path. A pre-fix helper or source archive must not be reused for activation.

A failed canary is a clean stop before production binary replacement. A failure after binary replacement preserves the current runtime state, durable activation phase and all backups, allowing the exact activation to resume or return for an explicit rollback decision. No speculative config edits, network changes, nginx changes, credential changes, Ubuntu relay mutations or AI worker mutations are part of this flow.

## Ubuntu Worker relay API profile

The Ubuntu Worker MediaMTX service is loaded by `sea-speed-stream.service` from
`/etc/mediamtx/mediamtx.yml` (not the shared runtime config copy). The relay API
profile on that host is deliberately narrower than the canary profile above and
contains one exception to the "unused servers disabled" line:

```yaml
api: yes
apiAddress: "127.0.0.1:9997"
authInternalUsers:
  - user: any
    ips: [127.0.0.1]
    permissions:
      - action: api
```

This `api` enablement is a deliberate exception to the "unused servers disabled"
profile line: its only purpose is local freshness-watchdog observation. The
`sea-speed-camera1-h264-freshness.timer` watchdog reads
`GET /v3/paths/get/{name}` on the loopback API and proves producer liveness by
requiring `ready` and `available` to be true and `inboundBytes` to strictly grow
between two samples (`readyTime` is the path start time, not frame age, and
MediaMTX v1.19.1 exposes no `lastFrameTime`).

Mitigation: the API binds loopback only — verified via `ss` as a listener on
`127.0.0.1:9997` alone — and no proxy tuple forwards port 9997, so the endpoint
is unreachable from outside the worker host. The watchdog observation uses no
credentials and the `api` permission is restricted to loopback source IPs.

### Foreign-rule sanitize runbook (issue #436)

The #407 on-box activation left a foreign UNMARKED `authInternalUsers` entry
(hand-added during the 2026-10-07 manual edit) whose scope exactly equals the
canonical loopback API rule above. It is inert (same loopback scope, verified
green) but re-renders preserve it forever: the canonical verifier is
marker-anchored and merges `ips`/`actions` across its span, so an unmarked
duplicate is invisible to it. The canonical tool now ships a bounded sanitize
transaction (`camera-relay.sh sanitize`, renderer mode
`ubuntu-sanitize-auth`):

- Scope: removes ONLY foreign (unmarked, i.e. not preceded by a canonical
  `# Sea Speed ` marker comment) `authInternalUsers` rules whose scope EXACTLY
  equals the canonical loopback API rule (`ips == ["127.0.0.1"]`,
  `permissions == [- action: api]`, fully modeled fields). ANY other foreign
  rule fails the whole transaction closed: the offending scope is reported on
  stderr, nothing is deleted, the candidate is not written, exit is nonzero.
- Verify-before/verify-after: the canonical marked loopback API rule and the
  reader rules are re-verified (`verify-reader-auth` on the LIVE config before
  the render and on the CANDIDATE after it; the renderer mode verifies the
  marked API rule on both), and the foreign-rule count is asserted == 0
  explicitly after the prune with a dedicated per-entry scanner (NOT the
  span-merge verify).
- Transaction shape (one bounded on-box transaction, run as root per the
  `camera-relay.sh` gating — the script refuses non-root; no chroot copy of
  the repo exists on the worker, run it from the exact deployed repository
  source):

  1. `camera-relay.sh sanitize --config /etc/mediamtx/mediamtx.yml --private-rtsp-address <RFC1918 IPv4:PORT> --reader-ip <VPS reader IP>` —
     renders the pruned candidate into the root-only state root and prints
     `SANITIZED_FOREIGN_AUTH=YES` plus `CANDIDATE_SHA256=<digest>`.
  2. `camera-relay.sh activate --config /etc/mediamtx/mediamtx.yml --private-rtsp-address <same> --reader-ip <same> --expected-sha256 <digest>` —
     the existing digest-bound runbook, reused unchanged: digest/mode checks,
     reader verify on the candidate, AI-worker-stopped gate, root-only
     timestamped backup, atomic install, `systemctl restart` of the relay
     service, private-listener probe. Automatic rollback is not authorized;
     the backup path is printed for an explicit rollback decision.
  3. Verify: `camera-relay.sh status` and a re-run of `sanitize` must report
     `foreign_rules_removed=0` (idempotent no-op).

- The AI worker is never started, stopped, restarted or enabled by this flow;
  secrets are never displayed (`SECRETS_DISPLAYED=NO`). A failed sanitize
  leaves the previous candidate untouched and it must not be activated.

### Relay service identity derivation (issue #447)

The 2026-10-10 on-box activate under docker-chroot: `systemctl show -p User`
returned empty (no system bus) and the script silently installed the config
root:root 0600 instead of the service's root:mediamtx 0640; mediamtx
crash-looped ~100 s until the operator hand-fixed ownership. Activate now
derives the service identity fail-closed, BEFORE any mutation (the
derivation precedes the root-only backup, which is itself a state-dir
mutation):

1. `systemctl show -p User -p Group <unit>` — definitive only when `User=`
   is non-empty (an empty answer under chroot means "unknown", never "root").
2. Fallback: `systemctl cat <unit>` (offline-safe; the unit file is on disk
   even under chroot) — the LAST `User=`/`Group=` assignment wins (systemd
   override semantics); `User=` absent or empty means the unit runs as root
   (root:root 0600); a non-root user installs root:<group> 0640, with
   `id -gn` resolving a missing Group.
3. Both derivations failing → `ERROR relay service identity could not be
   derived (systemctl unavailable and unit file unreadable); refusing to
   install with guessed ownership` and a nonzero exit BEFORE the backup or
   install — a wrong guess can never be silently installed.

On the success path the intended ownership is evidenced before the install:
`INSTALL_OWNER=<owner>:<group>` and `MODE=<mode>` — a wrong derivation is
visible in the transcript even when a later restart step fails.

### Declared-prune sanitize runbook (issue #444)

The 2026-10-10 operator sanitize retry failed closed as designed: besides the
target loopback-API duplicate, the live config carries two UNMARKED legacy
`authInternalUsers` rules for the dead `cam1-test` path (ips
`["10.123.239.102"]` with actions `publish, read`; ips `["10.123.239.101"]`
with action `read`). Repository evidence: `cam1-test` is dead legacy (its only
repository reference is a source-URL comment in a test fixture). #444 adds
repeatable explicit opt-in prune declarations to the same sanitize
transaction — retirement stays canonical and auditable, with no manual config
edits:

- Declaration grammar (repeatable `--prune-declared SPEC`, one per legacy
  rule): `path=NAME,ips=IPv4[,IPv4...],actions=read|publish|api[, ...]` —
  comma-separated; a bare token continues the previous key. Exactly one
  `path=`, at least one ip and at least one action are required; unknown
  keys, invalid ips, actions outside the renderer vocabulary
  {read, publish, api} and duplicate `path=` fail the transaction closed.
- Scope: a declared triple makes ONLY unmarked rules whose parsed
  (permission-path set, ips set, actions set) equals the declaration exactly
  removable — a partial match (same path, different ip; extra ip; extra
  action) is undeclared foreign scope and still refuses the whole
  transaction. Marked `# Sea Speed ` rules are never removed, even on an
  exact triple match. WITHOUT declarations the behavior is byte-for-byte the
  #436 fail-closed default above.
- Evidence: the renderer prints one `DECLARED_PRUNED path=... removed=N`
  line per declaration; the shell aggregates them into
  `DECLARED_PRUNED=path=cam1-test:removed=1,...` alongside
  `SANITIZED_FOREIGN_AUTH=YES` and the digest. The loopback-API duplicate
  still rides the default #436 scope and is counted in
  `foreign_rules_removed` only.
- Idempotency: re-running the same transaction on the sanitized config is a
  no-op (`foreign_rules_removed=0`, per-declaration `removed=0`, candidate
  byte-identical to the live config).
- Operator retry window (issue #444 relay context; live config
  `/etc/mediamtx/mediamtx.yml`, private-rtsp-address `10.123.239.102:8554`,
  reader-ip `10.123.239.101` — note the reader IP equals the second legacy
  rule's IP, which is why declarations match on the full path+ips+actions
  triple):
  1. Stop the AI worker (`systemctl stop sea-speed-worker` — the worker is
     operator-managed; the relay tooling never controls it).
  2. `camera-relay.sh sanitize --config /etc/mediamtx/mediamtx.yml --private-rtsp-address 10.123.239.102:8554 --reader-ip 10.123.239.101 --prune-declared "path=cam1-test,ips=10.123.239.102,actions=publish,read" --prune-declared "path=cam1-test,ips=10.123.239.101,actions=read"` —
     both legacy rules removed, `DECLARED_PRUNED=path=cam1-test:removed=1,path=cam1-test:removed=1`,
     `SANITIZED_FOREIGN_AUTH=YES`, `CANDIDATE_SHA256=<digest>`.
  3. `camera-relay.sh activate --config /etc/mediamtx/mediamtx.yml --private-rtsp-address 10.123.239.102:8554 --reader-ip 10.123.239.101 --expected-sha256 <digest>` —
     the unchanged digest-bound runbook (backup, atomic install, relay
     restart, listener probe; automatic rollback is not authorized).
  4. Start the AI worker (`systemctl start sea-speed-worker`).
  5. Remediate verify: `camera-relay.sh status`, a re-run of `sanitize` with
     the same declarations (`foreign_rules_removed=0`, no-op), and the #437
     reader-rule remediate check to confirm the canonical reader rules
     survived the transaction byte-identically.

### Reader-rule remediate runbook (issue #437)

During the #372 operator verification (2026-10-09) the canonical tool
correctly REFUSED a prepare-only re-render of a drifted cam1 reader rule
(fail-closed against widening via the `ensure_internal_reader_rule` byte-exact
guard). The refusal is right; the gap was process: no repo-owned path
converged a DRIFTED live reader rule back to canonical while PRESERVING the
live rule's current scopes. The canonical tool now ships a bounded remediate
transaction (`camera-relay.sh remediate`, renderer mode
`ubuntu-remediate-reader`):

- Scope: locates the canonical `# Sea Speed least-privilege reader` marker
  block for the path, reuses `_parse_rule_block` to extract the LIVE
  ips/actions, re-authorizes every scope element through the existing
  validators (`validate_peer_reader_ip` then `validate_reader_ip` — the relay
  profile renders reader IPs as literal RFC1918 IPv4), and re-emits the
  canonical block via `_reader_rule_lines` preserving the live scopes.
  Hand-edited FORM drift (missing `pass:` field, block-style or reordered
  ips, unquoted values) converges to the exact block a fresh `ubuntu-relay`
  render would produce for the same scopes.
- Fail-closed: ANY unauthorized scope refuses the whole transaction —
  non-IPv4, loopback, link-local, multicast, reserved, public or duplicate
  ips; actions outside {read, publish}; `publish` on the read-only cam1
  relay profile (publisher roles cannot be recovered from a flat live ips
  list). A merged span (foreign unmarked entry between the drifted block and
  the next reader marker) also fails closed: run the #436 sanitize first.
  The offending scope is reported on stderr, nothing is replaced, the
  candidate is not written, exit is nonzero.
- Verify-before/verify-after: `verify-reader-auth` runs on the LIVE config
  before the render (the drifted rule must still authorize the
  operator-stated reader IPs) and on the CANDIDATE after it; the renderer
  mode verifies the marked loopback API rule before and after, and asserts
  byte-exact `ensure_internal_reader_rule` idempotency on the result.
- Transaction shape (one bounded on-box transaction, run as root per the
  `camera-relay.sh` gating):

  1. `camera-relay.sh remediate --config /etc/mediamtx/mediamtx.yml --private-rtsp-address <RFC1918 IPv4:PORT> --reader-ip <VPS reader IP>` —
     renders the converged candidate into the root-only state root and prints
     `REMEDIATED_READER=YES`, `REMEDIATION_NEEDED=YES|NO` plus
     `CANDIDATE_SHA256=<digest>`.
  2. `camera-relay.sh activate --config /etc/mediamtx/mediamtx.yml --private-rtsp-address <same> --reader-ip <same> --expected-sha256 <digest>` —
     the existing digest-bound runbook, reused unchanged: digest/mode checks,
     reader verify on the candidate, AI-worker-stopped gate, root-only
     timestamped backup, atomic install, `systemctl restart` of the relay
     service, private-listener probe. Automatic rollback is not authorized;
     the backup path is printed for an explicit rollback decision.
  3. Verify: `camera-relay.sh status` and a re-run of `remediate` must report
     `REMEDIATION_NEEDED=NO` (idempotent no-op whose candidate is
     byte-identical to the live config).

- The AI worker is never started, stopped, restarted or enabled by this flow;
  secrets are never displayed (`SECRETS_DISPLAYED=NO`). A failed remediate
  leaves the previous candidate untouched and it must not be activated.

## Acceptance boundary

Issue #87 is complete only when all of the following are proven at runtime:

- the new physical camera is visible and moving at the existing Camera 1 position on `mostdef.ru`;
- public identity remains `/cams/hls/cam1/index.m3u8`;
- canonical VPS `cam1` still uses the credential-free Ubuntu relay with `sourceOnDemand: yes` and `rtspTransport: tcp`;
- VPS-local canonical HLS produces advancing media under the active production MediaMTX binary;
- `cam1-new` has been removed only after human confirmation;
- `sea-speed-worker.service` remains inactive during clean-live acceptance;
- camera credentials are not copied to the VPS or exposed in argv, logs, reports or browser-visible URLs;
- the previous MediaMTX binary backup and existing config backups remain preserved;
- no automatic rollback occurred.
