# Batch 7k2d: seven-day window assessment

Status: implemented with deterministic synthetic fixtures; awaiting review. The live ledger, collector probe and investigation gates move to [batch 7k2e](signoz-investigation-overhead.md).

## Intent

Show when the local SigNoz view supports a seven-day search SLO decision, and trace a bad result or operation to the exact request and retained evidence. Start from the [finite Job telemetry](signoz-connected-runtime.md) and [source-controlled dashboard](signoz-connected-investigation.md).

## Constraints

- Keep applications on vendor-neutral OTel contracts. Treat the frozen Blob report and human review as the promotion authority.
- A missing collector interval, insufficient sample count or unverified source-to-backend coverage must produce an **unknown** verdict. Do not infer success from absent telemetry.
- Keep normal traffic separate from warm-up, peak, stress and probes. Use the seven-day policy window and its 100-request minimum.
- Preserve distinct release, deployment, environment, comparison and immutable input identities. Keep dashboard dimensions bounded.
- Commit to a review branch, open a stacked PR and wait for user acceptance before merging to `main`.

## Acceptance criteria

1. Compute seven-day eligible/good/bad totals, target, remaining budget, burn and sample count from explicit counter buckets.
2. Require an independent request ledger, positive collector probe, complete aligned intervals and at least 100 requests before a `met` verdict.
3. Exercise fast, slow HTTP 200, error, deadline, retry, missing interval, failed probe, mismatch, no-data and low-sample fixtures.
4. Update the guide, evidence and roadmap; commit to a review branch and open stacked PRs. Leave `main` untouched.

## Where to find more information

- [Backend guide](../observability-backend.md), [dashboard evidence](../research/evidence/signoz-dashboard-2026-09-28.md), [finite Job evidence](../research/evidence/signoz-finite-jobs-2026-09-28.md)
- Search policy and analyser in `lab/observability/`; Gatling runner in `lab/run_gatling_job.py`; delivery verification in `lab/delivery_promote.py`
- [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)
