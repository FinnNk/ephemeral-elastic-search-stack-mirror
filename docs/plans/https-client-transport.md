# Batch: HTTPS Git clients

Status: implemented locally; awaiting review. The [Git client guide](../https-git-transport.md) records the current paths and live checks. OCI and host bootstrap transport move to the [next batch](https-oci-transport.md).

## Intent

Use the lab CA and a stable in-cluster HTTPS name for the control runtime, Argo CD and both Gitea Actions runners. Keep the reference workflow's source URL configurable for a later GHES migration.

## Constraints

- Keep CA private material outside Git, and leave TLS verification enabled.
- Preserve existing runner registrations, vault-backed Argo CD credentials, frozen environments and image digests.
- Change only Git and API clients in this batch. OCI transport has a separate node and Docker-in-Docker trust path.
- Retain the HTTP NodePort for host bootstrap until a reliable workstation DNS path is installed.

## Acceptance evidence

| Criterion | Local result |
| --- | --- |
| Control API and three retained Git checkouts use HTTPS | Authenticated smoke check and three `ls-remote` calls passed from the 4/4 Ready control Pod |
| Argo CD verifies Gitea's CA and loads both repositories | Vault URLs reconciled; 28 Applications returned to Synced and Healthy |
| Both runners register through HTTPS | Saved registrations show the internal HTTPS address; both runners report online |
| CI fetches over HTTPS | Temporary delivery-source PR passed and was closed; search-spike fixture PR #6 passed and remains open for review |
| Certificate chain works with the runtime | CA and leaf key identifiers added; Python 3.13 authenticated Gitea request passed |

The search-spike default-branch workflow remains on HTTP until fixture PR #6 is accepted and merged. The [protocol inventory](../https-git-transport.md#current-protocol-inventory) names the other remaining HTTP paths.

## Starting points

- [Local HTTPS ingress](../https-ingress.md)
- [Reference CI/CD](../delivery.md)
- [Argo CD private repository certificates](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/)
- [Gitea runner installation](https://docs.gitea.com/1.26/usage/actions/act-runner/)
