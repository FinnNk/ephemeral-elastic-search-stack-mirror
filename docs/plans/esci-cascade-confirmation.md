# Confirm a frozen ESCI judgement cascade

Status: specification for the next batch. No cascade is qualified. Actual gate
coverage remains 29.71%; the 80% gate is unchanged. This work follows the
[fitting screen](esci-fitted-specialists.md).

## Outcome and scope

Qualify one complete cascade for supplying missing ESCI judgements. Published
labels take precedence. Each model stage sees only unresolved pairs and can
return a label or abstain. Assessment covers both independent published pairs
and independently labelled pairs from the actual Search API recall pool.

The current development projection reaches 48.31% if its stages qualify. It
still needs 3,142 further labels for 80%. Improving that projection and proving
its labels reliable are separate tasks. See the [survey evidence](../research/evidence/esci-gap-surveys.md).

## Freeze before confirmation

Select one cascade using fitting, calibration and exposed development evidence.
Then freeze these items before inspecting any fresh confirmation outcomes:

- Source precedence, stage order, model/release/runtime hashes and feature code.
- Product fields, category handling, thresholds, class mapping and abstention rules.
- Fitting and calibration membership, using the owner's conservative
  `nfkc_html_whitespace_v1` query keys. Aliases from one query group must stay
  together; lexical tokenisation does not define independence.
- Confirmation reservations, sampling design, query/pair membership and sources.
- The quality policy below, analysis code and criteria for incomplete evidence.

Record a single cascade identity derived from these bytes. Each prediction must
retain its input hash and deciding stage. Confirm the complete cascade, including
its routing, rather than combining separate component passes. Keep stage-level
metrics to expose a weak stage hidden by the aggregate.

## Quality policy

Freeze an explicit cascade policy before confirmation. The original
[quality policy](../../evaluation/specs/esci-label-quality-v1.json) checks a
point estimate for I → E; the [class-threshold assessor](../../evaluation/calibrate_labels.py)
also checks upper bounds and Exact contamination. The cascade must name and
apply the stronger requirements below; it must not silently use the older
point-estimate check as equivalent evidence.

| Requirement | Frozen criterion |
| --- | --- |
| Accepted accuracy | Lower endpoint of a 95% whole-query interval is at least 95% |
| Irrelevant → Exact | Supported upper endpoint is at most 1% |
| Exact contamination | Supported upper endpoint is at most 1% |
| Basic support, separately for each cohort | At least 200 distinct normalised queries and 300 accepted pairs |
| Completeness | Every frozen pair has a prediction, abstention or recorded error; inference errors leave acceptance unresolved |
| Transfer to actual gaps | Independent, blinded human references are required; published-label confirmation alone cannot activate the cascade |

These are individual interval requirements, not a claim of simultaneous 95%
confidence across all criteria. For consistency with the existing interval
checks, use the 97.5th percentile as the upper endpoint of a central 95%
interval. Record any different statistical design explicitly before outcomes.

| Metric | Numerator | Denominator |
| --- | --- | --- |
| Accepted accuracy | Accepted predictions matching the reference | All accepted predictions |
| I → E | Reference Irrelevant accepted as Exact | All reference Irrelevant pairs, including abstentions |
| Exact contamination | Reference Irrelevant accepted as Exact | All accepted Exact predictions |
| Exact → Irrelevant | Reference Exact accepted as Irrelevant | All reference Exact pairs, including abstentions |

Keep confusion matrices, per-class precision, recall, accepted query support
and stage support. Classes with no accepted predictions have no precision
estimate. Reducing I → E by wrongly labelling Exact products Irrelevant is not
an acceptable way to increase coverage.

## Cohorts and practical support

Reserve fresh published confirmation with the research owner. Exclude all
fitting, threshold selection, earlier development and exposed confirmation
queries, official test, final assessments and specialist reservations. The new
1,000-query fitting reservation is permanently unavailable for confirmation.

Plan capacity for roughly 1,000–2,000 fresh query groups, rather than assuming
that 400 groups supply sufficient class support. Freeze any class-stratified
sampling and its analysis weights in advance. Do not keep adding samples until
a favourable bound appears; use a fixed design or a prespecified sequential
method. Unsupported strata remain inconclusive.

These planning counts concern **independent query incidents**, not pair-weighted
error rates:

| Observed error incidents | Queries needed for a one-sided 95% upper bound ≤1% | Queries needed for a 97.5% upper bound ≤1% |
| --- | ---: | ---: |
| Zero | 299 | 368 |
| One | 473 | 555 |
| Two | 628 | 720 |

An Irrelevant denominator needs enough I-bearing groups; contamination needs
enough groups with accepted Exact predictions. Previous development evidence
had only 137 I-bearing groups and 193 groups with accepted Exact predictions.
Many products from a few queries do not repair this shortage. The planning
counts do not establish bounds for differently weighted pair populations.

## Human references for actual gaps

Prepare the annotation packet while CPU fitting continues:

Use the [input-only packet tool](../gap-review.md) for reviewer files and the
operator mapping. Its preparation manifest is not a confirmation reservation;
the remaining steps and independent audit still apply.

1. Freeze an input-only sample from the actual unresolved, exception-eligible
   recall pool. Preserve the specialist exclusions. Record sampling strata,
   inclusion probabilities and hashes; do not select examples from known errors.
2. Show the query and relevant original catalogue fields. Hide candidate labels,
   scores, confidence, stage identity and outputs from other models.
3. Record independent human ESCI labels, uncertainty and a short reason. Use a
   second reviewer and adjudication for disagreement; unresolved references stay
   unknown and are reported rather than silently removed.
4. Freeze the reference source, reviewer/adjudication records and hashes before
   assessing the already frozen candidate.

Include accepted predictions and abstentions: sampling only accepted Exact
predictions can estimate contamination, but cannot establish I → E across all
Irrelevant gaps or the complete cascade's coverage. Stratified sampling requires
an explicitly weighted analysis. Do not report a convenient slice as the whole
recall pool.

New authoritative human labels can themselves fill gaps, with their source
preserved. They do not make the remaining model predictions qualified. Published
confirmation alone could support a narrower trial only if a separately recorded
policy permits it; this specification grants no such exception.

## Rare errors and incomplete evidence

Resample whole frozen normalised queries and retain pair weights. If a resample
has an empty denominator, report an unavailable interval and unresolved support;
do not discard those resamples. An empty Exact acceptance set has undefined
contamination, not zero contamination.

With no observed harmful errors, an ordinary percentile bootstrap returns
`[0, 0]`. That is not a supported upper population-risk bound. Keep it as a
clearly labelled descriptive result, and leave the usable pair-risk upper bound
unavailable unless the sampling design supplies a valid conservative bound for
that same estimand. A query-incident binomial bound cannot substitute for a
pair-weighted bound; treating clustered products as independent is also invalid.

Before the next confirmation run, review or extend the existing assessor's
rare-error handling. Reuse its membership, provenance and bootstrap checks;
do not introduce a second implementation of the same mathematics. Freeze the
chosen estimator and tests before labels are inspected. A separately designed
random-pair audit of a fixed finite recall pool may support finite-population
bounds, but that has narrower scope than qualifying a judge on future queries
and must be specified as such in the policy.

## Decisions and delivery

- Confirm only the frozen winner. Comparing several candidates or changing a
  stage after seeing confirmation consumes that evidence; reserve a fresh
  cohort for the revised cascade.
- Report published and actual-gap results separately. Passing one cohort cannot
  offset failure or missing references in the other.
- Verify isolated serving parity, tracing and source-separated persistence only
  after the selected release is frozen. CPU work can prepare these contracts
  while the research GPU remains occupied.
- Import eligible labels only after quality acceptance. Re-evaluate the exact
  source revision and selected variants, then publish its signed gate evidence.
- If quality, support or 80% coverage remains unmet, report the shortfall. A human
  exception requires an explicit recorded decision; do not issue one automatically.
