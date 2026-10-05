# Resolve judgements for additional queries

## Intent and constraints

Additional source query sets resolve gaps through the judgement API before scoring.
Keep the standard frozen suite unchanged. Pool results across all variants, reuse
exact-input evidence and freeze one judgement snapshot. Model predictions retain
provenance and qualification; report-only sets use exploratory selection. Required
sets still need authored references and qualified labels. Do not change thresholds.

## Acceptance criteria

- Register exact query bytes with the frozen catalogue and rubric.
- Resolve only missing pairs; repeat captures can reuse predictions and abstentions.
- Retain labels and the resolution receipt alongside observations.
- Show nDCG and baseline deltas, or an explicit reason they cannot be calculated.
- Disclose inference, reuse, abstentions, errors and excluded quality cases.
- Verify source comparison integration and API/report behaviour with focused tests.

## References

- [Variant evaluation](../variant-evaluation.md)
- [Judgement resolution](../judgement-resolution.md)
- `judgements/service.py`, `judgements/core.py`, `lab/delivery_source_comparison.py`

## Next batch

After acceptance, deploy the judgement and control images, then push a new demo
commit to trigger a fresh comparison. Inspect the four-query sneakers report and
verify a repeat uses cached outcomes. Retained older reports stay unchanged.

## Verification

Focused API, persistent-cache, scoring, source-comparison and gate tests:
61 passed, 49 subtests passed. Browser checks passed for unavailable nDCG,
resolution diagnostics, baseline overlap, progress, mobile layout and sign-in.
A real service instance with fixture predictions verified that repeating the
same additional queries reused both labels and abstentions without inference.
Live GPU inference and deployment of these changes await acceptance.
