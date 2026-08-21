# DR-007: Synchronous External Wait

Status: Accepted
Date: 2026-08-21
Issue: #248

## Context

The Delivery Orchestrator is synchronous, but active contracts allowed control to return only in a terminal interaction state. External operations such as exact-head CI can be validly pending while no safe action is executable. Treating that interval as `BLOCKED` or terminal is false, repeated reads create a planning loop, and background continuation is impossible without a scheduler.

Delivery Checkpoint v1 preserved phase and cursors but did not encode action executability or the exact predicate that resumes an external wait.

## Decision

Separate session disposition from lifecycle phase and terminal interaction state:

- `ACTIVE`: safe authorized work is executable now and must continue.
- `WAITING_EXTERNAL`: no safe action is executable now; one machine-observable transition is the sole prerequisite; return without background work.
- `TERMINAL`: exactly one of `DONE`, `BLOCKED`, or `HUMAN DECISION REQUIRED` is justified.

Delivery Checkpoint v2 is machine-readable and records action executability, session disposition, and an optional exact wait predicate. A later invocation observes the wait cursor once. Unchanged evidence preserves state and generation; changed evidence updates the cursor, increments generation, produces valid `ACTIVE` state and resumes the recorded action. Executable work and terminal conditions cannot coexist.

Persisted v1 checkpoints remain readable and are parsed/upgraded by repository tooling at the next meaningful transition without new source authorization.

## Consequences

- Pending external work no longer forces terminal misclassification or polling loops.
- The Orchestrator never promises work after a synchronous invocation ends.
- Human decisions and objective blockers cannot be hidden as waits.
- The existing three terminal interaction states remain unchanged.
- Checkpoint structure and replay are deterministic and behaviorally tested.

## Rejected alternatives

- Busy polling: repeats equivalent reads and can consume an unbounded invocation.
- `BLOCKED` for pending work: misstates an expected temporary transition.
- Terminal `WAITING_EXTERNAL`: conflates invocation handoff with task completion.
- Background continuation: no scheduler exists in the selected model.
