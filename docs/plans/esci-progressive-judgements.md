# Progressively fill ESCI judgement gaps

Status: implemented and measured; ready for review. Shared API persistence,
source separation and frozen exploratory/gate reports are verified.

[Measured evidence](../research/evidence/esci-progressive-judgements.md): 2,099
accepted Exact predictions, 4,821 abstentions and zero inference errors in
940.55 seconds. Exploratory coverage rises from 29.7% to 50.9%; gate eligibility
remains unchanged.

## Intent and constraints

Fill the frozen comparison recall pool progressively, retaining published labels,
model predictions and abstentions as distinct evidence. Measure exploratory
coverage before choosing the next model. Candidate version 4 is numerically
qualified but has not passed independent label-quality assessment.

- Preserve authoritative published labels and all earlier pass evidence.
- Pin catalogue, queries, observations, model release, policy and runtime image.
- Keep unqualified predictions out of gate selection; exploratory scores must be
  identifiable and rejected by the trusted merge gate.
- Infer only unresolved pairs, pool variants symmetrically and freeze one label
  selection before scoring. Never turn abstentions or failures into labels.
- Audit research query reservations before inference. The user authorised a
  recorded exception for isolated lab inference on 944 final-assessment queries.
  Exclude all six specialist queries and their 49 pairs. Preserve the original
  frozen research matrix and record exposure for future adaptive work.
- Coordinate a checkpointed GPU handover and respect its deadline. Do not change
  the model, prompt, mapping or thresholds based on this pass.
- Use current contracts directly. Recreate disposable API databases when their
  schema changes; do not add readers for old databases or artefacts.

## Work and acceptance

| Work | Required result |
| --- | --- |
| Preserve evidence | API returns source identities, model/version, release, policy, pass identity, confidence and attempts; earlier records remain queryable after restart and another pass |
| Select labels | Published labels win; gate selection uses only eligible labels; exploratory selection may use candidate predictions; selection is frozen and reported |
| Protect gates | A report containing unqualified labels cannot pass a trusted merge gate, even when reported coverage exceeds 80% |
| Freeze first pass | Audit protected query overlap; record exact eligible gaps and excluded pairs before deploying the pinned candidate |
| Measure | Record accepted labels, abstentions, failures, source contributions, per-variant coverage, remaining gaps and elapsed inference time |
| Finish | Remove temporary GPU resources, return the GPU, synchronise guides and workflow diagrams, commit and open stacked source/backup PRs |

## Next decision and sources

Review measured acceptance on the actual gaps before choosing another pass.
Independent label accuracy remains the next qualification batch; coverage alone
cannot establish eligibility for gates.

- [Numerical qualification](../research/evidence/esci-frozen-kernels.md)
- [Independent quality plan](esci-label-quality.md)
- [Judgement resolution](../judgement-resolution.md), `judgements/service.py`,
  `core.py`, `prepare.py` and `evaluation/offline.py`
- [Catalogue evidence](../research/evidence/esci-catalogue.md): 6,969 gaps in the
  recorded unchanged comparison, with 4,986 additional labels needed for 80%.
