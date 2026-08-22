# Sea Speed Workflow Overview — прозрачный процесс

**Цель:** один понятный путь `PR -> Quality -> main -> Autonomous -> Deploy` без легаси.

## Активные воркфлоу (6 файлов, 5 логических шагов)

1. **PR Validation** `.github/workflows/pr-validation.yml` (10м)
   - `pull_request` + `push main` + `workflow_dispatch`
   - Проверяет Change Contract, SDD, repo, contracts, unittest 427
   - Required check: `Repository validation`

2. **Quality integration gate** `.github/workflows/quality-integration.yml` (15м)
   - 4 независимых домена параллельно:
     - `static-contract-security`
     - `property-fuzz-reliability`
     - `exact-artifact-e2e` (build twice cmp)
     - `release-deployment-evidence` (quality-evidence.json)
   - Агрегат `quality-integration` `if: always()` — FAIL если любой домен != success
   - Required check: `quality-integration`

3. **Main Quality status publisher** `.github/workflows/main-quality-status.yml`
   - Триггер: `workflow_run Quality integration gate completed` на `main`
   - Публикует статус `sea-speed/quality-push-main` на exact SHA

4. **Autonomous runtime deployment** `.github/workflows/deploy-runtime-autonomous.yml`
   - Только `workflow_run Quality success` `push main`
   - Проверяет `fresh` (Quality SHA == current main tip)
   - `verify_source_protection.py --require-context "Repository validation" "quality-integration"`
   - `evaluate_production_policy.py` с `SEA_SPEED_PRODUCTION_DELEGATION_V1` (vars, environment: production)
   - Роутит в `deploy-vps.yml` / `deploy-ubuntu-worker.yml` только если Change Contract `REQUIRED`

5. **Deploy VPS / Deploy Ubuntu Worker** `.github/workflows/deploy-vps.yml` + `deploy-ubuntu-worker.yml`
   - `workflow_dispatch` + `workflow_call` только с `refs/heads/main`
   - Shared: `./.github/actions/verify-exact-release` (verify protection + resolve --first-parent + verify Quality + policy --require-allow)
   - VPS: `Configure SSH` -> `deploy/vps/deploy.sh`
   - Ubuntu: `Configure restricted VPS ProxyJump` (User sea-speed-deploy, ProxyJump sea-speed-vps-jump, StrictHostKeyChecking yes) -> `sea-speed-ubuntu-deploy-v1 <sha> <issue> <artifact-sha256>` -> `deploy/worker/ubuntu/deploy-authorized.sh`

## Отключены (legacy)
- `agent-hls-stabilize.yml`, `agent-hls-false-reconnect.yml`, `repair-speed-stability-branch.yml` — `disabled_manually` (были призраками в API)

## Диаграмма
```
PR --+--> PR Validation (required)
      +--> Quality gate (4 jobs + aggregate) --+--> merge main --+--> Quality (push main) --+--> Main Quality status
                                              |                 +--> PR Validation (push main)
                                              |
                                              +--> Autonomous (workflow_run) --+--> Deploy VPS (if VPS REQUIRED)
                                                                              +--> Deploy Ubuntu (if Ubuntu REQUIRED)
```

**Гарантии:** public protected main, exact Quality, first-parent, standing policy ALLOW, zero per-release approval, Operator actions 0.
