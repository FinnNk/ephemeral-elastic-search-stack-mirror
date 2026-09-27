# Million-product scale evidence

This run used the wholly synthetic [`retail-gb-1m-v1`](../million-synthetic-release.md) release on the Windows 11 local k3d lab. It tests the solution shape on one host; it does not estimate Azure capacity or a timing p95.

## Release and index

| Check | Observation |
| --- | ---: |
| Products / distinct queries / original graded assessments | 1,000,000 / 1,000 / 20,000 |
| Compressed product object | 104,911,501 bytes; SHA-256 `a6c78afb7df078016828a8a9a93b88b2d1db6a16ef64080a37dc33c23c2cc1d6` |
| Query object SHA-256 | `4ab64cfbb3a3a581593ec380f1eae2a5c33ecbce791578ed7f814be06eb05946` |
| Blob publish verification | 23.875 seconds |
| Shared index Job | 103.565 seconds; 1,000 batches of 1,000; 1,000,000 documents (9,656 documents/s over the Job) |
| Publish plus shared build | 135.563 seconds |
| Shared index store | 664,180,744 bytes; one shard; write-blocked |
| Separate mapping candidate | 1,000,000 documents; write-blocked; created in 113.844 seconds after Blob memory limit increase; 668,716,109 store bytes at a later sample |

The [recorded build measurements](million-build.json) include a clean rebuild in 48.750 seconds with an identical manifest and all three object hashes unchanged. Re-running the Blob/index loader took 3.860 seconds, found `created: false`, verified one million documents and the write block, and did not start an indexing Job.

Both indices use the same compressed release object. The baseline read credential cannot read the candidate index; the candidate read credential cannot read the baseline index or write to its own index. The [release generator](../../../lab/release_million.py), [bounded index worker](../../../research/platform-spike/index_job.py), [loader](../../../lab/load_million_release.py) and [access check](../../../lab/verify_million_access.py) make these checks repeatable. The ignored native result files are `.lab/evidence/million-release.json` and `.lab/evidence/million-access.json`.

## Environment creation and comparisons

| Environment | Index | Ready time | Result check |
| --- | --- | ---: | --- |
| `lab-million-baseline` | Shared | 8.156 seconds | Baseline for both pairs |
| `lab-million-api` | Shared | 7.719 seconds | 1,000/1,000 complete; zero changed ordered top tens; 637.781 seconds |
| `lab-million-index` | Separate | 113.844 seconds | 1,000/1,000 complete; 1,000 changed ordered top tens; 631.437 seconds |

For the mapping candidate, mean Jaccard@10 was 0.000632 and mean finite RBO@10 (`p=0.9`) was 0.001467 across the 1,000 returned lists. The title-as-keyword mapping is intentionally disruptive; these numbers describe result change, not relevance improvement.

Each 1,000-query comparison sends two requests per query through the current `kubectl exec` search probe. The two result checks' 631–638-second wall times include that process and API hop for every request. The low Elasticsearch CPU sample below and later Gatling latency are needed to separate comparison transport overhead from search time. A persistent in-cluster evaluator is a candidate optimisation if repeated comparisons become a bottleneck.

The API candidate uses the compatible query-understanding build from the earlier diagnostic workflow. Its `trainers` rewrite is outside this million-query suite, so the unchanged outcome demonstrates result preservation for these requests, not detection of that rewrite at this scale. The original API candidate build returned HTTP 200 with an older response shape; the 1,000-query comparison correctly became incomplete. The [sanitised failure report](million-initial-comparison-failure.json) records that attempt. A one-request schema preflight now stops incompatible candidates before the long run.

The release contains 20 intended no-match phrases. The shared-index baseline and API-only candidate returned incidental products for all 20 under broad lexical matching; the title-keyword mapping candidate returned zero products for those 20. An additional frozen [synthetic no-match request](../../../lab/million-no-match-v1.jsonl), SHA-256 `d7be779b06851ce41b6d99216b14faef6b617463a0666b85f8bc5139b2daa1e2`, returned zero products from all three APIs ([check output](million-no-match.json)). This checks empty-response handling separately; it does not change the 1,000-query release or its hashes.

## Capacity and limitations

The host is an ASUS ROG Strix G834JY with 32 logical processors and 102,673,936,384 bytes of RAM. Docker has 32 CPUs and 50,310,336,512 bytes of memory. The Elasticsearch Pod requests 2 GiB and is limited to 3 GiB with a 1 GiB JVM heap; during the functional run it used 1,680 MiB and 31 mCPU at one sample. The Floci Pod used 419 MiB and 12 mCPU at that sample.

The first separate-index attempt caused Floci to exceed its old 512 MiB memory limit while serving the 105 MB object. Its limit was raised to 2 GiB and the index build completed; this is a measured emulator capacity requirement. The local host had other lab services active. No p95 startup or production-scale multi-tenant capacity claim follows from these single measurements.

After the first Gatling report archives, the replacement Floci Pod had zero restarts and used 475 MiB at one sample. The raised 2 GiB limit has not been approached in that observation, but it remains a local emulator setting rather than an Azure Blob sizing rule.

The original 20-per-query labels are sparse. A symmetric [frozen v2 result pool](../../../lab/pool_million.py) retains those labels and adds both completed candidate pairs' top tens: 39,759 assessments (SHA-256 `38f3221880d7d7359fac2a919ed9688aa85c5d6c7ee69c8c448725b1f36eeace`). Its [manifest](million-judgement-pool-v2.json) pins the original judgement and two source report hashes. Its grades cover E/S/C/I: 16,307/18,934/1,960/2,558 assessments. Original grades take precedence; new IDs receive deterministic rule grades. A first v1 pool of returned lists alone produced an exploratory API report (SHA-256 `57c241c88dbe0444408fb9b2bb8efac235cd148f5728457ccad40f8a61a4e98b`) and is excluded from final relevance claims. Pool selection after seeing these result lists limits the relevance claim; future candidates may return unjudged products. Public API results remain the black-box measurement surface. Judged and load results are recorded below as they complete.

The corrected API-only pair completed all 1,000 judged requests in 643.547 seconds, report SHA-256 `c49f3ffc87f8fdac4272ff0e7581001e42edfa478080335e69a7c99ccfb58e83`. Both sides scored nDCG@10 0.979894, RR(rel=2)@10 0.98 and Judged@10 1.0, as expected from identical result lists. Returned IDs from the three lists used to construct this pool are judged by construction, so this coverage score is not evidence of broader relevance coverage.

The corrected mapping pair completed all 1,000 judged requests in 633.140 seconds, report SHA-256 `1dcaf66b025e9191a56675e9b1836b9d33b87849876590eabaa630a934f25dfa`. Baseline nDCG@10 was 0.979894; candidate nDCG@10 was 0.740959. Both had RR(rel=2)@10 of 0.98. Candidate Judged@10 was 0.98 because it returned no products for the 20 intended no-match requests; its returned lists are covered by the pool. The large nDCG decrease is a synthetic proxy result for this deliberately disruptive mapping, not a general judgement of keyword fields.

## Frozen load schedules

All four schedules compile from the 13,099-event [30-minute synthetic trace](../../../lab/traffic/source-trace-million-v2.csv), SHA-256 `db1ae9665204f9ce66164d85a86f7de976790e86ef4ff067ac4db19ce6f09576`. Their [recipes](../../../lab/traffic/recipes-million-v2.json) use separate source windows; no short query block is repeated to fill a long phase.

| Profile | Measured workload | Planned measured arrivals | Workload SHA-256 |
| --- | --- | ---: | --- |
| Smoke | Five minutes at 10 requests/s | 3,000 | `7f8efa450ea4c786c25d3d447698cadbb908e71acb6c0158b14def43aba09d55` |
| Normal full | Five minutes at source rate | 2,150 | `9ffeb8b3547a804f895b584388f9eb4279832c19cd1f18c54cee4582a9c586cd` |
| Sustained peak | 15 minutes at 20 requests/s | 18,000 | `bf627a414d36bd0aa477e69253e743a341e5e5af152fd821dd34c699b432a26b` |
| Stress full | Four two-minute steps, then five-minute recovery | 9,000 stress; 3,000 recovery | `3fef1380f127d2e508e00b5e88d7bd9aebcad6240c3e5f7a3fbe7414b9635707` |

An authenticated control API probe launched two finite Gatling Jobs, returned a valid within-budget report (SHA-256 `0f2afeb4830f5ba50610308c98cefd0383987c759b3b302332bb16d532f5136e`) and removed their Jobs, readers and PVCs. It sent 20 measured requests per side at 2 requests/s with no failures; normal-phase p95 was 41 ms baseline and 22 ms mapping candidate. This 10-second measured probe verifies the path, not the scale gate.

Three fixed-load smoke pairs passed the absolute and relative budgets. Each of the six runs delivered all 3,000 measured requests at 10 requests/s with zero failures. The baseline p95 spread was 2.564% against the provisional 10% stability limit; the median paired candidate p95 change was −41.026% against the ≤10% increase limit. The immutable three-pair report has SHA-256 `483390bee2937a82fb1191e23bb813862f946b4346073867d4397a9b1de66699`.

| Pair order | Baseline run / p95 / p99 | Candidate run / p95 / p99 | Candidate p95 change |
| --- | --- | --- | ---: |
| Baseline, candidate | `ac685f9b` / 40 / 62 ms | `32bd4d88` / 23 / 40 ms | −42.500% |
| Candidate, baseline | `53a9824c` / 39 / 63 ms | `78c00c95` / 23 / 39 ms | −41.026% |
| Baseline, candidate | `ef35f290` / 39 / 65 ms | `0ca85d2b` / 24 / 39 ms | −38.462% |

The separate trace-derived normal pair also passed: 2,150 measured requests per side over five minutes (7.167 offered requests/s), zero failures, baseline p95/p99 40/66 ms and candidate 22/43 ms. Its run IDs were `e1fdf695` and `991656e9`; the immutable paired report has SHA-256 `3944bebc68b10ec546ab49ddf4c15d2817e06e91c7d32676a3f04af2ca895dc7`. The baseline and candidate used the same frozen workload hash from the table above. These are separate sequential runs, so they show paired performance under the stated conditions rather than simultaneous capacity.

The first sustained-peak launch failed before creating a Job: client-side `kubectl apply` duplicated its 521,460-character CSV payload in the `last-applied-configuration` annotation, exceeding Kubernetes' 256 KiB annotation limit. The failed comparison record contains the API error and no performance verdict. The runner now creates each uniquely named ConfigMap without that annotation and places setup inside its cleanup block. The two partial resources were removed; the retry's peak ConfigMap has no last-applied annotation.

The corrected sustained-peak pair passed: 18,000 measured requests per side at 20 requests/s for 15 minutes, zero failures, baseline p95/p99 38/59 ms and candidate 23/40 ms. Its run IDs were `2a400ec9` and `4f4a4de1`; paired report SHA-256 `5345855c1dc159e01bddd719b39c79079c5c0f533349a5430582d8120a562a1e`. Both sides were below the separate 400/800 ms peak budget. An eleven-minute baseline spot sample showed Gatling at 1,013 MiB, the API at 16 MiB and Elasticsearch at 1,707 MiB; the candidate's ten-minute sample showed Gatling at 1,027 MiB, its API at 16 MiB and Elasticsearch at 1,707 MiB. Those samples do not establish maxima.

The stress/recovery pair also passed (baseline `eb05f918`, candidate `0236390b`; paired report SHA-256 `f59f65e149b52dbb1fa050c22ceec4364a4e3c0107a64c55b4da8355c121fab0`). Each side completed all 9,000 step requests and 3,000 recovery requests with zero failures. There was no latency-budget breach through the maximum offered 30 requests/s; this establishes a lower bound for this host and query mix, not the saturation point.

| Phase | Requests per side | Baseline p95 / p99 | Candidate p95 / p99 |
| --- | ---: | ---: | ---: |
| 10 requests/s, two minutes | 1,200 | 39 / 67 ms | 23 / 41 ms |
| 15 requests/s, two minutes | 1,800 | 39 / 74 ms | 22 / 37 ms |
| 20 requests/s, two minutes | 2,400 | 40 / 66 ms | 23 / 41 ms |
| 30 requests/s, two minutes | 3,600 | 40 / 80 ms | 23 / 48 ms |
| Recovery, 10 requests/s, five minutes | 3,000 | 38 / 64 ms | 22 / 41 ms |

At the 30 requests/s baseline step, spot samples showed Gatling at 1,103 MiB, its API at 18 MiB and Elasticsearch at 1,708 MiB; the candidate step showed 1,003 MiB, 15 MiB and 1,708 MiB respectively. These are not peak resource measurements. The [frozen schedules](#frozen-load-schedules), environment fingerprints, source hashes, native report hashes and arrival checks are in the immutable paired reports and ignored native evidence under `.lab/evidence/`.

## Cleanup

The authenticated control API deleted the index-change candidate in 51.969 seconds, the API-only candidate in 51.469 seconds and the baseline environment in 51.531 seconds. No `lab-million-*` namespace or Gatling Job, Pod or PVC remained. The dedicated `lab-million-index-idx` returned 404 after deletion; the shared `retail-gb-1m-v1` index retained exactly 1,000,000 documents and its write block. The [post-deletion check](million-cleanup.json) records the result. These three samples do not establish a deletion p95.

During the first five-minute smoke run, spot samples showed Elasticsearch at 18 mCPU/1,708 MiB in warm-up and 153 mCPU/1,709 MiB during measured load. Gatling used 288 mCPU/710 MiB and 58 mCPU/729 MiB at those same samples. A later measured sample showed the active baseline API at 42 mCPU/15 MiB, the idle mapping API at 1 mCPU/12 MiB, Elasticsearch at 142 mCPU/1,708 MiB and Gatling at 20 mCPU/747 MiB. A candidate-side sample showed its API at 43 mCPU/16 MiB, Elasticsearch at 117 mCPU/1,708 MiB and Gatling at 48 mCPU/749 MiB. These are individual `kubectl top` observations, not maxima or time-weighted averages; the runner limit is 2 CPUs/2 GiB.

## Verification

- Lab unit tests: 32 passed.
- Search API unit tests: four passed.
- Exact release hashes, document counts, write blocks and index-scoped access: passed.
