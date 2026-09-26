# Frozen index-change batch

## Intent

Demonstrate the second full source-to-comparison path: a reviewed index-design change builds a separate Elasticsearch index from the same frozen synthetic release, deploys a candidate API against it, compares final API results with the shared-index baseline and removes its dedicated resources on demand.

## Constraints

| Area | Constraint |
| --- | --- |
| Data | Reuse the immutable `retail-gb-10k-v1` products, queries and synthetic judgements. The index candidate must not alter canonical Blob objects or introduce production records. |
| Isolation | Give the candidate a dedicated index and scoped credentials on the shared self-managed Elasticsearch cluster. Keep the baseline's write-blocked index intact. |
| Pinning | Record source SHA, API image digest, mapping/analyser revision and hash, dataset hashes, Elasticsearch version, index name and environment fingerprint. Reject mutable-only references. |
| Build | Use a finite Kubernetes indexing Job reading Floci Blob through a short-lived SAS. Keep snapshot restore out of the first path because the tested Floci/Elasticsearch combination did not pass repository verification. |
| Comparison | Send identical original requests to both public APIs. Report result preservation and synthetic relevance separately; a deliberate index change need not preserve rankings. Use `_rank_eval` or `_profile` only as optional component diagnosis. |
| Cleanup | Delete the dedicated candidate index, namespace and scoped credentials; retain the shared baseline index, canonical Blob release, source revisions and reports. |

## Work

1. Version an alternative mapping/analyser specification and create its reviewable Gitea source/configuration PR.
2. Build the candidate index from the frozen release with a finite Job. Verify mapping hash, document count, dataset hash, write block, credentials and repeatability.
3. Deploy a pinned candidate API over that index. Run black-box result-preservation and graded relevance comparisons against the baseline; retain complete reports and selected component diagnostics.
4. Add this index kind to environment creation and deletion. Exercise the full create → compare → remove workflow through the control API/UI.
5. Measure request-to-first-correct-search and full reindex duration, resource use and failure recovery. Compare the first evidence with the provisional 10,000-product p95 ≤ five-minute target without claiming p95 from one run.

## Acceptance criteria

- The candidate has a distinct index with the intended mapping hash, 10,000 synthetic products, no writes after indexing and no access to unrelated indices. The baseline index and release hashes remain unchanged.
- Both API environments have pinned definitions and pass readiness through a real search. A failed index build cannot become ready.
- Public-API reports are complete, versioned and stored by hash, with changed ordered IDs and judgement coverage visible. Comparison modes retain separate verdicts.
- On-demand deletion removes the candidate namespace, credential and dedicated index. The shared baseline index, frozen objects and reports remain.
- Evidence records build and cleanup timings, resource conditions, retries and failures. Any missed target or unmeasured percentile is stated plainly.

## More information

- [Prototype design: startup, scale and targets](../prototype-design.md#startup-and-scale-validation)
- [Current frozen loader](../../lab/load_release.py) and [index Job research](../../research/platform-spike/index_job.py)
- [Elasticsearch/Floci compatibility evidence](../research/platform-spike.md)
- [Elasticsearch explicit mapping guidance](https://www.elastic.co/docs/manage-data/data-store/mapping/explicit-mapping): changing an existing field type requires a new index and reindexing
- [Controlled API comparison](../../lab/control_comparison.py) and [lifecycle backend](../../lab/lifecycle.py)
