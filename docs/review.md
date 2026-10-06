# Implementation review

An independent read-only review used better-coding-review and covered all backend modules and
Docker/Compose in responsibility-sized passes. Generated assets, dependencies and lockfiles were
excluded. No critical or major backend/deployment finding remained after corrections.

| Verified finding | Correction and evidence |
| --- | --- |
| JSON Schema remote references bypassed endpoint policy | Local references only, explicit empty registry; regression records zero remote retrievals |
| Duplicate schedule recovery could terminate worker | Handle already-enqueued schedule keys, advance state, guard scheduler exceptions |
| GEval could return a score above the valid range | Require finite score in [0,1], preserve invalid result as judge error |
| Last-case cancellation still ran subsequent criteria | Check before criteria and at final status; regression uses actual GEval with a simulated HTTP boundary |
| Wildcard proxy trust allowed spoofed client addresses | Trust explicit proxy IPs/CIDRs; loopback by default |
| History could combine different field definitions | Frozen comparison key and selection by field name |
| Judge mode retained hidden reference fields | Normalize inactive mode settings server-side |
| Reference annotation errors were found after API spending | Validate selected gold labels before enqueueing |
| Chunked requests escaped the size check | Count actual streamed request bytes; regression verifies HTTP 413 |
| Navigation retained a previous chart field | Reset field selection on run route changes |

Worker lock, queue bounds, secret encryption/redaction, CSRF, role boundaries, report escaping and
CSV formula handling were also examined. This review does not certify unconfigured live providers,
production hosting, universal accessibility or horizontal scaling. Dependency and runtime checks
are recorded separately in verification.md.
