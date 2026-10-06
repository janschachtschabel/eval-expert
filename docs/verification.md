# Verification record

First delivery, verified locally on 6 October 2026 UTC / 7 October Europe/Berlin.
The application code uses the committed dependency lockfiles. Live provider credentials and user
datasets were unavailable; network tests use explicit simulated HTTP boundaries.

| Check | Evidence |
| --- | --- |
| Backend lint and format | Ruff check and format check pass |
| Backend behavior | 28 pytest tests pass under Python 3.12 |
| Frontend production build | Angular 21 build passes locally and in the Docker build |
| Browser flows against Docker | 4 Chromium/Playwright tests pass |
| Reference flow | Actual 12-case local classifier run, result tables, case dialog and CSV download |
| Configuration flows | Criteria and JSONL dataset creation; daily schedule, five future dates, persisted configuration and deletion |
| Accessibility sample | axe finds zero violations for WCAG A/AA tags on the tested result page |
| Responsive sample | Result page at 375px and 320px has no document-level horizontal overflow; tables scroll internally; logout remains reachable with a 420px viewport height |
| Delayed navigation | A delayed previous-run response cannot overwrite the current run after SPA back navigation; the regression fails before the correction |
| Local assets | Browser flow records no external font, stylesheet, script or image request |
| Production dependencies | npm audit reports 0 vulnerabilities; pip-audit reports no known vulnerabilities after the cryptography upgrade |
| Docker runtime | One container starts and serves health/API/UI as uid/gid 10001, with a read-only root filesystem and a named data volume |
| Persistence | After container restart, counts remain identical: 1 user, 10 catalog entries, 11 versions, 2 runs and 24 results |
| Observed idle memory | 154.3 MiB on the local Docker host; this is not a capacity or hosting guarantee |
| Independent review | No critical or major backend, frontend or deployment finding remains; details in review.md |
| Secret exclusion | .env and .agents/skills are ignored; credentials are not part of saved public run snapshots or exports |

## Reproduce

From backend:

```sh
uv sync --frozen
uv run ruff check app tests
uv run ruff format --check app tests
uv run pytest -q
```

From frontend:

```sh
npm ci
npx prettier --check src tests
npm run build
npx playwright install chromium
# Start the application first. Use an isolated test installation.
# EVAL_TEST_URL and EVAL_TEST_PASSWORD can override the CI defaults.
npm run test:e2e
npm audit --omit=dev --audit-level=high
```

The browser tests create synthetic demo/configuration data and delete their temporary schedule.
They must not be pointed at a production installation.

From the repository root:

```sh
python scripts/init_env.py --dev
docker compose up -d --build
docker compose ps
docker compose restart
```

The helper deliberately refuses to replace an existing .env.

## Scope and publication checks

Backend regressions cover canonical labels, missing annotations, empty sets, failed calls,
gold-label preflight, authentication/CSRF/roles, password-reset revocation, encrypted credentials,
secret redaction, request and response bounds, total network deadlines, remote schema references,
real DeepEval schema handling, missing required evidence, invalid/reasoning-only judge responses,
combined one-target-call execution, cancellation, restart recovery, comparable snapshots, cron
recovery and both Europe/Berlin daylight-saving transitions.

GitHub Actions repeats backend, frontend, browser and image-build checks after publication.
The standalone Hostinger file uses a pinned Git context; its remote-context build is checked during
publication. The GitHub check status and delivery message are the evidence for these remote checks,
rather than this local record.

OpenAI and both b-api providers still need a live acceptance run with your keys and representative
datasets. Hostinger account deployment, HTTPS ingress, large-dataset/load behavior, universal
accessibility and multiple instances have not been verified. Text-only source evidence cannot
establish the visual absence of website advertisements.
