# Functional audit and repair

The reported judge profile is persisted with a null provider. Required Angular
controls are not checked on submit, and Plan validation normalizes modes without
requiring their dependencies. Starting detects the omission too late.

Scope: all nine primary views, run detail, evidence dialogs, history, exports and
printable reports. Keep the current architecture, accounts, secrets and data.
Run fixtures exclusively on port 8117 with separate data. External HTTP is mocked
at the transport boundary; the actual API, worker and DeepEval still execute.

Confirmed repair packages:

1. Validate catalog/login/team forms before sending; show German errors next to
   controls and preserve input. Require judge provider/criteria and reference
   fields on server save as well. Cover mode switching and incomplete submissions.
2. Show readiness on profile cards, including old incomplete records. Keep start
   disabled with an actionable explanation until dependencies and credentials are
   present. Preserve optional root JSON Pointers in reference fields.
3. Normalize structured API validation errors without echoing input/credentials.
   Explain malformed JSON and empty OpenAPI results; provide load-error recovery.
4. Show bounded input previews in case rows and backfill catalog/case summaries
   through an idempotent migration. Keep complete evidence on demand.
5. Hide team administration on unauthorized direct visits and provide a useful
   missing-run state rather than an endless spinner.

Verification matrix:

- Overview: empty state, counts, demo, latest run/navigation.
- Services: manual/OpenAPI setup, mapping persistence, URL preview, target error.
- Datasets: JSONL/file import, five URL cases, edit/reopen/counts, invalid content.
- Criteria: steps, threshold, context/output paths, edit/version/reopen.
- Providers: all adapter types, model discovery, secret retention, parameter edits.
- Profiles: all three modes, required selections, save/reopen/start, legacy errors.
- Runs: actual reference/judge execution, progress, error counts, history, rerun,
  reassessment, case dialog, cancellation, CSV/JSON/report and missing-run recovery.
- Schedules: create/edit/preview/disable/delete and dependency protection.
- Team/login: create account, roles, invalid submissions, revocation and logout.
- Cross-view: console errors, keyboard, axe, 320/375px reflow and local assets.

Each defect gets a failing regression before implementation. Read-only assessment
is documented separately from repairs. Verify full backend/unit/browser suites and
the Docker image; update the local installation only after backup and health checks.
Then repair the user's existing profile with the already configured OPENAI
connection and verify its requested five-case run. Publish on the existing branch
and PR with a new immutable preview tag; never merge or deploy to Hostinger.
