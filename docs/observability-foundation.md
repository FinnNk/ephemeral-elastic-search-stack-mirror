# OpenTelemetry search and SLO foundation

The first observability slice instruments the public Search API and defines the normal-load search SLIs. It produces OpenTelemetry traces and metrics through OTLP/HTTP, plus structured completion logs with matching trace/span IDs. The [SigNoz backend guide](observability-backend.md) covers collection and the current investigation status.

## Search signal contract

| Signal | Contents | Boundary |
| --- | --- | --- |
| Trace | `search.request` parent, `search.query_understanding` and `search.elasticsearch` child spans; W3C context extracted from the incoming request and injected into the Elasticsearch HTTP call | No query text, product body or credentials in span attributes |
| Metrics | Unsampled `lab.search.eligible`, `lab.search.success_good`, `lab.search.responsive_good` counters and `lab.search.server_duration` histogram in milliseconds | Valid accepted `/search` requests at the server; connection failures before the server need a separate client-side SLI |
| Log | One `search.completed` JSON event with UTC time, outcome, duration, bounded traffic class, optional request ID and trace/span IDs | Standard output is the sole log source for this event; the scoped log agent collects it |
| Resource | `service.name=search-api`, `service.namespace=relevance-lab`, version and deployment tier | Release/tier values are configured at deployment; per-query IDs and hashes stay out of metric dimensions |

The server counts an HTTP 200 with a contract-valid response as **success good**. It counts that same response as **responsive good** only at or below 250 ms. A 502 spends both budgets. Empty results are valid. Invalid requests rejected before acceptance and health checks are outside these search SLIs. The traffic class is one of `normal`, `warmup`, `peak`, `stress`, `recovery` or `probe`; any other value becomes `unspecified`. The normal-load dashboard will filter to `normal` without hiding stress outcomes in their own cohort.

The Search API enables OTel only when `OTEL_EXPORTER_OTLP_ENDPOINT` points to a Collector. Exporters use bounded trace queues and two-second timeouts; search execution does not wait for telemetry delivery. The release image pins OpenTelemetry Python 1.44.0. The version and package role follow the [Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/) and [OTLP exporter](https://opentelemetry.io/docs/languages/python/exporters/) guidance. Python trace and metric SDKs are stable; the log SDK remains in development, so this slice uses correlated structured stdout instead.

## SLO accounting fixture

[`lab/observability/policies/search-slo-v1.json`](../lab/observability/policies/search-slo-v1.json) defines a rolling seven-day normal-load window: 99% search success and 95% responsive search. [`slo.py`](../lab/observability/slo.py) checks the arithmetic on complete synthetic fixture events. It reports eligible/good/bad counts, fractional allowance, remaining budget and consumption. Zero events are **no data**; a fixture without verified coverage is **unverified**. The fixture analyser cannot detect dropped or duplicated telemetry and is not the dashboard data source. The eventual dashboard must use unsampled OTel counters and show collection gaps.

The OTel metric exporter defaults to cumulative temporality. The Collector/New Relic profile must verify and, where needed, convert temporality before comparing counts. The metric definitions, units, cohort rules and thresholds stay stable; backend queries and links are platform-specific. See the [OTLP metric exporter specification](https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/otlp/) and [OTLP configuration](https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/).

## Local checks and capacity

`docker build -t relevance-search-otel-foundation:local lab/search-app` runs the Search API tests in the pinned image. The checked-in OTLP probe can be piped into that image with Docker networking disabled:

```powershell
Get-Content lab/observability/probe_otlp.py -Raw | docker run --rm -i --network none --entrypoint python relevance-search-otel-foundation:local -
```

The [foundation evidence](research/evidence/otel-observability-foundation.md) records the original trace/metric and log checks. The [backend guide](observability-backend.md) records the third k3d worker, pinned SigNoz installation and current ingestion state. A separate SigNoz Docker deployment belongs to other local work and is not the lab backend.

`lab/observability/probe_collector_outage.py` exercises one public API search with OTLP pointed at an absent Collector. The response still completed; SDK retries occurred afterwards. This checks fail-open serving for one request, not overhead under a Gatling workload.
