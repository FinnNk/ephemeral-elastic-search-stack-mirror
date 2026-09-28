# Next batch: validate Azure Key Vault delivery

## Intent

Verify that the lab's `ExternalSecret` targets work with a real Azure Key Vault through ESO's Azure provider and Workload Identity. Keep the Kubernetes Secret names and keys used by the local lab.

## Constraints

- Use a disposable Azure vault and synthetic credentials. Do not copy local Gitea, Nexus or GitHub credentials to Azure.
- Give ESO a named Kubernetes ServiceAccount and narrowly scoped vault access. Keep application Pods free of direct vault permissions.
- Do not infer Azure RBAC, TLS or network behaviour from Floci's fake bearer check.
- Preserve the local Floci webhook store as the offline lab path.

## Acceptance criteria

1. A namespaced Azure `SecretStore` uses a referenced Workload Identity ServiceAccount and becomes Ready.
2. An unchanged `ExternalSecret` target creates the expected Kubernetes Secret from a synthetic Azure Key Vault value.
3. A new Key Vault version reaches the Secret; the chosen consumer restart procedure receives it.
4. Removing access causes a visible sync error while the last value follows the documented retention policy.
5. The test records the assigned identity, vault role, network path and timing without retaining secret values in evidence.

## Starting points

- [Current local contract and migration](../keyvault-secrets.md)
- [Local Floci/ESO proof](../../research/keyvault-eso-spike/README.md)
- [ESO Azure Key Vault provider](https://external-secrets.io/main/provider/azure-key-vault/)
- [ESO ExternalSecret lifecycle](https://external-secrets.io/main/guides/ownership-deletion-policy/)
