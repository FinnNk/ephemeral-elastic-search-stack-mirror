# Developer workflow improvements

Make the developer walkthrough repeatable without operator commands or manual
report publication. Publish the changes as separate review batches.

## Batches

| Batch | Outcome | Acceptance |
| --- | --- | --- |
| 1. Guidance and evidence | Copyable examples, public API comments, result similarity summaries, readable delivery status | Examples explain where to paste each snippet; summaries include RBO and Jaccard; contention waits for a bounded period; a merged PR cannot be merged again |
| 2. Query sets | Standard suite plus explicitly selected additional suites | Inputs are frozen; each suite has separate metrics; combined metrics disclose weighting and overlap; extra suites report only unless selected as required |
| 3. Actions and coordinator | Remote preview, comparison and promotion commands; fresh PR comparisons | Authenticated API, durable operation status, exact commit evidence, public links on source PRs; promotion retains Git review and Argo CD deployment |
| 4. Request pacing | Eight workers adapt to overloaded search APIs | Fresh requests, bounded retries, explicit failures, measured slowdown and recovery; Gatling arrival rates remain unchanged |

## Constraints

- The standard suite remains required. Additional report-only queries cannot
  improve the standard suite's coverage or hide a regression.
- Result similarity describes change risk. No new RBO or Jaccard gate is added.
  A future policy may require a recorded decision for a large result change.
- Sign the original immutable build receipt bytes. Candidate code never receives
  signing keys or coordinator credentials.
- Keep the implementation current and coherent; do not add adapters for old
  report formats. Preserve retained historical evidence.
- Prefer a suitable open-source pacing component when it keeps the design simple.
- Do not replace the coordinator or run competing load tests while the current
  production evaluation runs. Review branches are not installed automatically.

## Recorded batch 1 scope

Add the rewrite test as a snippet, with placement comments. Review the Search API's
public functions and the disconnected demo's entry points. Add similarity values
to variant evaluation reports and the summaries people read. Keep them outside
the gate policy. Preserve an existing source approval requirement but default new
lab source repositories to zero approvals, retaining their required checks.

Handle delivery contention with a finite wait and a concise CLI error. For an
already merged deployment PR, report that state and verify only if its declared
deployment still matches the target. Never merge again or restore an older target.

Verify these integrity boundaries with focused tests. Review the contributor
guide, delivery guide and variant evaluation guide for matching instructions.

## Batch 1 verification

The guidance, summary and delivery-status changes passed 28 focused tests.
These cover an original non-canonical receipt, an occupied operation slot,
repeat merge prevention, a target that has advanced, new and existing source
protection, result overlap and frozen scoring. They do not establish runtime
installation or a completed production load test.

Next: [additional query sets](walkthrough-query-sets.md). Publish source-template
changes with the workflow batch so the source PR can use fresh automatic evidence.

## References

Batch 3 adds durable remote operations, scoped OIDC, automatic exact-commit
comparisons and manual workflow submissions. Isolated checks cover the real HTTP
handler, identity restrictions, retry safety and separate standard/extra scoring.
77 focused checks passed, and the new modules passed Ruff. Both affected Archify
views were regenerated and passed automated browser checks; their light previews
were inspected. Runtime activation follows human acceptance. Next:
[request pacing](walkthrough-pacing.md).

Batch 4 keeps eight workers and adds per-API overload pacing. In three sustained
overload trials, adaptive captures completed all 48 queries; fixed retries lost
12–14. Healthy trials had no waits or retries. Recovery deliberately trades
duration for fewer failed requests. See the [measurements](../research/evidence/evaluation-pacing.md).
59 focused capture, queue, scoring and gate checks passed. Source application
tests passed with the accepted trainers rewrite preserved. Next:
[activation and a live rehearsal](walkthrough-activation.md).

The initial source/template PR #27 now has passing release and relevance checks.
Its new pacing Job captured both exact-image APIs in 32.047 seconds without
retries. Provider verification also corrected workflow selection and ensured
comparison checkout preparation cannot disable Actions. See the
[live record](../research/evidence/walkthrough-feedback-verification.md).

The existing production loop completed with build 108. Desired-state PR 16 was
approved, merged and verified; retained verification SHA-256 is
`d581ada3fff08bfeae966e47efb693ccbd4c96dbec063d49f7e1a8ee89642a44`.
This confirms the installed delivery path, not the uninstalled feedback changes.

- [Developer walkthrough](developer-walkthrough.md)
- [Delivery](../delivery.md)
- [Variant evaluation](../variant-evaluation.md)
- [Technical authorship](../technical-authorship.md)
- `lab/delivery_cli.py`, `lab/delivery_promote.py`, `lab/delivery_release.py`
- `evaluation/offline.py`, `lab/variant_gate.py`
- `lab/delivery/bootstrap/`, `lab/search-app/`

## Current follow-up

[Complete Actions delivery and documentation](developer-delivery-docs.md) closes
the remaining developer kubectl steps. The next executable batch is
[activation](walkthrough-activation.md), after review; earlier “next” links above
record the sequence of completed review batches.

## Deferred: comparison evaluator boundary

Requested on 6 October 2026. Record for later implementation; do not change the
runtime or diagram as part of this follow-up record.

Expose one **Evaluate comparison** operation to the SDLC coordinator. The
comparison evaluator owns optional judgement resolution and frozen scoring;
the pure scorer continues to calculate metrics from fixed inputs.

| Component | Responsibility |
| --- | --- |
| Comparison evaluator | Pool query/product pairs across all variants, resolve gaps when allowed, freeze one shared judgement set and score the comparison |
| Judgement service | Return stored labels, reuse cached inference or infer missing labels, retaining provenance |
| Pure scorer | Calculate metrics from captured results and the fixed judgement snapshot |
| SDLC coordinator | Request evaluation, publish the returned report and apply gates |

Inputs include captured baseline/variant rankings, frozen catalogue and query
identities, request context, metric specification and judgement policy. Product
IDs must resolve to the frozen product content. Pin the inference model and
acceptance policy, with a timeout or inference budget.

Two explicit modes preserve repeatability:

- **New comparison:** optionally resolve gaps across the union of all variants,
  then freeze a shared judgement snapshot before calculating scores.
- **Recalculate a retained comparison:** reuse its judgement snapshot without
  inference or newly available labels changing the scores.

Return metrics and the snapshot identity alongside coverage, stored labels,
cache reuse, newly inferred labels, abstentions, errors and timings. Explain
why nDCG is unavailable when it cannot be calculated. Keep coverage distinct
from search quality and retain current gate policies.

Acceptance for the eventual batch: identical frozen inputs reproduce scores;
all variants use the same labels; retained comparisons make no inference calls;
reports disclose resolution outcomes. Update the SDLC diagram to show
**Evaluate comparison**, with a conditional **Resolve missing judgements**
branch that rejoins scoring, followed by **Review the report**.

Starting points: `lab/delivery_source_comparison.py`,
`lab/additional_judgements.py`, `evaluation/offline.py`,
`evaluation/query_sets.py` and
`docs/diagrams/archify/relevance-sdlc.json`. Create the detailed implementation
plan when this deferred work is scheduled.

## Deferred: focused delivery workflows

Requested on 6 October 2026 during the build 158 promotion walkthrough. Implement
after the walkthrough; keep the running promotion unchanged.

Replace the general developer form with focused Actions workflows. Each fixes
its operation and, where applicable, its target, exposing only relevant inputs.
Keep one shared delivery client and the existing approval and gate checks.

| Workflow | Inputs |
| --- | --- |
| Create preview | Build number |
| Promote to integration | Build number, change intent |
| Promote to staging | Build number, change intent |
| Deploy approved promotion | Delivery-state PR number |
| Compare builds | Baseline build, candidate build |
| Request rollback | Target, previously verified release fingerprint, change intent |

**Rollback must have its own visible workflow**, rather than being tucked into
advanced operations. It creates a reviewed rollback proposal; it does not bypass
evaluation, approval or deployment verification. Production retains its full
load gate and prepared-slot checks.

Keep production release in the control UI, including its rollback control and
approved-PR dropdown. Reserve **Advanced delivery** for less common verification
and maintenance tasks. Default the catalogue to `esci-gb-v1` for the lab.

Acceptance: each workflow shows only relevant fields, uses bounded choices where
supported by both Gitea and GitHub Actions, calls the shared client and publishes
the existing progress/review links. Update delivery guides and source templates
together. Create the detailed plan when this batch is scheduled.

## Deferred: coordinator-only merges for delivery state

Requested on 6 October 2026. Implement after the walkthrough; keep the current
promotion process unchanged.

Restrict merges to `delivery-state` main to the delivery coordinator identity.
Humans review and approve the exact proposal, then request deployment through
Actions or the control UI. The coordinator revalidates the proposal immediately
before merging, waits for deployment and publishes the completion report.

Direct merges currently require approval and `delivery/validation`, but skip
the coordinator's immediate revalidation and combined completion report.
Argo CD still deploys the Git change and the watcher subsequently verifies it.

Apply this restriction to delivery state only. Source PRs retain their normal
review and merge workflow. Preserve approval requirements, stale-review
protection, status checks and the prohibition on administrator merge overrides.

Acceptance: a human can approve but cannot directly merge a delivery-state PR;
the coordinator can merge an approved, valid proposal through the existing
workflow or UI. Failed validation prevents the merge, and successful deployment
retains its verification and completion report. Document the developer steps
and administrator configuration. Create the detailed plan when scheduled.
