# Ephemeral search relevance lab

This project is a home lab for comparing ecommerce search changes against a reproducible baseline. It uses synthetic UK retail data, a self-managed Elasticsearch cluster and short-lived Kubernetes workloads. The first frozen dataset contains 10,000 products and 50 judged queries. A separate frozen release contains 1,000,000 products and 1,000 queries. Scale, load and 40-environment checks have local evidence; native Apple silicon and cloud validation remain open.

The [prototype design](docs/prototype-design.md) defines the architecture, quantitative targets, frozen datasets, environment lifecycle and three comparison modes: relevance, result preservation and Gatling performance. The design keeps a provider boundary for a later move from Gitea to GitHub Enterprise.

Browse the [architecture diagram gallery](docs/diagrams/index.html) or [diagram guide](docs/diagrams/README.md) for seven Structurizr C4 views and twelve interactive Archify views, with editable sources and rendering instructions.

The [delivery roadmap](docs/plans/roadmap.md) summarises demonstrated behaviour and remaining gates. See the [scale evidence](docs/research/evidence/million-scale.md), [concurrency evidence](docs/research/evidence/concurrency-isolation.md) and [native/cloud validation plan](docs/plans/native-cloud-validation.md).

The control services run in Kubernetes, and synthetic inputs and offline evaluation have separate contracts. The Search API has an OpenTelemetry signal contract, and the control services send signals to a local gateway. SigNoz stores synthetic search traces and metrics plus correlated delivery traces and logs; the [connected investigation](docs/plans/signoz-connected-investigation.md) will check dashboard arithmetic and navigation. The [roadmap](docs/plans/roadmap.md) lists the remaining validation gates.

## Current state

The [platform guide](research/platform-spike/README.md) runs local Gitea, Argo CD, Elasticsearch and Floci. The [lab guide](lab/README.md) covers browser pages and search APIs over frozen synthetic UK retail inputs. It compares query-understanding and ranking changes through the public APIs, with correlated diagnostics. Kubernetes-hosted control services create, search, compare and remove pinned API environments with durable leases, using either a shared index or a dedicated mapping-change index.

- [Research results](docs/research/platform-spike.md): 20 warm lifecycle trials, API and analyser comparisons, isolation and failure recovery.
- [Proposed decision](docs/adr/ADR-0001-reconcile-environments-from-git.md): reconcile environments from Git-file ApplicationSets; use k3d provisionally.
- [Local access](research/platform-spike/README.md#personal-access): named Gitea and Argo CD administrator logins and browser URLs.
- [Nexus artifact storage](docs/nexus.md): private images, release bundles and your separate administrator login.
- [Reference CI/CD](docs/delivery.md): Nexus releases, protected promotion PRs, three local targets and verified rollback; [detailed plan](docs/plans/reference-ci-cd.md) and [evidence](docs/research/evidence/promotion-deployment.md).
- [Lifecycle evidence](docs/research/evidence/lifecycle-measurement/README.md): named owner checks and 20/20 warm removals; nearest-rank deletion p95 53.844 seconds against the five-minute target.
- [Index-change evidence](docs/research/evidence/index-change.md): separate frozen index, authenticated API comparison, access isolation and cleanup.
- [Synthetic traffic and Gatling](docs/research/synthetic-traffic.md): frozen query/timestamp pairs, finite Kubernetes Jobs and public-API performance comparisons, including long-duration million-release schedules.
- [Million-product scale evidence](docs/research/evidence/million-scale.md): deterministic release, shared and mapping-change indices, full 1,000-query result comparisons and measured capacity limits.
- [Concurrency and isolation evidence](docs/research/evidence/concurrency-isolation.md): three complete environments, two 40-API fleets, access boundaries, cleanup and controlled contention.
- [Portability and Azure shape](docs/research/portability-azure.md): multi-platform image and Blob checks, C4 deployment updates, GHES/Nexus migration route with optional ACR and remaining native/cloud gates.

## Repository workflow

Gitea is the primary remote for day-to-day branches and pull requests. The private GitHub repository holds an offsite copy of this project's Git history.

| Remote | Role | Location |
| --- | --- | --- |
| `github` | Offsite backup | [FinnNk/ephemeral-elastic-search-stack](https://github.com/FinnNk/ephemeral-elastic-search-stack) |
| `origin` | Primary Gitea remote | [Local project](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack) |

Use `origin` for normal fetch/push operations and `github` explicitly for backup pushes with GitHub App authentication. Back up each completed batch branch; no unattended schedule is configured. Gitea's database, datasets, reports and registry images need separate volume backup and restore arrangements.

Work in batches on a branch, commit each batch and obtain acceptance before merging to `main`.
