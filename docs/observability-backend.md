# Investigate the lab with SigNoz

SigNoz stores the lab's metrics, traces and selected structured logs. Applications send OTLP/HTTP to `lab-otel-gateway.lab-observability.svc.cluster.local:4318`; the gateway forwards to SigNoz. A scoped DaemonSet collects Kubernetes stdout through the same gateway.

## Access and check ingestion

1. Trust the [lab certificate](workstation-access.md), then open [SigNoz](https://signoz.localhost:34443) with your personal account. Keep human and agent identities separate. An administrator can supply a manual invitation link when SMTP is unavailable; an expired link needs a new invitation.
2. From the repository root in PowerShell, select the installed state and inspect the backend:

   ```powershell
   $env:LAB_STATE_DIR = (Resolve-Path .lab).Path
   $kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
   kubectl --kubeconfig $kubeconfig get pods,pvc -n lab-observability
   kubectl --kubeconfig $kubeconfig -n lab-observability logs deployment/lab-otel-gateway --tail=30
   ```

3. In SigNoz, choose the service, deployment tier and time interval of a known instrumented request. Confirm a stored metric, trace or completion event rather than relying on Pod readiness. Organisation bootstrap is required: before bootstrap this version can configure `nop` pipelines and refuse OTLP.

For local diagnosis or tools using the default API URL, keep this forward running in another terminal:

```powershell
kubectl --kubeconfig $kubeconfig -n lab-observability port-forward svc/signoz 18090:8080
```

Open `http://127.0.0.1:18090` while it runs. Stopping the forward closes that diagnostic entry point; the backend continues running.

## Investigate a search or model problem

1. Open the search SLO or model-health dashboard. Select the relevant time range, service/version, tier and traffic cohort. Note whether the issue is slow success, an error, low coverage or missing telemetry.
2. Find a trace for that service and time. A search trace has `search.request` → `search.query_understanding` / `search.elasticsearch`. Compare stage durations to locate the delay.
3. For judgement inference, follow `judgement.evaluate` → `judgement.resolve` → `judgement.http` → `kserve.predict` → `model.http` → `model.predict`. The evaluator continues W3C context through both HTTP hops.
4. Find the completion log with the same trace ID. Read its outcome and retained observation/report references. A sampled-out trace may have only a log; a missing span is not proof the operation succeeded.
5. Open the retained report for relevance, coverage or deployment decisions. A later offline score is a separate operation, linked by observation hashes rather than one long-lived trace.

The [investigation diagram](diagrams/interactive/observability-investigation.html) shows these relationships. Backend queries and UI links are provider-specific. Local evidence confirms stored trace/log correlation; the complete browser drill-through and instrumented three-target release rehearsal remain in the [validation plan](plans/signoz-merged-release-rehearsal.md).

## Interpret dashboards

| View | Useful for | Limits and next action |
| --- | --- | --- |
| Search SLO | Normal-cohort eligible/good counts, percentages, allowance and burn; lifecycle success/deadline trends | Plots are interval increases selected by the time picker. Use the companion below for a coverage-verified seven-day verdict. |
| Model health | Inference errors, outcomes, batch latency, labelled coverage and label mix | The calibrated model returns labels or abstains. Label mix and coverage describe its activity; they do not establish accuracy. Inspect source/model counts in the frozen report. |
| Query-length input shift | Changes in which query-product pairs reach inference | Measures selection into inference, not drift against training data. Inspect recall and existing-label coverage before attributing a change to the model. |

Input shift is Jensen–Shannon divergence, bounded 0–1. The reference has one occurrence of each frozen query; the observed side is the query-length mix of inferred pairs. No inference attempts means no divergence value. The metric dimensions are the numbered model version and fixed feature name; detailed counts remain in frozen artefacts.

Older retained Search API images or NetworkPolicies may lack OTLP instrumentation/egress. Deploy an instrumented release before expecting search spans; do not reinterpret an old frozen release as the new implementation.

Dashboard definitions are source-controlled: [search](../lab/observability/dashboards/search-slo-v1.json) and [model](../lab/observability/dashboards/model-health-v1.json). An operator can regenerate them from the repository root:

```powershell
python lab/observability/dashboard.py --write-json
python lab/observability/model_dashboard.py --write-json
```

To update the installed dashboards, supply a short-lived administrator session token in `SIGNOZ_ACCESS_TOKEN` outside Git, start the diagnostic forward above, then run:

```powershell
python lab/observability/dashboard.py --apply
python lab/observability/model_dashboard.py --apply
Remove-Item Env:SIGNOZ_ACCESS_TOKEN
```

Reapplication updates the named dashboards. A failed API call requires checking session expiry, organisation access and the forward; it is not a successful update.

## Assess a seven-day window

Prerequisites: unsampled interval counter increases, an independently retained HTTP-attempt ledger (including retries), and readiness probes covering the same complete window. There is no continuously retained seven-day ledger in the lab yet.

Prepare a JSON file with `window_start`, `window_end`, `interval_seconds`, `source_verified` and one aligned bucket per interval. Each bucket has `start`, `collector_ok`, `expected_requests`, `eligible`, `success_good` and `responsive_good`. Set `source_verified` only after verifying both sources for the whole window. From the repository root in PowerShell:

```powershell
$buckets = Read-Host 'Absolute path to the verified seven-day bucket JSON'
python lab/observability/window.py --buckets $buckets
```

| Result | Meaning |
| --- | --- |
| Complete coverage and sufficient events | Objective counts, allowance, remaining budget and burn can support the verdict |
| Missing interval, failed probe or ledger mismatch | `unverified`; observed totals are lower bounds |
| Fewer than 100 eligible events or no events | Insufficient data for the policy; not a passing SLO |

Finite Gatling checks use `coverage_probe.py` during the run and `export_window.py` afterwards. The latter joins retained probes, actual normal-phase arrivals and SigNoz v5 counter increases. Its run total can be `matched-total-only`: metric export can shift counts between adjacent minute buckets. That does **not** verify minute coverage or the whole seven-day window. The [finite-run evidence](research/evidence/signoz-investigation-2026-09-28.md) and [window fixtures](research/evidence/signoz-window-2026-09-28.md) retain their input conditions.

## Install and preserve the backend

Use an existing Kubernetes worker labelled `lab.relevance/role=observability`, retained lab state, Helm and adequate capacity. The local worker has a 12 GiB limit; this is a lab allocation, not AKS sizing. Installation from the repository root:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/observability/install.py
```

The installer checks the labelled worker and chart hash, then installs/upgrades the backend, gateway and log agent. Organisation bootstrap uses `--agent-root` only after the bootstrap Secret exists; subsequent credentials follow the [Key Vault boundary](keyvault-secrets.md). Do not create another bootstrap account for routine access.

| Dependency | Pin/storage |
| --- | --- |
| SigNoz Community | Chart/application 0.143.0; archive and image hashes in [values](../lab/observability/signoz-values.yaml) |
| Gateway and log agent | Collector Contrib 0.161.0, amd64/arm64 digest-pinned manifests; native Apple silicon remains unverified |
| Local-path PVCs | ClickHouse 20 GiB, ZooKeeper 8 GiB, SigNoz state 1 GiB |
| Retention | Chart defaults: seven days traces/logs, 30 days metrics; the earlier draft is not the deployed retention policy |

Upgrades retain PVCs; deleting a cluster or uninstalling services is not a backup. Export configuration and back up persistent data before destructive recovery. [Installation evidence](research/evidence/signoz-backend-2026-09-27.md) preserves the measured host capacity and original bootstrap conditions.

## Transport and provider boundaries

| Source | Correlation and limits |
| --- | --- |
| Search API | Version/tier/traffic class; stdout completion trace/span IDs; no request or product bodies |
| Control/workers | Bounded `lab.operation.*` metrics; environment IDs and hashes only in spans/logs; errors use types, not raw exception messages |
| Finite producer/evaluator Jobs | Safe completion events include source/input/report hashes; Blob-only egress, no direct OTLP |
| Scoped stdout agent | One per node, starts at file end, promotes trace/span IDs; excludes unrelated containers and raw platform logs |

The gateway removes common body/authorisation attributes. Its 384 MiB memory limit, 512-batch in-memory queue and 30-second retry horizon permit export loss. Missing data cannot imply good requests. Search and lifecycle operations must remain usable during an outage.

The [New Relic profile](../lab/observability/gateway-newrelic.yaml) uses OTLP/HTTP over TLS, an `api-key` from a Secret and cumulative-to-delta counter conversion. Applications retain their SDK contract; exporter settings, queries and dashboards change. A [local mock-endpoint probe](research/evidence/signoz-investigation-2026-09-28.md) checked synthetic traces/delta metrics with a dummy key. Real tenant ingestion, regional endpoints, counter resets and budget totals remain [external validation](plans/native-cloud-validation.md).

Current local proofs include stored traces/metrics/logs, digest-pinned Job completion hashes and search serving during a gateway outage. The four retained overhead runs missed the arrival gate; they are inconclusive. Continuous seven-day coverage, full browser drill-through, all delivery-target instrumentation and the ≤5% p95 overhead hypothesis remain open.
