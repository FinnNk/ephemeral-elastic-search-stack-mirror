# Platform research harness

These scripts exercise Gitea builds, Argo CD environments and real Elasticsearch searches against a 10,000-product synthetic fixture. Read the [results](../../docs/research/platform-spike.md) before using the timings.

**Status:** tested as individual experiments on Windows x64. This is an experimental, sequential research recipe, not an idempotent lab installer. Run it in a fresh `relevance-lab` cluster and empty research repositories. Do not rerun initialisation over the retained review environment: some probes deliberately create and remove named indices.

## Prerequisites and versions

Run PowerShell from the repository root. `python` below means a Python 3.12+ interpreter with pip; substitute its full path if needed. Docker Desktop must use Linux containers. Git and kubectl must be on `PATH`.

| Component | Tested version |
| --- | --- |
| Docker Desktop / Engine | 4.85.0 / 29.6.2 |
| k3d / k3s | 5.9.0 / 1.35.8+k3s1 |
| kind alternative | 0.33.0, Kubernetes 1.35.8 |
| Helm | 4.3.0 |
| Gitea chart / server / runner | 12.7.0 / 1.27.0 / 3.5.0-dind-rootless |
| Argo CD / ECK | 3.5.3 / 3.5.0 |
| Shared / exceptional Elasticsearch | 9.5.4 / 9.5.3 |
| Floci / Azure Blob Python SDK | 0.13.0 / 12.27.0 |
| Fixture image | Python 3.13.7-alpine3.22 |

The two k3d nodes have a combined 10 GiB limit. Leave additional Docker memory for its VM, image builds and existing workloads. Downloads require internet access; offline bootstrap has not been tested. The downloader below selects Windows amd64 tools. The [Apple silicon route](../../docs/research/portability-azure.md#host-portability) uses native tools from `PATH`; its bootstrap still needs a native verification run.

## Bootstrap the research cluster

1. Download checksum-verified tools and the SDK into the ignored `.lab` directory:

   ```powershell
   $env:PYTHONUTF8 = '1'
   python research/platform-spike/download_tools.py
   python -m pip install --target .lab/python-libs azure-storage-blob==12.27.0
   ```

2. Create the named cluster and its dedicated kubeconfig. These commands do not switch the user's default Kubernetes context:

   ```powershell
   .lab/tools/k3d.exe cluster create --config research/platform-spike/k3d.yaml --servers-memory 6g --agents-memory 4g
   .lab/tools/k3d.exe kubeconfig get relevance-lab | Set-Content -Encoding utf8 .lab/kubeconfig.yaml
   kubectl --kubeconfig .lab/kubeconfig.yaml get nodes
   ```

3. Install the persistent services:

   ```powershell
   .lab/tools/helm.exe repo add gitea-charts https://dl.gitea.com/charts/
   .lab/tools/helm.exe repo update gitea-charts
   python research/platform-spike/install_platform.py
   kubectl --kubeconfig .lab/kubeconfig.yaml rollout status statefulset/elastic-operator -n elastic-system --timeout=180s
   kubectl --kubeconfig .lab/kubeconfig.yaml apply -f research/platform-spike/elasticsearch.yaml
   kubectl --kubeconfig .lab/kubeconfig.yaml apply -f research/platform-spike/floci.yaml
   kubectl --kubeconfig .lab/kubeconfig.yaml get elasticsearch -n platform
   kubectl --kubeconfig .lab/kubeconfig.yaml get pods -n argocd
   ```

   Wait for shared Elasticsearch to report green and the Argo pods to be ready. Gitea uses SQLite and its own PVC for this small lab. Credentials are generated in `.lab/credentials.json`; do not commit or paste that file.

   Install the Gitea HTTPS route and the CA bundle before starting its runner. This research bootstrap has not yet installed the other four web backends, so use the Gitea-only action:

   ```powershell
   python -m pip install -r lab/requirements-https.txt
   python lab/https_ingress.py bootstrap-gitea
   python lab/https_ingress.py trust
   ```

4. Register the repository-scoped runner:

   ```powershell
   python research/platform-spike/gitea.py
   kubectl --kubeconfig .lab/kubeconfig.yaml apply -f research/platform-spike/runner.yaml
   kubectl --kubeconfig .lab/kubeconfig.yaml rollout status deployment/build-runner -n platform --timeout=180s
   ```

   The rootless Docker-in-Docker runner is privileged and accepts trusted local repository code. Its Docker cache lives on a dedicated PVC; it does not mount the host Docker socket.

## Build and compare

Run these steps sequentially. They share one working copy of the environment-state repository and do not implement concurrent writer locking.

1. Push the baseline fixture and start loopback Elasticsearch/Floci port forwards:

   ```powershell
   python research/platform-spike/start_fixture.py
   ```

   Open [Gitea Actions](https://gitea.localhost:34443/elastic-agent/search-spike/actions). Sign in using the local agent account in `.lab/credentials.json`. Wait for a successful run and note its run ID. Run IDs vary between installations.

2. Freeze the catalogue and create the baseline. Replace `BASELINE_RUN_ID` with that successful ID:

   ```powershell
   python research/platform-spike/data_contract.py
   python research/platform-spike/environments.py --run BASELINE_RUN_ID
   kubectl --kubeconfig .lab/kubeconfig.yaml get applications -n argocd
   ```

   The data probe verifies Blob hash/conditional creation, read-only index access and denied cross-index access. The baseline should become Synced/Healthy. API correctness is checked separately by the measurement scripts.

3. Open a candidate PR which changes API query understanding:

   ```powershell
   python research/platform-spike/create_candidate.py
   ```

   Wait for its successful Actions run. The workflow tests the exact source SHA, publishes a unique SHA/run/attempt retention tag and records its OCI digest. Replace `CANDIDATE_RUN_ID` below:

   ```powershell
   python research/platform-spike/compare.py --run CANDIDATE_RUN_ID
   ```

   Expected: 12 queries compared; only `trainers` changes. The candidate is deleted and recreated, and all its result lists match. The report is stored in Floci and `.lab/evidence/api-comparison.json`.

4. Exercise index changes:

   ```powershell
   python research/platform-spike/probe_index.py
   python research/platform-spike/compare_index.py
   ```

   A Kubernetes Job builds an analyser that removes `model`. Both APIs are queried; the temporary namespace, credentials and dedicated index are then removed. The shared baseline index remains.

## Additional probes

| Command | Expected result |
| --- | --- |
| `python research/platform-spike/measure.py --repetitions 20` | 20 sequential create/search/delete records; approximately 20 minutes; no concurrent desired-state writers |
| `python research/platform-spike/probe_isolation.py --kubeconfig .lab/kubeconfig.yaml --name k3d` | Cross-node ingress and cross-namespace secret denial; probe namespaces cleaned |
| `python research/platform-spike/probe_plugin.py` | Plugin creation, source-error preservation, recovery and removal; recovery may take about three minutes |
| `python research/platform-spike/install_webhook.py` | Signed Gitea hooks registered; receiver is an in-memory diagnostic, not a deployment controller |
| `python research/platform-spike/version_experiment.py` | Separate ECK 9.5.3 cluster and loopback forward on 19201 |
| `python research/platform-spike/probe_snapshot.py` | Current combination records repository verification failure; canonical indexing succeeds |

For kind, create the separate named cluster, run the same probe and remove it through kind:

```powershell
.lab/tools/kind.exe create cluster --name relevance-kind --config research/platform-spike/kind.yaml --kubeconfig .lab/kind-kubeconfig.yaml --image kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0
python research/platform-spike/probe_isolation.py --kubeconfig .lab/kind-kubeconfig.yaml --name kind
.lab/tools/kind.exe delete cluster --name relevance-kind
```

## Inspect and recover

- Gitea: [project repository](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack), [fixture](http://127.0.0.1:31800/elastic-agent/search-spike), [desired state](http://127.0.0.1:31800/elastic-agent/environment-state).
- Search: forward a selected service with `kubectl --kubeconfig .lab/kubeconfig.yaml -n spike-baseline port-forward svc/search 18080:8080 --address 127.0.0.1`, then open `http://127.0.0.1:18080/search?q=trainers`. Use `spike-candidate-retained` to inspect the candidate.
- Evidence: `.lab/evidence`. Checked-in copies are under `docs/research/evidence/platform-spike`; they contain no generated credentials.
- Port-forward failures: inspect `.lab/*-forward.log`. A forward may still point at a replaced pod; stop that specific process and restart the forward. Never stop all kubectl processes.
- ImagePullBackOff: verify the digest still exists in Gitea. Build a new candidate definition from a retained digest; do not silently replace the image behind an old fingerprint.
- Failed probe: inspect its Job/pod logs and record the failure before removing only the named probe resources. Do not force-remove Argo finalisers to make a cleanup test pass.

The shared fixture, baseline and candidate remain running for review. **No lease controller exists yet**, so they do not expire after three days. Temporary kind and version-test clusters were removed after the recorded run.

## Personal access

The local lab can create a named reviewer account independently of the `elastic-agent` build identity:

```powershell
python -m pip install --target .lab/python-libs bcrypt==4.3.0
python research/platform-spike/enable_user_access.py
```

The script uses the local Git identity for the email address and creates `finnnk` as a Gitea site administrator and administrator collaborator on all three lab repositories. It also creates an Argo CD local account with the same username and the built-in administrator role. Initial passwords are distinct and stored in ignored `.lab/user-credentials.json`. Change them in the respective account settings after first login. Re-running the script preserves an existing Argo CD password.

| Endpoint | Local address | Login |
| --- | --- | --- |
| Gitea and its private pull requests | `https://gitea.localhost:34443` ([local HTTPS setup](../../docs/https-ingress.md)) | `finnnk` and `gitea_password` in `.lab/user-credentials.json` |
| Argo CD applications | `https://argocd.localhost:34443` | `finnnk` and `argocd_password` in the same file initially |

Argo CD uses HTTP only for this loopback port forward. Kubernetes keeps the service inside the local cluster; the browser address binds to `127.0.0.1`. The hidden port-forward process may stop after a cluster or pod restart; rerun `enable_user_access.py` to restore it. The bootstrap `lab-admin` Gitea account remains for recovery. Gitea repositories remain under the agent's namespace, while the personal account has site administration and explicit repository administration.

To stop the lab while retaining its Docker volumes, use `.lab/tools/k3d.exe cluster stop relevance-lab`; resume with `cluster start relevance-lab`. Full cluster deletion destroys the current local Gitea/registry/Blob data and requires a separate backup decision. A GitHub push does not back up these volumes.

## Git remotes and backups

The project uses local Gitea `origin` for branches and pull requests, and `github` for an explicit offsite Git copy. Push each completed review branch to both; after an accepted merge, fetch Gitea and push the resulting `main` to GitHub through its permitted protected-branch process. No unattended backup schedule is configured.

The probe repositories have their own independent Git histories. Their recorded source SHAs and images are local artifacts, not commits in the project repository. Preserve Gitea's database and registry to retain them; the fixture directory can generate a fresh walkthrough but will produce new source SHAs.
