# Informational nDCG significance

## Intent and constraints

Show uncertainty beside baseline-to-variant nDCG differences. Keep gate policy,
quality averages, frozen inputs and model thresholds unchanged. Use the existing
SciPy dependency, with fixed resampling seeds and bounded memory.

## Implementation

- Test per-query nDCG differences with a two-sided paired permutation test.
- Group case-varied and repeated requests by query, country, currency and filters.
- Bootstrap these request groups for a 95% percentile confidence interval.
- Apply Holm adjustment across variants and nDCG cut-offs within each suite or
  combined report. Use adjusted p < 0.05 for the informational status.
- Exclude queries without positive reference gain or paired finite scores;
  disclose their count. Fewer than two independent request groups is insufficient.
- Preserve raw statistics, method settings and grouping in retained report JSON.
- Show the mean tested difference, interval, raw and adjusted p-values, group count
  and exclusions in friendly reports. Explain when tested queries differ from the
  existing quality average, and that unqualified labels remain unqualified.

## Acceptance

Tests cover identical results, positive and negative differences, small samples,
repeated requests, missing labels, multiple comparisons and reproducibility.
Browser checks cover readable values and unavailable results. Existing scoring
and gate tests must pass unchanged.

## Next batch

Review and accept this report addition, then inspect a fresh source comparison
in the developer walkthrough. See [variant evaluation](../variant-evaluation.md)
for the report contract and [roadmap](roadmap.md) for current status.
