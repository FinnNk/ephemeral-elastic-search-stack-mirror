# Local Kubernetes control runtime

The lab UI/API, lease reconciler, PR watcher and delivery watcher run as four containers in one `lab-control` Pod. Its image contains the owned `lab/` and `data/` runtime code; research spike scripts are not needed by the Pod. A 2 GiB PVC holds SQLite, frozen releases, Git checkouts and local reports. Gitea, Argo CD, Floci and Elasticsearch use cluster service addresses; Nexus remains on its retained Docker volume and is reached through the `platform` Service. The browser uses a supervised localhost port forward at `http://localhost:18082/`.

The control Pod has one replica and a `Recreate` update strategy. Do not run the host control starters while it is active. The ignored `.lab/control-drain` flag keeps host processes from restarting during the cutover. A failed initial activation restores host processes. Ordinary cluster loss also removes the control UI until the cluster returns.

## Install and check

Run from the repository root with the lab cluster and retained services already bootstrapped. The `.lab` directory must contain the dedicated kubeconfig, scoped Gitea and Nexus credentials, and the retained control state. The publisher reads its password from the ignored Nexus credential file; it never prints it.

```powershell
python lab/control-runtime/publish.py
$controlImage = (Get-Content .lab/control-image.json -Raw | ConvertFrom-Json).image
python lab/control-runtime/install.py stage --image $controlImage --baseline-run 6
python lab/control-runtime/install.py activate --image $controlImage --baseline-run 6
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-control exec deployment/lab-control -c api -- python lab/control-runtime/smoke.py
```

Select a successful Gitea baseline run ID for this installation. `stage` applies the namespace, PVC, scoped credentials and bindings while the host remains active. `activate` drains the host, copies a consistent SQLite backup and selected state into the PVC, rewrites Git remotes to internal Gitea, then starts the Pod. It checks Gitea identity, Elasticsearch, Nexus and restored record counts before enabling the browser route. The control image is selected by a Nexus digest. `lab-indexing` holds temporary indexing Jobs and their credentials; the control ServiceAccount cannot write Secrets or Jobs in `platform`.

The publisher produces one Nexus manifest containing `linux/amd64` and `linux/arm64`. Arm64 construction and its native relevance imports were checked under emulation; a native Apple silicon run remains to be done. Repeating `stage` is safe for an existing installation and reconciles installer-owned control ingress on historical delivery targets.

After initial service bootstrap, run `python lab/keyvault.py migrate` as described in the [secret operating guide](keyvault-secrets.md). ESO then owns the retained control Gitea/Nexus Secrets and image-pull Secret. Repeating `stage` leaves these ESO-owned values intact.

The local browser forward reconnects after Pod replacement. To inspect the runtime:

```powershell
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-control get deploy,pod,pvc,svc
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-control logs deployment/lab-control -c api --tail=30
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-control logs deployment/lab-control -c leases --tail=30
```

For an existing installation, publish the new digest, restage its configuration, render the Deployment's image placeholder and apply it:

```powershell
python lab/control-runtime/publish.py
$labState = if ($env:LAB_STATE_DIR) { $env:LAB_STATE_DIR } else { (Resolve-Path .lab).Path }
$controlImage = (Get-Content (Join-Path $labState control-image.json) -Raw | ConvertFrom-Json).image
python lab/control-runtime/install.py stage --image $controlImage --baseline-run 6
(Get-Content lab/control-runtime/deployment.yaml -Raw).Replace('__CONTROL_IMAGE__', $controlImage) |
    kubectl --kubeconfig (Join-Path $labState kubeconfig.yaml) apply -f -
kubectl --kubeconfig (Join-Path $labState kubeconfig.yaml) -n lab-control rollout status deployment/lab-control --timeout=180s
kubectl --kubeconfig (Join-Path $labState kubeconfig.yaml) -n lab-control exec deployment/lab-control -c api -- python lab/control-runtime/smoke.py
```

Set `LAB_STATE_DIR` to the retained `.lab` directory when running these commands from an isolated worktree. `Recreate` removes the previous Pod before admitting the next one. Wait for active comparisons before updating; a replacement interrupts their in-memory execution. The browser forward reconnects after replacement. Background workers wait for API health using the canonical Host header.

## Retain and restore state

Export state to an operator-chosen location before replacing the cluster or its control PVC:

```powershell
$controlImage = (Get-Content .lab/control-image.json -Raw | ConvertFrom-Json).image
python lab/control-runtime/install.py export --image $controlImage --bundle .lab/control-backup.tar.gz
```

Export rejects an existing output file. It drains requests, waits for active lifecycle/comparison/delivery work to finish, scales the only writer to zero, copies a tar archive from the PVC and resumes the same Deployment. A `.sha256` sidecar records the archive hash. It does not include Gitea/Nexus credentials or the kubeconfig: retain those separately. The exported bundle includes SQLite, Git checkouts, frozen release files, comparison reports and workload records. Nexus, Gitea, Floci, Elasticsearch and the snapshot store each need their own retained data; this archive does not back them up.

In a **fresh checkout** with a new state directory, supply the archive and the separately retained kubeconfig and scoped credentials. Import refuses to overwrite existing state:

```powershell
python lab/control-runtime/install.py import --bundle D:\backups\control-backup.tar.gz
```

Then publish the control image and use `stage` / `activate` as above against a cluster without an active control Deployment. `activate --bundle <path>` can import and activate in one command. Import validates archive member paths and types. Keep the old writer stopped before activation. For an explicit return to host controls, first export the Kubernetes state, stop the Deployment, restore the bundle into a separate host state directory with its bootstrap credentials/tools, and start the three host launchers only after verifying there is no control Pod. The state volume is the source of truth after cutover; the old host SQLite file is stale.

This batch verified export, import in a clean checkout and repeated staging against the current cluster. Fresh-checkout activation in disposable control resources and a native installation on another machine remain. The PVC is a k3d local-path volume and is not a cross-host backup.
