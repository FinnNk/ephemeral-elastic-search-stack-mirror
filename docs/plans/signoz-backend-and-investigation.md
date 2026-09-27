# Batch 7k2: SigNoz backend and connected investigation

## Intent

Install a self-hosted SigNoz backend and a stable OTel Collector endpoint for the lab. Turn the [Search API foundation](../observability-foundation.md) into a single investigation path from an SLO breach through affected operations, traces and related logs. Add lifecycle, delivery and finite-job telemetry without changing frozen evidence contracts.

**Status: next batch after runtime consolidation and delivery rehearsal.** The earlier host measurement found about 3.4 GiB spare inside k3d node limits, below SigNoz's published 8 GB minimum. Recheck live headroom before installation and record the allocation chosen. Do not remove Elasticsearch, Nexus, Gitea or the control services to fit the dashboard.

## Constraints

- Pin and verify the SigNoz Community chart, Collector image and all dependent images. Confirm amd64/arm64 manifests; native Apple silicon remains an external test.
- Keep OTel SDKs and OTLP signal meanings independent of SigNoz. Use the gateway for batching, bounded queues, redaction, backend export and New Relic profile switching. Do not fork the application instrumentation for each backend.
- Use one log ingestion route per source. Preserve trace/span IDs, operation IDs and immutable report references; never emit credentials, raw customer-like queries or product bodies.
- Keep SLI counters unsampled. Record data gaps, low counts and Collector failures separately from good events. A slow successful response spends the responsiveness budget.
- Keep human review and immutable Blob reports authoritative. Telemetry is time-bounded operational evidence and cannot approve a promotion or replace a frozen comparison.
- Observe the installed `lab-control` Pod and all three local delivery targets; retain the separate reviewer and exact-head validation path. Trace a schema-changing promotion and rollback without treating the dashboard as release evidence.
- Use the platform's native dashboard and correlation features, with documented parameterised links only where navigation falls short. Do not build a second dashboard application.

## Acceptance criteria

1. **Capacity and pinned deployment.** Measure host, Docker and k3d CPU/memory/disk use. Allocate enough headroom without interrupting unrelated projects, then install a pinned SigNoz Community chart with retained ClickHouse storage in `lab-observability`. Prove reinstall from a clean checkout and record exact version/digests and retention settings.
2. **Collector and coverage.** Expose one stable OTLP endpoint. Instrument the control API, lease worker, comparison/capture Jobs, producer/evaluator Jobs and delivery coordinator. Verify service versions, operation IDs, both environment fingerprints and artifact hashes in traces/logs without using them as metric dimensions. Show asynchronous span links or an explicit operation correlation path.
3. **Dashboard and budgets.** Provision the lab activity/SLO dashboard from source. Show normal-load search success and responsiveness, operation deadline SLIs, eligibility, good/bad counts, target, remaining budget, burn and coverage. Keep warm-up, peak, stress and probes as separate cohorts.
4. **Connected drill-through.** In the browser, follow a slow HTTP 200 from its budget panel to the relevant search trace and log; follow a failed index restoration to its operation and dependency evidence; follow a failed promotion verification to the exact release and deployment. Record preserved filters and any fallback navigation.
5. **Failure and overhead checks.** Compare deterministic synthetic good/slow/failure and deadline/retry mixes with dashboard counts. Show no-data, telemetry interruption and sampled-out-trace states honestly. Stop the Collector/backend and confirm serving work continues; compare the same frozen normal load with telemetry enabled/disabled against the provisional ≤5% relative p95 overhead hypothesis.
6. **Portability and synchronisation.** Validate an alternate local OTLP export profile for the New Relic target, but defer tenant ingestion claims. Update the design, operations, access and recovery guidance, C4/Archify investigation views, evidence, roadmap and batch 8 external-validation plan. Commit and open a stacked PR; leave user acceptance and merging to the reviewer.

## Where to find more information

- [Parent observability plan](otel-observability.md), [foundation evidence](../research/evidence/otel-observability-foundation.md), [data/evaluation contracts](../data-evaluation-contracts.md)
- `lab/search-app/telemetry.py`, `lab/observability/policies/search-slo-v1.json`, `lab/observability/slo.py`
- `lab/control_api.py`, `lab/lifecycle.py`, `lab/control_comparison.py`, `evaluation/job_entry.py`, `lab/delivery_promote.py`
- [SigNoz local Kubernetes requirements](https://signoz.io/docs/install/kubernetes/local/), [OTel Collector Helm chart](https://opentelemetry.io/docs/platforms/kubernetes/helm/collector/), [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)
