# Reviewed release check plans

## Contract

Before Integration, Staging or production activation checks, suggest an explicit
check plan for the exact candidate deployment and current destination baseline.
Include source commits since the baseline, inherited and current additional
query sets with immutable source/content pins, and suggested per-variant intent.
Keep all protected standard/primary sets mandatory. Missing historical contracts,
divergent ancestry and conflicting suite versions must be visible to the reviewer.

The dashboard permits dispositions and reasons for every inherited set and an
explicit per-variant intent. Additional sets can be selected from files at the
candidate commit. Downgrading or retiring inherited requirements needs a reason;
required additions still need reviewed judgement files. Every suggestion must be
accounted for. The plan cannot change candidate variants/configuration or primary
policy. Cap the active additional sets at the existing eight-set contract.

A named human administrator approves the exact plan PR head in delivery-state.
Recording that approval merges only the plan record; it does not deploy. All
promotion entry points require a merged approved plan. Evidence and promotion
proposals bind the exact plan and its approval. Target, candidate, policy or plan
changes invalidate reuse. Production final checks use the same reviewed intents.

## Delivery and verification

Implement suggestion/validation, source-control approval, worker enforcement,
dashboard editing and report links in one reviewable batch. Test accumulation,
immutable historical suite pins, required-set dispositions, exact-head reviews,
plan staleness, bypass rejection and ordinary evaluation order. Keep the existing
lab, active checks, frozen releases and historical evidence unchanged until review.

## Implemented batch

The coordinator now suggests checks from complete Git ancestry, including
baseline-only commits for rollback or divergent histories. Historical suite
versions retain their original query and judgement content pins. The dashboard
edits dispositions, additional candidate files, per-variant release intent and
review reasons. A named administrator approves a content-addressed plan PR in
delivery-state; recording merges only that plan. The dashboard recovers recorded
plans from Git independently of operation history.

Promotion evaluation, proposal creation and deployment validation require the
current recorded plan. An explicit legacy intent cannot bypass that requirement.
Evidence records its start time and exact plan approval, which must precede the
checks. Production load and final comparison use the same plan. Existing
deployments and retained evidence are preserved, but new deployments cannot use
pre-plan evidence. Fresh installation packages the workflow with the ordinary
control runtime; there is no additional service or installation flag.

Validation on Windows: 133 tests passed across release plans, delivery gates,
production release, release controls, operations, dashboard, HTTP API, promotion
query sets and protected primary sets. The 23 release-plan tests cover inherited
and removed sets, distinct versions, immutable pins, mandatory-set protection,
intent review, exact-head approval, approval timing, stale plans, legacy bypass,
source-control recovery and selected catalogue/manifests. JavaScript syntax and
Git whitespace checks passed. In an isolated local browser fixture, the editor
displayed the accumulated commits and mandatory sets, retained notes across
rerenders and submitted the named plan operation while promotion remained
disabled. That fixture did not create or approve a live plan PR.

Activation and an end-to-end live promotion are pending review. No Mac execution
or production load run was performed for this batch. After merging and activating
when idle, resume the walkthrough by reviewing a plan for the selected build's
next destination, then run fresh checks. The source guide's matching plan section
is a companion documentation update; merge it after the lab implementation.
