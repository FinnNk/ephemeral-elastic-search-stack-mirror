# Lifecycle completion batch

## Intent

Finish the environment control workflow begun in the [lifecycle foundation](environment-lifecycle.md). An engineer should compare two pinned environments from the local UI, see a saved report and trust that expired or partially deleted environments are cleaned up even when the UI process restarts.

## Constraints

| Area | Constraint |
| --- | --- |
| Comparison | Reuse the frozen query and judgement releases and public search APIs. Pin both environment fingerprints and persist complete reports by hash. Keep relevance, result preservation and later Gatling verdicts separate. |
| Owner | The current loopback foundation identifies one trusted `local-operator`; add a named local identity boundary before claiming per-user ownership. Keep tokens out of browser responses, Git and reports. |
| Expiry | Preserve 72 hours after genuine use. Status polling, health checks and background scans must not extend leases. Run cleanup independently of the browser UI process. |
| Cleanup | Reuse the same idempotent path for manual and expiry deletion. Remove candidate-only indices when the index-change path exists; retain shared frozen indices and immutable artifacts. |
| Reliability | Recover requested, provisioning and deleting instances after controller restart. Keep failures visible and avoid claiming success when a request or report is incomplete. |
| Measurement | Record at least 20 warm removal trials, including failures, on the documented machine before reporting p95. Do not generalise one successful run. |

## Work

1. Add comparison create/status and report navigation to the control API/UI. Run two ready definitions against the same pinned query suite; preserve correlation IDs, errors and mode-specific verdicts.
2. Add named local operator authentication to the control surface, or an equivalent Gitea-backed local identity check, and record the authenticated owner on each instance and operation.
3. Run the expiry and retry reconciler independently of the UI server. Test a stopped/restarted server, incomplete provision, partial deletion and a lease that expires during downtime.
4. Exercise manual and expiry cleanup against live namespaced resources and credentials. Verify canonical Blob data, saved reports and shared indices remain.
5. Run at least 20 warm create/remove samples, publish the raw results and p95 with failures included, and update targets if the data warrants it.

## Acceptance criteria

- A user can complete create → ready search → comparison report → delete through the UI/API with no external Git service after bootstrap.
- Both compared definitions, dataset and query hashes, output completeness and verdict are visible; failed or partial comparisons cannot pass.
- Every ready instance records a verified owner and exact source SHA, image digest, dataset hash, fingerprint and expiry. No token appears in browser responses or saved reports.
- Genuine activity extends the lease; passive reads do not. Expiry begins cleanup within 10 minutes and finishes within 15 minutes under documented running-cluster conditions, including after a controller restart.
- On-demand removal is idempotent. Its measured p95 is ≤ 5 minutes over at least 20 warm samples, or the report explains a missed target and its cause.
- Recovery tests and live evidence show no orphaned namespace, credential or candidate-only index after the completed cleanup path.

## More information

- [Lifecycle foundation code](../../lab/lifecycle.py), [control API](../../lab/control_api.py) and [UI](../../lab/control-ui.html)
- [Foundation live evidence](../research/evidence/lifecycle-foundation/summary.json)
- [Prototype design: lifecycle and API](../prototype-design.md#environment-lifecycle-and-api)
- [Existing black-box comparator](../../lab/compare_search.py) and [graded evaluation](../../lab/evaluate_relevance.py)
