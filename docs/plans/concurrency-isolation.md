# Concurrency and isolation

## Intent

Demonstrate two or three complete local search environments at once, then measure whether the control plane can manage at least 40 lightweight API environments on suitable hardware. Separate the capacity of the local laptop from the intended fleet design.

## Constraints

| Area | Constraint |
| --- | --- |
| Frozen state | Every environment records its release, source revision, image digest, index, credentials and expiry. A shared index remains write-blocked. |
| Isolation | Use namespace-scoped Kubernetes resources and distinct Elasticsearch read credentials. Mapping experiments use distinct indices and build credentials. Do not treat namespace separation as Elasticsearch isolation. |
| Load | Concurrent lifecycle measurements must include actual ready Pods and real public API searches. A control-record-only simulation may inform API limits but cannot satisfy the deployment gate. |
| Capacity | Cap local environment creation at the measured host headroom. Run the 40-environment exercise only where CPU, memory and storage can support it; record the limit if that hardware is unavailable. |
| Reconciliation | Git desired state and Argo CD remain the deployment path. Measure drift recovery, failed create cleanup, expiry and on-demand deletion under concurrent requests. |
| Writer safety | The current lifecycle serialises provisioning around one Git checkout. Measure that path first, then introduce a bounded publication queue or batched desired-state commit if it prevents the 40-environment gate. Keep environment records and Git state recoverable together. |
| Long comparisons | The current lifecycle lock covers the full synchronous comparison, which took about eleven minutes for 1,000 queries. Move the measured work outside the shared lifecycle lock or queue it so unrelated create, search, lease and delete requests remain responsive. Preserve comparison ownership and immutable report state. |
| Review | Commit evidence and changes on a stacked branch; do not merge pending branches without review. |

The chart currently requests 25 mCPU and 32 MiB per search Pod, with limits of 250 mCPU and 96 MiB. Forty Pods therefore request 1 CPU and 1,280 MiB and have aggregate limits of 10 CPUs and 3,840 MiB, before Kubernetes, Argo CD, Gitea, Floci, Elasticsearch and network overhead. This is a scheduling model, not a capacity result. The current Docker allocation is 32 CPUs and 50,310,336,512 bytes of memory; measure actual headroom before the exercise.

## Work

1. Measure the current serial create path with two or three ready environments on one release. Record Git publication, Argo CD reconciliation, real search, lease extension and deletion times separately.
2. Exercise concurrent duplicate-name requests, create/delete races and controller restart recovery. Add database or Git writer coordination where the measured path fails, keeping the existing HTTP contract.
3. Run negative Elasticsearch credential, Kubernetes RBAC and cross-namespace network checks with two active environments. Repeat them after deleting one environment to catch stale permissions.
4. On suitable capacity, create at least 40 lightweight API deployments and matching control records, perform a real search through every deployment, then remove them. Record ready-time distribution, errors, Argo reconciliation lag, Pod resources, Elasticsearch resources and cleanup residue.
5. Compare isolated and intentionally contended search measurements. Record the observed point where shared Elasticsearch invalidates a performance comparison or where a dedicated cluster is warranted.

## Acceptance criteria

- Two or three environments, including an API-only candidate and an index-change candidate, serve real searches concurrently from the same frozen release. Deleting one leaves the others and the release intact.
- Cross-environment Elasticsearch reads and writes are denied by the tested credentials. Kubernetes RBAC and network reachability tests record the actual allowed and denied operations.
- Concurrent create, search, lease extension and delete requests preserve unique names, ownership and expiry state. Restarting the controller recovers outstanding work without duplicate or stranded resources.
- On suitable hardware, at least 40 simultaneous lightweight API environments become ready and serve one real search each. Measure creation p95 against the provisional five-minute target, errors, reconciliation lag and CPU/memory. If the hardware gate cannot be run, record the resource model and leave the target unverified.
- Record the maximum safe local concurrency, active Elasticsearch index count, disk footprint and contention effect on comparisons. Describe when a dedicated Elasticsearch cluster is required for engine-version experiments or trustworthy performance comparisons.

## More information

- [Design targets and isolation model](../prototype-design.md#provisional-quantitative-targets)
- [Lifecycle and identity evidence](../research/evidence/lifecycle-measurement/README.md)
- [Index-change evidence](../research/evidence/index-change.md)
- [Million-product scale evidence](../research/evidence/million-scale.md)
- [Lab control API](../../lab/control_api.py), [lifecycle controller](../../lab/lifecycle.py) and [deployment state](../../research/platform-spike/)
