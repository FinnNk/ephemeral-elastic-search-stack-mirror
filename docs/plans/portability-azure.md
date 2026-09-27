# Portability and Azure shape

## Intent

Make the lab reproducible beyond the present Windows host and describe a credible route to Apple silicon, AKS, Azure Blob Storage and GitHub Enterprise Server (GHES). Preserve the frozen-data and comparison contracts while replacing local integrations.

## Constraints

| Area | Constraint |
| --- | --- |
| Evidence | Distinguish a native run from image-manifest checks and configuration review. This Windows host cannot verify Apple silicon execution. |
| Source and deployment | Gitea remains the lab source of truth, with GitHub as backup. Argo CD remains the deployment controller. GHES is a migration target, not a new lab dependency. |
| Data | Product, query, judgement and traffic fixtures remain wholly synthetic. Immutable release manifests and hashes must survive a storage-provider change. |
| Search | Elasticsearch remains self-managed under ECK. A shared write-blocked index is the default for API and query experiments; index and engine changes retain separate paths. |
| Storage | Floci models Blob operations locally where compatible. The Azure design uses Blob Storage and workload identity; credentials must not be embedded in source or manifests. |
| Portability | Images and tooling need explicit amd64 and arm64 support. Local ports, hostnames and Docker Desktop assumptions must be isolated in host-specific configuration. |
| Review | Commit the batch to a stacked branch and open Gitea and GitHub backup PRs. Do not merge without review. |

## Work

1. Inventory architecture-specific images, binaries, workflows and host paths. Check published image manifests and build the search API for both architectures where the local builder permits it.
2. Introduce a documented configuration boundary for Blob endpoint, container, authentication and registry/source location. Keep the local Floci path runnable and validate the frozen-release hash contract after configuration changes.
3. Describe an AKS deployment shape: namespaces, Argo CD, ECK/Elasticsearch, Blob access with workload identity, image registry, ingress, secrets, expiry controller and observability. Record capacity assumptions and cost-sensitive unknowns rather than presenting local measurements as AKS sizing.
4. Map Gitea concepts to GHES repositories, apps, webhooks, Actions, registry and branch protection. Identify concrete adapter changes and migration checks.
5. Run the lab portability checks that this host supports, record gaps requiring an Apple silicon host and AKS, then update the design and diagrams where the deployment shape changes.

## Acceptance criteria

- A reproducible local runbook states prerequisites and commands for Windows and Apple silicon, and marks any platform step that has not been executed natively.
- The search API image is built or its multi-architecture publication path is tested for linux/amd64 and linux/arm64. Other pinned images have architecture evidence or an explicit blocker.
- Frozen release creation, retrieval and integrity verification use configurable Blob settings. The local Floci path passes a real read/write check; the Azure path has an explicit identity and container configuration contract.
- The AKS and GHES migration design identifies the resource, identity, network, reconciliation and registry changes, with primary-source links and specific validation steps.
- The roadmap and C4 deployment view agree with the demonstrated lab and proposed Azure shape. Remaining native Mac and cloud gates are reported as open if those environments are unavailable.

## More information

- [Prototype design](../prototype-design.md)
- [Current Azure deployment view](../diagrams/workspace.dsl)
- [Floci local service configuration](../../research/platform-spike/floci.yaml)
- [Search API build workflow](../../lab/search-app/.gitea/workflows/build.yaml)
- [Frozen million-product evidence](../research/evidence/million-scale.md)
- [Concurrency evidence](../research/evidence/concurrency-isolation.md)
