# Operate retained lab secrets

External Secrets Operator (ESO) reads retained service credentials from Floci Key Vault and writes the Kubernetes Secrets used by the lab. Services keep the same Secret names and keys. Each selected namespace has a `SecretStore` and `ExternalSecret`; ESO runs in `lab-secrets`.

## Check secret synchronisation

Use PowerShell from the repository root with the installed lab and `kubectl`. Select the retained state directory; in another worktree, use its existing absolute path instead of that worktree's `.lab`.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
kubectl --kubeconfig $kubeconfig get externalsecrets -A
```

Expect `Ready=True` for each retained secret. If one is not ready, inspect it before restarting its consumer:

```powershell
$secretNamespace = Read-Host 'Namespace from the failing row'
$externalSecret = Read-Host 'ExternalSecret name from the failing row'
kubectl --kubeconfig $kubeconfig -n $secretNamespace describe externalsecret $externalSecret
```

Descriptions explain reconciliation errors without requiring you to print Secret values. `deletionPolicy: Retain` keeps the last Kubernetes value when the vault source disappears; ESO still reports an error.

## Set up or reconcile

Prerequisites: Gitea, Nexus, control runtime, delivery and snapshot storage have created their initial credentials; Floci is running; the selected state directory contains kubeconfig and bootstrap records.

```powershell
python lab/keyvault.py migrate
kubectl --kubeconfig $kubeconfig get externalsecrets -A
```

Migration installs pinned ESO, seeds only absent Floci names from selected existing Kubernetes Secrets, creates namespaced stores and waits for Ready. It checks the resulting values without printing them. A source mismatch fails instead of silently overwriting the vault. Repeating migration with unchanged credentials is safe.

| Vault-backed credential | Consumer |
| --- | --- |
| Gitea agent/build/read and Nexus reader | Control services |
| Repository, webhook and plugin credentials | Argo CD and deployment services |
| Snapshot S3 client | Elasticsearch |
| Retained image-pull credentials | Selected lab namespaces |

A new ephemeral environment receives a lifecycle-owned copy of the retained image-pull credential and its own Elasticsearch password. Its deletion removes those copies; the lifecycle does not create a vault record for every environment.

## Rotate or recover

1. Coordinate the backing service's credential and its Floci value. ESO polls every minute.
2. Wait for the relevant `ExternalSecret` to be Ready and verify authentication through the consumer.
3. Restart consumers that mount credential files with `subPath`. For control, after the new value is ready:

   ```powershell
   kubectl --kubeconfig $kubeconfig -n lab-control rollout restart deployment/lab-control
   kubectl --kubeconfig $kubeconfig -n lab-control rollout status deployment/lab-control --timeout=180s
   ```

   A Secret update alone does not replace those mounted files. Wait for active comparisons before replacing the control Pod.
4. Retain Floci's WAL volume. If lost, restore vault data or migrate from still-present Kubernetes Secrets before restarting consumers. Recover or purge a soft-deleted name before seeding it again.

## Bootstrap and Azure boundaries

Initial service and human accounts, runner registration, generated ECK/Argo CD material, finite Job credentials and the external GitHub App key remain outside Floci. `.lab/credentials.json` and `.lab/nexus.json` support bootstrap and host tools. Gitea Actions owns its repository secrets; ESO does not populate them.

Floci emulates the secret API but does not validate Azure identity or RBAC. Its ESO webhook provider uses a placeholder bearer header over cluster HTTP. Do not put genuine external credentials into this emulator.

For Azure, replace the store provider with `azurekv` and Workload Identity while keeping the `ExternalSecret` targets. Validate authentication, vault policy, networking and rotation against a real tenant. See the [local adapter proof](../research/keyvault-eso-spike/README.md), [deployment diagrams](diagrams/index.html#system-architecture) and [Azure validation plan](plans/azure-keyvault-validation.md). The original migration counts are historical observations, not a readiness check for your installation.
