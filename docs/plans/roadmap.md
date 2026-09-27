# Lab delivery roadmap

The prototype is complete only after the million-product and 1,000-query scale gate, core workflows, lifecycle and portability checks have evidence. Targets below are provisional hypotheses from the [design](../prototype-design.md#provisional-quantitative-targets); measured results may change them.

| Order | Batch | Status | Reviewable outcome |
| --- | --- | --- | --- |
| 0 | Frozen API ranking evaluation | [Gitea PR #5](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack/pulls/5) open | Two pinned APIs scored against frozen synthetic judgements through their public endpoints. |
| 1 | Comparison diagnostics | Complete on `slice/comparison-diagnostics`; [plan](comparison-diagnostics.md), [evidence](../research/evidence/runnable-diagnostics/summary.json); review pending | Correlated API-stage evidence, a selected Elasticsearch probe and a result-preserving refactor with zero changed queries. |
| 2a | Lifecycle foundation | Complete on `slice/lifecycle-foundation`; [evidence](../research/evidence/lifecycle-foundation/summary.json); review pending | Durable 72-hour leases, loopback API/UI create, inspect, search, activity and idempotent deletion. One real HTTP lifecycle passed. |
| 2b | Controlled comparisons and expiry | Complete on `slice/lifecycle-comparison`; [evidence](../research/evidence/lifecycle-comparison/summary.json), [expiry check](../research/evidence/lifecycle-comparison/expiry.json); review pending | API/UI result-preservation and relevance reports, plus independent expiry cleanup while the UI is stopped. |
| 2c | Identity and lifecycle measurement | Complete on `slice/lifecycle-identity-measurement`; [evidence](../research/evidence/lifecycle-measurement/README.md); review pending | Named Gitea ownership and access checks; 20/20 warm removals passed, p95 53.844 seconds against five minutes. |
| 3 | Index-change workflow | Complete on `slice/frozen-index-change`; [evidence](../research/evidence/index-change.md); review pending | A mapping change built a separate frozen index and completed API comparisons and cleanup. Two candidate startups took 15.094 s and 17.703 s; p95 remains unmeasured. |
| 4 | Synthetic traffic and Gatling | Implemented on `slice/gatling-traffic`; [plan](synthetic-traffic-gatling.md), [calibration evidence](../research/evidence/gatling.md); [Gitea PR #11](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack/pulls/11), [GitHub backup PR #6](https://github.com/FinnNk/ephemeral-elastic-search-stack/pull/6); review pending | Frozen query/timestamp traces, finite Gatling Jobs, control UI mode and paired calibration. The three-pair stability and longer holds are measured in batch 5. |
| 5 | Million-product scale gate | Complete on `slice/million-scale`; [detailed plan](million-product-scale.md), [evidence](../research/evidence/million-scale.md); review pending | One million wholly synthetic products and 1,000 queries, repeatable builds, 1,000-query functional comparisons and immutable load reports. Three-pair smoke, five-minute normal, 15-minute peak and stepped stress/recovery passed on the local host. Shared startup was 7.719–8.156 s, separate reindex 113.844 s and comparisons about 10.5 min; these are single samples, not p95 estimates. |
| 6 | Concurrency and isolation | Next; [detailed plan](concurrency-isolation.md) | Two or three complete local environments; 40+ lightweight deployments on suitable hardware, with real searches, reconciliation timings and access tests. |
| 7 | Portability and Azure shape | Planned | Native Apple silicon run, AKS/Blob configuration, GitHub Enterprise migration path and operations/capacity notes. |

## Batch hand-off

1. Finish the active batch and record its tests, measurements and limitations.
2. Update this roadmap's status and links.
3. Write the detailed plan for the next batch, with intent, constraints, acceptance criteria and source material.
4. Commit the batch and both plan updates, then open a PR. When reviews are deferred, stack the next PR on the previous batch branch and retain the same order on merge.

The roadmap distinguishes demonstrated behaviour from a target. A passing functional check does not establish relevance quality or performance capacity.
