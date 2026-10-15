# Check required relevance evidence before Gatling

## Current behaviour and change

The standard result-regression and relevance captures already ran before
performance, but their validation occurred after Gatling. Declared additional
and extra standard query sets also ran after performance. A required relevance
failure could therefore waste a performance run.

For each selected candidate variant, capture and validate the mandatory
result-regression/relevance evidence, then capture and validate its declared
query sets, then run Gatling. Report-only sets remain informational. Retain
partial evidence when an earlier required check fails, mark performance as not
run and show that explicitly in the review report.

Successful promotion still requires all three reports and every required
query-set outcome. Partial evidence cannot pass the existing final validator.
No gate threshold, intent, exception rule or workload duration changes.

This reorders the per-variant promotion checks. The separate final production
active-versus-candidate comparison remains part of the final release process
after those complete checks.

## Validation

Forty-one delivery, production and query-set contract tests passed with locked
uv. Regression tests cover execution order, retaining incomplete/frozen-label
failures, retaining a failed required query-set report, rejecting partial
evidence for promotion and skipping Gatling after an earlier required failure.
The Chrome report fixture passed the explicit not-run performance state and
existing report/link behaviour. No live evaluation or load test was started.

## Next action

This batch follows the primary-control UI batch (#199). Merge #199 first, then
this batch. Activate only when current operations are idle.
The next new operation will use the revised order; retain current evidence and
allow an already running operation to finish under its original code.
