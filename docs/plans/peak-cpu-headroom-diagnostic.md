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
observed outcome will be recorded after execution. No p99 policy change is part
of this batch.
