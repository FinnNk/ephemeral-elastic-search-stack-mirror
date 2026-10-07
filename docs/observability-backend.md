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

1. Open the [search dashboard](https://signoz.localhost:34443/dashboard/01a0e51c-1043-79cb-94a8-9511cb0c665b) or [model dashboard](https://signoz.localhost:34443/dashboard/01a0ea97-de6a-74fb-bbc2-319512f4a8d2). Select the time range and the `$environment` (search environment) or `$model_version` selector. Use Traces for further service and tier filters. Note whether the issue is slow success, an error, low coverage or missing telemetry.
2. Find a trace for that service and time. A search trace has `search.request` → `search.query_understanding` / `search.elasticsearch`. Compare stage durations to locate the delay.
3. For judgement inference, follow `judgement.evaluate` → `judgement.resolve` → `judgement.http` → `kserve.predict` → `model.http` → `model.predict`. The evaluator continues W3C context through both HTTP hops.
4. Find the completion log with the same trace ID. Read its outcome and retained observation/report references. A sampled-out trace may have only a log; a missing span is not proof the operation succeeded.
5. Open the retained report for relevance, coverage or deployment decisions. A later offline score is a separate operation, linked by observation hashes rather than one long-lived trace.

The [investigation diagram](diagrams/interactive/observability-investigation.html) shows these relationships. Backend queries and UI links are provider-specific. Local evidence confirms stored trace/log correlation; the complete browser drill-through and instrumented three-target release rehearsal remain in the [validation plan](plans/signoz-merged-release-rehearsal.md).

## Interpret dashboards

| View | Useful for | Limits and next action |
| --- | --- | --- |
| Search activity | Whether the selected environment exports search counters, including probes and browser requests | Latest process counters reset on restart. They are not request totals for the selected window. |
| Search SLO | Normal-cohort eligible/good counts, percentages, allowance and burn; lifecycle success/deadline trends | Interval increases use the time picker; operation panels are lab-wide. Use the companion below for a coverage-verified seven-day verdict. |
| Model health | Inference errors, outcomes, batch latency, labelled coverage and label mix | Select `$model_version` to avoid combining historical judges. Version 1 abstains on every gap. These signals describe activity, not relevance accuracy. |
| Query-length gap-pool shift | Differences between the frozen query mix and pairs needing resolution | Includes cached resolution outcomes. It measures which queries lack labels, not drift against training data. |

Gap-pool shift is Jensen–Shannon divergence, bounded 0–1. The reference has one occurrence of each frozen query; the observed side is the query-length mix of pairs sent for gap resolution. No missing pairs means no new divergence value. Coverage and shift come from completed resolution pools and are separated by label selection: `gate`, `exploratory` or `demo`. Charts show interval averages of their last reported observations; exact pool counts remain in the frozen resolution report.

An empty chart is not a passing check. Start with **Search activity**: ordinary browser requests are unclassified, offline comparisons use probes, and normal-phase Gatling requests use the normal cohort. Only the latter belongs in the SLO charts. A diagnostic request can explicitly use that cohort, but a small sample does not establish an SLO. Idle counters have zero increase, so percentages and mean latency have no value. Short bursts before the first counter export can be missing from increases. Chart intervals adapt to the selected time range.

Coverage and gap-pool shift appear after a new additional-query or production-release comparison resolves its pool. Replaying retained scores makes no resolution calls. Neither dashboard reconstructs missing historical telemetry; widen the time window for earlier activity, or run a new comparison when appropriate.

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

For a fresh CPU lab on a laptop, use the smaller optional
[demo profile](fresh-install.md#add-demo-observability). It uses existing nodes,
12 GiB of PVC requests, bounded collector queues and 20% trace sampling.
Confirm seven-day logs/traces and 30-day metrics retention in the UI after
creating the first organisation. The instructions below describe the standard
installation with its dedicated worker.

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
