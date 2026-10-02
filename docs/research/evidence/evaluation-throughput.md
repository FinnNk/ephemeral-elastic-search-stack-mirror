# Offline evaluation throughput — 2 October 2026

**Decision:** adopt one verified connection pool per Search API process for
Elasticsearch requests. Keep eight query workers, sequential variants per query
and the current judgement resolver. Every capture performs fresh searches.

The [plan](../../plans/evaluation-throughput.md) was committed as `5ad2e5e` before
measurement. Its thresholds were 15% lower median capture time and 10% lower
capture-to-retained-report time, with at least four of six paired blocks improving.
Each additional technique had to beat the simpler qualifying alternative.

## Conditions and retained evidence

| Item | Recorded condition |
| --- | --- |
| Data | Frozen synthetic UK/GBP catalogue: 1,000,000 products; all 1,000 queries |
| API | One replica per transport arm; 250m CPU / 96Mi memory limits; same index and ranking settings |
| Worker | Finite Kubernetes Job; 1 CPU / 256Mi limits; no Kubernetes API token |
| Machine | Windows 11 Pro, Intel i9-13980HX, 24 cores / 32 threads, approximately 96 GiB RAM; Docker Linux VM approximately 46.9 GiB |
| Placement | API on k3d server node; capture worker on agent node; existing platform/observability services remained running |
| Experiment image | Pre-imported `relevance-throughput-experiment:20261002`; all four API Pods observed image ID `sha256:0f9c55e12eacfc312f847ed845cfcf3f774821b30ed67da37944608915d3ab69` |
| Execution | 57 fresh search captures, including warm-ups and a 50-query wiring check; 116,100 logical search requests plus 20 retry attempts |
| Identity | [Context](evaluation-throughput/context.json) records API/harness sources, image IDs, ranking configuration and resource quotas |
| Records | [Run ledger](evaluation-throughput/ledger.jsonl), [analysis](evaluation-throughput/analysis.json), [resource summary](evaluation-throughput/resources.json), [CPU counters](evaluation-throughput/cpu-ledger.jsonl) |

Each ledger entry includes a compressed raw-record hash and immutable Blob path.
Raw records retain observations, individual request timings, attempts and adaptive
concurrency history. The analyser verified all raw hashes and compared complete
observations across repetitions. No ordered list or total changed for an identical
query/variant scope. This establishes stability for these samples only.

The two-variant semantic hash was
`6e4c6a349f3fc38e18d0faefe9714515459e4932e5a1d6d2753852047c326c2c`;
the three-variant hash was
`f77264a4e7febe6db3f334565bed0fe79527a79d1a1d8b02c4d07a29e70e8768`.
The separate wiring scope has its own hash. Query-suite SHA-256 was
`4ab64cfbb3a3a581593ec380f1eae2a5c33ecbce791578ed7f814be06eb05946`.

## Transport confirmation

Six counterbalanced blocks captured all three options. Query order varied with a
recorded seed; each option returned observations in the original frozen order.

| Transport, eight query workers | Median capture | Median end to end | Worst capture | Errors / retries |
| --- | ---: | ---: | ---: | ---: |
| Original urllib / new TLS context per ES request | 58.49 s | 63.96 s | 59.68 s | 0 / 0 |
| Pooled API → Elasticsearch, urllib capture | 45.53 s | 50.38 s | 46.87 s | 0 / 0 |
| Both pools, HTTP/1.1 API and synchronous HTTPX capture | 39.01 s | 43.92 s | 39.69 s | 0 / 0 |

- **Elasticsearch pool qualifies:** capture −22.2%, end to end −21.2%; all six
  pairs improved. TLS context and verified connections are reused; search results
  are never reused.
- **Additional evaluator pool is excluded:** incremental capture −14.3%, end to
  end −12.8%. It missed the predeclared 15% capture threshold, despite improving
  all six pairs. Avoid adding a capture image/dependency and HTTP/1.1 serving
  change for this smaller incremental gain.
- **TLS-context-only reuse is excluded:** two screening runs had median capture
  52.02 s against 54.92 s originally, a 5.3% reduction.

For the first original transport screen, capture took 54.18 s, Job startup 1.44 s,
log collection 0.34 s, scoring 0.20 s and retention 0.06 s. Capture dominated this
measured path; optimising tiny scoring/retention stages would not clear the
end-to-end threshold.

End to end here means Job creation/wait, capture, log collection, synthetic pooled
label scoring, serialisation and verified Blob retention. It excludes API
readiness, input ConfigMap creation, source preflight, optional judgement resolution
and the release gate. Image pulls were already complete. These are experimental
reports, not a measurement of every operator action in a production workflow.

## Scheduling and request limits

Two counterbalanced screening runs per option used the same API/Job quotas.
These options did not warrant six-pair confirmation.

| Configuration | Limit | Median capture | Median end to end | Retries |
| --- | ---: | ---: | ---: | ---: |
| Original query threads | 16 | 61.08 s | 65.81 s | 0 |
| Original query threads | 32 | 64.28 s | 69.03 s | 20 |
| Elasticsearch pool, query threads | 16 | 53.64 s | 58.62 s | 0 |
| Elasticsearch pool, query threads | 32 | 56.70 s | 61.55 s | 0 |
| Both pools, query threads | 8 | 37.69 s | 43.45 s | 0 |
| Both pools, individual-request threads | 8 | 39.52 s | 45.05 s | 0 |
| Both pools, async queries | 8 | 37.72 s | 43.18 s | 0 |
| Both pools, async individual requests | 8 | 37.57 s | 42.30 s | 0 |
| Both pools, async individual requests | 16 | 47.35 s | 52.78 s | 0 |
| Both pools, async individual requests | 32 | 61.09 s | 65.98 s | 0 |
| Both pools, adaptive 8 → 32, minimum 2 | 32 ceiling | 38.97 s | 43.85 s | 0 |

Async and adaptive scheduling did not meaningfully beat synchronous query threads.
Higher limits slowed completion. The 32-worker original client required retries;
64 was excluded under the planned stop rule. Keep the default eight workers.

CPU counters show median throttled-period fractions of 97.7% originally, 93.8%
with the Elasticsearch pool and 88.8% with both pools during confirmation. This
supports CPU quota contention as an explanation for the higher-limit slowdown.
It does not prove that CPU was the only constraint or establish shared-engine
capacity. No API restarted or recorded an OOM in the [health snapshot](evaluation-throughput/api-health.json).

Two complete three-variant checks per original/both-pool option returned 3,000
fresh responses each, with no errors, retries or semantic changes. Median captures
were 88.11 s and 58.04 s respectively. They test N-way completeness; they do not
qualify the excluded evaluator pool incrementally against Elasticsearch-only
pooling. The adoption batch verifies that simpler option through normal Jobs.

## Judgement batching

The real judgement API and installed KServe **abstaining fixture** resolved a fixed
pool of 10,946 missing pairs, in 172 batches of 64. The isolated API used an empty
SQLite volume; the installed cache and source labels were untouched. The host
catalogue scan selected needed products in 13.11 s, separately from Job timing.

| Batch concurrency | Median resolution | Median Job duration | Labelled / unjudged / errors per run |
| --- | ---: | ---: | ---: |
| 1 | 6.76 s | 11.30 s | 0 / 10,946 / 0 |
| 2 | 4.54 s | 9.13 s | 0 / 10,946 / 0 |
| 4 | 5.87 s | 9.80 s | 0 / 10,946 / 0 |

Three counterbalanced rounds returned identical outcomes. Concurrency two helped
this fixture, but its absolute saving is about 2.2 s and its model performs no real
scoring. It neither clears a complete judgement-enabled workflow qualification
nor establishes capacity for a real model. Retain serial judgement batches.
[Judgement context](evaluation-throughput/judgement-context.json) pins the pair
pack and model; [individual runs](evaluation-throughput/judgement-ledger.jsonl)
retain the results. Preparing the cloned API needed two setup repairs (service
account and registry pull identity); readiness failures were excluded from timing.

The batching experiment uses a retained recall pool as its fixed input workload.
It does not replace any search capture or demonstrate a faster newly labelled
relevance report. Synthetic pooled labels were used only for search-report proxy
scoring; the abstaining model supplies no additional relevance coverage.

## Failure, fairness and observability checks

Five fixture tests passed, covering all six schedulers, fresh requests,
non-deterministic results, selectors, bounded transient/permanent failures,
adaptive backoff, a slow variant and two overlapping eight-request allocations.
The overlapping fixture stayed at or below 16 active requests within an aggregate
budget of 32. This is a functional budget check, not a multi-user capacity test.

A [live deadline check](evaluation-throughput/deadline.json) expired a blocked Job
at its three-second deadline. Kubernetes reported `DeadlineExceeded`, no success
and no capture output. This deliberate failure is distinct from successful timed
Jobs.

[Stored OTel spans](evaluation-throughput/otel-screen.jsonl) show all four marked
API modes emitting request, query-understanding and Elasticsearch spans. The
snapshot mixes request limits, so its average latencies are not transport
comparisons. API spans alone miss client connection retries; the run ledger owns
completion/retry counts. One deadline probe and read-only telemetry queries ran
alongside confirmation; existing services and the idle judgement clone remained
running throughout.

## Limits and next step

- Local x86-64 samples with a quarter-core API quota; no Apple silicon, Azure,
  GHES, p95 or Gatling/NFR claim.
- The adaptive prototype tested one bounded control policy. Scheduler queue
  waiting was not separately instrumented; no adaptive allocator is adopted.
- Experimental workers used an imported cached image tag with `Never` pull policy.
  API image IDs were observed; per-Job worker image IDs were not retained. Source
  bytes were held fixed, and the normal adoption proof uses a registry digest.
- No observation reuse, result cache, compatibility adapter or automatic approval
  was introduced. Alternative implementations remain in the research harness.

Proceed with the [adoption batch](../../plans/evaluation-throughput-adoption.md),
then return to the roadmap's existing HTTPS control-session work. Reproduce from
the [experiment harness](../../../lab/experiments/evaluation-throughput/README.md)
at the experiment revision, before its baseline API changes.
