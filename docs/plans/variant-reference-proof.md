# Next batch: live variant reference proof

## Intent

Demonstrate the full offline variant path against locally running Search APIs: frozen capture, pooled judgements, N-way scoring, selected-variant merge verdict and an authenticated human exception. Keep the example synthetic and reproducible on the lab laptop.

## Constraints

- Use the current frozen variant set and observation contracts only. Regenerate synthetic data where useful; do not read old pair-shaped observations through an adapter.
- Show two-variant replacement and three-variant ranking-change cases. The runtime default and evaluation baseline must be able to differ.
- Bind each gate report to the exact reviewed source commit. Publish signed evidence to Nexus after that commit exists; do not place a self-referential commit SHA in Git.
- Preserve measured quality and result-change values when an authorised reviewer accepts a bounded exception.
- Use existing synthetic generators, Search API, judgement service, Nexus and Gitea. Do not add a traffic splitter or online experiment service.
- Update current design guidance and Structurizr/Archify views so named variants, the baseline and decision record appear directly. Keep historical evidence clearly separate from current instructions.

## Acceptance

1. A live Search API returns the selected variant and configuration digest. A finite capture proves two or more variants from the same query suite; wrong or missing identity fails.
2. One pooled judgement set scores every variant. A frozen report contains all data, environment, evaluator and observation pins and the changed-result fraction.
3. Local gate runs show `pass`, `decision_required`, `approved_exception`, `blocked` and `invalid` with the correct source binding. A missing Nexus evidence bundle cannot pass a declared PR gate.
4. Documentation provides the reproducible command sequence and describes promotion of a selected replacement as a new production default. Diagrams match the implementation.
5. Focused tests and the relevant live probes pass. The review branch is committed and opened as a stacked PR; main remains untouched pending acceptance.

## Where to look

- [Variant contract](../variant-evaluation.md)
- [Variant capture worker](../../lab/variant_capture_worker.py)
- [Frozen evaluator](../../evaluation/offline.py)
- [Merge gate](../../lab/variant_gate.py)
- [Delivery workflow](../../lab/delivery/workflows/release.yaml)
- [Diagram sources](../diagrams/workspace.dsl)
