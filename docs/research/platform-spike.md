# Platform research: results and recommendation

**26 September 2026 · Windows x64 · experimental harness**

Use **Argo CD Git-file ApplicationSets**, a namespace per environment and a **shared, read-only Elasticsearch index** for API and ranking changes. Use **k3d provisionally** for the local bootstrap. Keep kind as a tested alternative and require a native Apple silicon run before confirming portability.

The [decision record](../adr/ADR-0001-reconcile-environments-from-git.md) is proposed for acceptance. The [research harness](../../research/platform-spike/README.md) reproduces the individual probes. This batch establishes platform feasibility; the lab API, UI, leases and three complete comparison workflows remain to be built.

## Measurements

| Probe | Result | What it establishes |
| --- | --- | --- |
| Warm creation, 20 sequential trials | **p50 7.54 s; p95 8.16 s**; all passed | Credential creation → Git commit/push → explicit Argo refresh → correct top-10 response |
| Removal, the same 20 trials | **p50 50.70 s; p95 54.30 s**; all passed | Desired-state removal → namespace deletion → credential revocation |
| Reproducibility | Identical ordered top-10 IDs in all 20 trials | Same pinned image and frozen index produce the same diagnostic result |
| API change | 12 queries; only `trainers` changed | Query understanding in the API changes results even when Elasticsearch and its index are shared |
| Candidate recreation | Same definition fingerprint and all 12 result lists | A retained image and dataset support deletion and recreation |
| Analyser build | 10,000 products in **7.17 s**, one observation | A scoped Kubernetes Job reads the frozen Blob and builds a separate index |
| Analyser API comparison | `model`: baseline has results; candidate has none | The changed analyser is visible through the public search surface; dedicated index and namespace were removed afterwards |
| k3d bootstrap | **34.86 s**, one observation | Two nodes created on this machine; excludes platform installation |
| kind bootstrap | Successful; timing unavailable | The command-output decoder failed after creation, so no startup comparison is claimed |
| Separate engine | ECK cluster on 9.5.3 alongside shared 9.5.4; 10,000 products indexed | Engine-version experiments can use a separate cluster without changing the shared engine |
| Plugin generator | Creation **7.23 s**; removal **52.69 s**; one successful trial | Viable alternative, with a recovery trade-off below |

Percentiles use the median for p50 and nearest rank for p95. Twenty samples are useful feasibility evidence, not a stable tail-latency estimate. [Raw lifecycle samples](evidence/platform-spike/git-lifecycle-measurements.json), [API comparison](evidence/platform-spike/api-comparison.json), [index build](evidence/platform-spike/index-job.json) and [analyser comparison](evidence/platform-spike/index-api-comparison.json) retain the details.

**Conditions:** 96 GiB host RAM, 32 logical CPUs; Docker Desktop 4.85.0 / Engine 29.6.2 on WSL2 with approximately 46.86 GiB available to Linux. k3d nodes were limited to 6 GiB and 4 GiB. Existing unrelated containers stayed running. Images were cached on both nodes; the shared index was already built. Other small probes ran during the series. These figures are environment lifecycle timings, not search latency or a Gatling benchmark.

The retained lab used approximately **4.80 GiB of Docker memory** in one post-trial snapshot. Node-local storage used about **108 MiB**, and the two containerd directories used **8.24 GiB** in total. These directory measurements exclude Docker Desktop's own image store and virtual disk overhead. PVC requests total 23 GiB; requested capacity is not measured utilisation. [Resource snapshot](evidence/platform-spike/resources.json).

The diagnostic catalogue has ten equal-sized categories, deterministic prices and brands, UK/GBP and stable product IDs. It contains **no production data**. It does not model realistic retail popularity, long-tail judgements or traffic; those belong to the runnable slice. [Dataset assumptions](evidence/platform-spike/dataset.json).

## Platform choice

| Option | Evidence in this batch | Recommendation |
| --- | --- | --- |
| Argo CD + Git files | Real Gitea builds, digest deployment, 20 lifecycle trials, failed-image cleanup, API comparison and recreation | **Use.** It meets the provisional startup budget while retaining desired state in Git |
| Argo CD + plugin | Real creation, injected source failure, recovery and explicit removal | Keep as an alternative if Git contention becomes measurable |
| k3d | Two-node runtime, registry routing and cross-node NetworkPolicy verified | Provisional local default; most of this batch ran here |
| kind | Two-node runtime and the same policy/RBAC probe passed | Supported research alternative; no measured speed or memory advantage established |
| Uffizzi OSS | Published chart rendered; API/CLI can integrate with arbitrary CI | Defer runtime installation: another application/controller and Flux stack overlap the required Argo path |
| Lifecycle | Documented onboarding uses a GitHub App installation | Revisit for GitHub Enterprise; a supported Gitea onboarding path remains unverified |
| Devtron | Documents Argo CD integration | Credible broader platform; defer until its portal saves more work than its additional control plane costs |
| Okteto CLI | Useful development/synchronisation tool; distinct from its platform | Optional engineer tool, not the experiment/lease controller |
| Signadot / Coolify | Constraints recorded in the earlier comparison | No change: hosted control-plane dependency / different deployment focus |
| vCluster / dedicated Kubernetes cluster | Not installed | Reserve for experiments needing their own operators, CRDs or Kubernetes versions |

The Uffizzi chart inspected was 1.3.0, declaring application 2.3.0. Its rendered defaults included unpinned application/controller images, Flux source/Helm controllers, PostgreSQL, Redis, cert-manager and ingress-nginx. That is a concrete integration and maintenance burden, not proof that Gitea is impossible. A competing platform should demonstrate a supported Gitea-to-Argo ownership model before another runtime trial.

Sources: [Uffizzi source and CI integration](https://github.com/UffizziCloud/uffizzi), [published chart](https://github.com/UffizziCloud/uffizzi/tree/develop/charts/uffizzi-app), [Lifecycle onboarding](https://uselifecycle.com/docs/getting-started/onboard-repository), [Devtron Argo integration](https://docs.devtron.ai/docs/user-guide/integrations/argocd). Earlier detail: [Okteto/Uffizzi](okteto-uffizzi.md), [Lifecycle/Signadot/Coolify](lifecycle-signadot-coolify.md).

## Isolation and failure recovery

| Boundary or failure | Observed behaviour | Design consequence |
| --- | --- | --- |
| Cross-node traffic, k3d and kind | Initially allowed; deny-all blocked both clients; namespace allow-rule restored only the intended client | Both tested defaults enforce these ingress policies; do not assume kind lacks policy support |
| Kubernetes credentials | Default service account could not read another namespace's secrets | Disable automatic token mounts for ordinary search workloads; scope any controller permissions |
| Shared Elasticsearch | Environment credential received 403 for another index and for writes | Keep distinct read-only credentials per environment; namespace isolation alone is insufficient |
| Plugin source outage | Existing workload remained searchable | A source error must preserve desired state, never become an empty environment list |
| Plugin recovery | **179.89 s** before generator success; an earlier deletion attempt exceeded 150 s | Treat deletion as asynchronous and observable; explicit refresh did not eliminate this observed delay |
| Unavailable image digest | Candidate entered ImagePullBackOff; Git removal deleted its namespace and credentials | Cleanup must work even when an environment never becomes ready |
| Repeated build of the same source SHA | Reusing a SHA tag left an earlier OCI digest unavailable | Use a unique retention tag per SHA/run/attempt; deploy by digest and verify that it remains retrievable |
| Gitea webhooks | Real signed pushes accepted, invalid signature rejected, repeated delivery ID recognised | Implement durable deduplication and verified build lookup in the lab API; the probe stores events only in memory |

[k3d isolation](evidence/platform-spike/k3d-isolation.json), [kind isolation](evidence/platform-spike/kind-isolation.json), [Elasticsearch access checks](evidence/platform-spike/data-contract.json), [plugin results](evidence/platform-spike/plugin-generator.json), [failed-environment cleanup](evidence/platform-spike/failed-environment-cleanup.json), [webhook evidence](evidence/platform-spike/webhook.json).

The runner uses upstream rootless Docker-in-Docker but **still requires a privileged pod**. It has a repository-scoped registration, its own cache volumes and no host Docker socket. This is a trusted-code lab configuration; untrusted PR execution requires a separate build isolation decision. [Gitea Kubernetes runner guidance](https://docs.gitea.com/runner/installation/kubernetes/).

## Storage and portability

| Check | Result | Next step |
| --- | --- | --- |
| Azure Blob SDK upload/download | Content hash matched | Keep Floci for canonical releases and reports |
| Conditional creation | Existing object was not overwritten | Apply this to manifests as well as product data |
| Blob SAS read | Job read its one-object, 15-minute SAS using the documented emulator key | Add negative SAS scope/expiry tests before claiming access isolation |
| Elasticsearch Azure snapshot repository | **Failed**: repository verification hit an unimplemented batch-delete operation (HTTP 501) | Use canonical Blob → bulk indexing; do not enable snapshot acceleration on this combination |
| Public runtime image manifests | Tested images include Linux amd64 and arm64 | Run natively on Apple silicon; manifest presence is not a runtime test |
| Search image build | Local amd64 build and pull passed | Add and verify multi-architecture publication in the next slice |

The snapshot failure was reproduced with Elasticsearch 9.5.3 and Floci 0.13.0 using the correct emulator key. Restore was **not reached**. [Snapshot evidence](evidence/platform-spike/snapshot-compatibility.json), [image platform inspection](evidence/platform-spike/image-platforms.json), [Azure repository settings](https://www.elastic.co/docs/reference/elasticsearch/configuration-reference/azure-repository-settings).

Floci's [SharedKey verifier](https://github.com/floci-io/floci-az/blob/0.13.0/src/main/java/io/floci/az/core/auth/SharedKeyAuthVerifier.java) accepts signatures in development mode. A successful SDK call therefore does not establish Azure-equivalent authentication enforcement. Keep Floci network access restricted and verify Azure authorisation separately during migration.

The spike also exposed a hostname issue: Git/curl treats `.localhost` specially even when cluster DNS supplies a different address. Git therefore uses Gitea's service DNS; registry clients use the configured mirror. Replace this workaround with a consistent TLS-enabled naming scheme in the runnable slice. Elasticsearch clients use the hostname present in ECK's certificate and verify its CA.

## Targets and remaining gates

**Retain every first-slice target.** The measurements support feasibility but do not justify tightening the acceptance budgets.

| Target | Evidence now | Still required |
| --- | --- | --- |
| Warm API environment p50 ≤ 60 s / p95 ≤ 120 s | 20 successful diagnostic trials, well inside budget | Include the lab API, metadata transaction, realistic frozen manifest and readiness validation |
| Index-changing environment p95 ≤ 5 min | One successful Job and one API deployment | Repeated combined measurements with the realistic dataset |
| PR update → correct search p95 ≤ 8 min | All stages demonstrated, with manual orchestration between them | Automated completion handling and 20 timed end-to-end trials; do not add individual timings and call that a measurement |
| Removal p95 ≤ 5 min | 20 namespace/credential deletions; one dedicated-index deletion | Lease expiry, crash recovery and failure injection in the actual controller |
| Ordered top-10 preservation | Diagnostic equality and recreation checks | Frozen judged query suite, exact verdict, RBO/Jaccard and artefact provenance |
| Gatling smoke and trace-derived profiles | Not run | All stated throughput, latency, error and generator-headroom checks |
| 1,000,000 products / 1,000 queries / 40+ environments | Not run | Dataset, index size, scheduling, Git write contention and noisy-neighbour scale tests |
| Apple silicon | Image availability only | Native bootstrap, runner, policies, search and cleanup |

Before the runnable slice is accepted:

- Implement 72-hour leases, meaningful activity extension, idempotent deletion and reconciliation after restart.
- Serialize desired-state Git writes with bounded conflict retries; keep immutable definitions after active entries are removed.
- Extend the spike fingerprint to include chart revision, mappings/settings hashes, query assets, runtime settings and evaluation inputs. The spike pins the API image, dataset hash, index name and engine version only; its chart tracks `main`.
- Pin runtime manifests by digest, protect baseline registry tags and verify image availability before declaring an environment reproducible.
- Replace the default Argo project and broad research bootstrap permissions with scoped projects and service accounts.
- Verify the clean bootstrap recipe and Apple silicon path. The scripts preserve working experiments, but are not yet a one-command installer.
- Rehearse backup and restore for Gitea's database, registry and Blob artifacts. GitHub copies Git history only.

The diagrams continue to describe the intended complete lab. No topology change is needed for this recommendation: the existing desired-state repository and Argo CD remain the deployment path.
