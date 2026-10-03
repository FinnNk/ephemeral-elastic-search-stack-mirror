# Fit complementary ESCI specialists

Status: the reserved pool and six fixed CPU classifiers have been measured.
None adds useful labels at the required precision. Actual gate coverage remains
29.71%. See the [results](../research/evidence/esci-fitted-specialists.md).

## Intent

Test whether a larger, separate fitting pool can supply high-precision labels
for the remaining gaps. Start with inexpensive models and published ESCI labels.
Use semantic and category information only where it adds a meaningful number of
labels over the simpler candidate.

## Constraints

- Verify the owner's reservation, source hashes and whole-query exclusions
  before reading its labels. Freeze product sampling first.
- Keep the existing 400-query development cohort, both original reservations,
  fresh category confirmation, official test and sealed research assessments
  out of fitting. The new fitting queries are excluded from future confirmation.
- Use original catalogue fields; synthetic price, popularity and stock cannot
  become relevance features. Do not expose reference labels or identifiers to
  feature generation.
- Perform CPU work while research owns the GPU. Cap threads and retain measured
  runtime. Use existing dependencies in isolated environments.
- Freeze a small candidate set and whole-query calibration split before fitting.
  Evaluate on the exposed development cohort as a screen; it remains development,
  regardless of its separation from the new fitting pool.
- Do not activate or import labels, change a gate or fit on unlabelled gap outputs.

## Work and acceptance

| Work | Required result |
| --- | --- |
| Materialise the fitting pool | Immutable label-free selection, catalogue inputs, selected published references and overlap receipt; no reserved references opened |
| Generate features | Lexical relations and optional pretrained query/product/category vectors; source/input/model hashes and CPU timings |
| Fit specialists | Small fixed linear and nonlinear candidates; separate query groups select class thresholds; unsupported classes abstain |
| Compare decisions | Full class confusion, accepted accuracy, coverage, I → E, Exact contamination and query uncertainty; retain unsuccessful candidates |
| Measure actual residual value | Score only unresolved, exception-eligible pairs; distinguish hypothetical coverage from current qualified coverage |
| Choose the next candidate | Prioritise a material addition to coverage subject to precision and harmful-error evidence; reject added complexity with negligible benefit |

The pool contains 16,768 pairs. Whole-query splitting assigns 11,749 pairs from
700 queries to fitting and 5,019 pairs from 300 queries to calibration. Sampling
was frozen before selected published labels were opened. The six candidates
were frozen before fitting outcomes; the exposed 400-query cohort was used only
for development screening.

The next batch tests [CPU pair models and prompt inference](esci-cpu-pair-judges.md).
A useful screen does not qualify a model. A selected candidate proceeds to the
[independent cascade confirmation](esci-residual-cascade.md#next-batch-qualify-complementary-stages)
with a frozen contract. Keep newly labelled gap-reference work separate from
candidate predictions.

## Sources

- [Residual survey results](../research/evidence/esci-gap-surveys.md)
- [Experiment tools](../../lab/experiments/esci-gap-surveys/README.md)
- Research-owned reservation:
  `.lab/esci-model-agent-repo/esci-tfm-experiment/data/interim/reservations/lab-gap-recalibrator-fitting-20261003.json`
- Owner's selection audit under
  `.lab/esci-model-agent-repo/esci-tfm-experiment/data/interim/lab-gap-recalibrator-fitting-20261003/`.
- [Quality policy and exclusions](esci-label-quality.md)
