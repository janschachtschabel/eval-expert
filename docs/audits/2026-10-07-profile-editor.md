# Profile editor verification

## Root cause and correction

The dataset selector dereferenced `cases.length`, but the bounded catalog list
returns only `case_count`. Angular threw an undefined-length TypeError and stopped
initializing the form, leaving labels and several controls blank. The one-line
correction uses the existing summary count. No API or database change is required.

The unrelated deletion warning in the user's screenshot came from a dataset
referenced by the demo profile. The repair does not remove that dataset or profile.

## Evidence

- A real-API browser regression failed against the previous Docker image after
  dataset lookups completed: the Name control was not accessible. Its trace also
  captured the undefined-length TypeError.
- `npm run test:e2e`: **14 passed (41.0 seconds)** against the fixed Docker image
  on port 8117 with a separate writable volume and the Compose security options.
  The new test selects a five-URL dataset, service, LLM connection and criterion;
  saves and reopens the profile with the same selections; checks axe and captures
  rendering errors. It explicitly verifies summaries omit `cases`.
- `npx prettier --check src tests`: all files pass.
- `docker build -t eval-expert:profile-editor .`: succeeds, including the Angular
  production build. Image: `sha256:71c7f86d6ef5c2b932a02da555aaaec8e7867e4d7af5ab66b761bb514e4708b3`.
- Scoped source review: spec compliance, security, correctness, performance,
  maintainability and testing pass; no actionable findings. The correction keeps
  small catalog lists and existing escaped template rendering.

## Local installation

No runs were active before updating. The complete stopped data directory, current
environment and previous image reference were backed up privately under ignored
`artifacts/profile-editor/backup/`. Before and after the upgrade, counts were
1 user, 14 catalog entries, 28 versions, 11 runs and 132 results. The Volltexte
service's version 4 and full input mapping remained unchanged. Health returns 200.

The actual local UI renders named controls and offers `Testwebseiten · 5 Fälle`.
An unsaved `Werbefreiheit – Volltext` draft selects the staging extractor, that
dataset, LLM-Bewertung, OPENAI and Werbefreiheit. The original empty draft had no
entered values to restore. No target API or live LLM request was made during this
repair. A reload attempted during startup briefly reached a network error page;
the repaired profile is open in a fresh in-app browser tab after health recovered.

The local and standalone Hostinger instructions reference the new immutable
`preview-2026-10-07-profile-editor` tag. Earlier preview tags remain unchanged.
