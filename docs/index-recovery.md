# Restore a frozen index

Create a new environment using the retained index recipe to recover an earlier schema. The recipe fixes the mapping, settings, catalogue, Elasticsearch version and indexer. Changing today's mapping file does not change that recipe.

## Recreate through the control UI

1. Obtain the historical recipe SHA-256, release and index kind from the retained environment definition or record. The original catalogue bytes and pinned images must still be available.
2. In **Create an environment**, supply those values and a successful compatible API build. Use a new environment name if the old one is active.
3. Wait for readiness. Inspect **Index path**, elapsed index time and any recovery errors on the card.
4. Compare the restored API against the candidate using the same selected query suite. For relevance, use one compatible judgement set across both sides.

| Path | Requirement |
| --- | --- |
| Reuse | Existing compatible frozen index |
| Clone | Live write-blocked source with matching recipe marker, mapping, settings, count and product IDs |
| Snapshot | Configured repository and verified snapshot matching the recipe |
| Rebuild | Retained catalogue, recipe and compatible pinned indexer |

A missing or invalid fast path falls back to a recipe rebuild; inspect the retained fallback error. A recipe for a different Elasticsearch version needs a compatible engine cluster. The shared baseline is not overwritten to accommodate a schema change.

## Configure local snapshot storage

Operator prerequisites: Docker, the bootstrapped k3d lab, retained bootstrap credentials, Python and the lab dependency directory. Run from the repository root in PowerShell; select the existing state directory when using another worktree. Wait for active work before changing Elasticsearch secure settings, because ECK may roll its Pod.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
uv run --locked python lab/setup_snapshot_store.py
```

The command creates or reuses SeaweedFS and its named Docker volume, configures the ECK S3 client, waits for Elasticsearch readiness and registers `lab-s3`. It prints JSON with the repository name, verified-node count, 100 analysis blobs and no detected issues. Repository verification failure must be resolved before relying on snapshot restores.

Check the control configuration:

```powershell
kubectl --kubeconfig $kubeconfig -n lab-control get configmap lab-control-config -o 'jsonpath={.data.LAB_SNAPSHOT_REPOSITORY}'
```

The current installer sets `lab-s3`. If absent, follow the [existing-runtime update](control-runtime.md#update-an-existing-runtime) to reconcile configuration and roll the Pod. Setting an environment variable in a host terminal alone does not update Kubernetes workers. After initial credential setup, [reconcile Key Vault](keyvault-secrets.md#set-up-or-reconcile).

## Retain and recover storage

| Retain | Why |
| --- | --- |
| SeaweedFS volume `relevance-snapshot-store` | Holds snapshot objects outside the Elasticsearch PVC |
| Bootstrap `snapshot-s3.json` and retained vault/Secret state | Allows the S3 client to authenticate after recreation |
| Catalogue objects and index recipes | Allows validation and rebuild fallback |
| API/indexer image manifests and layers | Recreates the pinned software |

Snapshots survive Elasticsearch Pod/PVC recreation when that storage remains, but do not protect against host or Docker-volume loss. Do not remove the snapshot volume during environment expiry. After replacing the k3d network, inspect the container's network membership:

```powershell
docker inspect --format '{{json .NetworkSettings.Networks}}' relevance-snapshot-store
```

If `k3d-relevance-lab` is absent, reconnect it before rerunning setup:

```powershell
docker network connect k3d-relevance-lab relevance-snapshot-store
```

Setup checks an existing container's image and starts it if stopped; it does not repair network membership.

If repository checks fail, inspect SeaweedFS connectivity and the ECK S3 credential before retrying. Search API credentials remain index-scoped; snapshot administration belongs to the controller. Restore timing evidence and snapshot qualification are in [repository evidence](research/evidence/durable-snapshot-repository.md) and [restoration research](research/index-restoration-options.md). The [recovery diagrams](diagrams/index.html#schema-and-index-recovery) show schema, clone and snapshot paths.
