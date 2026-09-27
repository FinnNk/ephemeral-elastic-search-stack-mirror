# Batch 7k2e: connected investigation and overhead

## Intent

Complete the local path from a seven-day search or operation SLO breach to the exact request, dependency and immutable report. Use the [seven-day companion](signoz-window-coverage.md) and installed SigNoz dashboard, then measure telemetry failure isolation and search latency overhead.

## Constraints

- Keep Search API and control telemetry vendor-neutral. Blob reports and human review remain authoritative for promotion.
- No green verdict without a full independent request ledger, collector-probe coverage, aligned unsampled SigNoz counter buckets and at least 100 normal requests. Gaps remain unknown.
- Keep warm-up, peak, stress and probe traffic outside the normal SLO cohort. Keep release, deployment and frozen comparison identities distinct.
- Preserve Blob-only egress for finite Jobs and bounded gateway queues. Work on a review branch; do not merge `main` before user acceptance.

## Acceptance criteria

1. Connect a retained load-driver request ledger and collector probe to the seven-day companion. Verify counter reset handling and a live or accelerated synthetic window. Show gaps as unknown in the dashboard or an adjacent reviewable report.
2. Exercise the installed control Pod and all three delivery targets with telemetry-enabled releases. Preserve both comparison fingerprints and exact release/deployment references.
3. Follow a slow HTTP 200 from a budget view to its trace and related log; follow failed index restore to operation/dependency evidence; follow failed promotion verification to its exact release and deployment. Record browser filters and manual fallback. If browser access is unavailable, keep that acceptance gate open and record API/storage checks separately.
4. Interrupt and restore the collector/backend. Confirm serving continues and the coverage verdict records a gap. Check sampled-out traces. Compare identical frozen normal Gatling runs with telemetry enabled and disabled against the provisional ≤5% relative p95 overhead hypothesis, with sample sizes and uncertainty.
5. Update the guide, design, diagrams where the topology or path changes, evidence and roadmap. Create the next detailed plan; commit and open a stacked review PR.

## Where to find more information

- [Backend guide](../observability-backend.md), [window evidence](../research/evidence/signoz-window-2026-09-28.md), [finite Job evidence](../research/evidence/signoz-finite-jobs-2026-09-28.md)
- `lab/observability/window.py`, `lab/observability/dashboard.py`, `lab/run_gatling_job.py`, `lab/delivery_promote.py`
- [SigNoz correlation guide](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)
