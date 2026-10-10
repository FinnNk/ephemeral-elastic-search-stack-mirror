# Use Nexus artefact storage

Nexus stores container images, deployment bundles, build receipts and signed merge-gate evidence. The older Gitea registry retains its historical images. Frozen datasets and comparison reports use Azure Blob Storage; Elasticsearch snapshots use the separate snapshot store.

## Open an existing installation

Open [Nexus](https://nexus.localhost:34443/) after [trusting the lab certificate](workstation-access.md). Use your personal account, not the CI publisher.

| Account | Access | Credential source |
| --- | --- | --- |
| `finnnk` | Personal administrator | `personal.password` in retained `nexus.json` |
| `elastic-agent` | Setup/maintenance administrator | Retained bootstrap record |
| `lab-publisher` | Read/publish images and releases; no delete/admin | Scoped CI credential |
| `lab-reader` | Read repositories and pull images | ESO-backed deployment credential |

These are distinct from Gitea logins. Anonymous access is disabled. Do not commit credentials or generated environment files. The recovery administrator is not used by CI.

## Install or reconnect

Operator prerequisites: the [platform bootstrap](../research/platform-spike/README.md), Docker and Python. Use PowerShell from the repository root; select the existing state directory when working elsewhere.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
uv run --locked python lab/setup_nexus.py
```

Setup creates or reuses the pinned containers, configures repositories/accounts and refreshes cluster endpoint addresses. It refuses to silently change an existing container's image. Check the command's result, open the UI and confirm `lab-images` and `lab-releases` exist. Repeat setup after cluster/container recreation to reconnect endpoints; do not delete retained volumes to resolve an address problem.

## Repair access after a Docker restart

Docker may assign Nexus a different address after restarting. If a build reports
`connection refused` at `nexus.localhost:18185`, refresh its cluster route.
Run from the lab repository root with Docker running and the operator kubeconfig
in the retained state directory:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
uv run --locked python lab/setup_nexus.py --repair-network
```

This updates routing only. It preserves accounts, repository contents and volumes.
Rerun the failed release workflow in Gitea Actions after the command succeeds.

## Storage and transport

| Item | Location |
| --- | --- |
| Container images | Hosted `lab-images`; `nexus.localhost:18185`, deployed by digest |
| Bundles, receipts and gate evidence | Raw hosted `lab-releases`, with content hashes and write-once policy |
| Browser | HTTPS ingress at `nexus.localhost:34443` |
| Host API/diagnostic access | HTTP loopback `127.0.0.1:18183` |
| Cluster API access | HTTP Kubernetes Service on the private lab network |
| Nexus data | Docker volume `relevance-nexus` |
| Database | Docker volume `relevance-nexus-db`; no published database port |

Volumes survive container replacement, not host/disk loss. Back up the database and blob store consistently before upgrades. GitHub Git backup does not include these artefacts. No automatic cleanup runs: keep manifests, layers and bundles required by comparisons and rollback.

The lab caps Nexus at 4 GiB and PostgreSQL at 512 MiB. This is a local trial allocation, not production sizing. Multi-platform images are pinned; native Apple silicon remains unverified. See the [original installation evidence](research/evidence/nexus-artifacts.md) for measured scope.

## Edition and migration

Community Edition provides the hosted Docker/raw repositories used here. Check the current [edition limits](https://help.sonatype.com/en/nexus-repository-editions.html) before increasing retention or load. Setup accepts its documented EULA; promotion uses reviewed Git state and Argo CD rather than paid Nexus staging features.

Nexus can remain after migration to GitHub Enterprise. Azure needs verified registry transport, secret management, backups and resource sizing. An optional ACR copy must verify the resulting digest and deployment reference. See [delivery](delivery.md) for publishing and promotion and [OCI transport](plans/https-oci-transport.md) for the remaining local HTTP path.
