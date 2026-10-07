# Transfer the existing lab to another host

For a new installation with fresh credentials and certificates, use
[fresh installation](fresh-install.md). This runbook preserves existing service
identity; omitting its credentials and keys is not a supported restore method.

Transfer the Git checkout, persistent service data and protected configuration
as one consistent set. Keep the Windows lab available for recovery until the
Mac has passed acceptance. Start with [Mac prerequisites](mac-setup.md).

This is an operator runbook. The repository does not yet provide a tested,
one-command whole-lab migration. The control export/import is tested separately;
the first complete Windows-to-Mac restore must be rehearsed on the target.

## Inventory before choosing the cutover

From the source repository root, using its Python environment and retained state:

```powershell
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
python lab/mac_preflight.py --target arm64 --cluster --images --output "$env:LAB_STATE_DIR/mac-transfer-inventory.json"
```

Use `--server https://127.0.0.1:<port>` if the retained kubeconfig's endpoint does
not resolve. Obtain the current published port from `docker port
k3d-relevance-lab-server-0 6443/tcp`; do not reuse an old example port.

The command reads metadata and manifests, never Secrets or container environment
variables. It does not stop services. `unknown` architecture support requires
investigation; a successful command does not make every image portable. An
intentionally broken test image must remain recognisably a test fixture.

The 6 October inventory found 109 workload image references; 97 advertised
arm64 support. The unknown references included historical search-spike images,
older judge images and optional inference fixtures. The current lab-control,
search-api, abstaining relevance-judge, Gitea, Keycloak, Headlamp, Elasticsearch
and SigNoz images advertise arm64. Separate inspection confirmed K3s, Nexus
and the snapshot store. Image metadata is not a native execution test.

## What must be retained

| State | Transfer requirement |
| --- | --- |
| Lab Git checkout and the three delivery repositories | Accepted code plus the actual Gitea service data; Git mirrors do not contain reviews, Actions history or repository settings |
| Control PVC | Authoritative lifecycle database, operation queue/logs, local evidence, frozen inputs and checkouts; the host's old SQLite files are stale after activation |
| Gitea PVC | Database, repositories, attachments, Actions records, configuration and keys |
| Floci PVC | Frozen catalogue/query/judgement blobs, reports, MLflow artefacts where stored there, and Key Vault secret values |
| Elasticsearch PVC and snapshot-store Docker volume | Search data and snapshot repository contents; retain index recipes and catalogue manifests together |
| MLflow database PVC and artefact storage | Registry/run metadata plus every referenced model artefact; a database dump alone is insufficient |
| Keycloak PVC | Realm, users, client configuration and signing identities |
| Nexus and Nexus PostgreSQL Docker volumes | Image blobs, repository configuration and metadata as a matched pair |
| Judgement cache PVCs | Cached decisions and abstentions with their model/input provenance |
| SigNoz PVCs | SQLite, ClickHouse and ZooKeeper state if retaining observability history |
| Runner PVCs | Registration and retained Actions data; disposable Docker caches may be rebuilt after confirming their role |
| Ignored host state | CA/key material, scoped bootstrap credentials, retained image references, OIDC client settings and installed plugin archives |
| K3s server database and token | Cluster objects and encrypted bootstrap data when preserving the existing cluster identity |

Protect the transfer as a secret-bearing backup. Copy it through a trusted
channel into private storage. Do not put `.lab`, database dumps or CA private
keys into the Git mirror. Exclude unrelated Docker applications from this transfer.

## Prepare a consistent backup

1. Finish or explicitly stop active comparisons, promotions and model jobs at
   a saved boundary. Check the delivery queue and Actions pages, not just Pod
   readiness. Record the active production build, staging build, retained image
   references and open promotion PRs. Do not run duplicate watchers on the Mac.
2. Export the control state using the accepted installer:

   ```powershell
   $controlImage = (Get-Content "$env:LAB_STATE_DIR/control-image.json" -Raw | ConvertFrom-Json).image
   $bundle = Join-Path $env:LAB_STATE_DIR 'control-transfer.tar.gz'
   python lab/control-runtime/install.py export --image $controlImage --bundle $bundle
   ```

   Choose a new filename if it exists. Export drains and briefly stops the
   control writer, then resumes it. The archive includes both SQLite databases;
   the host exporter uses SQLite's backup API so committed WAL rows are retained.
   Verify the printed SHA-256 against the `.sha256` sidecar. This archive does
   not back up the other services in the table.
3. Take logical database backups for Nexus PostgreSQL and MLflow PostgreSQL,
   and preserve the Gitea/Keycloak/SigNoz databases using their service-specific
   backup procedures. Keep application versions and credentials with the
   protected transfer inventory. Use logical PostgreSQL restores if physical
   database files fail native architecture compatibility checks.
4. At the agreed cutover, stop **only** this lab's writers and containers.
   Capture the K3s SQLite database and its original server token together, then
   each node's local-path storage and the named external Docker volumes. A live
   tar of writable database files is not a consistent backup.

   [K3s requires the SQLite database and server token](https://docs.k3s.io/datastore/backup-restore).
   That backup does not include persistent volumes. The inventory maps each
   node's Docker volume mounted at `/var/lib/rancher/k3s`; local-path data lives
   beneath its `storage` directory. Preserve node names and the mapping between
   each PVC and its original node. Do not restore amd64 `containerd` files or
   cached binaries onto arm64 nodes.
5. Retain `/etc/rancher/k3s` configuration, the original node identity files
   under `/etc/rancher/node`, the server's OIDC CA, and the lab OIDC startup hook.
   These files are outside the database backup. The startup hook restores issuer
   name resolution after node restarts; omitting it can break Headlamp sign-in.
6. Archive the three external data volumes listed in the inventory:
   `relevance-nexus`, `relevance-nexus-db` and `relevance-snapshot-store`.
   Verify each volume exists before archiving. Use Docker's
   [volume backup procedure](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes)
   with a read-only source mount and a new archive destination, while its writer
   is stopped. Preserve numeric ownership and permissions.
7. Record checksums for every archive and copy them with the protected host
   configuration. Keep the originals on Windows. A Windows Docker/WSL virtual
   disk is not a portable Mac lab archive; transfer the service data, not the VM.

The initial read-only inventory has been performed. No service has been stopped
or cold backup taken by the documentation batch.

## Restore into a stopped target

1. Verify archive checksums before extraction. Prepare native host tools and
   an empty k3d topology at the original K3s version. Retain the server/main-agent
   names. Add the CPU observability and testbed nodes with their original names
   and scheduling labels if restoring their local-path PVCs. Omit the GPU node.
2. Stop the target before replacing its generated database or persistent data.
   Restore the K3s server database/token according to the K3s guide, the mapped
   per-node local-path storage, node identities and server configuration. Do
   not copy Windows bind-mount paths or the old Docker network addresses.
3. Restore Nexus, its database and the snapshot-store volumes before application
   Pods need them. Recreate their Docker network attachment and Service endpoints
   for the new host; the old IP addresses are not portable. Once the restored Nexus containers
   and cluster are running, `python lab/setup_nexus.py --repair-network` refreshes
   its route from the current Docker address without resetting accounts or
   storage. Preserve the public
   registry name so existing immutable image references remain meaningful.
4. Restore remaining databases and artefact stores before their writers start.
   Keep one authoritative control database. If preserving the original control
   PVC, do not import a second copy. When rebuilding that PVC instead, use the
   [control import/first activation procedure](control-runtime.md#back-up-and-restore-control-state)
   with the exported archive, scoped credentials and the target kubeconfig.
5. Regenerate the target kubeconfig with `k3d kubeconfig get relevance-lab`.
   Reconcile ingress port mappings, native DNS and CA trust. Verify OIDC API
   server configuration and the startup hook before testing Headlamp login.
6. Prevent GPU-only and incompatible optional workloads from starting. Use the
   retained CPU abstaining judge. Preserve their saved data rather than deleting
   model history. Inspect pinned images before changing them; rebuilding an
   image creates a new release identity and requires a reviewed state change.
7. Start storage/identity services first, then the control workers and Actions
   runners. Inspect ESO secret readiness, registry access, Argo CD synchronisation
   and local-path volume placement before retrying failed delivery operations.

This sequence describes the restore dependencies, not a tested automated
restorer. Validate database integrity and node/PVC placement on the Mac. If a
dependency cannot be restored, leave the Windows source intact and report the
specific blocker instead of reinitialising missing state.

## Accept the Mac lab

Run these checks in macOS Terminal from the accepted repository checkout:

```sh
export LAB_STATE_DIR="$PWD/.lab"
python lab/mac_preflight.py --target arm64 --cluster --images --output "$PWD/mac-lab-check.json"
kubectl --kubeconfig "$LAB_STATE_DIR/kubeconfig.yaml" get nodes
kubectl --kubeconfig "$LAB_STATE_DIR/kubeconfig.yaml" -n lab-control \
  exec deployment/lab-control -c api -- python lab/control-runtime/smoke.py
python lab/https_ingress.py verify
```

On Intel, use `--target amd64`. Resolve any core image reported unsupported or
unknown. Optional deliberately failing fixtures do not prove core restore failure.

| Check | Expected result |
| --- | --- |
| Storage and databases | Required PVCs Bound on intended nodes; database integrity checks pass; transferred blob/image/model objects readable |
| Control smoke | Cluster identity matched; Gitea, Elasticsearch and Nexus reachable; retained record counts agree with the source |
| Sign-in | Named user can enter Control, Gitea and Headlamp; read-only roles remain read-only |
| Release tree | Same active production, staging and candidate identities; queue/logs and reviewed PR links retained |
| Search | Same frozen catalogue and representative product IDs/order for unchanged inputs |
| Judge | CPU runtime ready; provenance/cache retained; no attempt to schedule NVIDIA workloads |
| Actions | Runner online; one small authorised CI check completes without duplicate operations |
| Comparison/notebook | One small authorised comparison renders report and notebook links using the same frozen labels |
| Telemetry | Fresh traffic appears in the existing dashboard windows |
| Restart | Cluster restart preserves readiness, DNS and OIDC login |

Record the native results, Mac model/RAM, Docker allocation and exact image
digests before removing source backups. Full performance/load acceptance is a
separate step; the laptop need not reproduce Windows timings.
