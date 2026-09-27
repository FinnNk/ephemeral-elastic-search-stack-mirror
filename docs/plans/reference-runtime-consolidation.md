# Next batch: runtime consolidation and delivery rehearsal

## Intent

Put the new catalogue and comparison contracts into the running control Pod, complete a reviewed schema-changing delivery exercise, and move active runtime helpers out of the research spike tree. A new reader should find one current implementation path and a clearly labelled historical replay path.

## Constraints

- Keep frozen 10k/1M source bytes, format-1 recipes, snapshots, reports, approved deployment records and prior PRs immutable.
- Merge the separate [delivery-source schema contract PR](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/4) only after review. Use its successful merged-source push build for promotion; a PR-head build cannot enter a stable target.
- Keep the project implementation branch and delivery-source change reviewable as separate PRs. Do not merge either on behalf of the reviewer.
- Preserve API, index and evidence fingerprints during module moves. Source paths used in immutable recipes stay embedded in their old objects.
- Avoid a broad platform redesign. Gitea, Nexus, Argo CD, Floci and the shared Elasticsearch cluster remain the local topology.

## Work

1. Build and roll out the accepted control runtime image. Prove the UI and API create a new format-2 10k environment, select revised query/judgement inputs and retain the resulting comparison hashes. Recreate a pinned historical format-1 environment through the same deployed control path.
2. Once the schema source PR is accepted, identify its merged-source CI release. Evaluate a baseline against the dedicated title-keyword recipe, propose and verify promotion through the three local targets, then evaluate and propose the reverse rollback. Record exact release, recipe, manifest, evidence and deployment fingerprints.
3. Move live Blob, index, Git and Kubernetes helpers imported from `research/platform-spike` into owned runtime modules. Update entry points, images and tests. Keep research scripts as evidence or explicit adapters to the owned modules; remove dead migration code from the active path.
4. Audit guides and C4/Archify sources against the deployed behaviour. Regenerate changed views, inspect them and retain precise limits where an exercise was not performed.

## Acceptance criteria

- The running control Pod serves the new catalogue/input-selection UI and provisions a format-2 shared index without a combined release manifest. Two API-only environments reuse it; a dedicated schema candidate serves searches from a separate index.
- Historical format-1 replay produces the old ordered sample after the current mapping source changes.
- A merged-source schema release passes exact compatibility checks, full public-API result/relevance checks and a delivery-owned Gatling probe. Reviewed promotion and rollback restore the complete pinned definitions across the local targets; an unreviewed or mismatched input is rejected.
- Active runtime imports no longer depend on `research/platform-spike` for production control, while retained recipe source hashes and historical rebuilds stay valid.
- Focused and full tests, live evidence, diagram validation and a clean branch diff accompany the PR. Where local capacity or review timing prevents an exercise, record the specific gate without claiming it passed.

## Sources

- [Catalogue recipe and delivery evidence](../research/evidence/catalogue-recipe-delivery.md)
- [Reference-clarity audit](reference-clarity.md) and [current roadmap](roadmap.md)
- [Control runtime guide](../control-runtime.md), [delivery guide](../delivery.md) and [data contracts](../data-evaluation-contracts.md)
- [Historical index recipes](historical-index-recipes.md) and [recovery evidence](../research/evidence/index-recovery-workflows.md)
- [Architecture diagram guide](../diagrams/README.md)
