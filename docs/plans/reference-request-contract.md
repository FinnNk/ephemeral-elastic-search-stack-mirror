# Filtered Search API requests and frozen capture

Status: implemented for review. Deployable API changes are in
[delivery-source PR #14](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/14),
stacked on #13; both retain the normal relevance gate. See the [contract](../search-request.md) and
[verification record](../research/evidence/search-request-filters.md). The next
detailed batch is [canonical HTTPS control sessions](reference-https-control-session.md).

## Intent

Apply caller filters consistently through the public Search API, paired and N-way
capture, disconnected demo and retained observations. A recorded request must
match the request executed by every variant.

## Contract and constraints

- `filters` is an optional JSON object: exact `category`, `colour` and `material`
  arrays, plus `price_minor` with inclusive `gte` and/or `lte` integer bounds.
- OR within a field; AND across fields and the fixed GB/GBP/available scope.
- Reject unknown fields, malformed JSON, duplicate keys, invalid ranges and
  incorrectly echoed filters. Never silently drop a filter.
- One current request contract; no compatibility reader, response fallback or
  old-image adapter. Update current demo releases to use the new API.
- Preserve historical schema/index examples and their original frozen evidence.
- Keep independent producer contracts independent of API/control implementation.

## Work

1. Add a small shared filter contract to the Search API build context. Compile
   filters into Elasticsearch filter clauses; echo applied filters in every response.
2. Forward/verify filters in paired and N-way workers and preflight/probes. Include
   the contract source in finite Jobs and retained execution identity.
3. Apply the same filter semantics in the disconnected demo and browser controls.
4. Validate current retained observation filters; update Docker/source packaging.
5. Verify valid filtering, empty outcomes, invalid requests, echo mismatches and
   identical request dispatch to every variant. Use actual HTTP and Elasticsearch
   in a disposable check where available.
6. Update current guides and roadmap; publish separate project/source PRs as needed.
   Record tests separately from live frozen evaluation and gate approval.

## Acceptance criteria

- Filters change actual result membership and totals without changing scoring.
- Every variant executes the same frozen query/market/filter request.
- The API's echoed filter object is mandatory in capture; mismatches fail closed.
- Demo filtering agrees with the supported contract; invalid filters return HTTP 400.
- Current packaging includes the contract, and historical schema artefacts are unchanged.
- No compatibility adapter or silently unfiltered success path remains.

## Sources

`lab/search-app/`, `evaluation/capture.py`, `evaluation/offline.py`,
`lab/evaluation_worker.py`, `lab/variant_capture_worker.py`, `lab/evaluation_job.py`,
`lab/compare_search.py`, `lab/search_probe.py`, `lab/setup_delivery.py`, related tests,
[input contracts](../data-evaluation-contracts.md) and [evaluation runbook](../evaluation-runbook.md).

Canonical HTTPS control/session handling remains a separate implementation batch.
