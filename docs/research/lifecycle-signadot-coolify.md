# Lifecycle, Signadot and Coolify: relevance to the search lab

Desk research on 26 September 2026. These are suitability hypotheses, not installation or performance results. The lab needs on-demand API and query experiments over a frozen catalogue, occasional independent indices, three-day leases, on-demand deletion, a shared self-managed Elasticsearch cluster, Argo CD ownership and a path from a small local demonstration to 40+ lightweight environments.

| Platform | Relevance | Research disposition |
| --- | --- | --- |
| Lifecycle by GoodRx | High for environment workflow; blocked by the stated self-contained Gitea requirement on current documentation | Revisit only if a supported Gitea integration is demonstrated; also require one controller to own each workload cleanly |
| Signadot | High as an architectural reference; low as the selected self-hosted platform | Borrow the changed-service and baseline-routing idea; revisit the product only if hosted control plane is acceptable |
| Coolify | Low for the intended Kubernetes platform | Do not spend a main spike on it; consider only for a separate Docker-based demonstration |

## Lifecycle by GoodRx

Lifecycle is [Apache-2.0 open source](https://github.com/GoodRxOSS/lifecycle) and [runs on Kubernetes](https://uselifecycle.com/docs/operations/architecture). Its API-created environments are no longer restricted to pull requests: an authorised caller can select an onboarded repository and branch, create an environment with an idempotency key, poll its status, change overrides, redeploy, extend its lease and delete it. The UI offers the same PR-less path. This maps unusually well to engineers creating and destroying query-understanding or ranking candidates on demand. Its [API documentation](https://uselifecycle.com/docs/features/api-environments) also describes a configurable default/maximum lease policy.

The important fit questions are:

1. **Argo CD authority.** Lifecycle's worker [builds and applies workloads to Kubernetes](https://uselifecycle.com/docs/operations/architecture). The current design expects Argo CD to reconcile environment resources. Two reconcilers must not claim the same Deployments, Jobs or namespace resources. The spike should determine whether Lifecycle can delegate environment manifests to Argo CD. If it cannot, trial it as an alternative deployment owner while Argo CD owns only the long-lived platform; compare the operational impact explicitly. This delegation is not established by the reviewed documentation.
2. **Repository and local setup.** API-created environments still require an [onboarded repository](https://uselifecycle.com/docs/features/api-environments), and the documented onboarding path uses a GitHub App. Its [local development guide](https://github.com/GoodRxOSS/lifecycle) uses kind, Tilt and an ngrok domain for the GitHub integration. The lab now requires Gitea for a self-contained source lifecycle. No supported Gitea integration was found in the reviewed Lifecycle documentation, so treat this as a selection blocker until a working supported path is shown.
3. **Control-plane weight and hardening.** The [architecture](https://uselifecycle.com/docs/operations/architecture) includes PostgreSQL and Redis, with identity and build dependencies depending on installation. Its [security guide](https://uselifecycle.com/docs/operations/security) says default Kubernetes permissions are broad and that the stock chart is not an authentication-on profile ready for shared-network exposure. These costs matter for a local lab and for 40 users.
4. **Lease semantics.** An API lease can be extended, but the [extension starts from the later of now and the current expiry](https://uselifecycle.com/docs/features/api-environments). The lab's desired rule is expiry 72 hours after last genuine activity. Repeated fixed extensions could yield a longer lease than that rule. Test whether Lifecycle policy/override can express the exact rule; otherwise the lab API must calculate and manage it.
5. **Search-specific state.** Lifecycle's environment abstraction does not by itself provide immutable dataset manifests, shared-index reference tracking, narrowly scoped Elasticsearch credentials or end-to-end relevance comparison. Those remain lab responsibilities. Verify that its service configuration can point an API-only candidate at a shared frozen index and run an isolated reindex job for mapping changes.

The hands-on comparison should run the same prebuilt search API image through Lifecycle and the Argo CD-native path, first against a shared index and then with a changed mapping. Measure request-to-first-search, creation failures, deletion completeness and control-plane resource use. Do not credit Lifecycle with speed or 40-environment capacity until measured.

## Signadot

Signadot's [sandbox model](https://www.signadot.com/docs/concepts/architecture/operator) forks changed workloads and routes selected traffic to them while other services stay at a baseline. For this lab, that is a useful model for changing the *search API* itself: query parsing, spelling correction or reranking may change without a new Elasticsearch index. Its [sandbox specification](https://www.signadot.com/docs/reference/sandboxes/spec) includes a mutable TTL, so a three-day lease is expressible.

I could not verify an official self-hosted **Community Edition**. The [pricing page](https://www.signadot.com/pricing/) instead lists a free Starter plan with 50 sandbox creations per month and one cluster, and says the dashboard and API are hosted in Signadot's cloud. The [architecture documentation](https://www.signadot.com/docs/concepts/architecture/control-plane) identifies `api.signadot.com` as the control-plane API; the in-cluster operator connects to it. That misses the stated self-managed, open-source platform preference. The free plan also should not be mistaken for proof that 40+ recurring environments are economical: creation volume, not simply concurrency, matters. It is worth revisiting only if using a hosted control plane becomes acceptable.

Its baseline-routing pattern also needs care for reproducibility. The evaluator must pin the sandbox route, API revision, dataset and index for every request; otherwise a request that falls through to baseline would contaminate the comparison. Index-changing experiments still require separate index creation and credentials.

## Coolify

Coolify is a self-hosted deployment UI and API for [Docker containers on connected servers](https://coolify.io/docs/applications/). It has [pull-request preview deployments](https://coolify.io/docs/applications/deployments/preview-deployments), preview-specific variables and automatic removal when the pull request closes. Its [deployment API](https://coolify.io/docs/api/endpoints/deployments/deploy-by-tag-or-uuid) can trigger image-based previews. This could shorten a disposable Docker-only API/UI proof of concept.

Its documented destinations and deployments use Docker and Compose rather than the Kubernetes and Argo CD control path required here. The [scaling documentation](https://coolify.io/docs/core/infrastructure/scaling/docker-swarm) also marks its older Swarm support as deprecated. It would introduce another deployment surface without exercising namespace isolation, ECK, Kubernetes Jobs or Argo CD. A preview's closure-based cleanup is not the specified activity-based 72-hour lease; the lab would still implement that policy. For this project, Coolify is not a leading candidate.

## Decision to make in the research spike

Start with **Argo CD-native namespace/Helm backed by Gitea**. Compare Lifecycle only if a supported Gitea integration is demonstrated; Uffizzi remains a candidate if its Gitea and Argo CD coexistence can be demonstrated in the open-source edition. Keep Signadot as a design reference and Coolify outside the main spike. The decision turns on a fully local source-to-preview path, one owner per Kubernetes object, exact lease behaviour, API-only warm-start time, shared-index isolation, setup weight and the cost of 40 active environments.
