# Batch 7k: OpenTelemetry observability and SLOs

## Intent

Give the lab one SigNoz dashboard for activity, service-level objectives (SLOs) and error budgets, with direct navigation between metrics, traces and logs. Preserve enough context to follow a slow search or failed environment operation across service boundaries. Use OpenTelemetry (OTel) instrumentation and collection so New Relic can replace SigNoz in the eventual deployment.

**Status: implementation split into [7k1 Search API foundation](../observability-foundation.md) and [7k2 SigNoz investigation](signoz-backend-and-investigation.md), after [7i: Kubernetes controls](kubernetes-control-services.md) and [7j: independent data/evaluation contracts](independent-data-evaluation-contracts.md).** The first slice has measured Search API signal output and synthetic SLO arithmetic. No SigNoz deployment, connected dashboard or system-wide OTel coverage is claimed.

Here, **“observability v2 light” means a single pane of glass with connected investigation across signals**. The required journey is **SLO breach → affected operations → trace → related logs**, retaining the service, time window and applicable environment/release context. Use each platform's existing explorers and correlation features; build only the lab's instrumentation, configuration and dashboard definitions.

## Placement and ownership

| Component | Planned responsibility and boundary |
| --- | --- |
| Application instrumentation | OTel SDKs in the search API, control services and finite workers. Export asynchronously through OTLP. No SigNoz or New Relic SDK dependency in application logic. |
| Collector gateway | A stable OTLP Service in `lab-observability`. Normalise resource attributes, redact secrets, batch and export with bounded queues, retries and memory. Keep vendor export configuration here. |
| Infrastructure collection | Reuse supported Collector receivers and Kubernetes collection components for selected platform metrics and container logs. Scope reads to lab workloads; avoid collecting unrelated host containers. |
| SigNoz | Self-hosted Community deployment in `lab-observability`, using the upstream Helm chart, its supported Collector integration and persistent ClickHouse storage. Pin the chart and all images. Avoid duplicate log ingestion or overlapping collectors. |
| Dashboard and policies | Version-controlled SLO definitions, dashboard exports, saved queries, links and local alert rules. Provision repeatably. Link from the lab UI and operation/report pages into SigNoz. |
| Durable evidence | Frozen inputs, observations and comparison reports retain their existing stores and hashes. Telemetry has bounded retention and links to that evidence; it is not the replay record. |
| New Relic target | Alternate Collector export profile, attribute/query mapping, service-level definitions and dashboard specification. Verify OTLP output locally; actual ingestion and UI equivalence require an authorised tenant in batch 8. |

SigNoz documents an **8 GB RAM, four-core and 30 GB storage minimum** for local Kubernetes, with arm64 support. These are upstream requirements, not measured spare capacity on this laptop. Start the batch by measuring available resources alongside Elasticsearch, Nexus and the remaining lab services. Verify the pinned images for both architectures and set requests, limits and retention from that evidence. If the stack does not fit, record the required resource adjustment before deployment. Do not silently remove core services to make the demonstration pass. [SigNoz local installation](https://signoz.io/docs/install/kubernetes/local/)

Start with 72-hour logs/traces and seven-day SLI metrics, subject to the selected edition's supported retention controls and measured disk use. Older budget windows may outlive their individual traces; mark expired detail explicitly and keep the retained report link. The observability namespace shares the cluster's failure domain; it cannot prove the cluster's availability while that cluster is down. Telemetry export failure must not prevent searches, comparisons or lifecycle work from completing.

## Signal and correlation contracts

| Signal or boundary | Required context and behaviour |
| --- | --- |
| All signals | Stable `service.name`, `service.namespace`, `service.version`, deployment environment and Kubernetes resource identity where applicable. Pin semantic-convention versions. Use a documented `lab.*` namespace for lab attributes. |
| Request traces | W3C trace context across HTTP calls; spans for query understanding, Elasticsearch requests and reranking. Capture duration, outcome and bounded error category. Existing request IDs remain searchable. |
| Workflow traces | Operation, comparison and CI run IDs; release/source revision; baseline/candidate fingerprints; catalogue, query, judgement, observation, recipe and report references where relevant. Persist correlation context across restarts. Link the independently packaged producer, capture Job and evaluator by immutable artifact references as well as operation IDs. Use span links and explicit operation IDs for asynchronous Jobs, polling and Git reconciliation; avoid one trace spanning a three-day lease or human review. |
| Logs | Structured records with severity, event name, service/resource fields and native OTel trace/span IDs when a span exists. Include operation IDs for background activity outside a span. Choose OTLP log export or parsed stdout per source, not both. |
| Metrics | Unsampled request counts, good/bad SLI counts, duration histograms, operation states and selected resource/dependency metrics. Declare units and histogram boundaries, including SLO thresholds. Check SDK flushing for short-lived Jobs. |
| Cardinality | Keep metric dimensions bounded: service, operation kind, deployment tier, traffic class, dataset size class and SLO policy revision. Per-request/query/PR IDs and content hashes belong in traces/logs. Bounded resource identity may support instance-level views; document its series cost. |
| Data handling | All demonstration requests remain synthetic. Exclude authorisation headers, tokens, SAS query parameters, credentials and full product/response bodies. Prefer immutable input references to copying payloads into telemetry. |
| Third-party services | Use existing metrics/log interfaces and caller-side spans for Gitea, Argo CD, Nexus, Blob, snapshots and Elasticsearch. Join by time, resource and deployment IDs where trace context is unavailable; do not invent spans inside uninstrumented services. |

Collect 100% of the small acceptance scenarios so their navigation is deterministic. Configure bounded sampling for larger runs; record the policy with run evidence. **SLI totals must remain independent of trace sampling.** Aggregate metric points identify a population, not every underlying request: use exemplars when supported end to end, otherwise open a trace query with the same service, time and cohort filters. Make a missing/sampled-out trace explicit.

SigNoz supports trace-to-log and log-to-trace navigation using trace and span IDs. Its documented mechanism informs the contract; verify it against the pinned build. [SigNoz correlation guide](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/)

## SLOs and error budgets

An SLI is a measured proportion of good events; its SLO is the required proportion over a defined window. An error-budget event is **any eligible event that fails that SLO's definition**, including a successful response that is too slow. Keep budgets separate for each objective and cohort; do not add overlapping failures into one global budget.

Start with a **rolling seven-day lab window** and show counts, coverage and shorter activity windows alongside it. These are provisional operational policies derived from the [design targets](../prototype-design.md#provisional-quantitative-targets), not claims that the lab already achieves them.

| Objective | Eligible population and good event | Draft target |
| --- | --- | --- |
| Search success | Valid search attempts at the declared observation point return a successful, contract-valid response. Empty results are valid; timeout, connection failure, malformed response and server failure are bad. | At least 99% good |
| Responsive search | The same eligible searches return a valid successful response within 250 ms. Slow HTTP 200 responses consume this budget. | At least 95% good |
| Warm API creation | Accepted API/query/ranking environment requests reach verified public-API readiness within 120 s, with a compatible retained index. | At least 95% good |
| Index-changing creation | Accepted 10,000-product index-change requests reach verified readiness within 300 s. Keep million-product and restoration-path cohorts distinct. | At least 95% good |
| Removal | Accepted explicit deletion or due expiry reaches verified resource removal within 300 s. | At least 95% good |
| Source to candidate | Accepted opted-in Gitea source updates reach the first verified candidate search within 480 s. Include queue/build/deploy time; define treatment of superseded source revisions before measurement. | At least 95% good |
| Promotion and rollback | An approved desired-state merge reaches Argo health and public-API verification within 120 s, with retained artifacts and a warm compatible index. Measure promotion and rollback separately. | At least 95% good |

Apply the initial search thresholds to the 10,000-product normal-load cohort; retain workload/profile identity and configure other populations separately. The seven-day window and event-based workflow percentages are new draft policies. Existing Gatling requirements remain unchanged, including p99 ≤ 500 ms and the strict **< 1%** failure check; a rolling 99% success SLO does not replace that run-level gate. Show cached CI duration, restoration path/time, comparison throughput and p50/p95/p99 as supporting measurements without inventing additional budgets before their populations and thresholds are agreed.

**Counting rules**

- Define an observation point for every SLI. Server spans describe requests that reached the API; client-side runner/load-generator observations also capture connection failures and caller-visible duration. Display these separately and never sum both into one denominator. An independent synthetic probe can measure reachability within the lab's failure domain; label its cadence and gaps.
- Record every accepted operation. Reconciliation classifies deadline breaches even if the worker never completes. Retried attempts retain the original operation ID and deadline; count the operation once per SLO. Keep a durable classification/export checkpoint so recovery does not silently lose or duplicate outcomes. User cancellations and superseded work have explicit, versioned eligibility rules and visible counts.
- Keep warm-up, normal, sustained peak, stress, recovery, probes and fault demonstrations as declared traffic cohorts. Stress breaches remain visible in their own cohort; they do not silently change normal-load eligibility. Unexpected failures in normal operation always consume the relevant budget.
- Human approval time is visible separately; promotion timing begins at the approved merge. Invalid requests rejected before acceptance are visible but outside an accepted-operation SLI.
- No traffic means **no data**, not 100% success. Show low sample counts, startup/reset boundaries, late telemetry, dropped signals and incomplete coverage. An unknown interval cannot be painted green; laptop sleep is a data gap, not proof of availability.
- SLI counters and threshold classification precede trace sampling. Validate counter temporality, resets and export/retry behaviour. If delivery loss prevents reliable totals, mark the affected interval incomplete rather than claiming durable exactly-once telemetry.

For target fraction `T`, eligible events `N` and bad events `B` in the same window:

| Value | Definition |
| --- | --- |
| Observed SLI | `(N - B) / N` |
| Allowed bad events | `N × (1 - T)` |
| Remaining budget | `N × (1 - T) - B`; show negative values when exhausted |
| Budget consumed | `B / (N × (1 - T))` |
| Burn rate | `(B / N) / (1 - T)`; 1× consumes the allowed fraction at the target rate |

For `N = 0`, ratios are undefined. Do not round an allowed fraction up into a free failure. For example, 1,000 requests at a 95% target allow 50 bad events; 30 slow successful responses consume 60% of that latency budget even with no HTTP errors. Budget exhaustion and sustained burn should appear as local alert state with links to evidence; no external paging integration or automatic promotion freeze is required in this batch.

## Dashboard and investigation

The landing dashboard is **Lab activity and service levels**. It retains time, service, deployment tier and traffic-cohort filters. Environment/release/operation selection narrows trace/log views; aggregate metric panels clearly state when they cannot honour a more specific filter.

| Section | Contents | Drill-through |
| --- | --- | --- |
| Activity | Active environments, outstanding operations, comparisons, builds, promotions, rollbacks and recent outcomes | Selected operation → related traces/logs and retained report or source PR |
| SLOs and budgets | Target, good/bad/eligible counts, observed SLI, remaining budget, consumption, short/long-window burn and data coverage | Breached objective → affected requests/operations in the same cohort and interval |
| Search | Rate, latency distribution, failures, result count, baseline/candidate context and pipeline timings | Slow or failed request → pipeline/dependency spans → correlated logs |
| Lifecycle and delivery | Queue and execution time, index reuse/clone/snapshot/rebuild path, readiness/deletion deadlines, deployment markers | Failed stage → worker/dependency evidence; release marker → matching deployment and comparison |
| Platform and telemetry | Selected Pod/node pressure, Elasticsearch health, dependency failures, Collector queue/drops/export failures and ingestion freshness | Resource/service → metrics and logs; lost telemetry → an explicit coverage warning |

Use native correlation first, then parameterised saved queries or supported dashboard links. Preserve applicable filters without copying IDs by hand. Where a platform cannot carry a filter or show an exemplar/span link, document the exact fallback and visibly retain the operation ID. Browser evidence must demonstrate the journey; placing three unrelated charts beside each other does not satisfy it. Use supported SigNoz [dashboard configuration and JSON export](https://signoz.io/docs/userguide/manage-dashboards/) rather than building a second dashboard application.

## New Relic migration boundary

| Preserve | Adapt and validate |
| --- | --- |
| OTel SDKs, W3C context, OTLP signals, event meanings and correlation IDs | Collector endpoint, TLS/authentication Secret, resource mapping and platform entity association |
| Versioned eligible/good/bad definitions, windows, thresholds and cohort rules | SigNoz queries/panels/alerts versus New Relic NRQL, dashboards and service-level definitions |
| Trace/log relationships and investigation scenarios | Platform-specific deep links, exemplars, span-link navigation and filter behaviour |
| Counter/histogram meaning, units and threshold counts | Temporality and aggregation support; New Relic recommends delta counters/histograms and exponential histograms. Keep explicit good/bad counters so the SLO does not depend on estimating a bucket at the threshold. |

OTLP makes the signals portable; dashboard JSON, query languages and native UI behaviour remain backend-specific. Keep both mappings in source and verify a representative exported payload with a local OTLP receiver. Do not call that a successful New Relic ingestion test. Actual tenant checks cover identity, all three signals, count equivalence, budget arithmetic and the same browser journeys. [New Relic OTLP configuration](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/), [log correlation](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-best-practices-logs/) and [service-level definitions](https://docs.newrelic.com/docs/service-level-management/create-slm/)

## Work and acceptance criteria

1. **Prove the backend fit.** Pin a supported Community chart and image set, inspect its actual dashboard/query/alert/retention capabilities, and measure memory/disk headroom. Use ordinary metric queries for SLO/budget panels if no suitable native SLO feature exists. Do not assume enterprise features or add another SLO platform. Record amd64/arm64 manifest support; native Mac execution remains batch 8.
2. **Publish contracts and collection configuration.** Define attributes, observation points, SLO policies and filter mappings; instrument search/control/worker boundaries. Show one linked asynchronous operation through acceptance, Job execution and publication. Correlate a producer publication, two-API observation capture and offline rescore across separate image identities using retained hashes. Retain finite-job telemetry after the Pod exits. Preserve frozen evidence and independent producer/evaluator ownership.
3. **Provision the dashboard.** Recreate the Collector, backend configuration, dashboard and local alert rules from a clean checkout. Keep named human access distinct from provisioning credentials. Verify healthy activity and failure states in the actual browser, including links from the lab UI.
4. **Prove three investigation journeys.** Follow a slow successful search from a latency-budget panel to its trace and logs; follow a dependency failure during index restore/provisioning to the failed stage; follow a promotion verification failure to the exact release and deployment. Preserve applicable filters, include baseline/candidate context, and record every native-correlation limitation and tested fallback.
5. **Check SLO accounting.** Run deterministic synthetic mixes of good, slow and failed requests, plus deadline-exceeded/retried operations. Compare expected and displayed counts/budget arithmetic. Show no-data, low-count, counter-reset, sampled-trace and Collector-interruption cases; totals remain correct or are explicitly incomplete. A relevance verdict below its threshold is distinct from an operational failure to execute the comparison.
6. **Bound overhead and failure effects.** Compare the same frozen normal workload with telemetry enabled/disabled; record latency, CPU, memory and ingest volume without claiming production capacity. Initial overhead hypothesis: ≤ 5% relative p95 latency increase under that controlled workload. Stop the Collector/backend and verify searches and lifecycle operations remain usable with bounded buffers and visible data loss. Evidence must include the resource footprint and retention configuration.
7. **Rehearse portability and document.** Validate the alternate OTLP export configuration locally; write the New Relic query/service-level/deep-link mapping and external checks. Update C4 containers/local/Azure placement and Archify investigation workflows, distinguishing synchronous spans from asynchronous links. Refresh design/access/recovery guidance, roadmap and batch 8 plan, then commit one stacked implementation PR.

## Where to find more information

- [Roadmap](roadmap.md), [topology boundaries](local-reference-boundaries.md), [native/cloud validation](native-cloud-validation.md)
- [Design targets](../prototype-design.md#provisional-quantitative-targets), [Gatling contract](../prototype-design.md#performance-check-the-search-api-with-gatling), [delivery targets](reference-ci-cd.md)
- `lab/search-app`, `lab/control_api.py`, `lab/lifecycle.py`, `lab/index_recovery.py`: request, operation and restoration boundaries
- `lab/evaluation_worker.py`, `lab/delivery_runtime.py`, `lab/delivery_gates.py`: finite execution, deployment verification and report references
- [OTel log correlation](https://opentelemetry.io/docs/specs/otel/logs/), [OTLP metric exporter configuration](https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/otlp/)

Upstream documentation checked on 27 September 2026. Recheck capabilities against the versions selected at implementation time.
