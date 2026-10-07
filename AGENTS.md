# Eval Expert

## Architecture and constraints

Angular 21 / Material 3 and FastAPI serve one shared team from one Docker image.
Keep SQLite WAL and a single worker/process. Reference metrics use scikit-learn;
qualitative assessment uses DeepEval. No additional evaluation platforms are needed.
All browser assets and fonts remain local. UI copy uses the German i18n dictionary.
Credentials use the separate encrypted field and never belong in public configuration.

## Workflow

Use better-coding-workflow for implementation, test a reported defect before fixing
it, and keep logical fixes in separate commits. Follow the approved audit correction
plan in docs/plans/2026-10-07-audit-remediation.md. Update migration/API documentation
with changes. Test installations use separate data directories; never run browser
fixtures against the user's container on port 8080.

## Commands

- Backend: uv run --project backend pytest backend/tests -q
- Backend lint: uv run --project backend ruff check backend/app backend/tests
- Backend format: uv run --project backend ruff format backend/app backend/tests
- Frontend build: npm run build (frontend directory)
- Browser tests: npm run test:e2e (frontend directory; isolated backend on 8117)
- Frontend format: npx prettier --check src tests (frontend directory)
- Deployment: docker build -t eval-expert:verification .

Keep preview-2026-10-06 immutable. Changes go to the existing feature branch and PR.
