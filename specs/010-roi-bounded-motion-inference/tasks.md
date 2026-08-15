# Tasks: ROI-bounded motion and AI inference

Status: Active
Issue: #168
Specification: `specs/010-roi-bounded-motion-inference/spec.md`

- [x] Recover current `main` and confirm the approved five-file scope.
- [x] Create canonical Issue #168 and a fresh branch from exact `main`.
- [ ] Add deterministic effective-ROI processing signature and same-size polygon masking.
- [ ] Reset motion baseline/AI-active deadline when the effective ROI signature changes.
- [ ] Route motion detection through the ROI processing frame.
- [ ] Route AI inference through the same ROI processing frame without coordinate rebasing.
- [ ] Reuse the same per-frame ROI snapshot for the final detection guard.
- [ ] Remove yellow technical motion rectangles from the Worker overlay while preserving AI detection boxes/labels.
- [ ] Add focused ROI-pipeline tests for mask/full-frame fallback, reset semantics, processing order and overlay ownership.
- [ ] Verify the exact changed-file set remains limited to the approved five paths.
- [ ] Open a PR with a valid Change Contract and specification link.
- [ ] Obtain PR Validation and Quality integration success on the exact PR head.
- [ ] Merge with expected-head protection after fresh main/head/scope/review checks.
- [ ] Verify post-merge exact-SHA quality gates.
- [ ] Request separate exact-SHA production authorization for the Ubuntu Worker contour.
- [ ] Deploy through the repo-owned exact Worker updater using one largest-safe operator step.
- [ ] Record sustained Worker runtime and operator-visible acceptance evidence, then close Issue #168.
