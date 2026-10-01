# Reject unsupported comparison request filters

## Intent

Prevent a frozen observation from claiming filters that were not applied. The
query-suite envelope permits a filter object, but the current capture worker and
Search API only implement query, country/currency and fixed availability filtering.

## Constraints

- Do not invent caller-filter semantics or add backward-compatibility adapters.
- Keep empty/absent filters valid; generated suites and existing truthful reports stay usable.
- Fail before dispatch/retention for unsupported inputs. A failed comparison must not publish successful gate evidence.
- Separate this correction from the HTTPS control/session implementation gap.

## Work and acceptance

1. Trace paired and N-way capture, shared worker requests and independent query publication.
2. Reject non-empty or malformed filters at the request/capture boundary; avoid silently dropping them.
3. Test that no HTTP call occurs for rejected inputs, every variant sees the same valid request, and incomplete outcomes cannot pass.
4. Update the owning request contract and operator guides; state the supported surface directly.
5. Commit a separate code batch and open a PR. No new live image/deployment should be claimed without its own check.

## Sources

`evaluation/capture.py`, `lab/evaluation_worker.py`, variant worker/job code,
`data/contracts.py`, `lab/search-app/app.py`, their tests, the
[evaluation runbook](../evaluation-runbook.md), [review](../reviews/documentation-2026-10-01.md)
and [roadmap](roadmap.md).

Caller filtering can be designed later as an explicit Search API feature. This
batch closes silent misrepresentation without claiming that feature exists.
