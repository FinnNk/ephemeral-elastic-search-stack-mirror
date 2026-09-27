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
| Environment creation | Default `current_recipe()` still constructs format-1 recipes from a combined release. Explicit format-2 catalogue recipes already work. | **Next batch:** make a retained catalogue manifest the default for new environments; keep a narrowly scoped format-1 *recovery* reader for previously frozen environments. Prove old recipe replay and new recipe creation side by side. |
| Comparison selection | The prior control UI derived queries and judgements from a combined release. | **Implemented in this batch:** the UI selects pinned independent query and judgement manifest hashes; the controller verifies their bytes and dependencies. The [local check](../research/evidence/independent-comparison-inputs.md) used default and revised suites against unchanged frozen APIs. Control image rollout remains. |
| Delivery | Normal release resolution still creates a format-1 recipe when no hash is supplied; independent offline evidence is an optional addendum. | **Next batch:** require explicit catalogue recipe and evidence references for new promotion proposals; rehearse schema-changing promotion and rollback. Existing approved deployment records remain readable. |
| Source layout | Live indexing and platform helpers still reside in `research/platform-spike` and are imported by `lab/`. | **Later cleanup:** move runtime modules to an owned package after the contract migration, then update imports and entry points in one batch. Preserve research measurements as evidence. |
| Diagrams | C4 and interactive views already show separate input/evaluation contracts and historical index recovery. | Review the rendered views when the default control/delivery path changes; do not imply independent UI selection is live before it is. |

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

## Next batch: default contract migration

**Intent:** make new environment creation and delivery consume independent catalogue and evaluation contracts end to end. Comparison input selection is now implemented in the branch described above.

**Acceptance criteria:** new shared and dedicated environments pin format-2 catalogue recipes; delivery validates selected input hashes and a real addendum-backed promotion and schema-changing rollback; existing format-1 recipes can still be restored through an explicit historical route. Unit tests and one live 10k comparison cover both paths, and the C4 and interactive diagrams reflect the verified behaviour. See the [detailed next-batch plan](catalogue-recipe-delivery.md).

**More information:** [input and evaluation contracts](../data-evaluation-contracts.md), [historical index recipes](historical-index-recipes.md), [independent contract plan](independent-data-evaluation-contracts.md), [delivery guide](../delivery.md), [architecture diagrams](../diagrams/README.md).
