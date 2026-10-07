# Audit remediation

User authorization: address all open confirmed findings from the complete audit,
using better-coding-workflow. The 13 findings are still present at 1b78263.
The audit's existing roadmap is approved by this request; no additional approval
round is required. This document records implementation decisions and acceptance.

## Design

Keep the one-container/single-worker SQLite design. Comparing full JSON on every
read (current behavior), moving to PostgreSQL (unnecessary infrastructure), and
storing lightweight read metadata were considered. Choose lightweight metadata
with a versioned, idempotent SQLite migration and bounded paginated reads.
Dataset details remain individually retrievable. Public run details omit dataset
cases and contain a bounded results page; status polling retrieves metadata only.
History supports pagination, total counts and a comparison-key filter. Exports
remain complete and stream stored cases. Worker aggregation is incremental and
runs CPU work off the eventloop. Default stored evidence budget is 50 MB per run;
classification vocabulary is limited to 10,000 labels per field. Limits fail
explicitly, retain existing evidence and never silently fabricate complete scores.

Protect login with synchronized, TTL-bounded per-IP and per-account budgets.
Protect catalog updates with an expected version and transactional conflict check.
Reject deletion of referenced resources and invalid dependencies. Preserve raw
responses separately from per-field validation failures, including reassessment.
Automatically scrub configured authentication headers from existing public bodies
while retaining the configured credential in encrypted storage where possible;
historical snapshots/versions must not expose plaintext headers.

The worker supervisor retries worker initialization with bounded backoff, marks
unfinished running work interrupted and never repeats uncertain target calls.
Health reports degraded/recovering state until processing resumes. Persistent
failure terminates the container process so its restart policy can recover it.

## Work packages (each starts by refreshing better-coding-workflow)

1. SEC-01/02: auth.py, new login_limits.py, models.py and credential sanitation.
   First add tests for rotating names, TTL/capacity, configured headers and historical
   reader exposure. Implement budgets and case-insensitive credential validation.
2. COR-01, DB-01/02, API-01: scheduler.py, run_store.py, catalog.py, database.py,
   models.py, datasets.py, runs.py, connections.py. First add queue-full catch-up,
   stale-version, referenced-delete and four malformed-request regressions.
   QueueFull leaves due unchanged; stale updates yield 409, missing version 422;
   referenced deletion yields 409; invalid input yields 422 and unknown run 404.
3. COR-02/PERF-02: target.py, runner.py, benchmarks.py, new aggregation.py.
   First test raw invalid responses, independent valid fields, reuse after mapping
   repair, metric equivalence and nonblocking aggregation. Preserve raw JSON and
   field errors; maintain documented recall/undefined/macro conventions.
4. PERF-01/OPS-01: new migrations.py/read metadata module, database.py, run_store.py,
   runs.py, exports.py, runner.py, main.py, new worker supervisor. First test legacy
   migration, bounded list/case reads, full streaming exports, evidence budget and
   worker recovery without target replay. Keep functions grouped by responsibility.
5. UI integration (refresh better-coding-frontend): catalog.ts/html, home.ts,
   runs.ts, run.ts/html, app.ts, styles, i18n.ts, API DTOs. Fetch dataset detail only
   for editing, show save conflicts, paginate history/cases, load individual cases
   on demand. TEST-01/UX-01: delayed demo completion must preserve the current route;
   mobile close/Escape returns focus. Write browser regressions first.
6. DEP-01: patch Angular CLI and lockfile, add npm/Python CI audits. Verify installed
   dependency metadata, scans and builds. No new runtime library is needed.
7. Review and verify: independent fresh review, security/audit regression closure,
   all backend/browser tests, lint/format, production build, dependency scans,
   Docker build/run against isolated storage, backup/restore smoke test. Record each
   finding's final evidence and update README/API/upgrade notes. Live provider and
   Hostinger acceptance remains explicitly dependent on actual credentials/access.

## Verification and rollback

Use temporary DBs and the isolated 8117 installation. Every implementation package
starts with a failing behavioral test and ends with relevant passing tests and a
logical commit. The final suite must retain the original reference/judge/security
flows. Schema migration must be rerunnable and preserve accounts, credentials,
catalog versions, snapshots and results. Before upgrading an existing installation,
back up the complete volume and secret key; rollback restores that backup and the
immutable original preview. UI and API pagination changes ship together.

## Progress

- [x] SEC-01 / SEC-02
- [x] COR-01 / DB-01 / DB-02 / API-01
- [x] COR-02 / PERF-02
- [x] PERF-01 / OPS-01
- [x] TEST-01 / UX-01
- [x] DEP-01
- [x] Independent review and final verification

Closure evidence: docs/audits/2026-10-07-remediation.md. The read models include
paginated per-label scores as well as case pages; SQLite upgrades to schema 3.
Frontend regressions additionally cover cancelled/replaced editors and two
delayed case-page responses spanning terminal status. Live provider/Hostinger
acceptance remains outside this technical correction verification.
