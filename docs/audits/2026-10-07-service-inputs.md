# Service editor and preview verification

## Root causes

The existing Volltexte service retained its complete URL mapping in SQLite at
version 4. The already open browser used code from before catalog editing switched
to full detail reads. Reloading restored the mapping without a database change.
The persistence regression verifies saving a changed mapping, reopening and a full
page reload against the real catalog API.

The current service preview separately used one shared hardcoded title input for
all services. The new regression failed with `{"title":"Beispiel"}` where
`{"url":""}` was expected. Previews now fetch saved service detail on demand,
derive editable fields from input pointers and keep input, response and errors in
the corresponding service card. No API or database migration is required.

## Verification

- `npm run test:unit`: 6 passed; pointer nesting, exact substitution semantics,
  escaping, parent/child paths and prototype-shaped field names are covered.
- `npm run test:e2e`: 13 passed in an isolated installation, including changed
  mapping persistence, independent preview input, target-error recovery and axe.
- `uv run --project backend pytest backend/tests -q`: 51 passed.
- Angular production build, TypeScript, Prettier and Git whitespace checks pass.
- Fresh independent source review: no actionable findings.
- `docker build -t eval-expert:service-inputs .`: succeeds. All 13 browser tests
  also pass against that image (37.3 seconds) with a writable isolated data volume,
  a read-only root filesystem and the Compose security options.

An initial additional Docker test omitted the writable data volume and failed to
start SQLite. Correcting that test setup made both regressions pass; application
code and the existing Compose volume configuration needed no change.

## Local installation

Before updating, no runs were active. The stopped data directory, deployment
environment and previous image reference were saved privately under the ignored
`artifacts/service-inputs/backup/` directory. The updated local image is
`sha256:cd65dfdba574cc80b112a6bc997d5323261f81614ee83ffc963a720f662b28da`.
After the update, counts remained 1 user, 18 catalog entries, 25 versions, 11 runs
and 132 results. The Volltexte service's version and mapping remained unchanged.

In the actual user's browser, the URL-derived preview was filled with
`{"url":"https://www.wirlernenonline.de"}` and called the configured staging
extractor. It returned full text, language `de`, target status 200,
`likely_error_page: false` and extractor version `fc082d38`.

The standalone Hostinger Compose import is advanced to the new immutable
`preview-2026-10-07-service-inputs` tag. Existing preview tags remain unchanged.
The actual Hostinger installation and live LLM judging are outside this change.
