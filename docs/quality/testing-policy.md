## Static analysis (Ruff and mypy)

The static analysis gate runs inside the `static-contract-security` domain of the merge-facing aggregate `Quality integration gate`; it adds no new workflow, no new required context and no aggregate mutation.

### Ruff

Ruff is pinned at `ruff==0.16.10` and configured by the committed `scripts/quality/ruff.toml`. The rule set is deliberately low-noise and non-mutating:

- `select = ["E9", "F"]` — syntax/runtime-level errors (E9) plus pyflakes (F: unused imports/variables, f-strings without placeholders). The default E4/E7 rule families are deferred: the legacy codebase uses a dense multi-statement style (267 findings on main for E701/E702/E401 alone), and enabling them now would require a mass rewrite that no task has requested. Line length (E501) is likewise deferred: ~300 legacy lines exceed 120 characters.
- `fix = false` — the gate is non-mutating. CI never rewrites source, locally or remotely.
- No blanket ignores: suppressions are only ever narrow — a per-file-ignore entry for a named rule or an inline `# noqa: CODE` with the specific code, each with written justification in review.

### mypy

mypy is pinned at `mypy==1.18.2` — the last release line whose dependencies are pure-Python (1.19+ requires the librt C extension; 2.x additionally requires the Rust-based `ast_serialize` parser), so the install is a pure `pip install` with no native toolchain. Version bumps are deliberate decisions with a re-run of the local battery, not silent floating pins.

The committed `scripts/quality/mypy.ini` is the progressive baseline. The global section stays permissive; per-module sections with `strict = True` are the adoption mechanism. Current strict set:

1. `scripts/quality/common.py`
2. `worker/analytics_profiles.py`
3. `worker/detection_performance.py`
4. `scripts/release/production_policy.py`
5. `scripts/ci/validate_delivery_checkpoint.py`

New small, pure, well-tested modules should be added to the strict set during code review (one `[mypy-<module>]` section each). Suppressions must be narrow — `# type: ignore[code]` with the specific error code — never blanket ignores.

### Deterministic local invocation

After `pip install ruff==0.16.10 mypy==1.18.2`, from the repository root:

```text
ruff check --config scripts/quality/ruff.toml .
mypy --config-file scripts/quality/mypy.ini scripts/quality/common.py worker/analytics_profiles.py worker/detection_performance.py scripts/release/production_policy.py scripts/ci/validate_delivery_checkpoint.py
```

Both commands must exit zero on every merge candidate; CI runs exactly these commands.
