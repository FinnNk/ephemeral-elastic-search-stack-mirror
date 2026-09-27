# Nexus artifact storage

Nexus stores private container images and immutable release bundles for the reference CI/CD workflow. The existing Gitea registry retains historical images. Frozen datasets and reports remain in Floci Blob; Elasticsearch snapshots remain in SeaweedFS.

## Start and sign in

From the repository root in PowerShell, after the [platform bootstrap](../research/platform-spike/README.md):

```powershell
python lab/setup_nexus.py
```

Open [Nexus](http://127.0.0.1:18183). Your administrator login is `finnnk`; its generated password is the `personal.password` entry in ignored `.lab/nexus.json`. Automation uses `elastic-agent`. These are separate from your Gitea credentials.

| Identity | Access |
| --- | --- |
| `finnnk` | Personal administrator |
| `elastic-agent` | Setup and maintenance administrator |
| `lab-publisher` | Read and publish to `lab-images` and `lab-releases`; no delete or administration |
| `lab-reader` | Read the two repositories; Kubernetes image pulls |

Anonymous access is disabled. Do not commit `.lab/nexus.json` or the generated environment files. The local bootstrap account is retained for recovery; it is not used by CI.

## Storage and connectivity

| Item | Location / behaviour |
| --- | --- |
| Images | Docker hosted `lab-images`, registry `nexus.localhost:18185`; deploy by digest |
| Release bundles | Raw hosted `lab-releases`; content hashes and write-once repository policy |
| Nexus data | Docker volume `relevance-nexus`, mounted at `/nexus-data` |
| PostgreSQL | Docker volume `relevance-nexus-db`; no published database port |
| Browser/API | Loopback `127.0.0.1:18183` |
| Runner and Pods | Private lab network, Kubernetes service and CoreDNS rewrite |

The setup is idempotent and refuses to silently change an existing container's image. Run it again after recreating the cluster or Nexus container to refresh endpoint addresses and registry configuration. Named volumes survive container restarts and replacement; they do not protect against host or disk loss. Back up Nexus's database and blob storage consistently before upgrades. GitHub Git mirroring does not back up these artifacts.

Nexus has a 4 GiB memory cap (1.5 GiB Java heap, 1 GiB direct-memory limit); PostgreSQL has 512 MiB; the Nexus connection pool is capped at 20. This is a local trial allocation. [Sonatype's production sizing](https://help.sonatype.com/en/sonatype-nexus-repository-system-requirements.html) is substantially larger. amd64/arm64 manifests are pinned; native Apple silicon execution remains untested.

## Edition and migration

- Community Edition supports the hosted Docker and raw repositories used here. Its usage limits are 40,000 components and 100,000 requests per day; monitor these before increasing retention or load. See [edition limits](https://help.sonatype.com/en/nexus-repository-editions.html) and the [feature matrix](https://help.sonatype.com/en/nexus-repository-feature-matrix.html).
- Setup accepts the [Community Edition EULA](https://links.sonatype.com/products/nxrm/ce-eula) through the documented bootstrap API. Promotion uses Git PRs and Argo CD; it does not require Nexus's paid staging features.
- No automatic cleanup is configured. Live releases, historical comparisons and rollback targets must retain their image manifests, layers and bundles.
- Local HTTP stays on loopback/private lab networks. Hosted use requires HTTPS, external secret management, backup/restore and suitable resource sizing.
- Nexus can remain the artifact service after Gitea moves to GHES. ACR remains an optional Azure image destination; copying there requires verification of the resulting digest and deployment reference.

The [delivery plan](plans/reference-ci-cd.md) defines CI and promotion. The [Nexus batch plan](plans/nexus-artifacts.md) lists the required live checks.
