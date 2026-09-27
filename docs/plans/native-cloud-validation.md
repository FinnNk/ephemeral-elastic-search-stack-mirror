# Native and cloud validation

## Intent

Close the hardware and cloud gates left open by the Windows portability build. Reproduce the frozen-search lifecycle on Apple silicon, then validate the proposed GHES, ACR, AKS and Azure Blob boundaries in a test tenant before using local measurements for a production proposal.

## Constraints

| Area | Constraint |
| --- | --- |
| Access | Requires an Apple silicon Mac and an authorised Azure subscription. A GHES test organisation is needed for provider migration checks. Do not label simulated checks as native or cloud evidence. |
| Data | Use only the versioned synthetic UK/GBP releases, judgements and traffic profiles. Preserve byte hashes and report fingerprints across hosts. |
| Comparison | Keep two frozen environments per check. The same public API relevance, result-preservation and Gatling contracts, query-level report and judgement-coverage caveat must run in both placements. |
| Security | Use workload identity and scoped Blob roles in AKS, digest-pinned ACR images, index-scoped Elasticsearch roles and authenticated Git/webhook access. |
| Review | Record each external validation as evidence on a branch and PR. Keep local and cloud results separate. |

## Work

1. On Apple silicon, bootstrap a fresh k3d cluster with native tools. Run the 10,000-product walkthrough, million-product release, one API candidate, one index candidate, all three checks, activity extension and deletion. Record native image digests, resource headroom and timing distributions.
2. In an Azure test tenant, provision AKS, ACR, Blob Storage, workload identity, Argo CD and ECK through reviewed infrastructure definitions. Package the control API and durable metadata store for AKS; replace the single-checkout writer coordination before multiple replicas.
3. Verify identity-scoped Blob create/read, a user-delegation read SAS with expiry, immutable hashes, ACR pulls and a self-managed Elasticsearch bulk build. Test private DNS and network policies with negative access probes.
   Register and analyse a real Azure Blob snapshot repository with ECK workload identity. Restore the historical million-product snapshot to a separate index after deleting the source, verify recipe and ordered sample, and measure three searchable restore times. Keep S3 and Blob timing evidence separate.
4. In a GHES test organisation, migrate application and desired-state repositories, build the same commit, resolve its ACR digest, deliver signed events and run a baseline/candidate comparison through Argo CD. Map the local `lab-evaluate` opt-in and exact-head verdict status to GHES, then verify stale-head handling, idempotent retries and recreate-after-delete from retained source and data.
5. Measure at least 40 real shared-index API environments and controlled neighbour load on AKS; size Elasticsearch, node pools, disks, load generators and retained artifacts from p95/p99 and cost evidence. Test a controller/node failure during provisioning, comparison and deletion.

## Acceptance criteria

- Apple silicon runs the complete lifecycle natively with matching release hashes and valid comparison reports; native performance figures are recorded separately from Windows.
- AKS creates and removes baseline, API and index candidates with no orphaned namespace, index credential or writer permission. Blob and ACR identity checks pass, including negative access and expired SAS.
- GHES source SHA and ACR OCI digest remain pinned through build, environment, report and recreation. Argo CD converges from the migrated desired-state repository.
- The migrated PR workflow links query-level reports and records the exact evaluated head SHA. An event retry does not duplicate a verdict; a changed SHA starts a separate run. The local polling prototype remains the reference behaviour, not evidence of signed GHES delivery.
- Forty AKS APIs answer real searches with measured p95 readiness and cleanup; relevance/performance validity and resource contention are assessed against the provisional targets.
- A capacity and operating-cost proposal states region, SKUs, replicas, retention, licences, expected tenant concurrency and uncertainty ranges.

## More information

- [Portability design](../research/portability-azure.md) and [Windows evidence](../research/evidence/portability-azure.md)
- [Batch 7 plan](portability-azure.md)
- [Million-product evidence](../research/evidence/million-scale.md)
- [Concurrency evidence](../research/evidence/concurrency-isolation.md)
- [C4 Azure deployment](../diagrams/rendered/06-azure.svg)
- [Local developer evaluation loop](developer-evaluation-loop.md) and [measured evidence](../research/evidence/developer-evaluation-loop.md)
