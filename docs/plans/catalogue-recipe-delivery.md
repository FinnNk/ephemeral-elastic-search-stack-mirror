# Catalogue recipes and delivery

**Status:** implemented on the review branch. A live 10k delivery comparison passed; schema-changing promotion awaits a reviewed merged-source release. The [batch evidence](../research/evidence/catalogue-recipe-delivery.md) records both the passing check and its limits. The [next detailed plan](reference-runtime-consolidation.md) covers deployed control validation and the reviewed source release.

## Intent

Make independent catalogue manifests the normal source for new shared and dedicated frozen indices and for release promotion. Keep format-1 recipe reading only for explicit replay of already pinned historical indices. The previous batch made functional comparisons select independent query and judgement manifests; this batch completes the index and delivery side of that contract.

## Constraints

- Do not rewrite the 10k or 1M source bytes, existing index recipes, snapshots, reports or approved deployment records.
- A format-2 recipe must pin its exact catalogue manifest, product bytes, mapping, engine and indexer. Validate retained Blob bytes before admitting it.
- A newly created shared format-2 index needs its own stable recipe-derived name. The existing release-named shared index carries a format-1 marker; changing that marker in place would make historical recovery ambiguous.
- Keep reuse, clone, regular snapshot restore and recipe rebuild ordered and observable. A failed fast path must leave no partial index.
- Preserve old format-1 replay through an explicit historical selection, with a test proving the same ordered product sample after a schema change.
- Promotion retains review, exact source/image digests, environment fingerprints and rollback of the complete definition. Synthetic relevance scores remain evidence for review, not quality approval.

## Work

1. Resolve a new environment's catalogue from a retained independent manifest and create a format-2 recipe by default. Expose the catalogue manifest hash with the environment. Route an explicitly selected historical format-1 recipe through the existing recovery path.
2. Materialise format-2 shared and dedicated indices directly from the pinned catalogue object. Use a recipe-derived name for shared indices so a new schema does not collide with the old release-named index. Reuse the same frozen index across API-only candidates.
3. Make delivery resolution select a format-2 recipe and bind its catalogue manifest and selected functional input hashes to evidence. Validate exact inputs again at promotion. Rehearse a schema-changing proposal and rollback.
4. Update the control UI, operating guides, Structurizr and Archify sources to show actual new defaults and the separate historical recovery route. Render and inspect changed diagrams.

## Acceptance criteria

- A new 10k shared environment and a dedicated mapping-change environment serve correct public searches from format-2 recipes; an API-only candidate reuses the shared index without indexing.
- The 1M catalogue can be materialised from its retained manifest and a new or restored index reaches the expected document count and ordered sample. Record timing as a sample, not a percentile.
- A deleted historical format-1 index is restored or rebuilt from its exact old recipe; new environment creation does not produce format-1 recipes implicitly.
- Delivery promotes the same immutable release through local targets with selected independent input hashes. A mismatched catalogue/query/judgement or unreviewed proposal is rejected; schema-changing rollback restores the previous complete definition.
- Focused tests, one live 10k comparison and updated diagram render/browser receipts pass. Record any local capacity or dependency limits in evidence.

## Sources

- [Reference-clarity audit](reference-clarity.md) and [selected-input evidence](../research/evidence/independent-comparison-inputs.md)
- [Data and evaluation contracts](../data-evaluation-contracts.md)
- [Historical recipe plan](historical-index-recipes.md) and [recovery options](../research/index-restoration-options.md)
- [Promotion and deployment plan](promotion-deployment.md) and [operating guide](../delivery.md)
- [C4 and Archify diagram guide](../diagrams/README.md)
