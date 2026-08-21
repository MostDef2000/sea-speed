# Sea Speed Execution Cursor Protocol

Version: 1.0.0
Status: Proposed

## Purpose

Define the runtime control layer between approved delivery scope and repository mutation.

The Delivery Orchestrator must not replace execution with status narration after a valid source admission.

## Execution invariant

After:

```text
OUTCOME APPROVED
+ valid checkpoint
+ branch available
+ no hard blocker
```

the next transition MUST be execution of the recorded cursor action.

Forbidden transitions:

```text
IMPLEMENTING -> STATUS REPORT ONLY
IMPLEMENTING -> NEW APPROVAL REQUEST
IMPLEMENTING -> FULL RECOVERY
```

unless a terminal blocker exists.

## Execution Cursor

The canonical delivery checkpoint should resolve to one bounded action:

```yaml
execution_cursor:
  task: <canonical issue>
  phase: IMPLEMENTING
  action_id: <monotonic id>

  operation:
    type: MODIFY_FILE
    target:
      - <repository path>

  expected_artifact:
    type: COMMIT

  validation_required:
    - syntax
    - tests
    - scope verification

  stop_conditions:
    - scope violation
    - missing permission
    - failed mandatory validation
```

## State transitions

```text
READY_FOR_IMPLEMENTATION
        |
        v
EXECUTION_LOCKED
        |
        v
IMPLEMENTING
        |
        v
VALIDATING
        |
        v
CHECKPOINTED
```

`EXECUTION_LOCKED` means authorization has been consumed for the bounded implementation scope and the orchestrator must continue until a terminal interaction state.

## Blocker classification

Hard blockers only:

- repository access failure;
- permission denial;
- approved scope violation;
- mandatory validation failure;
- missing protected input.

Uncertainty about implementation details is not a blocker. Choose the smallest reversible implementation and record the decision.

## Connector loop guard

Repeated reads are invalid when:

- the object identity is unchanged;
- the evidence cursor is unchanged;
- the question is unchanged;
- no mandatory gate requires freshness.

A read must advance execution, validate a gate, or resolve an evidence gap.

## Completion rule

Intermediate execution states do not return control while a safe authorized next action exists.

Valid terminal states remain:

```text
DONE
BLOCKED
HUMAN DECISION REQUIRED
```
