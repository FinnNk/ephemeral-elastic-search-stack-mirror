# Reference clarity and contract consolidation

## Intent

Make the default lab workflow explain one coherent architecture: independent synthetic inputs, frozen API observations, offline evaluation, catalogue-pinned indices and reviewed delivery. Keep historical artefacts replayable without presenting conversion tools or earlier schemas as the route for new work.

The audit separates immutable evidence from executable defaults. Old reports, index recipes and Gitea PRs remain evidence. A current entry point must describe what it runs today. No frozen object is rewritten to make it look newer.

## Audit and disposition

| Surface | Finding | Disposition |
| --- | --- | --- |
| Input publication | `data/publish.py` required the original combined `manifest.json`, although it published separate input envelopes. The example generator wrote a combined manifest solely for that path. | **This batch:** discover the three input files directly, validate their references, take explicit source provenance and publish immutable independent manifests. A new output directory avoids overwriting previously retained manifests. |
| Retention inventory | Read-only inventory depended on the same combined manifest. | **This batch:** read source identity and content hashes from the independent manifests. |
| Offline evaluation | A one-time complete-report importer lived in the current evaluator package. | **This batch:** remove that conversion path. Previously retained reports and observations remain unchanged; new observations come from API capture. |
| Current documentation | README and roadmap described merged Gitea batches as pending; design text called the Kubernetes control placement future work. | **This batch:** make the roadmap a current-state entry point and label older detailed plans as historical records. |
| Environment creation | The earlier default constructed format-1 recipes from a combined release. | **Deployed:** new environments pin a retained independent catalogue and format-2 recipe; explicit historical format-1 replay remains. [Evidence](../research/evidence/runtime-consolidation-delivery.md) records the control-Pod check. |
| Comparison selection | The prior control UI derived queries and judgements from a combined release. | **Deployed:** the UI selects pinned independent query and judgement manifest hashes; the controller verifies their bytes and dependencies. The [local check](../research/evidence/runtime-consolidation-delivery.md) used revised inputs against unchanged frozen APIs. |
| Delivery | Normal release resolution previously created a format-1 recipe when no hash was supplied. | **Deployed:** new resolution pins an independent catalogue recipe and selected query/judgement hashes. The [runtime delivery evidence](../research/evidence/runtime-consolidation-delivery.md) records the merged-source schema release and local target exercise. Existing approved deployment records remain readable. |
| Source layout | Live indexing and platform helpers were imported from `research/platform-spike` by `lab/`. | **Consolidated:** active control and delivery modules own their runtime helpers; historical research measurements and embedded recipe source remain as evidence. |
| Diagrams | C4 and interactive views show separate input/evaluation contracts and historical index recovery. | Their sources and rendered views were validated against the deployed contract; the accompanying guide identifies the current control runtime. |

## Constraints

- Preserve the existing 10k and 1M frozen source bytes, retained manifests, reports, recipes and snapshot identities.
- Do not silently adapt an old report into a new observation set or create a new format-1 recipe for an independent catalogue.
- Historical schema support is justified only where a pinned environment or index must be replayed. Keep it explicit and tested at that boundary.
- Keep all example data synthetic and use British English in user-facing guidance.
- Work on a branch; commit and submit each batch for acceptance before merging.

## Acceptance checks for this batch

1. The independent example generates product, query and judgement files without a combined release manifest.
2. Publication validates references and emits the same immutable envelope shapes without reading `manifest.json`; a repeat is idempotent and conflicting output is rejected.
3. Retention inventory identifies source and byte hashes from the independent envelopes.
4. The current evaluator has no one-time old-report importer; focused input and evaluator tests pass.
5. README, design, contract guide and roadmap agree on what is implemented and what remains.

## Follow-on batch: runtime consolidation

**Intent:** consolidate the runtime and exercise reviewed delivery after the catalogue/input contract changes. See the [detailed plan](reference-runtime-consolidation.md) and [live evidence](../research/evidence/runtime-consolidation-delivery.md).

**Acceptance criteria:** the deployed control Pod creates format-2 environments; a reviewed merged-source release supports schema-changing promotion and rollback; active runtime helpers move out of the research tree. See the [detailed next-batch plan](reference-runtime-consolidation.md).

**More information:** [input and evaluation contracts](../data-evaluation-contracts.md), [historical index recipes](historical-index-recipes.md), [independent contract plan](independent-data-evaluation-contracts.md), [delivery guide](../delivery.md), [architecture diagrams](../diagrams/README.md).
