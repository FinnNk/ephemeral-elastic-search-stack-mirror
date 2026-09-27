# Batch 7i: Kubernetes control services

## Intent

Move the lab UI/API, lease reconciler, PR watcher and delivery coordinator into a dedicated `lab-control` namespace. Preserve their responsibilities, frozen definitions and existing workflows. This changes deployment placement and removes host dependencies; it does not introduce a new orchestration platform.

**Status: planned.** The current controls still run on the host. The user accepts that control services become unavailable when the local cluster is unavailable.

## Constraints and placement

| Area | Planned boundary |
| --- | --- |
| Runtime | One active Pod, with separate containers for the API and background workers. Preserve shared loopback coordination and use persistent storage for SQLite, Git checkouts and control records. |
| Updates | Prevent overlapping writers during replacement; retain one active instance. Do not infer single-Pod exclusivity from a `ReadWriteOnce` volume alone. No multi-replica controller in this batch. |
| Deployment owner | Argo CD continues to reconcile search workloads. Bootstrap installs the control application; Argo can subsequently manage its declared version. Host recovery must work if that application is unavailable. |
| Persistent services | Gitea, Argo CD, Elasticsearch and Floci keep their existing placement. Nexus/PostgreSQL and SeaweedFS remain outside the cluster with retained volumes. |
| State migration | Back up and copy the required state deliberately. Preserve bytes, IDs, fingerprints, owners, leases and report references; do not copy developer caches or the entire host credentials directory into the image. |
| Access | Use internal service addresses and configurable external URLs. Expose the UI through a Service with a local access route; browser port forwarding may remain a convenience, but internal operations must not depend on host port forwards. |
| Identity | Use a runtime ServiceAccount with explicit RBAC and mounted application credentials. Keep bootstrap administrator credentials and the simulated reviewer outside ordinary runtime control. |
| Scope | All data remains synthetic. Keep SQLite and the existing workflow contracts. No queue, service mesh, external identity provider or new database is required for placement alone. |

A namespace groups and isolates resources only as far as its policies permit. The controller needs some cross-namespace and cluster-scoped operations, including namespace creation. List these explicitly; ownership checks on lab resources do not make them an RBAC prefix restriction. Evaluation and search workloads retain their separate, narrower permissions. Follow the [Kubernetes RBAC guidance](https://kubernetes.io/docs/concepts/security/rbac-good-practices/) when defining the runtime roles.

## Work

1. **Inventory runtime dependencies.** Separate shipped code/tools, configuration, credentials, durable state and disposable caches. Parameterise state paths, service URLs, cluster identity checks, API bind/public addresses and credential sources. Package Linux amd64/arm64 images with pinned dependencies. Publish/version the controls independently of search API releases; a controller update must not require rebuilding the search application.
2. **Declare the deployment.** Add the namespace, persistent volume claim, Service, probes, resource limits, ServiceAccount/RBAC and NetworkPolicies. Run workers through container entrypoints rather than host process launchers. Provide structured stdout logs and existing operation IDs; retain detailed reports in Blob storage. Preserve correlation IDs and accept configurable OTel resource/endpoint settings for [batch 7k](otel-observability.md); ordinary work must remain independent of telemetry availability.
3. **Migrate state and cut over.** Drain or explicitly resolve active work, stop host writers, take a consistent state backup, seed the volume, then enable the Pod. Verify fingerprints before accepting new operations. Document rollback to the host process with exactly one active writer throughout.
4. **Remove hidden host dependencies.** Call Gitea, Elasticsearch, Floci and Nexus through their configured service endpoints. Replace host kubeconfig use with in-cluster access. Keep host-only cluster creation, retained-service setup and recovery in a separate bootstrap entrypoint.
5. **Exercise restart and dependency failure.** Interrupt a real provision, comparison and deletion in separate trials. Reconcile completed resources or mark work explicitly interrupted and make retry safe. Test unavailable Git/artifact endpoints and failed deployment readiness; never record an unverified deployment as a successful source for promotion.
6. **Rehearse installation and recovery.** Use a fresh checkout with an explicitly supplied state/credential bundle, not the existing developer `.lab` tree. Install into disposable control resources against authorised retained services; rerun installation safely. Restore a consistent control-state backup into an isolated volume and verify references. Protect the current review environment and retained data throughout.
7. **Synchronise documentation.** Update access and recovery commands, local deployment C4 placement, control/delivery views and lifecycle workflows. Record actual constraints and resource use. Update the roadmap and refine batch 7j before opening the implementation PR.

## Acceptance criteria

| Boundary | Required demonstration |
| --- | --- |
| Host independence | Ordinary create, compare, promote, rollback and expire operations work with host control processes and internal-service port forwards stopped. Host bootstrap remains usable independently. |
| Existing contracts | A migrated environment and report retain their original hashes and identities; both frozen APIs still receive the same selected inputs. |
| End-to-end operation | Create an API candidate and an index candidate, execute the three check types, promote and roll back a fixture release, then explicitly remove and expire previews. Check workflow completion and references; this batch adds no relevance-quality or performance-capacity claim. |
| Pod replacement | Replacing the control Pod retains state and restores readiness. No duplicate promotion, permanent lease blockage or orphaned lab credential remains after interrupted work is reconciled. |
| Single writer | Competing control instances/operations cannot mutate the same checkout or state unsafely. Deployment update and host rollback both preserve this rule. |
| Authority | Runtime operates without the user's kubeconfig or blanket `cluster-admin`. Negative probes cover unrelated secrets and prohibited writes; explicitly document necessary broad namespace permissions. |
| Independent bootstrap | Fresh-checkout installation and isolated state restoration work from documented durable inputs. A repeated install preserves existing identities and frozen artifacts. |
| Review evidence | Retain manifests, sanitised recovery records and observed resource use; publish one stacked PR. Native Mac execution remains an external gate. |

## Where to find more information

- [Roadmap](roadmap.md), [local topology assessment](local-reference-boundaries.md), [next data/contracts batch](independent-data-evaluation-contracts.md)
- [Current delivery operations](../delivery.md), [identity boundary](../identity-boundary.md), [portability design](../research/portability-azure.md)
- `lab/control_api.py`, `lab/control_identity.py`, `lab/lifecycle.py`, `lab/reconcile_leases.py`, `lab/start_pr_watch.py`
- `lab/delivery_runtime.py`, `lab/delivery_promote.py`, `lab/delivery_cli.py`, `lab/start_delivery_watch.py`
- `research/platform-spike/common.py`, `gitea.py`, `data_contract.py`, `environments.py`: current host URLs, kubeconfig and state access
- [Concurrency evidence](../research/evidence/concurrency-isolation.md): existing persisted-state recovery and its untested live-interruption boundary
- [Deployment evidence](../research/evidence/promotion-deployment.md), [C4 local placement](../diagrams/rendered/05-local.svg)
