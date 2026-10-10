# Operate the Kubernetes control services

The control UI/API, lease worker, PR watcher and delivery watcher run in one `lab-control` Pod. Use this guide to inspect, update or back up that runtime. Use the [lab workflows](../lab/README.md) to create and compare environments.

The Pod has one replica. Its 2 GiB persistent volume holds SQLite, Git checkouts, frozen inputs and local reports. Do not start host control or watcher processes alongside it: both would write the same logical state.

## Connect and check

Prerequisites: an installed lab, `kubectl`, Python and the retained state directory containing `kubeconfig.yaml`. Commands below use PowerShell from the repository root. macOS operators can use
the Terminal commands in [Mac setup](mac-setup.md); the same Python entry points
apply once its venv and `LAB_STATE_DIR` are set. In another worktree, set `LAB_STATE_DIR` to the **existing** state directory rather than creating new state.

```powershell
# Replace this with your retained state directory if it is elsewhere.
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$labState = $env:LAB_STATE_DIR
$kubeconfig = Join-Path $labState kubeconfig.yaml
kubectl --kubeconfig $kubeconfig -n lab-control get deploy,pod,pvc,svc
kubectl --kubeconfig $kubeconfig -n lab-control exec deployment/lab-control -c api -- uv run --locked python lab/control-runtime/smoke.py
```

Expect ready `lab-control` and `lab-control-oidc` Deployments, four ready control containers and a Bound PVC. The smoke check prints JSON containing `cluster: matched`, the Gitea runtime identity, Elasticsearch version, record counts and `nexus: reachable`. It checks connectivity; it does not run a comparison.

Open [Control UI](https://control.localhost:34443/) and sign in with your lab
identity. OAuth2 Proxy runs in a separate Pod; the control Pod still contains
four workers. See [OIDC access](oidc-access.md#open-the-control-ui) for reader
permissions and operator verification.

A loopback port forward can help diagnose readiness, but authenticated browser
access uses the canonical HTTPS URL.

| Problem | Check and recovery |
| --- | --- |
| Pod unavailable | Inspect `kubectl --kubeconfig $kubeconfig -n lab-control describe pod`; check image pulls and PVC binding before restarting anything. |
| Smoke check fails | Read the named service error and the API log below; verify that service and its ESO-backed Secret are ready. |
| UI redirects or refuses a request | Use the canonical `https://control.localhost:34443/` address; inspect `LAB_CONTROL_PUBLIC_URL` in `lab-control-config`. |
| Comparisons fail after restart | Inspect retained comparison state and logs. Do not delete SQLite or rerun initial activation. |

```powershell
kubectl --kubeconfig $kubeconfig -n lab-control logs deployment/lab-control -c api --tail=30
kubectl --kubeconfig $kubeconfig -n lab-control logs deployment/lab-control -c leases --tail=30
```

## Update an existing runtime

Wait for active comparisons and delivery work to finish. The Deployment uses `Recreate`, so an update stops the old Pod before starting the new one and interrupts in-memory work.

1. Obtain a successful **search-spike Actions run ID** for the baseline. Keep the installed value if the baseline is unchanged:

   ```powershell
   $baselineRun = kubectl --kubeconfig $kubeconfig -n lab-control get configmap lab-control-config -o 'jsonpath={.data.LAB_PR_BASELINE_RUN}'
   ```

   For a new baseline, use the ID in the successful run's `/actions/runs/<id>` URL. The worker resolves its source commit and image digest. Do not use a PR number or a delivery-source run ID.

2. Publish the image and reconcile configuration:

   ```powershell
   uv run --locked python lab/control-runtime/publish.py
   $controlImage = (Get-Content (Join-Path $labState control-image.json) -Raw | ConvertFrom-Json).image
   uv run --locked python lab/control-runtime/install.py stage --image $controlImage --baseline-run $baselineRun
   ```

   Publishing requires Docker buildx and the retained Nexus publisher credential. It prints the immutable Nexus image reference and writes `control-image.json`. The manifest contains amd64 and arm64 images; native Apple silicon operation remains unverified. `stage` reconciles installer-owned resources and leaves ESO-owned Secret values intact.

3. Apply that image, wait for readiness and repeat the smoke check:

   ```powershell
   uv run --locked python lab/install_control_oidc.py --image $controlImage
   kubectl --kubeconfig $kubeconfig -n lab-control rollout status deployment/lab-control --timeout=180s
   kubectl --kubeconfig $kubeconfig -n lab-control exec deployment/lab-control -c api -- uv run --locked python lab/control-runtime/smoke.py
   ```

If rollout fails, inspect Pod events and logs. Keep the previous digest for rollback; do not invoke `activate` on an existing Deployment.

## First activation

This is an operator procedure for a bootstrapped cluster **without** an active control Deployment. The state directory must already contain scoped Gitea/Nexus credentials, kubeconfig and retained control state. Choose a successful search-spike baseline run as described above, then publish the image and run `stage`.

```powershell
$baselineRun = Read-Host 'Successful search-spike Actions run ID'
uv run --locked python lab/control-runtime/publish.py
$controlImage = (Get-Content (Join-Path $labState control-image.json) -Raw | ConvertFrom-Json).image
uv run --locked python lab/control-runtime/install.py stage --image $controlImage --baseline-run $baselineRun
uv run --locked python lab/control-runtime/install.py activate --image $controlImage --baseline-run $baselineRun
```

`activate` drains legacy host writers, copies consistent retained state to the PVC, rewrites known Git remotes, starts the Pod and runs the smoke check. It refuses an existing control Deployment. A failed initial activation attempts to restore host writers; inspect the failure before retrying. After activation, the PVC is authoritative and the old host SQLite file is stale.

After the initial credentials exist, reconcile [Key Vault secrets](keyvault-secrets.md). Temporary indexing Jobs use `lab-indexing`; the control ServiceAccount cannot create Secrets or Jobs in `platform`.

## Back up and restore control state

Choose a new archive path before replacing the cluster or control PVC:

```powershell
$controlImage = (Get-Content (Join-Path $labState control-image.json) -Raw | ConvertFrom-Json).image
$backupPath = Join-Path $labState ('control-backup-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.tar.gz')
uv run --locked python lab/control-runtime/install.py export --image $controlImage --bundle $backupPath
```

Export rejects an existing path, drains work, stops the sole writer, checkpoints
and checks both databases, copies the selected PVC state including
`delivery-operations.sqlite3`, and resumes the Deployment. It prints the archive
path and SHA-256 and writes a `.sha256` sidecar.

| Included | Retain separately |
| --- | --- |
| Lifecycle SQLite, durable delivery queue/logs, Git checkouts, frozen local inputs, reports and workload records | Kubeconfig, bootstrap credentials and CA keys |
| Control PVC contents selected by the exporter | Gitea, Nexus, Floci, Elasticsearch and snapshot-store data |

To restore, stop the old writer and use a fresh checkout with a new empty `LAB_STATE_DIR`. Supply the separately retained scoped credentials and kubeconfig, then import the archive:

```powershell
$backupPath = Read-Host 'Absolute path to the retained control archive'
uv run --locked python lab/control-runtime/install.py import --bundle $backupPath
```

Import validates the archive and refuses to overwrite existing state. Then follow first activation against a cluster without an active control Deployment. A local-path PVC is not a cross-host backup. The [whole-lab transfer runbook](lab-transfer.md) lists the other databases, volumes and credentials required for a Mac migration. See the [dated runtime checks](research/evidence/kubernetes-control-services.md) and [state-transfer checks](research/evidence/runtime-consolidation-delivery.md) for tested scope.
