# Million-product scale gate

## Intent

Test the existing release, index and comparison paths at 1,000,000 wholly synthetic UK products and 1,000 distinct queries. Use measured build, startup, comparison and load results to decide whether the solution shape remains useful at this scale.

## Constraints

| Area | Constraint |
| --- | --- |
| Source | Generate every product, query and judgement. Use [ESCI and ESCI-S aggregates](../research/esci-synthetic-calibration.md) as modelling references only; copy no records. Retain `retail-gb-10k-v1` byte for byte. |
| Freeze | Give the new release its own ID, profile/seed, object hashes, byte counts, query and judgement counts. Reject differing bytes for an existing release ID. Baseline and index-change candidates consume the same objects. |
| Capacity | Record host, Docker/k3d, Elasticsearch heap, disk, Blob size and concurrent workloads. Run one index build at a time until throughput and headroom are known. Avoid changing cluster sizing without recording the before/after settings. |
| Separation | API-only candidates share the write-blocked million-product index with distinct credentials. Mapping candidates get separate indices and build credentials. Cleanup must preserve the baseline release. |
| Metrics | Compare public API results and black-box Gatling profiles. Keep `_rank_eval`/`_profile` and index statistics as supporting component evidence. Sparse synthetic labels are proxies, not human relevance judgements. |
| Review | Keep this batch in a stacked branch and PR. Do not merge pending earlier batches. |

## Work

1. Implement a streaming, deterministic generator for 1,000,000 products and 1,000 distinct requests. Document category mapping, text-length/presence distributions, UK price/stock assumptions, head/tail requests and graded pooling rules. Add a small fixture and reproducibility tests before the full build.
2. Publish and verify frozen objects in Azure Blob Storage. Measure object bytes, generation time and deterministic rerun; use bounded memory and content hashes while streaming.
3. Build and write-block a million-product baseline index with a finite Job. Measure indexing throughput, disk and heap; tune batch size, shards or Job limits only with recorded evidence. Verify mapping, count, hash and index-scoped access.
4. Deploy a shared-index API candidate and a separate mapping candidate. Time warm startup and full reindex independently. Run result-preservation and judged relevance comparisons over all 1,000 requests, with query-level differences and immutable reports.
5. Run the fixed 10 requests/s Gatling smoke profile and the frozen normal/peak/stress profiles against both APIs. Validate arrival completeness, latency, failures and resource conditions. Record failed attempts and whether the local host meets each provisional target.

## Acceptance criteria

- Exactly 1,000,000 generated product IDs and 1,000 distinct query IDs are present; synthetic graded assessments, including explicit irrelevant and unjudged distinctions, are reproducible. The manifest and Blob objects verify byte for byte.
- The baseline index is write-blocked with 1,000,000 documents. A repeat load detects the existing frozen index without replacing it. An index-change candidate is built from the same release and removed without damaging baseline.
- The public APIs complete the 1,000-query result-preservation and relevance suites. Missing responses produce an incomplete report. The 15-minute functional comparison and two-minute warm shared-index startup are measured hypotheses; report misses rather than relaxing them silently.
- A full reindex is measured against the provisional 20-minute hypothesis, including Job startup and final verification. Record peak resource observations and disk footprint.
- At least one paired five-minute fixed-load smoke run and the normal, peak and stress/recovery profiles complete at this scale, or a capacity limit is identified with a reproducible failure report. Their black-box results are tied to exact workload and environment fingerprints.
- The release, native reports, comparison artifacts, host configuration and limitations are linked from a concise evidence summary. No production product or traffic data is included.

## More information

- [Design scale gates and targets](../prototype-design.md#provisional-quantitative-targets)
- [ESCI-informed synthetic profile](../../lab/profiles/esci-informed-uk-v1.json) and [modelling note](../research/esci-synthetic-calibration.md)
- [Current release generator](../../lab/release.py), [Blob/index loader](../../lab/load_release.py) and [index-change workflow](../../lab/index_candidate.py)
- [Frozen traffic model](../research/synthetic-traffic.md) and [Gatling runner](../../lab/gatling/README.md)
