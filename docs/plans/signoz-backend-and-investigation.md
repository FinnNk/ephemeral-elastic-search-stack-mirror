# Batch 7k2a: SigNoz backend and signal transport

## Intent

Install a self-hosted SigNoz backend and a stable OTel Collector endpoint for the lab. Add Search API and control telemetry, a scoped log route and the initial investigation diagrams without changing frozen evidence contracts. The [connected investigation batch](signoz-connected-investigation.md) completes dashboard, SLO and browser checks after the first SigNoz organisation exists.

**Status: implemented locally; awaiting review.** A dedicated 12 GiB k3d worker hosts the pinned SigNoz chart, ClickHouse, OTLP gateway and log agents. The instrumented control image is deployed and smoke-checked; the alternate New Relic export profile passed a local mock check. The approved agent account bootstrapped `relevance-lab`, and local storage now contains synthetic search traces and metrics plus correlated delivery traces and logs. Elasticsearch, Nexus, Gitea and control services remain running. The [backend guide](../observability-backend.md) and [evidence](../research/evidence/signoz-backend-2026-09-27.md) give the verification boundary.

## Constraints

- Pin and verify the SigNoz Community chart, Collector image and all dependent images. Confirm amd64/arm64 manifests; native Apple silicon remains an external test.
- Keep OTel SDKs and OTLP signal meanings independent of SigNoz. Use the gateway for batching, bounded queues, redaction, backend export and New Relic profile switching. Do not fork the application instrumentation for each backend.
- Use one log ingestion route per source. Preserve trace/span IDs, operation IDs and immutable report references; never emit credentials, raw customer-like queries or product bodies.
- Keep SLI counters unsampled. Record data gaps, low counts and Collector failures separately from good events. A slow successful response spends the responsiveness budget.
- Keep human review and immutable Blob reports authoritative. Telemetry is time-bounded operational evidence and cannot approve a promotion or replace a frozen comparison.
- Observe the installed `lab-control` Pod and all three local delivery targets; retain the separate reviewer and exact-head validation path. Trace a schema-changing promotion and rollback without treating the dashboard as release evidence.
- Use the platform's native dashboard and correlation features, with documented parameterised links only where navigation falls short. Do not build a second dashboard application.

## Acceptance criteria

1. **Capacity and pinned deployment.** Measure host, Docker and k3d CPU/memory/disk use. Allocate enough headroom without interrupting unrelated projects, then install a pinned SigNoz Community chart with retained ClickHouse storage in `lab-observability`. Prove reapplication from a separate checkout and record exact version/digests and current retention defaults.
2. **Collector and control coverage.** Expose one stable OTLP endpoint. Instrument the control API, lease worker, comparison capture Job and delivery coordinator. Verify bounded operation kind metrics, safe immutable references in traces/logs and a correlation path to the finite comparison Job. Remaining independent producer/evaluator Job coverage is in [7k2b](signoz-connected-investigation.md).
3. **Failure isolation.** Stop the gateway Pod and confirm the control smoke path still works. Restore the gateway. Record signal loss during the outage and distinguish transport checks from stored-signal and dashboard checks.
4. **Portability and synchronisation.** Validate an alternate local OTLP export profile for New Relic against a mock receiver, without tenant ingestion claims. Update the design, operations, access and recovery guidance, C4/Archify investigation views and evidence. Commit and open a review PR; leave acceptance and merging to the reviewer.

## Where to find more information

- [Parent observability plan](otel-observability.md), [foundation evidence](../research/evidence/otel-observability-foundation.md), [data/evaluation contracts](../data-evaluation-contracts.md)
- `lab/search-app/telemetry.py`, `lab/observability/policies/search-slo-v1.json`, `lab/observability/slo.py`
- `lab/control_api.py`, `lab/lifecycle.py`, `lab/control_comparison.py`, `evaluation/job_entry.py`, `lab/delivery_promote.py`
- [SigNoz local Kubernetes requirements](https://signoz.io/docs/install/kubernetes/local/), [OTel Collector Helm chart](https://opentelemetry.io/docs/platforms/kubernetes/helm/collector/), [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)
