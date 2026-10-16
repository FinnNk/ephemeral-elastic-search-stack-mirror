# Elasticsearch node memory investigation

The first resource change to validate is more memory for the enclosing k3d
server node. A short diagnostic removed its memory-limit pressure and improved
search latency. The full Production load gate still needs to run at that
capacity before treating the change as a release solution.

## Observed bottleneck

On 16 October 2026, the Windows/WSL lab's server node had a 6 GiB Docker memory
ceiling. It contained Elasticsearch, the Kubernetes control plane, Gatling and
retained API previews. Read-only samples during the build-207 Production gate
showed repeated node-limit hits, active swap traffic and eviction of cached
index pages. Elasticsearch remained below its own 3 GiB limit.

The shared catalogue index occupied 1.66 GiB. Elasticsearch's charged file cache
fell to 52–209 MiB during that observation window. This is memory accounted to
its container, not a measurement of every shared page available to Elasticsearch.
The whole index does not need to fit in cache for searches to benefit.

The [Production operation](https://control.localhost:34443/api/delivery/operations/d1a395df985069e928b57bdd98ce382b)
failed its unchanged budgets. Normal p99 was 555 ms for baseline build 108 and
554 ms for candidate build 207, against 500 ms. Peak p99 was 1,120 ms and
1,558 ms respectively, against 800 ms; candidate peak p95 also missed its
400 ms budget at 455 ms. Its required standard relevance set passed.

## Controlled diagnostic

After all delivery work and lifecycle comparisons became idle, the user-approved
pair replayed build 207 (`1.2.3+build.207.1`, source `a7cb12a20522`) through its
existing preview. Each arm used a 60-second warmup at 10 requests per second,
then the same first 6,000 frozen peak requests over five minutes at 20 requests
per second. The workload digest was
`15e39a2502c5ceb99baab11b2ff5d1ada1f9ba011dbba92227d2f45760c6a566`.

Only the enclosing node memory ceiling changed: 6 to 10 GiB. The swap allowance
remained 6 GiB, so Docker's total RAM-plus-swap limit changed from 12 to 16 GiB.
Elasticsearch retained its 3 GiB container limit, 1 GiB heap and two-CPU ceiling.
API resources, image, catalogue, Redis rewrites, ranking configuration and gate
budgets were unchanged. Redis access was checked before the pair.

| Measurement | 6 GiB node | 10 GiB node |
| --- | ---: | ---: |
| Measured requests | 6,000 | 6,000 |
| Failed requests | 0 | 0 |
| Client p95 | 100.6 ms | 71.7 ms |
| Client p99 | 189.4 ms | 118.9 ms |
| Individual requests over 800 ms | 0 | 0 |
| Elasticsearch `took` p99 | 149 ms | 92 ms |
| Elasticsearch dependency span p99 | 171.4 ms | 102.0 ms |
| Sampled node memory-limit events, interval increase | 32,098 | 0 |
| Elasticsearch charged file cache, sample mean | 185.6 MiB | 693.9 MiB |
| Elasticsearch average CPU, sampled intervals | 0.672 CPU | 0.659 CPU |

Returned product ordering was identical across all 6,000 measured requests;
both result-order hashes were
`d71ff1f750ce39b409d3a8b65ddd84d893e2c11607fe47d624e85016f28b38e2`.
SigNoz retained all 6,000 Elasticsearch spans per arm, each with `took`.
No old-generation GC or OOM kill occurred in the sampled intervals.

The measured request windows were 15:38:32–15:43:32 UTC and
15:44:37–15:49:37 UTC. Five-second counter samples fully inside those windows
covered approximately 291 and 295 seconds. Their boundaries exclude warmup
and several seconds at each edge; the latency percentiles use all requests.
Node swap-out counters increased by 370,631 pages in the first sampled window
and 85 in the second. Elasticsearch file-cache refaults also fell sharply.

## Interpretation and retained state

The pair supports node memory pressure as a real bottleneck. It does not prove
that every historical burst had that cause or that the Production gate will
pass. This was a sequential short replay using the Python diagnostic driver,
not Gatling. The second arm also benefited from running later with warmer
caches. Neither arm reproduced an individual request over 800 ms. A full
Gatling run additionally places its JVM inside the same node's memory budget.

The node remains at 10 GiB with a 6 GiB swap allowance. At cleanup, anonymous
and kernel memory occupied about 5.72 GiB, leaving insufficient headroom for
a safe return to the old 6 GiB ceiling. The user's approved fallback was to
retain 10 GiB and report it. The diagnostic helpers and temporary port-forward
were stopped. Deployment specifications and active blue build 108 were unchanged.
This runtime setting is not an installer-default change.

Raw request files remain under
`/state/experiments/es-node-memory-build207/` in the control PVC. Local receipts,
samples, interval summaries and the original node limits are retained under
`.lab/walkthroughs/build207/node-memory-test/` in the shared lab-state directory.
They are diagnostic records and do not replace immutable promotion evidence.

## Full Production validation and fresh setup

The subsequent full Production operation
`fd78bddcf1caaeb169c4f7a504044dc8` completed successfully at 10 GiB, with the
normal, peak and recovery budgets unchanged. It produced delivery-state PR #42,
which the user approved and deployed. Operation
`d2063a29ed69dce39d9bcb752426e8ef` verified the active green build 207 image.

The walkthrough completion batch therefore sets new servers to 10 GiB. Existing
installations keep their configured limits on resume. The fresh guide allows
40 GiB for Docker Desktop, including the 16 GiB application agent and external
stores. Elasticsearch's own CPU, 3 GiB container memory and 1 GiB heap stay
unchanged. Keep measuring host and enclosing-node pressure when adding workloads.

This evidence was collected on Windows/WSL. Native Mac performance acceptance
is still required. See the earlier [API CPU experiment](peak-cpu-headroom-diagnostic.md)
and Elastic's [filesystem-cache guidance](https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/search-speed).
