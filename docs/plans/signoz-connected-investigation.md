# Batch 7k2b: connected SigNoz investigation

## Intent

Complete the local observability demonstration from a search or operation SLO breach to its trace, related log and immutable report. Start with the pinned backend and gateway in [7k2a](signoz-backend-and-investigation.md). Keep the dashboard and saved queries in source so a new lab can reproduce them.

## Constraints

- Organisation `relevance-lab` and agent administrator `elastic-agent@lab.local` are bootstrapped, with the credential outside Git. Invite the human owner as a separate administrator. Verify each connected result from stored signals, not Kubernetes readiness alone.
- Retain the current Search API and control OTLP contracts. Keep unsampled eligible/good counters separate by normal, warm-up, peak, stress and probe cohorts. Never use operation IDs, queries or product bodies as metric dimensions.
- Keep Blob reports, release digests and human review authoritative. Telemetry may link to them but cannot replace frozen comparison evidence.
- Preserve Blob-only egress for independent producer/evaluator Jobs; use safe structured Kubernetes logs for their operation and artifact correlation. Keep each source on one log ingestion route.
- Test native SigNoz navigation in the browser and record any filter or trace/log link that needs a fallback. New Relic tenant checks remain in [batch 8](native-cloud-validation.md).

## Acceptance criteria

1. **Organisation and ingestion.** Create the approved first administrator and organisation, verify the collector's active trace/metric/log pipelines, then send deterministic synthetic Search API and control events. Query the backend to prove all three signals arrived with service version, cohort, operation ID and immutable references. Record exact counts and loss/reset boundaries.
2. **Finite Jobs and target coverage.** Add safe completion telemetry for independent producer/evaluator Jobs and verify it through the scoped log agent. Rebuild/publish pinned images where required. Exercise the installed control Pod and all three delivery targets using fresh telemetry-enabled releases; show both environment fingerprints for comparisons and exact release/deployment references for promotion or rollback.
3. **Dashboard and budgets.** Provision a source-controlled SigNoz v2 dashboard. Show normal-load search success and responsiveness, accepted-operation deadlines, eligible/good/bad counts, target, remaining budget, burn rate, sample count and collection coverage. Keep other traffic cohorts separate. Validate arithmetic against deterministic good, slow HTTP 200, failure and deadline/retry mixes. Label no-data and incomplete coverage without a green verdict.
4. **Connected investigation.** In the browser, follow a slow HTTP 200 from a budget panel to its request trace and related log; follow failed index restoration to its operation and dependency evidence; follow failed promotion verification to the exact release and deployment. Record preserved filters, links and any manual fallback.
5. **Resilience and overhead.** Stop and restore the backend/collector and confirm serving work continues while the dashboard shows a gap. Check sampled-out trace behaviour. Compare the same frozen normal Gatling load with telemetry enabled and disabled against the provisional ≤5% relative p95 overhead hypothesis; include run inputs, uncertainty and limitations.
6. **Reviewable completion.** Update the backend guide, design, diagrams, evidence and roadmap with observed behaviour. Prepare the batch 8 plan if findings change its scope. Commit this batch to a branch and open a Gitea PR for user acceptance before merging.

## Where to find more information

- [Backend operations guide](../observability-backend.md), [7k2a local evidence](../research/evidence/signoz-backend-2026-09-27.md) and [parent observability plan](otel-observability.md)
- Search SLO policy in `lab/observability/policies/search-slo-v1.json`; Search API instrumentation in `lab/search-app/telemetry.py`; control instrumentation in `lab/operation_telemetry.py`
- Independent Jobs in `data/`, `evaluation/` and `lab/evaluation_job.py`; delivery verification in `lab/delivery_promote.py`; Gatling runner in `lab/run_gatling_job.py`
- [SigNoz dashboard v2 API](https://signoz.io/docs/dashboards/dashboards-v2-api/), [trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/) and [New Relic OTLP guidance](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/)
