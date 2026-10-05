# Activate the calibrated judgement model

## Intent and constraints

Use the loaded MLflow model version 4 through both judgement APIs for new gaps.
Reuse its running KServe predictor; do not allocate a second GPU or reload weights.
Require matching numerical evidence and retain unqualified label accuracy.
Keep frozen gate evidence, thresholds and stored judgements unchanged.

## Acceptance criteria

- Both APIs report model version 4 and the pinned inference protocol.
- Real inference returns probabilities and can produce a relevance label.
- Repeated exact inputs reuse predictions without additional inference.
- Preserve source documents, PVCs and reference-label precedence.
- Record a reproducible activation command and block accidental bootstrap resets.

## Verification

The deployed full-catalogue API returned Exact with confidence 0.9722098068 for
a product-title smoke request. It inferred one pair; the repeat reused one cached
outcome and inferred zero pairs. The label was explicitly gate-ineligible.
The control runtime smoke check and API connection passed. This is serving and
cache evidence, not an independent model-accuracy assessment.

## Next batch

Push a fresh demo source commit and inspect additional-query labels, abstentions,
coverage and calculable nDCG in the new comparison report. Continue the walkthrough
using the same frozen standard suite.

## References

- [Model installation](../esci-model-installation.md)
- [Judgement resolution](../judgement-resolution.md)
- `lab/activate_judgement_model.py`
