# Search telemetry and SLO contract

The Search API exports OpenTelemetry traces and unsampled metrics through OTLP/HTTP. Structured completion logs carry the same trace/span IDs. Use [SigNoz](observability-backend.md#investigate-a-search-or-model-problem) to investigate an event; use verified counters and independent coverage evidence to assess an SLO.

## Search signals

| Signal | Contents | Boundary |
| --- | --- | --- |
| Trace | `search.request`, with `search.query_understanding` and `search.elasticsearch` children; incoming W3C context continues into the Elasticsearch call | No query text, product bodies or credentials |
| Metrics | `lab.search.eligible`, `lab.search.success_good`, `lab.search.responsive_good`; `lab.search.server_duration` in milliseconds | Valid accepted `/search` requests; pre-server connection failures need client-side accounting |
| Log | One `search.completed` JSON stdout event with UTC time, outcome, duration, traffic class and trace/span IDs; optional request ID | The scoped log agent collects stdout; no duplicate SDK log export |
| Resource | `service.name=search-api`, `service.namespace=relevance-lab`, version and deployment tier | Per-query identifiers and hashes stay out of metric dimensions |

| Accepted outcome | Success budget | Responsiveness budget |
| --- | --- | --- |
| Contract-valid HTTP 200, including empty results, ≤250 ms | Good | Good |
| Contract-valid HTTP 200, >250 ms | Good | Bad |
| HTTP 502 | Bad | Bad |
| Health check or invalid request rejected before acceptance | Outside this SLI | Outside this SLI |

Traffic class is `normal`, `warmup`, `peak`, `stress`, `recovery` or `probe`; other values become `unspecified`. Normal-load SLOs use the `normal` cohort. Inspect stress and other cohorts separately.

## Seven-day objectives

The [policy](../lab/observability/policies/search-slo-v1.json) defines:

- A rolling seven-day normal-load window and minimum 100 accepted requests.
- 99% success and 95% responsiveness within 250 ms.
- Independent coverage verification before a verdict. Missing data cannot count as good requests.

For each objective, allowed bad requests are `eligible × (1 − target)`. Remaining budget subtracts observed bad requests; budget consumption divides bad requests by the allowance. Slow successful responses consume the responsiveness budget.

[`slo.py`](../lab/observability/slo.py) checks synthetic event arithmetic. Zero events are **no data**; unverified coverage is **unverified**. It cannot detect telemetry loss and is not the dashboard's data source. The [backend guide](observability-backend.md#assess-a-seven-day-window) describes the independent ledger/counter check and its remaining live-coverage limit.

## Export behaviour

OTel is enabled when `OTEL_EXPORTER_OTLP_ENDPOINT` identifies a Collector. Bounded trace queues and two-second timeouts keep search execution independent of export delivery. The release pins OpenTelemetry Python 1.44.0. Metrics use cumulative temporality by default; the New Relic gateway profile converts counters to delta. Verify resets and totals on the destination backend before making budget decisions.

The stdout log path supplies correlation without using the experimental Python log SDK. Collector sanitisation, queue limits and provider boundaries are in the [backend reference](observability-backend.md#transport-and-provider-boundaries).

## Check the local contract

Prerequisites: Docker, a checkout and its Search API build context. Use PowerShell from the repository root:

```powershell
docker build -t relevance-search-otel-foundation:local lab/search-app
Get-Content lab/observability/probe_otlp.py -Raw | docker run --rm -i --network none --entrypoint python relevance-search-otel-foundation:local -
```

The build runs API tests; the disconnected probe checks emitted OTLP and correlated logs. Neither sends data to SigNoz or establishes live SLO compliance. A non-zero exit needs investigation before publishing that image.

The [foundation evidence](research/evidence/otel-observability-foundation.md) preserves the original probe and absent-Collector checks. A single request surviving an exporter outage is not a measured overhead result.
