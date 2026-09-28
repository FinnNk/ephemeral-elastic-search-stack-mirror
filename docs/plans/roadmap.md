# Lab delivery roadmap

The lab has demonstrated a million-product catalogue, 1,000 queries, frozen API comparisons, Gatling load profiles, index recovery, a 40-API fleet and a three-target release path. These are local measurements, not evidence that the same capacity or latency will hold on Apple silicon or Azure. The [design targets](../prototype-design.md#provisional-quantitative-targets) remain provisional.

The control-runtime consolidation and delivery rehearsal are merged to `main`. Earlier batch plans remain in this directory, with measured results such as the [million-product](../research/evidence/million-scale.md) and [control-runtime](../research/evidence/kubernetes-control-services.md) evidence. A merged implementation does not close a measurement or integration gate.

| Area | Demonstrated locally | Remaining gate |
| --- | --- | --- |
| Search and scale | 1M synthetic products, 1,000 queries, shared and dedicated indices, API relevance and result-preservation comparisons, Gatling profiles | Repeat timing samples and capacity checks where a percentile or target claim requires them; native and cloud verification |
| Lifecycle and recovery | Kubernetes `lab-control`, durable leases, expiry, deletion, interrupted-operation recovery, index reuse/clone/snapshot/rebuild; updated Pod created shared, dedicated and historical environments | Complete disposable activation and recovery rehearsal; repeat timing samples where a target claim requires them |
| Input and evaluation contracts | Independent manifests, producer/evaluator Jobs, retained observations and offline rescoring; deployed control selects hash-checked inputs and catalogue-only recipes by default. New 10k/1M indices, historical replay and deployed comparison have live checks. | Exercise an addendum-backed promotion through the same installed control path; validate external producer/evaluator boundaries on Azure |
| Delivery | Gitea Actions, Nexus images and release bundles, protected promotion PRs; merged-source 1M schema release promoted and rolled back through all three local targets with fresh direction-specific evidence | Validate GHES portability and repeat timing samples where a target claim requires them |
| Observability | Search API signal contract and SLO arithmetic; pinned SigNoz, ClickHouse, gateway and scoped log agents installed; 12-panel dashboard; stored delivery and diagnostic search span/log correlation; digest-pinned finite Job logs; fail-closed seven-day fixtures; finite Gatling arrival ledger, independent readiness probe and SigNoz counter join; gateway outage leaves search serving; local New Relic profile checked against a mock endpoint | Continuous seven-day verified source coverage and bounded counter alignment; browser drill-through, instrumented release across all delivery targets and a valid overhead comparison |
| Platform | Gitea, Argo CD, Floci, SeaweedFS, Elasticsearch and ESO on the local host; 40 retained Kubernetes Secrets reconcile from Floci Key Vault; five web services pass CA-validated HTTPS through Traefik | HTTPS client and OCI migration; Apple silicon, AKS, Azure Blob/Key Vault identity and New Relic validation |

The [reference-clarity audit](reference-clarity.md) tracks historical-schema and documentation cleanup separately from these delivery gates. It retains frozen replay without making old schemas the default path.

## Next batches

1. [SigNoz backend and signal transport](signoz-backend-and-investigation.md) is ready for review. The backend, gateway and log agent are deployed; the agent organisation is bootstrapped and all three signal types have stored records.
2. [SigNoz account and SLO dashboard](signoz-connected-investigation.md) is ready for review. The owner invitation is pending activation; the dashboard and synthetic interval checks are live.
3. [Finite Job telemetry](signoz-connected-runtime.md) is ready for review; the producer and evaluator run as digest-pinned Jobs and their safe outcome logs reach SigNoz.
4. [Seven-day window assessment](signoz-window-coverage.md) is ready for review; synthetic fixtures verify totals and unknown-on-gap behaviour.
5. [Connected investigation and overhead](signoz-investigation-overhead.md) has a finite live ledger/counter join, outage check and retained overhead runs ready for review. The four overhead runs missed the arrival gate, so the result is inconclusive.
6. [Merged-release investigation rehearsal](signoz-merged-release-rehearsal.md) closes the instrumented three-target, browser and valid overhead gates after the pending source stack is accepted.
7. [Native and cloud validation](native-cloud-validation.md): run the full lifecycle on Apple silicon and Azure/GHES, including New Relic ingestion.
8. [Azure Key Vault delivery](azure-keyvault-validation.md): prove the unchanged Kubernetes Secret targets with ESO's Azure provider, Workload Identity and real vault policy.
9. [HTTPS clients and transport](https-client-transport.md): move Git, webhook and OCI clients to verified TLS and validate workstation trust on both host platforms.

Each batch ends with evidence, an updated roadmap and the next detailed plan. Commit it to a branch and submit a PR; merge to `main` only after acceptance. A passing functional check does not establish relevance validity or performance capacity.
