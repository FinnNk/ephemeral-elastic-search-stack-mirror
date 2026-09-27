# Lab delivery roadmap

The lab has demonstrated a million-product catalogue, 1,000 queries, frozen API comparisons, Gatling load profiles, index recovery, a 40-API fleet and a three-target release path. These are local measurements, not evidence that the same capacity or latency will hold on Apple silicon or Azure. The [design targets](../prototype-design.md#provisional-quantitative-targets) remain provisional.

All earlier Gitea implementation batches through 7k1 have been merged to `main`. Their plans remain in this directory, with measured results such as the [million-product](../research/evidence/million-scale.md) and [control-runtime](../research/evidence/kubernetes-control-services.md) evidence. A merged implementation does not close a measurement or integration gate.

| Area | Demonstrated locally | Remaining gate |
| --- | --- | --- |
| Search and scale | 1M synthetic products, 1,000 queries, shared and dedicated indices, API relevance and result-preservation comparisons, Gatling profiles | Repeat timing samples and capacity checks where a percentile or target claim requires them; native and cloud verification |
| Lifecycle and recovery | Kubernetes `lab-control`, durable leases, expiry, deletion, interrupted-operation recovery, index reuse/clone/snapshot/rebuild | Complete disposable activation and recovery rehearsal; validate delivery and rollback with the Kubernetes control runtime |
| Input and evaluation contracts | Independent manifests, producer/evaluator Jobs, retained observations and offline rescoring; branch code selects hash-checked queries and judgements, with live API checks | Roll out the updated control image; make catalogue-only recipes the default for new environments and delivery; rehearse addendum-backed promotion and schema-changing rollback |
| Delivery | Gitea Actions, Nexus images and release bundles, protected promotion PRs, three local targets and rollback | Re-run end-to-end with the final control/data contracts; validate GHES portability |
| Observability | Search API traces, SLI counters and correlated logs; synthetic SLO arithmetic | Deploy SigNoz/Collector, connect dashboard-to-trace-to-log investigation, measure overhead and map to New Relic |
| Platform | Gitea, Argo CD, Floci, SeaweedFS and Elasticsearch on the local host | Apple silicon, AKS, Azure Blob/identity and New Relic validation |

The [reference-clarity audit](reference-clarity.md) tracks historical-schema and documentation cleanup separately from these delivery gates. It retains frozen replay without making old schemas the default path.

## Next batches

1. [Catalogue recipes and delivery](catalogue-recipe-delivery.md): move default environment and delivery creation to independent catalogue recipes while retaining explicit historical recovery. The [reference-clarity audit](reference-clarity.md) and [comparison-input check](../research/evidence/independent-comparison-inputs.md) record the preceding cleanup.
2. [SigNoz backend and investigation](signoz-backend-and-investigation.md): deploy the observability backend and prove connected investigation.
3. [Native and cloud validation](native-cloud-validation.md): run the full lifecycle on Apple silicon and Azure/GHES, including New Relic ingestion.

Each batch ends with evidence, an updated roadmap and the next detailed plan. Commit it to a branch and submit a PR; merge to `main` only after acceptance. A passing functional check does not establish relevance validity or performance capacity.
