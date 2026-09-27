# Batch 7k2d: connected window and investigation

## Intent

Show when the local SigNoz view supports a seven-day search SLO decision, and trace a bad result or operation to the exact request and retained evidence. Start from the [finite Job telemetry](signoz-connected-runtime.md) and [source-controlled dashboard](signoz-connected-investigation.md).

## Constraints

- Keep applications on vendor-neutral OTel contracts. Treat the frozen Blob report and human review as the promotion authority.
- A missing collector interval, insufficient sample count or unverified source-to-backend coverage must produce an **unknown** verdict. Do not infer success from absent telemetry.
- Keep normal traffic separate from warm-up, peak, stress and probes. Use the seven-day policy window and its 100-request minimum.
- Preserve distinct release, deployment, environment, comparison and immutable input identities. Keep dashboard dimensions bounded.
- Commit to a review branch, open a stacked PR and wait for user acceptance before merging to `main`.

## Acceptance criteria

1. Add a reproducible seven-day companion assessment or dashboard totals for eligible, good, bad, target, remaining budget, burn and sample count, with explicit collection coverage. Validate fast, slow-success, error, deadline and retry fixtures, including missing intervals and counter resets.
2. Use the running system to follow a slow HTTP 200 to its trace and related log, a failed index restore to operation/dependency evidence, and a failed promotion verification to its exact release and deployment. Record filters and any manual fallback. If browser access is unavailable, record API/storage checks separately and keep the browser gate open.
3. Check the installed control Pod and all three delivery targets with telemetry-enabled releases, preserving both comparison fingerprints and exact release references.
4. Interrupt and restore the backend/collector. Confirm serving continues, identify the telemetry gap, and check sampled-out trace behaviour. Compare identical frozen normal Gatling loads with telemetry enabled/disabled against the provisional ≤5% relative p95 overhead hypothesis; report sample sizes and uncertainty.
5. Update the runbook, design, diagrams where the actual path changes, evidence and roadmap. Create the next detailed plan.

## Where to find more information

- [Backend guide](../observability-backend.md), [dashboard evidence](../research/evidence/signoz-dashboard-2026-09-28.md), [finite Job evidence](../research/evidence/signoz-finite-jobs-2026-09-28.md)
- Search policy and analyser in `lab/observability/`; Gatling runner in `lab/run_gatling_job.py`; delivery verification in `lab/delivery_promote.py`
- [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)
