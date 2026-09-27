# Local observability backend

SigNoz Community, ClickHouse and the SigNoz collector run in `lab-observability` on a dedicated k3d worker. Applications send vendor-neutral OTLP/HTTP to `lab-otel-gateway.lab-observability.svc.cluster.local:4318`. A single DaemonSet reads selected structured Kubernetes stdout events, attaches trace IDs and sends them through the same gateway. The gateway batches and forwards all three signals to SigNoz.

## Placement and pins

| Item | Local choice |
| --- | --- |
| Capacity | Host measured at 95.6 GiB RAM, 36.9 GiB free and 32 logical cores before installation; Docker VM had 46.9 GiB. A third `k3d-observability-0` worker has a 12 GiB limit. Existing two lab nodes and unrelated containers stayed running. |
| Backend | SigNoz Community chart `0.143.0` (application `v0.143.0`), archive SHA-256 `e3ec7144de45404b10837ef80e86c6cec4960cde41e914f4782d9205c739adad`. The chart and every running image are digest-pinned in [values](../lab/observability/signoz-values.yaml). The ClickHouse histogram UDF archive is SHA-256 checked for amd64 and arm64. The test-hook BusyBox image is not run during installation. |
| Gateway and log agent | OpenTelemetry Collector Contrib `0.161.0`, multi-architecture digest `fd328de2552466ad78385e1b1289c3f2402b1c45f265b252aab1955b42845ac1`. Its manifests include linux/amd64 and linux/arm64. Native Apple silicon remains an external validation task. |
| Storage | Local-path PVCs: ClickHouse 20 GiB, ZooKeeper 8 GiB and SigNoz state 1 GiB. Helm upgrades retain the PVCs; cluster removal or a normal uninstall is **not** a backup. Export configuration and copy persistent data before destructive recovery. |
| Retention | Chart defaults are seven days for traces/logs and 30 days for metrics. The earlier 72-hour/7-day draft needs configuration and verification after organisation setup. |

The [upstream local Kubernetes guide](https://signoz.io/docs/install/kubernetes/local/) calls for at least 8 GB memory, four cores and 30 GB storage and documents arm64 support. The extra worker keeps SigNoz within its own node limit while the Elasticsearch and delivery workloads continue on the existing nodes. These are lab allocations, not AKS sizing.

## Install and access

1. Create or label a worker `lab.relevance/role=observability` with enough capacity. For this Windows lab, the worker was added with `k3d node create observability --cluster relevance-lab --role agent --memory 12g --k3s-node-label lab.relevance/role=observability`.
2. From the repository root in PowerShell, point the installer at the existing `.lab` state directory containing `kubeconfig.yaml` and the bundled Helm executable, then run it:

   ```powershell
   $env:LAB_STATE_DIR = (Resolve-Path .lab).Path
   python lab/observability/install.py
   ```

   The installer downloads chart `0.143.0` when absent, checks its SHA-256, verifies the labelled worker and installs the backend, gateway and log agent. Re-running it upgrades the existing deployment and retains its PVCs.
3. Start `kubectl --kubeconfig "$env:LAB_STATE_DIR\kubeconfig.yaml" -n lab-observability port-forward svc/signoz 18090:8080` and open `http://127.0.0.1:18090`. In this lab, the approved [agent-root overlay](../lab/observability/signoz-agent-root-values.yaml) bootstrapped organisation `relevance-lab` with administrator `elastic-agent@lab.local`. Its password is in the ignored `.lab/secrets/signoz-agent-root.password` file and Kubernetes Secret `lab-signoz-root`; never commit or print it. Apply the overlay with `python lab/observability/install.py --agent-root` after creating that Secret. A separate human administrator still needs an invitation.
4. Confirm `kubectl --kubeconfig "$env:LAB_STATE_DIR\kubeconfig.yaml" get pods,pvc -n lab-observability`. A healthy Pod is not proof of ingestion. Check the active collector pipelines and send the [connected synthetic probe](../lab/observability/probe_connected.py). Before organisation setup, this SigNoz version configured `nop` pipelines and refused OTLP; after bootstrap, the pipelines export to ClickHouse.

The UI is accessible only through a local port-forward at present. Terminating the forwarding process closes that local entry point; the in-cluster services and PVCs continue running.

## Signal contract

| Source | Signal | Correlation |
| --- | --- | --- |
| Search API | `search.request`, query-understanding and Elasticsearch spans; unsampled eligible/good counters and duration histogram | `service.version`, deployment tier, traffic class and `request_id`; completion stdout carries trace/span IDs. The request and product bodies are excluded. |
| Control API and workers | HTTP server spans and `lab.operation.*` counters; operation completion events in the rebuilt image | Environment/comparison ID, fingerprint and immutable hashes appear only in spans and logs. Metric dimensions use a bounded operation kind. A failed operation emits an error type, not its exception message. |
| Selected Kubernetes stdout | One filelog agent per node; structured events only | The log parser promotes `trace_id`/`span_id` into OTel log context. It starts at the end of each file and excludes unrelated project containers and raw platform logs. |

The gateway deletes common query, product-body and authorisation attributes, has a 384 MiB memory limit, a 512-batch in-memory queue and a 30-second retry horizon. Export loss is possible; do not infer good requests from missing data. Search and lifecycle work must remain usable when the gateway or backend is down. The collector endpoint is an application contract; replacing SigNoz with New Relic changes gateway export configuration and dashboard/query definitions, not application SDK calls. The local [New Relic mapping plan](plans/otel-observability.md#new-relic-migration-boundary) remains to be verified against a tenant.

The [New Relic gateway profile](../lab/observability/gateway-newrelic.yaml) uses OTLP/HTTP over TLS with an `api-key` header sourced from a Secret and converts cumulative counters to delta at the gateway. The [local probe](../lab/observability/probe_newrelic_profile.py) sent synthetic traces and delta metrics through the pinned Collector to a mock OTLP/HTTP receiver with a dummy key. No tenant data was sent. Real deployment must choose the correct regional HTTPS endpoint, test counter resets and compare budget totals before using it for decisions. [New Relic OTLP guidance](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/).

## Investigation and evidence status

The [Archify investigation view](diagrams/interactive/observability-investigation.html) shows the intended path from a bad SLO event to the same service/time/cohort, trace, related log and immutable report. A slow HTTP 200 counts against responsiveness; failed restore and deployment verification retain operation and artifact references. The underlying frozen report remains authoritative for promotion.

The backend now ingests traces, metrics and selected structured logs. A synthetic three-outcome search probe and a real delivery operation have records in ClickHouse, including trace IDs shared between the delivery spans and logs. The [dated evidence](research/evidence/signoz-backend-2026-09-27.md) records the exact checks. Dashboard arithmetic, browser drill-through, retention changes, three delivery-target coverage and the ≤5% p95 overhead hypothesis remain unverified.
