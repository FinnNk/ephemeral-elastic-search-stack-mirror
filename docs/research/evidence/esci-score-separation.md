# Saved scores and harmful Exact judgements

The completed survey's confidence, margin and entropy give **no convincing
signal for rejecting Irrelevant-to-Exact errors**. On this small development
sample, those errors are at least as confident as correct Exact claims. Keep
the [different-model role check](../../plans/esci-role-check-execution.md)
ahead of a confidence-only recalibration.

This CPU diagnostic, run on 4 October 2026, reuses contract A's frozen outputs
and the same already-exposed 512-pair references. It examines only A's 80
additional Exact claims after the frozen prefix: 66 correct and 14 incorrect.
It fits no model and selects no threshold.

## Observed separation

AUROC measures how often a score places a correct claim above an error.
Here, 0.5 means no useful ordering; larger is better. Confidence is the largest
class probability, margin is the difference between the largest two, and lower
entropy means a more concentrated probability distribution.

| Score, ordered towards correctness | Correct vs all 14 errors | Correct vs four I → E errors |
| --- | ---: | ---: |
| Mapped confidence | 0.619 | 0.447 |
| Mapped margin | 0.628 | 0.470 |
| Lower mapped entropy | 0.622 | 0.455 |
| Raw confidence | 0.611 | 0.432 |
| Raw margin | 0.626 | 0.436 |
| Lower raw entropy | 0.615 | 0.451 |

Median mapped confidence is 0.9327 for correct claims, 0.9216 for all errors and
**0.9332 for I → E**. Every mapped confidence falls in the fixed [0.90, 0.95)
band. Increasing the existing cutoff to 0.95 would therefore remove every
addition, including the correct ones; this observation does not select a new
policy.

| Reference outcome | Pairs | Query groups |
| --- | ---: | ---: |
| Correct Exact | 66 | 56 |
| Substitute → Exact | 7 | 6 |
| Complement → Exact | 3 | 2 |
| Irrelevant → Exact | 4 | 4 |

The 80 claims span 64 query groups; some groups contain both correct and
incorrect claims. Existing whole-query bootstrap intervals for mean scores
overlap substantially. Small-class intervals remain unavailable when a
resample lacks support. AUROC intervals were not calculated: the reused
bootstrap helper handles ratios, and this diagnostic adds no new statistical
method.

## Decision and limits

- There is a modest descriptive signal for general accuracy, but it does not
  prioritise a confidence-only filter for I → E protection.
- A multivariate score map fitted on an independent training cohort remains a
  separate hypothesis. These summaries do not test such a map.
- Four I → E cases cannot establish general effectiveness or a rare-error
  bound. The sample was selected after a partly fitted prefix and its labels
  were already exposed; it is not independent confirmation.
- Full-pool coverage and actual-gap human quality remain unmeasured. No labels,
  thresholds, serving releases or gate policy changed; qualified coverage is
  still 2,946/9,915 (29.71%).

The diagnostic verifies source hashes and exact joins before using values.
An independent replay into a fresh directory reproduced the aggregate SHA-256
exactly: `541e8325b1691e550a5257e4234e8ec3e8ff9392d0a76ca8c2a72b69d9765e7b`.
The [compact record](esci-score-separation.validation.json) retains the source
commitments and scores. The standalone tool and complete aggregate remain in
ignored state at `.lab/esci-category-increment/score-separation-01/`.

See the [category results](esci-category-survey-results.md),
[role-check preparation](esci-role-check-preparation.md) and
[next execution plan](../../plans/esci-role-check-execution.md).
