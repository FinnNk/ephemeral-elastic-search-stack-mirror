# Lab delivery roadmap

The prototype is complete only after the million-product and 1,000-query scale gate, core workflows, lifecycle and portability checks have evidence. Targets below are provisional hypotheses from the [design](../prototype-design.md#provisional-quantitative-targets); measured results may change them.

| Order | Batch | Status | Reviewable outcome |
| --- | --- | --- | --- |
| 0 | Frozen API ranking evaluation | [Gitea PR #5](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack/pulls/5) open | Two pinned APIs scored against frozen synthetic judgements through their public endpoints. |
| 1 | Comparison diagnostics | Complete on `slice/comparison-diagnostics`; [plan](comparison-diagnostics.md), [evidence](../research/evidence/runnable-diagnostics/summary.json); review pending | Correlated API-stage evidence, a selected Elasticsearch probe and a result-preserving refactor with zero changed queries. |
| 2 | Environment lifecycle and UI | Next; [detailed plan](environment-lifecycle.md) | API/UI create, inspect, compare, use and delete; 72-hour activity-based leases and recovery. Removal p95 ≤ 5 minutes. |
| 3 | Index-change workflow | Planned | A mapping-changing source PR builds a separate frozen index, runs comparisons and cleans up. 10,000-product startup p95 ≤ 5 minutes. |
| 4 | Synthetic traffic and Gatling | Planned | Frozen query/timestamp traces compiled into warm-up, normal, sustained-peak and stress/recovery phases; paired API reports and validity checks. Initial 10 requests/s smoke budgets: p95 ≤ 250 ms, p99 ≤ 500 ms, failures < 1%. |
| 5 | Million-product scale gate | Planned | One million wholly synthetic products, 1,000 judged queries, repeatable builds, functional comparisons and load profiles. Test ≤ 2-minute shared-index startup, ≤ 20-minute reindex and ≤ 15-minute comparison hypotheses. |
| 6 | Concurrency and isolation | Planned | Two or three complete local environments; 40+ lightweight deployments on suitable hardware, with real searches, reconciliation timings and access tests. |
| 7 | Portability and Azure shape | Planned | Native Apple silicon run, AKS/Blob configuration, GitHub Enterprise migration path and operations/capacity notes. |

## Batch hand-off

1. Finish the active batch and record its tests, measurements and limitations.
2. Update this roadmap's status and links.
3. Write the detailed plan for the next batch, with intent, constraints, acceptance criteria and source material.
4. Commit the batch and both plan updates, then open a PR. When reviews are deferred, stack the next PR on the previous batch branch and retain the same order on merge.

The roadmap distinguishes demonstrated behaviour from a target. A passing functional check does not establish relevance quality or performance capacity.
