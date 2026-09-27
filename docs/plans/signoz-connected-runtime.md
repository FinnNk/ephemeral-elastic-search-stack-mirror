# Batch 7k2c: connected SigNoz runtime investigation

## Intent

Complete the local observability demonstration from a search or operation SLO breach to its trace, related log and immutable report. Start with the pinned backend, stored signals and [source-controlled dashboard](signoz-connected-investigation.md). Test the runtime path rather than assuming API acceptance means a useful investigation.

## Constraints

- Keep OTel SDKs, OTLP meanings and the Search API contract vendor-neutral so New Relic remains a configuration and dashboard migration. Keep Blob reports and human review authoritative.
- Preserve Blob-only egress for independent producer/evaluator Jobs. Their completion correlation must use safe structured stdout through the existing scoped log agent, with no duplicate log route or secret-bearing fields.
- Keep normal, warm-up, peak, stress and probe populations separate. No telemetry gap may produce a green verdict. Use a seven-day search window and the 100-request minimum only when collection coverage is known.
- Work on a review branch and open a stacked PR. Do not merge main before user acceptance.

## Acceptance criteria

1. **Finite Jobs and target coverage.** Add safe completion events for independent producer/evaluator Jobs, rebuild and publish digest-pinned images, and verify the events in SigNoz. Exercise the installed control Pod and all three delivery targets with telemetry-enabled releases. Preserve both comparison fingerprints and exact release/deployment references.
2. **Window totals and collection coverage.** Extend the dashboard or companion checks to show seven-day eligible/good/bad totals, target, remaining budget, burn, sample count and collection gaps. Verify arithmetic with deterministic fast, slow-success, error, deadline and retry mixes. Mark no data and incomplete coverage as unknown, with no green verdict.
3. **Connected investigation.** In the browser, follow a slow HTTP 200 from a budget panel to its request trace and related log; follow failed index restoration to its operation and dependency evidence; follow failed promotion verification to the exact release and deployment. Record preserved filters, links and any manual fallback.
4. **Resilience and overhead.** Stop and restore the backend/collector and confirm serving work continues while the dashboard shows a gap. Check sampled-out trace behaviour. Compare the same frozen normal Gatling load with telemetry enabled and disabled against the provisional ≤5% relative p95 overhead hypothesis; record inputs, uncertainty and limitations.
5. **Reviewable completion.** Update the backend guide, design, diagrams, evidence and roadmap with observed behaviour. Revise the native/cloud plan if findings change its scope. Commit this batch to a branch and open a Gitea PR for user acceptance.

## Where to find more information

- [Dashboard evidence](../research/evidence/signoz-dashboard-2026-09-28.md), [backend guide](../observability-backend.md) and [parent observability plan](otel-observability.md)
- Independent Jobs in `data/` and `evaluation/`; delivery verification in `lab/delivery_promote.py`; Gatling runner in `lab/run_gatling_job.py`
- [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/) and [New Relic OTLP guidance](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/)
