# Elasticsearch timing and API CPU headroom

## Question

Production build 204 failed peak p99 at 987 ms against an 800 ms limit, despite
zero errors and p95 of 257 ms. Keep that budget unchanged while measuring whether
API CPU throttling contributes to the intermittent tail.

Record Elasticsearch's own `took` value as `elasticsearch.took_ms` on its
dependency span. The span's elapsed time also includes connection, network and
serialization and client scheduling delays, so the two measurements must remain distinct. Ignore
missing or malformed timing metadata without changing successful query results.
Elasticsearch's reported time includes internal communication and search queue
waits. It is not a query CPU timer; see the [Search API definition](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search).

## Experiment

Create two disposable namespaces using the same pinned build-204 image,
configuration, index, Redis binding, memory allocation and node placement.
Mount the same instrumented Elasticsearch method in both. Change only the API
CPU ceiling: 250m versus one CPU. These diagnostic copies are not frozen release
deployments and cannot supply promotion evidence.

Replay the same compiled warm-up and peak queries: 60 seconds at 10 requests/s,
then 900 seconds at 20 requests/s for each arm. The standard-library HTTP driver
runs from the control Pod, uses up to 64 client workers and labels traffic as
probe. It records request IDs, result-order hashes, client/API timings, failures
and arrival drift. It is not Gatling and does not recreate its transport exactly.

Collect API and Elasticsearch CPU-counter deltas and query SigNoz traces for each
unique namespace/window. Keep both elapsed dependency time and Elasticsearch
`took`, including slow-request examples. Check identical result hashes and actual
CPU limits before interpreting the comparison.

This is one sequential pair, so changes in host pressure can confound the result.
Do not claim general reliability or a capacity limit from one pair. Repeat in
reverse order if a result is material but not explained by the measured signals.

## Boundaries and execution

Require idle delivery and lifecycle comparisons before starting. The driver
stops issuing requests if delivery work starts. Copy only referenced credentials
and configuration into the labelled namespaces; grant no Kubernetes token to the
API Pods, create no public route, and remove owned namespaces on completion or
failure. Retain raw diagnostic files outside promotion records.

The normal Redis ingress policy accepts registered search namespaces. Diagnostic
namespaces deliberately lack that registration label, so the runner creates a
temporary Redis-only ingress policy matching its ownership and experiment ID.
It requires a direct Redis HGET to succeed in both previews before load begins,
then removes that policy alongside the previews. A Redis timeout followed by
local fallback would invalidate the comparison even if searches returned HTTP 200.

From the repository root in PowerShell, with the locked uv environment and lab
state configured, first obtain the API port with
`docker port k3d-relevance-lab-serverlb 6443/tcp`. Then run:

```powershell
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
$env:UV_CACHE_DIR = Join-Path $env:LAB_STATE_DIR 'uv-cache'
$env:PYTHONPATH = '.;lab;data;evaluation;judgements;lab/search-app;lab/observability'
uv run --locked python lab/experiments/peak-cpu-headroom/run.py --server https://127.0.0.1:<API-port>
```

Replace `<API-port>` with the discovered port. This targeted experiment expects
the existing build-204 preview and its compiled workload; it is not a fresh-install
step. Each arm reports progress every minute. Results appear beneath the ignored
`.lab/experiments/peak-cpu-headroom/` state directory. SigNoz analysis and the
observed outcome are recorded below. No p99 policy change is part of this batch.

## Observed result: 16 October 2026

The corrected pair, `67014db1`, used build 204 (`1.2.2+build.204.1`, source
`c83307104982`) and its default `ranker-a` configuration. The measured windows
were 12:09:53–12:24:53 UTC at 250m and 12:25:57–12:40:57 UTC at one CPU.
Each completed 18,000 requests without failure. Returned product ordering was
identical across both arms; client arrival drift p95 was approximately 0.15 ms.
Memory remained 96 MiB, and both APIs ran on the same node.

| Measurement | 250m API ceiling | One-CPU API ceiling |
| --- | ---: | ---: |
| Client p95 | 73.9 ms | 73.9 ms |
| Client p99 | 126.8 ms | 181.2 ms |
| Individual requests over 800 ms | 0 | 97 |
| API average CPU use | 0.0959 CPU | 0.0956 CPU |
| API throttled quota periods | 1.90% | 0.03% |
| Elasticsearch `took` p99 | 109 ms | 147 ms |
| Dependency span minus `took`, per-request p99 | 13.8 ms | 16.8 ms |
| Redis lookup span p99 | 1.65 ms | 1.72 ms |
| Request traces with `took` | 18,000 | 18,000 |

Extra API CPU nearly eliminated quota throttling but did not prevent a latency
burst during the final minute. In the [slow Elasticsearch trace](https://signoz.localhost:34443/trace/044407731b21e265f4f1b3cee5194c9e?spanId=29bd8c059d67d564&levelUp=0&levelDown=0), the
request took 2,967 ms, its Elasticsearch dependency span took 2,963 ms and
Elasticsearch reported 2,956 ms. Of 85 request spans exceeding 800 ms in this
arm, 84 had an Elasticsearch `took` above 800 ms. Client timings additionally
include time outside the instrumented request span. No Elasticsearch warning
or GC-overhead message was found in the checked six-minute log window around
the burst.

These observations do not establish that extra CPU made performance worse:
the pair was sequential, shared Elasticsearch and host conditions could change,
and this driver differs from Gatling. They show that the API's CPU ceiling alone
does not explain or prevent the observed burst. The original 987 ms Gatling p99
failure was not reproduced at either quota; its traces did not contain `took`,
so the new measurement cannot retrospectively divide that earlier dependency time.

Keep the 800 ms peak p99 budget and existing API resource settings for now.
Publish the instrumentation for subsequent source builds. Before attributing a
future failure to API CPU, inspect the corresponding `took` values and shared
Elasticsearch/host signals. A reverse-order pair would be needed to claim a CPU
performance improvement; no such improvement is claimed here.

The earlier trial `b0ec3628` is retained as invalid: missing Redis ingress access
caused timeout and local fallback. Its measurements are excluded from the table.
The corrected runner verifies Redis access before issuing load.

Raw request files remain in the control PVC under
`/state/experiments/peak-cpu-headroom/67014db1/`. Local `result.json`,
`runtime-limits.json`, `pressure-samples.jsonl` and `trace-analysis.json` are in
the corresponding ignored lab-state directory. The temporary previews and
Redis ingress policy were removed after execution. Deployment and promotion
evidence was not changed.

Focused validation passed: 10 lab Search API tests, four diagnostic-boundary
tests and all 22 delivery-source tests in their locked uv environments. SigNoz's
span detail view also displayed `elasticsearch.took_ms: 2956` on the example
above. The persistent changes remain subject to PR review; deployed build 204
continues to use its original image.
