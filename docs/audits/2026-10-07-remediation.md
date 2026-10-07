# Audit remediation verification — 2026-10-07

All 13 confirmed findings from [the original audit](2026-10-07-audit.md) have
been addressed and regression-verified. The original audit describes ea703bc;
this report records the corrections on `codex/first-version` through 09e8d0a.
The original 67/100 score is historical, not a fresh score of the corrected app.

The work used better-coding-workflow, test-first reproductions, focused commits,
an independent source review, and fresh verification. It retains Angular 21,
FastAPI, SQLite WAL, one process/worker and one Docker image. No additional
evaluation platform, database or queue service was introduced.

## Finding closure

| ID | Correction | Verification |
| --- | --- | --- |
| SEC-01 · High | Separate synchronized IP/account login budgets, bounded TTL/LRU storage and four concurrent password verifications | Rotating-name/IP and capacity/expiry regressions in `test_audit_security.py`; existing login/session tests retained |
| SEC-02 · Medium | Reject configured auth headers in plaintext public headers; scrub legacy catalog/history/snapshots and retain credentials encrypted | Case-insensitive custom-header tests and automatic legacy credential migration; v1 upgrade and actual Docker restore preserve encrypted credentials |
| COR-01 · High | QueueFull leaves the due time unchanged; records a retry reason; schedule keys retain enqueue idempotency | Queue saturation/catch-up regression in `test_audit_integrity.py`; schedule UI shows last error and next due |
| COR-02 · Medium | Preserve raw schema-invalid output; validate fields separately; retain valid fields; reassess stored responses after mapping repair | `test_audit_evidence.py`, execution and combined reference/GEval regressions |
| DB-01 · Medium | Expected-version check and save inside one immediate transaction; stale PUT yields 409 | Two-client stale-save regression and browser conflict/reload flow; typed form data stays visible |
| DB-02 · Medium | Validate dependencies and block deletion of referenced catalog records transactionally | Missing-reference/referenced-delete regressions; historical run snapshots remain readable |
| API-01 · Medium | Malformed CSV/start/schedule inputs yield 422; missing recompute yields 404; CSV cells follow the 5 MB upload limit | Four malformed-request regressions; valid 150k-character CSV cell succeeds; parser errors map to client errors |
| PERF-01 · High | Persist small catalog/run/case/aggregate read models; page history, cases and label scores; status omits configuration/results; stream complete exports; cap evidence at 50 MB/run | 205-run history reaches records beyond 200; 60-case pages and complete export; 10,000-label views stay below 20 KB in the regression fixture; atomic storage-limit test |
| PERF-02 · Medium | Incremental counters replace repeated class-by-case scans; worker no longer retains all result bodies; aggregation runs in a thread | Metric conventions and label-budget regressions; same-process legacy/current benchmark with identical complete metrics |
| OPS-01 · Medium | Bounded worker recovery, degraded health and process exit after persistent failure | Supervisor regressions plus actual Docker fault injection: exit code 1, automatic restart, preserved export and backup/restore |
| DEP-01 · Medium | Angular CLI 21.2.26 uses MCP SDK 1.31.0; full npm and Python audits added to CI | Full npm audit, production npm audit and pip-audit: zero known vulnerabilities; builds succeed |
| TEST-01 · Medium | Ignore demo completion after leaving its page; await demo navigation in the schedule test; wait for startup readiness; separate audit test account within login budgets | Deterministically held demo response; existing schedule/reference flows and all 11 browser tests pass |
| UX-01 · Low | Reachable mobile close button and Escape; return focus to the navigation opener | Keyboard/focus browser regression at 375px; existing 320px/375px responsiveness and axe scan pass |

All listed findings are closed in the tested implementation. This is a technical
remediation verdict, not universal production/hosting or LLM quality certification.

## Review corrections and preserved behavior

Independent review found a remaining large-summary read path and two async races
in the draft corrections. These were reproduced and fixed before closure:

- Aggregate summaries are persisted separately. Trimming already-loaded class
  tables would not have addressed database-read memory. Label scores load 50 at
  a time; full class tables remain in JSON exports.
- Late save/detail responses cannot clear a newer editor or reopen a cancelled
  one. Cancellation and requests share a generation guard.
- When two case-page responses are delayed while a run advances from 51 to 52
  to 60 cases, the view fetches again until it catches up. Completion therefore
  displays all ten cases on the final page even after polling stops.

The final focused independent review reported zero critical/major blockers.
The original combined-run assertion now retrieves full case evidence from
`/cases/0`; its source-supplied and credential-redaction assertions are retained.
This adapts the test to the intentionally bounded detail contract.

## Fresh verification

| Command / check | Observed result |
| --- | --- |
| `uv run --project backend pytest backend/tests -q` | 51 passed, 0 failed, 29.81 seconds |
| Ruff check and format check of backend/app and backend/tests | All checks passed; 42 files already formatted |
| `npx prettier --check src tests` | All matched files use Prettier style |
| `npx tsc --noEmit --project tsconfig.json` | Exit 0 |
| Angular production build | Exit 0; final initial transfer estimate 156.63 KB |
| Full Playwright suite against current Docker image on isolated 8118 | 11 passed, 0 failed, 37.7 seconds |
| axe, keyboard/focus, 320px/375px widths and local-asset check within browser suite | No reported violations/page errors/external asset requests in the tested states |
| Full `npm audit`, `npm audit --omit=dev` | Zero known vulnerabilities in both scopes |
| `uv tool run --from pip-audit==2.10.1 pip-audit --path backend/.venv/Lib/site-packages` | No known vulnerabilities |
| `docker build -t eval-expert:verification .` | Exit 0; image `sha256:2758edef4db7fcc627baed255946319179b27c684967d778003fbb43e5ab8d8c` |
| Docker fault injection and restored hardened container on 8119 | Automatic restart after exit 1; export SHA preserved; encrypted credential decrypts with retained secret key |

Docker tests used a read-only root filesystem, UID 10001, dropped capabilities,
no-new-privileges, /tmp tmpfs and a separate named data volume. No fixtures were
run against the user's preview on 8080.

The metric benchmark evaluated 1,000 cases and 1,000 distinct labels with the
audited source and current source in the same Python process. Complete metric
objects were equal: 2.0474 seconds before versus 0.0162 seconds after (about
126× in this one local fixture). This is measured evidence, not a promised
speedup for arbitrary datasets or remote target/LLM requests.

## Local preview and deployment

Before updating the local preview, it contained one account, 16 catalog records,
20 versions, 11 runs and 132 case results, with no active/queued runs. The complete
stopped data directory, deployment environment and previous image reference were
saved privately under `artifacts/preview-backup-2026-10-07/` (ignored by Git).
The verified image then replaced the local preview without changing its secret key.
After migration to schema 3, all five record counts remained identical and the
preview on `http://127.0.0.1:8080/` reported healthy.

Schema 3 automatically backfills read models while retaining full stored evidence.
The previous immutable Git tag remains `preview-2026-10-06`; the updated standalone
Hostinger Compose import references `preview-2026-10-07`. An upgrade rollback needs
the corresponding original volume backup and image, not just a source downgrade.

## Evidence and limits

- [Container fault/restore script](evidence/2026-10-07-container-remediation.py)
  and [observed result](evidence/2026-10-07-container-remediation.json).
- [Legacy/current metric benchmark](evidence/2026-10-07-metrics-remediation.py)
  and [observed timings](evidence/2026-10-07-metrics-remediation.json).
- Backend regressions: `backend/tests/test_audit_*.py`. Browser regressions:
  `frontend/tests/audit.spec.ts` and `workbench.spec.ts`.
- Local screenshots and actual backup files stay in ignored `artifacts/`.

Live OpenAI/b-api/AcademicCloud calls, calibration with your rated datasets and
the actual Hostinger HTTPS/proxy setup still require their real access/data.
No full OS-image CVE scan, comprehensive license audit, universal WCAG certification
or multi-instance deployment validation was performed. Single-instance operation
and the original feature boundaries remain documented in README.
