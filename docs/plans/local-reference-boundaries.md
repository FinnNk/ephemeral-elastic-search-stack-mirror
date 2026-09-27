# Local reference: topology and contract boundaries

This assessment concerns component placement, ownership, interfaces and lifecycle. It does not assess whether synthetic relevance scores or laptop latency predict production outcomes.

After batches [7i](kubernetes-control-services.md), [7j](independent-data-evaluation-contracts.md) and [7k](otel-observability.md), the intended local structure is representative of a small deployment: independent producers publish immutable inputs; versioned search releases consume catalogues; evaluators consume API observations; reviewed desired state drives Argo CD; persistent services retain artifacts beyond ephemeral runtimes. OTel signals connect operations across these boundaries in a shared SigNoz dashboard.

## Remaining structural checks

| Boundary | Present gap | Bounded local demonstration |
| --- | --- | --- |
| Bootstrap and state recovery | Control state now lives on a k3d PVC. An isolated import of an exported archive passed; fresh-checkout deployment and independent host recovery remain. | Finish batch 7i installation and recovery from separately retained state, credentials and services. Full all-service disaster recovery remains separate. |
| Interrupted orchestration | Provisioning recovered automatically, deletion completed and an interrupted comparison failed explicitly while cleaning its Gatling resources. Unavailable dependencies and failed readiness still need trials. | Finish batch 7i dependency/readiness checks without duplicate publication or blocked leases. |
| Service and credential ownership | Ordinary controls now use internal Services and a dedicated ServiceAccount; temporary index Jobs use `lab-indexing`. Bootstrap and reviewer authority stay separate. | Verify the complete runtime action set and negative authority probes, retaining narrow search/evaluation access. |
| Independent source and evaluation ownership | Dataset-name branches and a combined release manifest couple data selection, index recipes and evaluation. | Batch 7j: separately runnable producers/evaluator, explicit artifact/API/report contracts, independent revisions and backwards-compatible readers. |
| Software/schema promotion | Promotion and rollback passed with an unchanged shared recipe; historical-schema recovery was tested separately. | Batch 7j: connect those contracts in one schema-changing delivery and rollback walkthrough. |
| Artifact lifecycle | Frozen inputs, snapshots and releases survive runtime deletion, but no complete cross-store retention inventory or automatic cleanup exists. | Batch 7j: inventory reference dependencies and missing artifacts. Keep deletion disabled; distinguish retained evidence from disposable runtime. |
| Connected observability | Current logs, diagnostic records and reports lack a common metrics/trace/log investigation surface and operational error-budget view. | Batch 7k: SigNoz and OTel contracts; demonstrate SLO breach → affected operation → trace → logs, including slow successful requests, with a New Relic mapping. |

The first three remain the main operational checks for removing workstation dependence. They fit within batch 7i and require no additional platform.

## Deliberate local simplifications

| Simplification | Consequence and external validation |
| --- | --- |
| One laptop and one cluster | Namespaces demonstrate deployment/permission boundaries, not independent availability zones or failure domains. The user accepts cluster-wide loss of the controls. |
| One active control Pod with SQLite | Preserves the current ownership model. Multiple controller replicas need shared coordination and storage; forty API environments do not imply forty controllers. |
| Persistent services outside the lab cluster | Nexus and snapshot storage model dependencies with lifetimes independent of search runtimes. Their local Docker volumes still share the laptop's failure domain. |
| Gitea and local application identities | Demonstrates Git/CI/review/service contracts. GHES API behaviour, enterprise SSO and Azure workload identity require their actual systems. |
| Private local HTTP and simple browser access | Sufficient for the local workflow. End-to-end TLS, enterprise ingress and certificate rotation remain deployment concerns; internal service discovery should already be explicit. |
| Frozen catalogue and query inputs | Deliberate for reproducible development/evaluation. Streaming catalogue updates, customer sessions, live experiments and commerce backends are outside this reference. |
| One local observability backend | Planned SigNoz shares the cluster failure domain, has bounded retention and requires additional memory/storage. An export outage must not block lab operations; external New Relic validation remains separate. |

SigNoz is the additional platform component requested for the local reference. Its resource fit is the first check in batch 7k. Full external-service disaster recovery, automatic retention cleanup and enterprise identity remain recorded gaps rather than additional implementation batches. [Batch 8](native-cloud-validation.md) validates the real provider, hosting and New Relic boundaries.

## Evidence behind the assessment

- [Research bootstrap](../../research/platform-spike/README.md): fresh-cluster assumptions and non-idempotent original recipe
- [Concurrency/isolation](../research/evidence/concurrency-isolation.md): tested workload boundaries and live-interruption limitation
- [Promotion/deployment](../research/evidence/promotion-deployment.md): three targets, unchanged-recipe rollback and host metadata
- [Snapshot repository](../research/evidence/durable-snapshot-repository.md): retained-volume and cluster/PVC replacement evidence, host-loss limit
- [Nexus guide](../nexus.md): publisher/reader separation, retained volumes and cleanup limitations
