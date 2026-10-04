# Category survey: no useful additional precision

The completed 512-pair survey found no useful gain from finer categories or
product-role instructions. All four contracts added only Exact labels after the
retained experimental stages, and all four made the same 14 errors. No labels
are qualified or active. The 80% gate remains unchanged at **29.71% coverage**.

Recorded on 4 October 2026. The analysis uses the frozen method from
[the preparation batch](esci-category-increment.md). Its source revision is
`732390dfdfbaa696b168683a0cfc059d68a8bf5c`; the results batch changes documentation
and retains aggregate evidence without changing that method.

## Additional labels

The four contracts use the same 512 published development pairs across 295
normalised query groups. The retained prefix, the Exact 0.95 stage followed by
the experimental recalibrator, accepted 150 pairs. The following counts concern
only the **362 pairs where that prefix abstained**.

| Contract | Added labels | Correct | Accuracy | 95% whole-query interval | Query groups with additions |
| --- | ---: | ---: | ---: | --- | ---: |
| A: broad category | 80 | 66 | 82.50% | 73.03–90.81% | 64 |
| B: leaf category | 79 | 65 | 82.28% | 72.97–90.67% | 64 |
| C: full hierarchy | 76 | 62 | 81.58% | 72.13–90.41% | 61 |
| D: hierarchy and role instructions | 77 | 63 | 81.82% | 72.16–90.41% | 62 |

Every addition is Exact; there is no accepted Substitute, Complement or
Irrelevant support. Each contract makes four Irrelevant → Exact, three
Complement → Exact and seven Substitute → Exact errors. Those error identities
are identical across all four contracts. The seven Irrelevant/Complement errors
span six query groups; six of the seven products have categories.

The Irrelevant → Exact estimate is **4/51 = 7.84%**, with a whole-query interval
of **1.67–16.40%**, for every contract. Its denominator is all 51 reference
Irrelevant pairs in the matched survey. Irrelevant contamination of accepted
Exact labels ranges from 5.00% to 5.26%. These development results fall short of
the [confirmation policy](../../plans/esci-cascade-confirmation.md).

| Paired contrast | Net additions | Coverage difference | 95% whole-query interval |
| --- | ---: | ---: | --- |
| B − A | −1 | −0.195 percentage points | −1.103 to +0.604 |
| C − B | −3 | −0.586 percentage points | −1.721 to +0.207 |
| D − C | +1 | +0.195 percentage points | 0 to +0.609 |

Coverage differences use all 512 matched pairs. Correct-addition differences
are identical: richer contracts change only correct Exact acceptances. The
role-instruction contrast's interval touches zero. None supplies a useful
precision improvement in this sample.

## Error and probability diagnostic

A separate retrospective CPU diagnostic inspected only these completed quick
outputs, their exposed references and the retained prefix. It selected no new
threshold, fitted no model and opened no other cohort.

- All 14 shared errors already have **raw Exact argmax** in every contract. The
  fitted score mapping did not create their wrong class.
- There are 75 unanimous additional acceptances, including all 14 errors.
  Agreement between these contracts supplies no error filter.
- Across all 512 pairs, the mapping changes 13–16 raw winners and reduces the
  total number of Exact winners. Raw residual Exact winners number 243–244;
  mapped residual Exact winners number 230–232.
- Adding role instructions changes one raw winner across the entire sample and
  none of the shared errors. It changes probabilities, but does not correct
  those cases.
- The shared errors include an explicitly different phone model, product-role
  distinctions and ambiguous requests. Published references remain authoritative;
  this inspection does not relabel them or establish why an annotation was made.

Source inspection confirms that the contract question reaches the model and
the token audit retains it. The current model is the question-conditioned
`Mapika/decider-4b` option classifier with an ESCI adapter and fitted score
mapping. It scores answer options and supplies no reasoning trace.
[The developer's model card](https://huggingface.co/Mapika/decider-4b) describes
the classification interface and confidence limitations. These observations
do not show that the model ignored its instructions.

## Execution and verification

| Check | Observed result |
| --- | --- |
| Exclusive execution | Owner's approved interrupted-run grant; twelve source-bound jobs complete, their containers removed and guardian creation identities stopped before the deadline |
| Numerical repeats | Four contracts × 32 matched pairs in forward/reverse order; maximum raw and mapped probability difference 0.0, no decision flips, tolerance 0.00001 |
| Frozen analysis | All source/input hashes match; saved mapped confidence ≥0.90 decisions retained; no recalibration |
| Uncertainty | Existing 2,000 whole-query resamples for statistics and 20,000 paired resamples for contrasts |
| Independent review | A separate read-only agent reproduced joins, masks, counts, intervals and exact error overlap from the same authorised quick data |
| Repeat procedure | Retained protocol replayed into a fresh output file; result SHA-256 matches the original exactly |
| New diagnostic | Completed CPU-only, source-bound analysis; earlier local import/serialization failures retained separately |

Ignored evidence lives under `.lab/esci-category-increment/`:

| Record | SHA-256 |
| --- | --- |
| Frozen protocol, `registered-01/protocol.json` | `499816707f7af473067facb584c695490fb965d4542ec66b57858b3033e4c737` |
| Residual result, `registered-01/result.json` | `81da80fa5b313bcafc247fb1d5452e8c3b8a9b9699fe58554c0163baf5884684` |
| Diagnostic aggregate, `diagnostic-03/summary.json` | `93d4567fc8137748d4b6cca7a812f43189d89b8cb3c1fa556545d770d3d3977f` |

Six Gitea-rendered static document previews were inspected in local Chrome at
1280 × 1000. Openings, tables, the probability diagnostic and next-survey
acceptance section are readable; no horizontal overflow was detected. These
previews establish document layout, not hosted UI or model quality.

The [aggregate validation record](esci-category-survey-results.validation.json)
keeps counts and provenance without publishing pair text or model weights.
Whole-window GPU handback remains a separate owner action; successful per-job
cleanup alone does not release that hold.

## Decision and limits

Do not spend the reserved full four-pass study on these contracts without a
distinct new measured reason. The next proposal is a
[small cached-model Exact check](../../plans/esci-exact-veto-survey.md), aimed
at the shared role and explicit-requirement errors. Its input-only packet is
prepared; no new inference is authorised by the completed quick-only grant.

These are exposed development results. Part of the retained recalibrator fitted
that development cohort, so its prefix is optimistic. The quick sample cannot
predict full-pool coverage or establish independent quality. Zero observed
Exact → Irrelevant errors do not establish a rare-error bound. Actual-gap human
references remain absent; fresh confirmation remains sealed.

Qualified coverage is still **2,946/9,915**. Reaching 80% requires **4,986 additional
qualified labels**. No gate exception, model activation or source-label change
has been made.
