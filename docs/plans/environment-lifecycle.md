# Environment lifecycle and UI plan

This plan was split into a [reviewable foundation](../research/evidence/lifecycle-foundation/summary.json) and the [lifecycle completion batch](lifecycle-completion.md). The acceptance criteria below describe the complete workflow; the foundation alone does not meet all of them.

## Intent

Make the current script-driven environment workflow usable through a small local API and web UI. An engineer can create or reuse a pinned environment, inspect its state and source, run a comparison, record genuine activity and remove it. A reconciler expires unused instances after 72 hours and safely recovers partial cleanup.

## Constraints

| Area | Constraint |
| --- | --- |
| Source of truth | Keep immutable environment definitions in Gitea and Argo CD responsible for Kubernetes workloads. The controller stores runtime state and leases separately. Do not make the browser write Kubernetes resources directly. |
| Identity | Continue using distinguishable local Gitea/Argo CD identities. Do not put credentials or tokens in Git, reports or browser responses. |
| Reuse | A request with the same fingerprint may reuse its frozen index; runtime instance IDs, ownership, state and expiry remain distinct. |
| Expiry | Start at 72 hours after creation; extend only after explicit, genuine use. Polling, health checks and background reconciliation do not renew the lease. |
| Deletion | Manual and expiry paths share one idempotent operation. Remove namespaced resources, dedicated credentials and candidate-only indices, while preserving canonical datasets, definitions, shared frozen indices and reports. |
| Portability | Prefer Kubernetes and standard libraries; keep metadata access behind an interface so local SQLite can be replaced if 40+ deployments show contention. Avoid Windows-only logic in the service. |
| Scope | The UI may be simple. It must expose the useful lifecycle without a terminal after bootstrap. Synthetic data only. |

## Work

1. Define runtime states, the request/response schema and a durable metadata repository. Pin source SHA, image digest, dataset hash, index design and engine version in each definition.
2. Implement `GET /datasets`, create/list/get/delete/activity for environments, and comparison creation/status around the existing evaluators. Return state-transition errors and timings.
3. Reconcile Gitea state, Argo CD readiness, credentials and cleanup after retries or process restarts. Add an expiry scan; prevent passive operations from extending leases.
4. Add a small browser page for environment creation, status, search, comparison and deletion. Show source and fingerprint links and clear incomplete/failed states.
5. Test repeated create/delete, partial failure recovery, access boundaries and expiry with a controllable clock. Measure at least 20 warm removal samples and keep failures in the sample.

## Acceptance criteria

- A local user can complete create → ready search → comparison → delete through the UI/API, using only the lab's local Gitea and cluster after bootstrap.
- Every ready environment identifies exact source SHA, image digest, dataset hash, definition fingerprint, owner and expiry; mutable-only references are rejected.
- Genuine activity extends expiry to 72 hours after the activity. Read-only status polling and health probes leave it unchanged. The expiry scan starts cleanup within 10 minutes of expiry and finishes within 15 minutes under the documented warm-lab conditions.
- On-demand deletion is idempotent and targets p95 ≤ 5 minutes over at least 20 samples. Shared frozen data and completed reports remain accessible.
- A failed provision or deletion reports its state and can be reconciled after restart without orphaning credentials or a dedicated index.
- UI and API reject invalid inputs and do not expose secrets. Tests and live evidence establish the implemented behaviour; a passing smoke test is not a 40-environment capacity claim.

## More information

- [Prototype design: environment lifecycle and API](../prototype-design.md#environment-lifecycle-and-api)
- [Provisional quantitative targets](../prototype-design.md#provisional-quantitative-targets)
- [Argo CD environment-state publisher](../../research/platform-spike/environments.py)
- [Current baseline deployment](../../lab/deploy_baseline.py) and [comparison runner](../../lab/compare_search.py)
- [Platform lifecycle research](../research/platform-spike.md)
