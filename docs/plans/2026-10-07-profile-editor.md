# Profile editor repair

The dataset selector still reads `cases.length` from catalog summaries, which now
provide `case_count` without case bodies. Angular throws a TypeError during
rendering, leaving the new-profile form partially initialized and blank.

This needs a one-line template correction, not an architectural change. The
failing browser regression reproduces the blank labels against the real summary
API after lookups finish loading. Its trace confirms the undefined-length error.

Acceptance criteria:

- The profile form renders with named and usable controls.
- Dataset options display the persisted case count without loading case bodies.
- A five-URL judge profile can select service, dataset, provider and criterion,
  save and reopen with the same selections.
- No rendering errors or axe violations occur in that flow.

Change the selector to `case_count`, verify the new regression and full browser
suite in an isolated Docker installation, then update the local preview after a
stopped-volume backup. Preserve the current user's empty profile draft. No API,
database, provider credential or evaluator changes are needed.
