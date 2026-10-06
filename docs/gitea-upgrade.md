# Upgrade and recover Gitea

Gitea runs in the `platform` namespace with SQLite and one persistent volume.
The lab pins the rootless **28.0.0** image by its multi-platform digest. Helm
chart **12.7.0** and Actions runner **3.5.0** remain unchanged.

## Before an upgrade

Use the lab administrator checkout and its `.lab/kubeconfig.yaml`.
This is an administration task; developers use Gitea and the delivery workflows.

1. Check that Actions and delivery operations have finished.
2. Save `helm get values gitea -n platform -o json` and the Gitea Deployment
   in ignored lab state. Include the lab kubeconfig when running Helm.
3. Scale `platform/deployment/gitea` to zero and wait for its Pod to terminate.
4. Mount `gitea-shared-storage` read-only in a temporary backup Pod on the
   volume's node. Archive all of `/data`, including SQLite, repositories,
   Actions files and configuration. Stream the archive to the host as binary
   data; a PowerShell text pipeline can corrupt it.
5. Read every archive member and run SQLite `PRAGMA integrity_check` on a
   copy of the archived database. Save its checksum and size.
6. Apply the new image using the saved Helm values. Preserve the OIDC, CA,
   GitHub App helper, volumes and runner settings. Wait for readiness, then
   check the API version, sign-in, Git, Actions and push mirrors.
7. Remove the temporary Pods after verification. Keep the backup outside
   the cluster volume.

The current image and baseline settings are in
[`gitea-values.yaml`](../research/platform-spike/gitea-values.yaml).
Do not replace an established release's values with that baseline: installed
OIDC and mirroring settings also need to be retained.
Follow the [upstream upgrade guide](https://docs.gitea.com/installation/upgrade-from-gitea/)
and [backup guide](https://docs.gitea.com/administration/backup-and-restore/).

## Network access and retention

| Setting | Lab behaviour |
| --- | --- |
| `security.EGRESS_MODE = lax` | Public hosts remain reachable; private hosts require an allowlist entry. |
| `security.ALLOWED_HOST_LIST` | Allows the in-cluster webhook receiver. |
| `actions.RUN_RETENTION_DAYS = 0` | Retains completed Actions runs until explicitly removed. |

Gitea 28 applies outbound network controls to more Git operations. Check both
local webhook delivery and GitHub push mirrors after changing these settings.
The explicit lax setting preserves the lab's existing public access; it does
not make the allowlist an exclusive list of all destinations.

## Recover the pre-upgrade server

The 28.0.0 upgrade backup is under `.lab/gitea-upgrade-28/`:

| File | Contents |
| --- | --- |
| `gitea-data-before.tar.gz` | Complete stopped-server `/data` archive. |
| `backup-receipt.json` | SHA-256, size, SQLite integrity and database counts. |
| `before-values.json` | Previous Helm values, including installed integrations. |
| `before-deployment.json` | Previous image, replicas and volume references. |

These files contain secrets and are excluded from Git. GitHub repository
mirrors do not back up the Gitea database, PR history or Actions files.

Database migrations can prevent an image-only downgrade. If recovery is needed:

1. Stop Gitea and archive the failed upgraded volume separately.
2. Verify the pre-upgrade archive against its receipt.
3. Restore the complete archive to the Gitea PVC, replacing the upgraded data
   and preserving ownership. Keep Gitea stopped during replacement.
4. Apply `before-values.json` with the original chart and restore the original
   replica count. Start Gitea and repeat the verification checks.

The backup was validated before migration; a full disaster-recovery restore
has not been rehearsed. See the [upgrade evidence](research/evidence/gitea-28-upgrade.json).
