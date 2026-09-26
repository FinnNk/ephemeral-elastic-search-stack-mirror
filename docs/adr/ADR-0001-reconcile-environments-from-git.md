# ADR-0001: Reconcile ephemeral environments from a dedicated Git repository

- **Status:** Proposed
- **Deciders:** AI (Codex GPT-6); awaiting user acceptance
- **Date:** 2026-09-26

## Context

The lab must create reproducible search environments quickly, use Gitea locally and migrate to GitHub Enterprise. Argo CD is already a production constraint. Environment definitions must survive workload deletion; a live lease service must not become the only record of what was deployed.

The research harness created and removed 20 environments through a Git-file ApplicationSet. Warm creation was p95 8.16 seconds. A plugin generator also worked, but recovery after a source error took 179.89 seconds in the observed trial. Neither result measures the future complete lab controller.

## Decision

We will publish active environment definitions to a dedicated Git repository and use Argo CD's Git-file ApplicationSet generator to reconcile them. The lab API will own leases, comparison records and publication retries. Argo CD will own the declared Kubernetes workloads.

Removing an active entry will remove its workloads. Immutable environment definitions and referenced artifacts will remain available for recreation. The API will revoke credentials and remove dedicated indices as explicit, retryable cleanup steps.

## Consequences

- Gitea and GitHub Enterprise can use the same desired-state structure and Argo deployment path.
- Git gives an inspectable record of creation and removal, with enough measured startup headroom for the first slice.
- The lab must handle concurrent Git writers, retries and drift between metadata, Git and cluster status. Git is not the lease database.
- A missed refresh must recover through polling. API responses must distinguish requested, ready, deleting and failed states.
- The Git repository and retained image/dataset artifacts become recovery dependencies.
- The implementation remains experimental until lease/restart recovery, full manifest pinning and the 40-environment exercise pass. The harness can be removed independently of the eventual lab API.

## Options considered

1. **Git-file ApplicationSet — selected.** Tested lifecycle, persistent desired state and no additional deployment controller.
2. **Plugin generator — retained as an alternative.** Direct access to active metadata is attractive, but adds an availability dependency and source-error semantics. Revisit if measured Git contention warrants it.
3. **Ready-made environment platform — deferred.** Uffizzi adds overlapping controllers; Lifecycle's documented onboarding assumes GitHub; Devtron offers a wider platform. None demonstrated a simpler Gitea-to-Argo integration for this batch.
4. **Direct Helm/Kubernetes orchestration — rejected as the default.** It would duplicate the required Argo reconciliation responsibility.
5. **Do nothing — rejected.** Leaving deployment ownership undecided would make the next slice build both competing paths or couple the API to an untested controller.

## Links

- [Platform research and measured evidence](../research/platform-spike.md)
- [Prototype architecture and lifecycle](../prototype-design.md)
- [Argo CD Git generator](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/)
