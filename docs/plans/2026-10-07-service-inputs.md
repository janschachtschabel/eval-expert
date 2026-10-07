# Service input repair

## Evidence and scope

The user's URL mapping is stored correctly (service version 4). An already open
browser still ran the frontend predating detail reads for catalog editing. A full
reload restored the saved mapping. The current frontend separately uses a shared
`{"title":"Beispiel"}` preview input for every service, including URL extractors.

## Acceptance criteria

- Saving a changed mapping, reopening the editor and reloading the page retain it.
- Service previews load the full saved service configuration on demand.
- Input placeholders come from `$input` pointers; a URL service starts with `url`.
- Each service has its own editable input and response, with loading/error states.
- Closing and reopening a preview keeps the user's input within that page session.
- Constants in the request mapping are not required again in the test input.

## Smallest implementation

1. Add browser regressions for mapping persistence and independent preview inputs;
   run them against an isolated installation before changing application code.
2. Add a small, dependency-free input-example helper with focused pointer tests.
   Without an input schema, placeholders cannot infer scalar types or array types;
   the UI explicitly asks users to check values and types.
3. Move service preview ownership into a standalone component. Fetch detail when
   opened, generate its input, and show responses in the service card. Remove the
   global hardcoded preview field and method from the catalog component.
4. Verify build, helper tests and the full browser suite in isolated test data.
   Review the diff and update input-mapping documentation.
5. Build the Docker image, back up user data and update the local preview. Verify
   the existing Volltexte service without introducing test fixtures into it.

No backend schema, evaluator, dependency or credential changes are needed.

## Outcome

All acceptance criteria are verified. See the
[verification record](../audits/2026-10-07-service-inputs.md) for red/green evidence,
test counts, the local data-preserving upgrade and the real extractor response.
