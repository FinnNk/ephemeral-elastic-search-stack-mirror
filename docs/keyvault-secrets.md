# Retained lab credentials

External Secrets Operator (ESO) reads retained lab credentials from Floci Key Vault and creates the Kubernetes Secrets consumed by the running services. The Kubernetes Secret names and keys remain stable. Each selected namespace has its own `SecretStore` and `ExternalSecret`; ESO runs in `lab-secrets`.

## Set up or reconcile

Run from the repository root after Gitea, Nexus, the control runtime, delivery and snapshot storage have created their initial credentials. Select the lab kubeconfig through the script's retained state directory. When working in an isolated worktree, point `LAB_STATE_DIR` at the original `.lab` directory first.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/keyvault.py migrate
kubectl --kubeconfig .lab/kubeconfig.yaml get externalsecrets -A
```

The command installs pinned ESO 2.11.0, copies only the selected existing Kubernetes Secret values into Floci if their vault names are absent, creates namespaced stores and `ExternalSecret` resources, waits for each to become Ready, and checks the resulting values. It refuses a source mismatch instead of replacing a vault value silently. Re-running it against unchanged credentials is safe.

On 28 September 2026, this reconciled **17 Floci values into 40 Kubernetes Secrets** in the running lab. ESO adopted the existing Secret objects; all 40 `ExternalSecret` resources were Ready. Gitea health, Argo CD applications, the Elasticsearch cluster and the control runtime smoke check remained healthy. The control Pod was rebuilt and rolled to a digest-pinned image after the migration.

| Vault-backed Kubernetes Secrets | Examples |
| --- | --- |
| Control services | Gitea agent/build/read credentials, Nexus reader credentials and control image-pull Secret |
| Deployment services | Argo CD repository credentials, webhook signature secret and plugin token |
| Storage | ECK S3 snapshot client credentials |
| Image pulls | Existing Gitea and Nexus image-pull Secrets in lab namespaces |

The controller still creates an image-pull Secret directly when it creates a **new** short-lived environment. It derives that Secret from its ESO-backed Gitea or Nexus credential. The same lifecycle owns and removes that copy with the environment; it does not create a new vault record for every environment. Per-environment Elasticsearch passwords follow the same short-lived ownership model.

## Boundaries

Initial Gitea and Nexus accounts, human accounts, runner registration, ECK and Argo CD generated material, finite Job credentials and the external GitHub App key remain outside Floci Key Vault. The ignored `.lab/credentials.json` and `.lab/nexus.json` are retained for bootstrap and host-only tooling. Gitea Actions stores its own repository secrets, which ESO does not populate. Do not place genuine external credentials in this emulator.

Floci's Key Vault endpoint implements the secret API but does not validate Azure identity or RBAC. The local ESO webhook store uses a placeholder bearer header over cluster HTTP. In Azure, replace the store provider with ESO's `azurekv` provider and Workload Identity, retaining the `ExternalSecret` targets. Azure authentication, policy, network isolation and rotation must be tested against a real tenant. The [local proof](../research/keyvault-eso-spike/README.md) records initial sync, rotation, source deletion and recovery.

## Operate and recover

1. Check `kubectl --kubeconfig .lab/kubeconfig.yaml get externalsecrets -A`. Investigate any `Ready=False` before relying on a retained Secret. `deletionPolicy: Retain` keeps the last value if a Floci source disappears, but ESO reports an error.
2. Rotate a backing service credential and its Floci value as one change. ESO polls every minute. Verify the synced Kubernetes Secret before restarting consumers. The control Pod mounts individual files with `subPath`, so a Secret update alone does not change those files; roll `deployment/lab-control` after the new value is ready. Environment image-pull credentials are used on subsequent image pulls.
3. Keep Floci's persistent WAL volume with the other retained lab state. If it is lost, restore its Key Vault data or run the migration against still-present Kubernetes Secrets before restarting consumers. A soft-deleted Floci name must be recovered or purged before it can be seeded again.

The [C4 local and Azure deployment views](diagrams/index.html#system-architecture) show Floci/Azure Key Vault, ESO and the Kubernetes consumers. The [Azure validation plan](plans/azure-keyvault-validation.md) covers the identity and policy checks that the emulator cannot prove.
