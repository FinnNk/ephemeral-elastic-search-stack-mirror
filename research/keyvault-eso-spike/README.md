# Floci Key Vault to Kubernetes Secret proof

**Historical isolated proof — 28 September 2026.** ESO and the adapter were subsequently adopted for lab credentials. Use the [Key Vault guide](../../docs/keyvault-secrets.md) for current reconciliation and rotation; this proof does not migrate application secrets.

This isolated check tests whether External Secrets Operator (ESO) can adapt the lab's Floci Key Vault endpoint to the Kubernetes Secret contract already used by workloads. It does not migrate any application credential or select ESO for the wider lab.

## Setup

Tested on 28 September 2026 with Floci AZ 0.13.0 and ESO Helm chart 2.11.0 on the local k3d cluster. The proof used only `synthetic-proof-v1` and `synthetic-proof-v2`. The Helm release ran in `external-secrets-spike`; all test resources ran in `keyvault-eso-spike`.

From the repository root, with the lab kubeconfig selected:

```powershell
$env:KUBECONFIG = (Resolve-Path .lab/kubeconfig.yaml).Path
& .lab/tools/helm.exe upgrade --install external-secrets-spike external-secrets `
  --repo https://charts.external-secrets.io --version 2.11.0 `
  --namespace external-secrets-spike --create-namespace --wait --timeout 5m
kubectl -n platform port-forward svc/floci 14578:4577
```

In a second terminal, create the disposable source and apply [secret-sync.yaml](secret-sync.yaml):

```powershell
$uri = 'http://127.0.0.1:14578/devstoreaccount1-keyvault/secrets/eso-spike-proof?api-version=7.4'
$headers = @{ Authorization = 'Bearer synthetic-local-test' }
$body = @{ value = 'synthetic-proof-v1' } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body | Out-Null
kubectl apply -f research/keyvault-eso-spike/secret-sync.yaml
kubectl wait --for=condition=Ready externalsecret/proof -n keyvault-eso-spike --timeout=90s
```

The `SecretStore` URL has a literal in-cluster host and templates only the secret name. Its bearer header is a synthetic placeholder: Floci checks for a header but does not prove Azure identity or authorisation. The JSONPath selects the Key Vault response's `value` field.

## Observed results

| Check | Result |
|---|---|
| Initial sync | `SecretStore` Ready; `ExternalSecret` Ready; Kubernetes Secret `proof` contained the exact v1 value. |
| New source version | A second Key Vault `PUT` with `synthetic-proof-v2` produced a new version and ESO updated the same Kubernetes Secret. |
| Missing source | [missing-source.yaml](missing-source.yaml) reported `SecretSyncedError` and created no Kubernetes Secret. |
| Deleted source | Soft-deleting `eso-spike-proof` made the `ExternalSecret` unready. `deletionPolicy: Retain` kept the last synced v2 value. |
| Recovery | Recovering the Floci secret returned the `ExternalSecret` to Ready. |

These checks prove the local Floci → ESO webhook → Kubernetes Secret path, including rotation and failure handling. They do not exercise ESO's Azure Key Vault provider, Azure Workload Identity, Azure RBAC, network restrictions or a workload restart. The existing control runtime mounts individual Secret files with `subPath`, so a rotated Kubernetes Secret will not update those mounted files until its Pod restarts.

At the measurement point, the controller, certificate controller and webhook used 37 MiB, 52 MiB and 27 MiB respectively (116 MiB combined). These are observed Pod values, not resource limits or a sizing recommendation.

## Clean-up

The test namespace, Helm release and synthetic Floci secret can be removed independently of the live lab. Before removing ESO CRDs, check that no other `ExternalSecret` or `SecretStore` uses them.

```powershell
kubectl delete namespace keyvault-eso-spike
& .lab/tools/helm.exe uninstall external-secrets-spike --namespace external-secrets-spike
kubectl delete namespace external-secrets-spike
Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers | Out-Null
Invoke-RestMethod -Method Delete `
  -Uri 'http://127.0.0.1:14578/devstoreaccount1-keyvault/deletedsecrets/eso-spike-proof?api-version=7.4' `
  -Headers $headers | Out-Null
```

The next decision is whether to adopt ESO as the standard secret synchroniser. A wider batch would need to cover the existing JSON-file and image-pull Secret shapes, explicit restart on rotation, bootstrap ownership, and Azure Key Vault provider authentication against a real Azure tenant. Do not put the GitHub App private key or other genuine external credentials into Floci.

References: [ESO webhook provider](https://external-secrets.io/main/provider/webhook/), [ESO Azure Key Vault provider](https://external-secrets.io/main/provider/azure-key-vault/), [Floci Key Vault](https://floci.io/floci-az/services/key-vault/), [Kubernetes Secret volume updates](https://kubernetes.io/docs/concepts/configuration/secret/).
