# Portability and Azure deployment shape

The [C4 local](../diagrams/rendered/05-local.svg) and [Azure](../diagrams/rendered/06-azure.svg) deployment views show the placements. The lab has run on Windows x64. The Azure view is a migration design; neither AKS nor Apple silicon has been exercised.

## Host portability

| Concern | Windows lab | Apple silicon route | Check still needed |
| --- | --- | --- | --- |
| Cluster tools | Pinned Windows downloads under `.lab/tools` | Install arm64 Docker Desktop, k3d, kubectl, Helm, Git and Python; `common.py` uses Helm from `PATH` when no bundled binary exists | Run fresh bootstrap natively |
| Cluster | Two-node k3d with 6 GiB server and 4 GiB agent limits | Use the same `k3d.yaml`, adjusting Docker Desktop memory to leave room for the host | Verify NetworkPolicy, storage and node memory |
| Images | Pinned manifests checked for amd64 and arm64 | Pull native arm64 variants | Run the full lifecycle natively |
| Search API | Buildx produced and published an amd64/arm64 OCI index; tests ran during each build | Use the arm64 digest from the same manifest list | Search, compare and Gatling on native arm64 |
| Performance | Windows k3d results in the batch evidence | Calibrate on the Mac independently | Never compare host latency numbers as if hardware matched |

On a fresh Apple silicon machine, install the native tools at the versions in the [research harness](../../research/platform-spike/README.md), install the Blob SDK with `python3 -m pip install --target .lab/python-libs azure-storage-blob==12.27.0`, then create a cluster with `k3d cluster create --config research/platform-spike/k3d.yaml --servers-memory 6g --agents-memory 4g`. Save `k3d kubeconfig get relevance-lab` to `.lab/kubeconfig.yaml`; confirm `kubectl --kubeconfig .lab/kubeconfig.yaml get nodes` and `helm version`. Continue the harness's platform install and the [runnable search](../../lab/README.md) checks. The research bootstrap is sequential and expects fresh local repositories; it is not an idempotent installer. Use native arm64 builds for performance evidence; emulation only proves build and functional compatibility.

## Azure component mapping

| Lab component | Azure target | Identity and operational check |
| --- | --- | --- |
| Gitea source and Actions | GitHub Enterprise Server (GHES) and a trusted self-hosted Actions runner | Replace repository/PR/run APIs, webhook signatures and runner registration behind the source-provider boundary. Keep source SHA and image digest in the environment record. |
| Nexus; historical Gitea registry | Retain Nexus, or use ACR for Azure image distribution | Nexus stores immutable images and release bundles independently of Git provider. ACR is optional; verify copied image digests and grant AKS scoped pull access. |
| k3d and local Argo CD | AKS and Argo CD | Keep Argo CD as sole deployment reconciler. Configure Git credentials and authenticated webhook/refresh against GHES, then measure event-to-ready latency. |
| Host API, UI, expiry reconciler and SQLite | AKS lab service, CronJob and durable metadata store | Move the current one-controller process behind ingress and service authentication. Choose a transactional shared store and writer coordination before multiple API replicas; SQLite and one Git checkout do not provide that. |
| Floci AZ | Azure Blob Storage | Keep immutable object names and SHA-256 checks. Use a dedicated workload identity for the Blob-writing lab controller and a short user-delegation read SAS for the finite index Job. |
| Shared ECK Elasticsearch | Self-managed Elasticsearch under ECK on AKS | Separate node/storage sizing from 40 API replicas. Retain index-level read roles, write blocks, dedicated index builds and a separate cluster for engine-version work. |
| Local Gatling Job | Reserved AKS worker pool | Isolate the generator from API/Elasticsearch capacity, pin workload bytes and record resource headroom with every run. |

The lab now reads `LAB_BLOB_ACCOUNT_URL` (default `http://127.0.0.1:14577/devstoreaccount1`), `LAB_BLOB_CONTAINER` (default `datasets`) and `LAB_BLOB_POD_URL` (default in-cluster Floci URL). For Azure, set an HTTPS account URL such as `https://<account>.blob.core.windows.net`; the Pod URL defaults to that same endpoint. Install [the pinned Azure packages](../../lab/requirements-azure.txt). The client uses `DefaultAzureCredential`; the index Job receives a short read SAS signed with a user delegation key. The Azure identity needs Blob data rights and the account-scoped `generateUserDelegationKey` action. [Microsoft's Blob SDK reference](https://learn.microsoft.com/python/api/azure-storage-blob/azure.storage.blob.blobserviceclient) and [delegation-key guidance](https://learn.microsoft.com/en-us/rest/api/storageservices/get-user-delegation-key) define those operations. The [AKS workload identity guide](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview) requires a federated identity, annotated service account and labelled Pod. The local Floci path continues to use its public emulator key; Azure credentials are not placed in source or a Kubernetes Secret by this adapter.

The current API and indexer are not yet packaged as AKS services with workload-identity service accounts. The Azure path must be validated in a tenant, including Blob round trips, delegation-SAS expiry, private endpoint/DNS and identity scope. Snapshot acceleration is separate: Floci 0.13.0 did not pass the Elasticsearch repository verification, so the canonical Blob-to-bulk path remains the baseline. [ECK documents Azure workload identity for snapshots](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/cloud-on-k8s); test it against the chosen Elasticsearch licence and Azure storage account before adopting it.

## GHES migration rehearsal

1. Mirror the application and environment-state repositories to a GHES test organisation. Map Gitea ownership and branch protection to GHES teams and rules; retain source commit SHAs.
2. Run the same source revision through a GHES Actions runner, publish its release to Nexus and capture the manifest-list digest. If ACR is selected for Azure distribution, copy and verify the same image digest. Resolve the image from AKS with its pull identity. [AKS–ACR integration](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration) describes the kubelet identity and registry role; the exact role differs for ABAC-enabled registries.
3. Run the shared `.github/workflows/release.yaml` and `ci/build.sh` from the delivery reference. Adapt repository, run, PR and status calls in `lab/delivery_provider.py`, protection/review calls in `lab/delivery_promote.py`, and configured URLs/credentials. The older `search-spike` path still has Gitea URLs and log parsing in `research/platform-spike/environments.py`; migrate those only if retaining that legacy path. The source-provider contract remains revision, build status, PR reference, webhook verification and immutable digest; do not place provider event bodies in frozen reports.
4. Configure GHES webhook delivery to the lab API and Argo CD. [Argo CD supports GitHub webhooks](https://argo-cd.readthedocs.io/en/stable/operator-manual/webhook/) and otherwise polls Git; repeat the measured event-to-ready check rather than assuming parity with Gitea.
5. Recreate a baseline and candidate, run relevance, unchanged-result and Gatling checks, promote one immutable release through all three targets, and roll back. Verify GHES branch protection and current-head statuses before deleting the previews. Verify source SHA, digest, dataset hash, comparison fingerprint and report bytes survive migration.

GHES's [3.21 container registry documentation](https://docs.github.com/en/enterprise-server@3.21/packages/working-with-a-github-packages-registry/working-with-the-container-registry) calls it public preview; retaining Nexus also avoids coupling the lab to that preview, with ACR optional for Azure distribution. GHES availability, version, Actions policy and registry choice require the target organisation's confirmation. No GHES instance is available to execute this rehearsal yet.

## Capacity and operations questions for AKS

| Decision | Evidence or starting assumption | AKS validation |
| --- | --- | --- |
| API fleet | 40 real shared-index APIs ready locally in about 73 seconds; 40 Pod sample used 460–488 MiB | Node-pool requests/limits, image pull concurrency, autoscaler lag and p95 readiness with 40+ environments |
| Elasticsearch | One local million-product shard used 647,231,847 bytes at a sample; contention pair p95 rose 4.762% under 25 rps neighbour load | Replicas, disks, shard count, heap, recovery time, licensing and performance noise at intended tenant load |
| Index builds | One dedicated million-product reindex took 113.844 seconds locally | Bound simultaneous builds by measured write throughput, disk headroom and query degradation |
| Load tests | Local Gatling phases reached 30 rps stress step | Reserve generator workers; verify they do not become the bottleneck or perturb Elasticsearch nodes |
| Lease cleanup | Second 40-environment deletion returned 40/40 in 149.157 seconds | Durable claims/heartbeats, Argo pruning, credential revocation and orphan sweep across process and node failures |
| Spend | No cloud price estimate is defensible from the local run | Price AKS system/user pools, Elasticsearch persistent disks and replicas, Nexus hosting (and optional ACR), Blob requests/storage/egress, ingress, logs and retained reports after selecting region/SKU and retention |

Keep 72-hour leases with activity extension and on-demand deletion. Alert on failed provisioning/deletion, stale leases, Git/Argo drift, index write-block loss, credential residue, Blob hash mismatches and comparison validity failures. Retain synthetic frozen releases and immutable reports according to a separate retention policy; expiry removes runtimes and dedicated indices only. The first cloud trial should measure create, compare, expiry, failure recovery and delete on one release before fleet sizing.
