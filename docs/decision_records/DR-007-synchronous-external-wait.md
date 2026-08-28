# DR-007: Synchronous External Wait

Status: Accepted
Date: 2026-08-21
Issue: #248
Amended: 2026-08-28 through continuation Issue #337

## Context

The Delivery Orchestrator is synchronous, but active contracts allowed control to return only in a terminal interaction state. External operations such as a non-CI machine-observable transition can be validly pending while no safe action is executable. Treating that interval as `BLOCKED` or terminal is false, repeated reads create a planning loop, and background continuation is impossible without a scheduler.

A known GitHub Actions run or check that is `queued` or `in_progress` is different: the Orchestrator can observe the exact run/check cursor through the official Connector and should remain `ACTIVE` with foreground rate-limited observation rather than returning `WAITING_EXTERNAL`, because the pending state is deterministic and observable within the same synchronous invocation.

Delivery Checkpoint v1 preserved phase and cursors but did not encode action executability or the exact predicate that resumes an external wait.

## Decision

Separate session disposition from lifecycle phase and terminal interaction state:

- `ACTIVE`: safe authorized work is executable now and must continue.
- `WAITING_EXTERNAL`: no safe action is executable now; one non-CI machine-observable transition is the sole prerequisite; return without background work.
- `TERMINAL`: exactly one of `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED` is justified.

A known GitHub Actions run or check that is `queued` or `in_progress` is never represented as `WAITING_EXTERNAL`. The invocation remains `ACTIVE`, foreground-waits, and re-observes only the exact run/check cursor through the official Connector at least 30 seconds after the previous equivalent status observation, with no observation count or deadline that itself hands control back, no busy/tight polling, and no checkpoint-generation churn per observation. Success continues automatically to the next gate; failure immediately narrows to failed job/log remediation. A Connector/provider capability outage that prevents this observation is `BLOCKED` or `HUMAN DECISION REQUIRED`, not CI pending.

Delivery Checkpoint v2 is machine-readable and records action executability, session disposition, and an optional exact wait predicate. A later invocation observes the non-CI wait cursor once. Unchanged evidence preserves state and generation; changed evidence updates the cursor, increments generation, produces valid `ACTIVE` state and resumes the recorded action. Executable work and terminal conditions cannot coexist.

Persisted v1 checkpoints remain readable and are parsed/upgraded by repository tooling at the next meaningful transition without new source authorization.

## Consequences

- Pending non-CI external work no longer forces terminal misclassification or polling loops.
- CI pending is handled with foreground rate-limited exact-cursor observation without returning `WAITING_EXTERNAL`.
- The Orchestrator never promises work after a synchronous invocation ends for a non-CI wait.
- Human decisions and objective blockers cannot be hidden as waits.
- The existing three terminal interaction states remain unchanged.
- Checkpoint structure and replay are deterministic and behaviorally tested.

## Rejected alternatives

- Busy polling: repeats equivalent reads and can consume an unbounded invocation.
- `BLOCKED` for pending work: misstates an expected temporary transition.
- Terminal `WAITING_EXTERNAL`: conflates invocation handoff with task completion.
- Background continuation: no scheduler exists in the selected model.
- Returning `WAITING_EXTERNAL` for a known queued/running GitHub Actions run: would hand control back for a deterministic transient state that the Connector can observe directly.
