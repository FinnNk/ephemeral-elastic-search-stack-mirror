# Concurrency and isolation evidence

The local Windows 11 / two-node k3d lab used the write-blocked `retail-gb-1m-v1` synthetic release. The [batch plan](../../plans/concurrency-isolation.md) states the provisional targets. These are local measurements, not an AKS capacity estimate.

## Three complete environments

| Environment | Index | Ready time | Public search |
| --- | --- | ---: | --- |
| `lab-concurrency-baseline` | Shared million-product index | 6.469 s | 20 results |
| `lab-concurrency-api` | Shared million-product index | 7.844 s | 20 results |
| `lab-concurrency-index` | Separate million-product mapping candidate | 119.828 s | 20 results |

All three served real searches concurrently. The baseline and API candidate returned the same first product; the mapping candidate returned a different first product. The dedicated candidate was then deleted in 51.906 seconds. The two shared-index APIs still served the same 20-result search.

Live isolation probes found:

| Boundary | Observation |
| --- | --- |
| Elasticsearch | Baseline could not read the candidate index; candidate could not read the shared index or write to its own. Each could read its assigned million-document index. |
| Namespace network | Baseline API Pod could not reach the candidate service; a platform probe could reach it as the policy allows. |
| Kubernetes identity | Search API Pod had no mounted service-account token; its namespace's default service account could not read peer secrets. |

The exact checks are in [`verify_concurrency_isolation.py`](../../../lab/verify_concurrency_isolation.py) and ignored `.lab/evidence/concurrency-isolation.json`. Namespace separation and scoped Elasticsearch credentials are both required: the network policy alone does not prevent an API with valid Elasticsearch credentials from reading another index.

## Control plane under comparison

During a real paired Gatling probe comparison, unrelated activity completed in 2.079 seconds, a public search in 2.343 seconds and a new shared-index environment became ready in 7.938 seconds. Deleting the comparison's candidate returned HTTP 409 until its immutable report completed (SHA-256 `85a934a6b537a87d3c354a31eab01d7677fb4a3add7f2e2118fe2f998279f34c`). The lifecycle now persists the running comparison under a short lock and executes its work outside that lock; deletion checks the running record. A restarted single-process controller marks interrupted comparisons failed so they cannot permanently pin environments. The local implementation serialises performance pairs to avoid self-induced load contention.

## Forty live API environments

The two k3d nodes advertised 4 GiB and 6 GiB of allocatable memory. At the initial headroom check they had 1,110 MiB and 2,548 MiB of memory requests allocated. The local Docker allocation was 32 CPUs and 50,310,336,512 bytes, but the two node limits are the relevant scheduling constraint.

A single authenticated batch request created 40 distinct namespace-scoped API environments and matching Elasticsearch read credentials. It published one desired-state commit to Gitea; Argo CD created 40 Applications and 40 Pods. All 40 were ready, with zero failures, in 72.407 seconds of request wall time; nearest-rank p95 from creation to recorded readiness was 70.277 seconds against the provisional five-minute gate. Every API then answered a real public search with at least ten products, with zero errors. The 40 API Pods used a total of 460 MiB at one `kubectl top` sample. Nodes used 2,629 MiB / 4,279 MiB at that sample, with idle CPU around 151 mCPU / 131 mCPU. Elasticsearch had zero restarts. The shared index retained 1,000,000 documents and occupied 647,231,847 bytes at one sample; no `lab-fleet-*` index existed. These spot samples are neither peaks nor a production capacity claim.

A second full 40-environment creation reached 40/40 ready in 72.813 seconds, with a 70.667-second readiness p95. Its first bulk deletion call returned 40/40 deleted in 149.157 seconds. A direct audit found zero fleet namespaces, Argo CD Applications, Elasticsearch users and roles afterwards. The shared index still had 1,000,000 documents and its write block remained enabled.

The first bulk deletion revealed a cross-process race: after two minutes, the independent expiry reconciler reclaimed records still being cleaned by the API process. The API response initially counted only two deletions, although the reconciler eventually marked all 40 deleted and removed their resources. The deletion path now heartbeats its claim while waiting for Argo CD and revoking Elasticsearch credentials; credential removal also accepts an already-removed resource. A unit test advances a second controller's clock across the stale threshold. The second 40-environment cycle above exercised the fix at the original scale. Bulk deletion remains bounded by Argo CD pruning and 40 credential removals; 149 seconds is one observation, not a p95 estimate.

The [live harness](../../../lab/measure_concurrency.py) retains each environment ID, fingerprint, ready time, search result and deletion outcome under ignored `.lab/concurrency-state.json`. It uses the same authenticated HTTP API as the UI. The bulk path is limited to 40 shared-index API environments per request; index-changing environments retain their separate reindex workflow.

## Contention and remaining limits

A controlled idle-versus-busy check used identical frozen API workload bytes (SHA-256 `861c1d3777c95bf42b540afff95b877a2486f995b66386fc6781e2dca08e1c34`) and the same baseline fingerprint. Each Gatling run measured 1,103 requests with zero failures. With 40 neighbours idle, p95/p99 was 42/71 ms (`bb709431`, native archive SHA-256 `0f84655a2f1596e604afbaa27b3e4a59d02974f7a28095bdca0af04d9cece563`). While a separate synthetic client sent all 5,250 planned requests at 25 requests/s across those neighbours, p95/p99 was 44/72 ms (`45373149`, native archive SHA-256 `e9a2ec7164a251b27ddacd13d0596bf6ce49079e1e914f9017901d545755c2f7`). The one-pair p95 increase was 4.762%. The neighbour client used 50 wholly synthetic queries and had zero failures. A spot sample during that run put all 40 fleet Pods together at 164 mCPU/488 MiB and Elasticsearch at 328 mCPU/1,654 MiB. See [`measure_contention.py`](../../../lab/measure_contention.py) and ignored `.lab/evidence/concurrency-contention.json` for the exact runs.

The increase is smaller than the provisional 10% paired p95 budget but is one observation, not a stable effect estimate. Performance comparisons on shared Elasticsearch should record other tenants' load, use paired order and repeat runs. A dedicated cluster is required for engine-version experiments and may be needed when neighbour load makes baseline stability fail. This run did not find the saturation rate.

One local 40-Pod result does not establish 40-environment capacity on AKS or multiple concurrent index builds. The SQLite store and single Git checkout remain a one-controller design; multi-replica control-plane operation needs a separate coordination and metadata-store decision. The controller restart recovery was tested against persisted records, but deliberately interrupting a live provision or comparison process was not part of this run.
