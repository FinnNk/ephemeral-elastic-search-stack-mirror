# Elasticsearch connection reuse: normal-path verification

The API now reuses verified Elasticsearch connections. Every capture still runs
fresh searches. Normal paired and N-way Jobs and the exact-commit source gate
passed against the million-product catalogue on 2 October 2026.

## Adopted change

| Behaviour | Implementation |
| --- | --- |
| Elasticsearch transport | One HTTPX client per API process; at most 64 connections, verified CA, unchanged 10-second timeout |
| Freshness | Every search sends a new Elasticsearch request; no observation or response cache |
| Capture scheduling | Existing eight query workers; sequential variants per query; unchanged retries, deadlines and worker image |
| Tracing | Inject the current dependency span's headers for each request; retain the frozen index attribute |
| Lifecycle | Close the pool when the server closes or cannot bind |
| Disconnected demo | Lazy dependency import; the in-memory backend still works with Python alone |

The [experiment](evaluation-throughput.md) selected this change against rules
committed before measurement. Six counterbalanced confirmation pairs showed:

| Median duration | Original | Adopted | Reduction |
| --- | ---: | ---: | ---: |
| Fresh 1,000-query, two-variant capture | 58.487 s | 45.530 s | 22.2% |
| Job creation → retained experimental report | 63.961 s | 50.375 s | 21.2% |

All six pairs improved, with zero errors and retries. That report boundary includes
capture, scoring and Blob read-back; it excludes deployment and release gates.
Adding evaluator pooling missed the incremental capture threshold. Async
scheduling, adaptive throttling, higher worker limits and concurrent judgement
resolution remain research code, with no normal-path switches. Gatling is unchanged.

## Normal Job and delivery checks

All captures used the frozen `retail-gb-1m-v1` index and all 1,000 queries.
Disposable Argo-managed environments pinned the old and new image digests and
variant configurations. Each API retained the experimental 250m CPU / 96Mi limit.

| Check | Fresh search responses | Result | Observed duration |
| --- | ---: | --- | ---: |
| Two-variant Job | 2,000 | All ordered IDs and totals match the frozen experimental observations | 50.766 s |
| Three-variant Job | 3,000 | All ordered IDs and totals match the frozen experimental observations | 72.906 s |
| Paired old/new Job | 2,000 | Zero changed queries | 37.391 s |
| Public capture → offline scoring → retained report | 2,000 | Zero changed queries; signed preservation gate passes | 41.391 s |

These are single functional runs. Placement and the two-image gate topology differ
from confirmation; their durations cannot be used as additional speed comparisons.
The jobs made 9,000 fresh searches in total. Repeated observations are evidence to
compare, not substitutes for later searches.

| Source check | Outcome |
| --- | --- |
| Local application tests | 15 passed, including real HTTP connection reuse, fresh response handling, upstream failure and invalid trust material |
| Disconnected demo with site packages disabled | Passed; no Elasticsearch client constructed |
| Source build run 58, attempt 1 | Passed 15 tests before build and in both amd64 and arm64 images; published a digest-pinned image |
| Source relevance run 59, attempt 1 | Rejected missing exact-commit report evidence |
| Source relevance run 59, attempt 2 | Passed after the signed report and attestation were published to Nexus; no human override |
| Stored OTel data for the new image | 7,000 spans each for request, query understanding and Elasticsearch; zero span errors; all dependency spans pin the frozen index |

The synthetic rule pool gave both gate variants nDCG@10 = 0.979894 and judged
coverage = 1.0. These labels were informed by earlier recall pools: this proves
preservation and transport, not independent relevance quality or customer benefit.
The arm64 image test is an emulated build check, not an Apple silicon workstation
rehearsal. Earlier source PRs retain their own evidence requirements.

## Pins and retained evidence

| Item | Pin |
| --- | --- |
| New source commit | `5c8339dc07948053eeeea8290dde7f637a89c42d` |
| Baseline source commit | `3ea07f0a355864aee34e0468ee06cb37322d222c` |
| New image digest | `sha256:90d3180aa108ba917c5b01948b7efa26d7bedd8400f4ff28f9203d47ac641340` |
| Baseline image digest | `sha256:b48c4cd1acf2ff50c1035009c642757ba3ee417c72ef397f73a8401d2bcbb295` |
| Environment-state revision | `fefbabcdef88efd41a1dce00bd7d5a5e0e72ecd8` |
| Report SHA-256 | `ecd450b5fac4a2d647fcf510b26cd78bef62198fa3437fa928881d72e0c42c06` |

- [Normal summary and gate verdict](evaluation-throughput/normal-summary.json).
- [Image and configuration definitions](evaluation-throughput/normal-environments.json).
- [Variant selection](evaluation-throughput/normal-variant-set.json) and
  [judgement manifest](evaluation-throughput/normal-judgement-set.json).
- [Raw proof archive hashes, Blob references and worker pins](evaluation-throughput/normal-archives.json).
- [Source CI status](evaluation-throughput/normal-ci.json) and
  [test log extract](evaluation-throughput/normal-tests.txt).
- [Owned resource cleanup](evaluation-throughput/normal-cleanup.json).
- [Stored span counts](evaluation-throughput/normal-otel.jsonl) and
  [read-only query](evaluation-throughput/normal-otel-query.sql).

Raw observations and the report were uploaded to hash-addressed Floci Blob objects
and read back for equality. The signed report and attestation are also retained in
Nexus under the new source commit's gate evidence path.

Disposable proof applications, namespaces and experiment services were removed.
The frozen index and evidence remain. The candidate is available in the registry;
accepted environments and main branches were not updated. Review and merge the
stacked project and source PRs before treating this as an accepted release.
