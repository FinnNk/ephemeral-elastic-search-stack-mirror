# Okteto and Uffizzi for the relevance lab

This is a desk-research comparison, not an installation or benchmark. Product editions and support can change; verify the selected version in the hands-on research spike. The lab needs on-demand environments from a frozen dataset and configuration fingerprint, a separate search API version per environment, a shared Elasticsearch cluster for most experiments, a 72-hour activity-based lease, Argo CD as the production deployment authority, and eventual Apple silicon use. Query understanding, rewriting and API-side reranking are first-class experiment types.

## Edition boundary

| Product | Open source capability relevant to the lab | Full platform capability |
| --- | --- | --- |
| Okteto | Apache-2.0 CLI, chiefly `okteto up`/`down` for live code synchronisation into a development container. The open source mode supports the `dev` section of `okteto.yaml`, not full deployment or preview management. | Self-hosted Okteto adds preview namespaces, build/deploy, UI, access controls and garbage collection; it requires a platform licence, including for its Free Tier. |
| Uffizzi | Apache-2.0 self-hosted API, controller, cluster operator and CLI for creating virtual-cluster, dev-cluster and Compose environments. | Premium editions add the dashboard, RBAC and sleep/wake; these are absent from Uffizzi Open Source. |

Sources: [Okteto CLI repository](https://github.com/okteto/okteto), [Okteto CLI reference](https://www.okteto.com/docs/reference/okteto-cli/), [Okteto licence](https://www.okteto.com/docs/1.48/self-hosted/manage/okteto-license/), [Uffizzi Open Source](https://docs.uffizzi.com/open-source).

## Fit against this workload

| Requirement | Okteto open source CLI | Okteto self-hosted platform | Uffizzi Open Source |
| --- | --- | --- | --- |
| Quick edit/debug loop for the search API | Strong: live sync into a Kubernetes development container | Strong | Offers dev clusters; test the interaction with the search API workflow |
| Create/delete complete environments on demand | Not provided by open source CLI | Preview deployment and destruction are provided | Core environment creation and removal are provided |
| Activity-based 72-hour expiry | Must be built elsewhere | Garbage collector has configurable idle sleep/delete periods; verify what counts as activity and whether it matches the lease exactly | No matching lease behaviour established from the open source docs; plan an external lease controller unless tested otherwise |
| Shared Elasticsearch and frozen index reuse | Orthogonal to the CLI | Requires configuration and an integration test | Requires configuration and an integration test, especially network access from virtual/Compose environments |
| Argo CD ownership of environment workloads | CLI development mode may mutate Argo-managed Deployments; test drift/reconciliation | Argo CD can install the Okteto chart, but this does not establish that Argo CD owns each generated preview | Uffizzi has its own API/controller; test whether it can provision only the environment boundary while Argo CD owns the workloads inside it |
| Multiple engineers and 40+ environments | No environment access-control plane | Platform has access control, subject to licence and capacity | Open source edition lacks RBAC; its documentation recommends it for fewer than 5–7 developers, although that is a user-count statement rather than a measured environment-count limit |
| Apple silicon local installation | CLI documents macOS support | ARM images exist, but current self-hosted ARM support excludes bare metal and AKS ARM; Apple silicon local use is not a documented supported configuration | ARM support for the complete self-hosted stack is unverified; must be tested |

Sources: [Okteto preview workflow](https://www.okteto.com/docs/previews), [Okteto garbage collection](https://www.okteto.com/docs/admin/cleanup/), [Okteto on Argo CD](https://www.okteto.com/docs/1.44/self-hosted/manage/argocd/), [Okteto ARM support](https://www.okteto.com/docs/1.48/self-hosted/manage/arm-support/), [Uffizzi environment types](https://docs.uffizzi.com/core-concepts/ephemeral-environments), [Uffizzi Open Source limits](https://docs.uffizzi.com/open-source).

## Assessment

Okteto's **open source CLI** becomes more useful when engineers change query understanding or reranking code in the search API: live sync can shorten their edit/test loop without rebuilding the API image after every edit. A reproducible comparison still needs a pinned API image and assets; an interactive development container is not a frozen experiment artifact. The CLI does not replace the lab's environment manager. The **self-hosted platform** is a more direct competitor to Uffizzi, with preview lifecycle and garbage collection, but introduces a licensed platform and its own deployment workflow alongside Argo CD. Its documented ARM exclusions make local Apple silicon deployment a material uncertainty. The licence may still be acceptable if commercial tooling is permitted; it is not the open source-only answer.

Uffizzi Open Source is closer to a headless environment manager and merits a small installation spike. Its missing RBAC and dashboard mean the lab would still need user access control and a UI, and the 72-hour lease may still require custom code. It also adds a second environment controller beside Argo CD. Virtual clusters may be useful for experiments that change Kubernetes-wide resources, but their overhead could work against the fast default API/query path. A virtual Kubernetes control plane does not by itself provide a different Elasticsearch version. These are architectural inferences to test, not observed results.

The current leading baseline remains **Argo CD ApplicationSet + namespace + shared Elasticsearch**, with a small lab service for dataset fingerprints, leases and comparisons. Test Uffizzi Open Source against that baseline on the same create/update/delete workload. Keep Okteto's CLI as an optional development aid; evaluate the licensed Okteto platform only if the organisation is willing to adopt a second platform and its licence.

## Decisive spike questions

1. Can Uffizzi create an environment whose workloads are reconciled by Argo CD without competing ownership or unexpected deletion?
2. Can it reach a shared private Elasticsearch service with per-environment credentials and prevent cross-environment index access?
3. What are warm request-to-search, cleanup, idle resource and control-plane costs for namespace/Argo CD versus Uffizzi at 2, then 40 API-changing environments that share the same frozen index?
4. Does the complete Uffizzi self-hosted stack run on Apple silicon without architecture emulation? If not, is the local Argo CD path sufficient while Uffizzi is tested on x64?
5. For Okteto, can open source `okteto up` be used safely against a development copy of the search API without Argo CD undoing its changes? If considering the platform, confirm licence terms and its supported Apple silicon deployment path first.
