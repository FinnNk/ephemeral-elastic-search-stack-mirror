# Promotion query sets

## Scope

Carry `gate/selection.json` additional sets into Integration, Staging and
Production checks for every selected candidate variant. Keep the catalogue's
standard manifest mandatory. No source selections, labels, thresholds or
existing retained reports are rewritten by this batch.

## Implementation

- Freeze query and reference-label bytes at the exact merged source commit.
- Run the existing standard functional/performance checks, then capture each
  additional set once for that candidate/baseline configuration pair.
- Reuse the judgement resolver and retain a single label snapshot per set.
- Apply the trusted required-set limits independently. Report-only failures
  stay informational; required failures and pending decisions block proposals.
- Retain a hash-addressed suite report and validate its complete declared set,
  source bytes, policy, standard measurements and runtime identities again
  when proposing and validating a reviewed deployment.
- Show named sets, their requirement and outcome in browser reports and PR
  prose. Combined averages remain informational; incomplete capture suppresses
  the combined view. Repeated query cases and pooled coverage are disclosed.
- Keep the primary manifest a single suite. Grouping queries within it does
  not create named sub-results; named additional sets provide that distinction.

## Validation

89 affected Python tests passed on Windows using the locked uv environment.
They cover required and report-only failures, real offline scoring with supplied
reference labels, fixed standard selection before workloads, exact-commit file
loading, missing/altered evidence, independent variant orchestration, report
hash verification, HTTP authentication and existing production checks.

The headless Chrome report fixture passed, including separate required and
informational outcomes, unavailable combined results and mobile layout. It uses
synthetic retained reports, not a live promotion. No new Gatling run, live
inference, proposal merge or deployment was performed.

## Activation and walkthrough

1. Review and merge this batch, then publish and activate the control runtime.
2. Build 184 declares report-only `sneakers`. Its retained evidence for
   delivery-state #25 predates this support and omits that set. The updated
   validator rejects it; do not deploy using the old evidence.
3. Rerun **Check and propose Integration** for build 184. Review the standard,
   `sneakers`, combined view and performance probe in the new report.
4. Review and approve only the resulting exact desired-state PR head, then
   deploy through the dashboard. Handle the superseded proposal explicitly.

Per-set promotion exceptions are not implemented. `Decision required` stays
closed; a source-merge exception cannot authorise a new target comparison.
