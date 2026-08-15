# Tasks: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Delivery tasks

- [x] Confirm latest `main` and failed production evidence.
- [x] Record fresh `OUTCOME APPROVED` scope on Issue #159.
- [x] Create bounded source branch from exact `main`.
- [x] Add persistent YOLO inference child with framed local IPC.
- [x] Preserve `model.track(... persist=True ...)`, tracker selection, detection
      shape, and vehicle allow-list.
- [x] Add explicit CUDA device selection and inference deadline.
- [x] Add child restart/backoff so inference failure returns control to the
      media/state loop.
- [x] Add two-step startup inference progression and tracker reset.
- [x] Extend non-secret heartbeat with AI readiness/progression counters.
- [x] Strengthen exact activation verifier with AI startup progression.
- [x] Add focused source/behavioral contract tests.
- [ ] Open PR with exact Change Contract.
- [ ] Pass PR Validation, Quality integration, and Worker package gates.
- [ ] Merge exact green head and pass post-merge gates.
- [ ] Obtain fresh exact-SHA production authorization.
- [ ] Run Worker exact activation and browser/runtime acceptance.
- [ ] Deploy VPS/frontend on the same accepted SHA and close Issue #159 with
      production evidence.

## Completion gate

Source work is complete only when the exact PR head is green and merged, and the
merged SHA has fresh post-merge gates. Production remains incomplete until the
same exact SHA passes Worker activation/runtime acceptance and the Issue #159
VPS/frontend acceptance after separate production authorization.
