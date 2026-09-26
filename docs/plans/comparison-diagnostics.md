# Comparison diagnostics batch

## Intent

Explain *where* a customer-visible search result changed while keeping the final public API response as the comparison authority. Demonstrate a behaviour-preserving source refactor that produces no result changes, and a query-understanding change whose final result and API-stage evidence change while the index does not.

## Scope and constraints

| Area | Constraint |
| --- | --- |
| Inputs | Use the frozen `retail-gb-10k-v1` products and queries, the existing `trainers` extra query and UK/GBP context. No production data. |
| Isolation | Deploy source variants with pinned image digests, distinct namespace credentials and the existing read-only shared index. Do not modify the frozen baseline. |
| Black box | Compare ordered IDs from the public `/search` response. Failed or incomplete requests cannot pass result preservation. Keep result equality, Jaccard and RBO separate from latency. |
| Grey box | Add an opt-in, versioned diagnostic record and request correlation ID. Include original and normalised query, rewrite decision, Elasticsearch request fingerprint, returned IDs and stage times; avoid credentials and private configuration. Missing stage data is explicitly unavailable. |
| White box | Run selected Elasticsearch `_profile`, `_explain` or `_rank_eval` queries against a known mapping/index outside the API comparison path. Store their outputs as diagnostic evidence only. |
| Reproducibility | Pin source SHA, image digest, dataset/query hashes, index, Elasticsearch version and diagnostic schema. Store reports in Floci by content hash. |
| Delivery | Use local Gitea source PRs for variants and one project PR stacked on the relevance batch. Leave merge decisions for review. |

## Work

1. Add an opt-in API diagnostic contract and tests. Keep the ordinary response and ranking stable when capture is enabled.
2. Build a diagnostic-only candidate from baseline source and a diagnostic plus `trainers` candidate; deploy each from its Gitea Actions image through Argo CD.
3. Compare the frozen suite through the public APIs. Require zero changed queries for the diagnostic-only variant, and detect the deliberate `trainers` change on the instrumented candidate.
4. Link black-box requests to grey-box records by correlation ID. Run a small, selected white-box Elasticsearch probe and label its scope.
5. Save immutable complete reports, checked-in sanitised evidence, commands and limitations. Repeat the critical run to test stable hashes.

## Acceptance criteria

- All environments are Synced/Healthy, have exact image digests and use the same frozen index and dataset hash.
- The diagnostic-only refactor has **zero** changed ordered top-ten results across the frozen suite; the query-understanding variant changes `trainers` and identifies the rewrite stage without changing the index.
- Every captured request has one correlation ID joining its final API response and diagnostic record. The report clearly marks unavailable stages and separates client-visible results from component probes.
- Enabling diagnostics does not change the returned ordered IDs or totals for selected requests. Secrets do not appear in saved reports.
- The report identifies errors, zero-result requests and incomplete runs. A failed or missing request cannot produce a passing preservation verdict.
- Unit and live checks pass; repeating the complete frozen run yields the same report hash. The local source PRs and project PR show exact SHAs.

## More information

- [Prototype design: evidence layers and comparisons](../prototype-design.md#search-and-comparison)
- [Runnable lab and existing comparison](../../lab/README.md#compare-a-pinned-api-candidate)
- [API source](../../lab/search-app/app.py) and [comparison code](../../lab/compare_search.py)
- [Platform research and isolation evidence](../research/platform-spike.md)
- [Architecture diagrams](../diagrams/index.html)
