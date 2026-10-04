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

## Detailed next batch: guidance and evidence

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
