# Functional audit and repairs

Scope: all nine primary views, run detail, case evidence, histories, exports and
printable reports. Assessment was read-only before the requested repairs. Browser
fixtures use port 8117 and separate data; the user's port 8080 is never a fixture.

## Confirmed defects

| Finding | Root cause | Repair and regression |
| --- | --- | --- |
| Incomplete judge profiles save, then fail to start | Angular submit ignores invalid controls; Plan normalizes mode without checking dependencies | Required controls checked before HTTP; server rejects missing provider, criteria or reference fields with 422 |
| Existing incomplete profiles offer an unusable start action | List summaries omit connection and criterion links | Schema 4 backfills bounded readiness data; cards explain omissions and disable start until corrected |
| Invalid configuration echoes credential input | Catalog serializes Pydantic exception text | Structured validation issues exclude input, context and URLs; credential-echo regression |
| Missing run remains in a loading state | Null run template has no error branch | German missing-run message, retry and return navigation |
| Result input column only shows case IDs | Bounded case responses omit input while template expects it | Title/URL preview capped at 240 characters; full evidence remains on demand |
| Saving immediately after file selection fails silently | File.text completion does not trigger zoneless form refresh | Import signal blocks save until data arrives; cancelled editors ignore late file data |
| Empty OpenAPI import provides no next step | Zero operations has no feedback state | Explicit explanation of unsupported operations and document URL |
| Unauthorized Team URL presents an unusable form | Navigation permission check does not protect the page UI | Permission state and no administrative request or form for viewers |
| Disabled schedule appears as a blocked account | Shared inactive label has account wording | Separate Inaktiv schedule label |
| Token counts use English thousands separators | Angular locale remains en-US despite German UI | Bundled German locale and LOCALE_ID; a 2,200-token browser regression fails before correction |

Regression evidence before implementation: six backend tests failed because five
incomplete profiles returned 200 and validation echoed the supplied secret; two
browser tests failed because invalid forms saved and no inline error appeared.
Two migration/preview tests failed because neither summary contained the new data.
The full journey also reproduced the immediate-file-import problem before its fix.

## Verification

- Backend: 59 tests pass; Ruff check and format check pass.
- Frontend: six input-mapping unit tests pass; TypeScript no-emit check and Angular
  production build pass; Prettier check passes.
- npm audit: zero vulnerabilities; pip-audit: no known vulnerabilities.
- The new full journey passes against the built Docker image with the real API,
  SQLite, worker and DeepEval. Only external HTTP transport is simulated. It
  verifies OpenAPI and service preview, file import, criteria, credential retention
  and discovery, all provider paths and three evaluation modes, case evidence,
  CSV/JSON/report, re-evaluation, rerun, history, cancellation, schedule dependencies
  and account revocation. Each main view is sampled with axe and at 320/375px.
- Final complete browser suite: **17 passed (1.6 minutes)** against the built
  Docker image with a fresh, separate volume and the Compose security settings.
  This includes the German token-count regression. Verified image:
  `sha256:163cb95591982fac74a739501f798a1c70a1279289ec5c617a5286b86f905ded`.
- Local upgrade: the stopped volume, environment and previous image are backed
  up under ignored `artifacts/functional-audit/backup/`. Before/after counts stay
  identical: 1 account, 14 catalog entries, 29 versions, 11 runs, 132 case results.
  The fulltext service version 4 and input mapping remain unchanged. Schema 4 and
  health 200 are confirmed. The existing judge profile now selects its configured
  OPENAI provider and is stored as version 2 with an enabled start action.
- A second stopped-volume backup under `artifacts/functional-audit/backup-after-live/`
  preserves the completed live acceptance before the locale update. Counts remain
  identical across this update: 1 account, 14 catalog entries, 30 versions, 12 runs,
  137 case results. Health returns 200; no run is queued/running. The UI shows the
  retained 5/5 completed cases and judgments, and the corrected 71.666 token count.

| Verification command | Observed result |
| --- | --- |
| `uv run --project backend pytest backend/tests -q` | 59 passed in 42.52s |
| `uv run --project backend ruff check backend/app backend/tests` | All checks passed |
| `uv run --project backend ruff format --check backend/app backend/tests` | 45 files already formatted |
| `npm run test:unit` (frontend) | 6 passed |
| `npx tsc --noEmit -p tsconfig.json` (frontend) | Exit 0 |
| `npx prettier --check src tests` (frontend) | All matched files use Prettier code style |
| `npm run build` (frontend) | Exit 0; initial bundle 737.68 kB |
| `npm run test:e2e` (frontend, isolated built-image backend on 8117) | 17 passed (1.6m) |
| `docker build -t eval-expert:verification .` | Exit 0 |

Requirements checklist:

- [x] All nine primary views exercised through real application endpoints.
- [x] Reported incomplete-profile defect reproduced before correction; saving and
  readiness regressions now pass.
- [x] Imports, configuration persistence, all three evaluation modes, evidence,
  repeat runs, exports, cancellation, schedules and permissions verified.
- [x] Existing user profile repaired and its actual five-URL evaluation completed.
- [x] Local Docker upgraded with backups and retained data verified after restart.
- [x] Migration/API documentation synchronized; independent source review completed.

The prior conflict-reload fixture omitted a required threshold. It now includes
0.7, matching a valid server response; its conflict and cancellation assertions
remain unchanged. Test selectors and waits use case IDs and await completed
navigation/mutations, without changing production authentication budgets.

## Review and boundaries

Independent source review of every application change and adjacent dependencies:
zero confirmed critical, major, minor or nit findings. Schema 4 migration is
transactional and idempotent; versions, full snapshots and evidence remain intact.
An empty output pointer still selects a root scalar/list response. Imported
reference data is an object and classification comparisons need a label-bearing
reference field.

These tests establish the implemented workflows and sampled accessibility; they
do not establish universal accessibility, hosting capacity or visual absence of
advertising on the original rendered website. Hostinger deployment is not part of
this local repair. Live provider acceptance is recorded separately from simulation.

## Live acceptance

The actual existing five-URL profile was corrected through the UI, saved and
started once. The configured model is present in the provider's live model list.
The real staging extractor and direct OpenAI completed all five cases: technical
success 100%, five valid judgments, zero judge errors, source evidence supplied
in each case. Results, explanations and token counts are stored in the user's
installation. No user credentials or response bodies are published in this report.
The quality score is a judgment of the extracted text under the user's criterion,
separate from this successful technical acceptance. Live b-api credentials and
Hostinger deployment were not exercised; both b-api adapters are covered by the
real application/DeepEval test with simulated external HTTP.
