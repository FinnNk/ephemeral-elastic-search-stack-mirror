# Ephemeral search relevance lab

This project is a planned home lab for comparing ecommerce search changes against a reproducible baseline. It will use synthetic UK retail data, a self-managed Elasticsearch cluster and short-lived Kubernetes workloads. The first dataset will contain 10,000 products and 50–100 judged queries. The prototype will remain in development until its design has been tested with 1,000,000 products and 1,000 queries.

The [prototype design](docs/prototype-design.md) defines the architecture, quantitative targets, frozen datasets, environment lifecycle and three comparison modes: relevance, result preservation and Gatling performance. The design keeps a provider boundary for a later move from Gitea to GitHub Enterprise.

Browse the [architecture diagram gallery](docs/diagrams/index.html) or [diagram guide](docs/diagrams/README.md) for six Structurizr C4 views and seven interactive Archify views, with editable sources and rendering instructions.

The [delivery roadmap](docs/plans/roadmap.md) tracks reviewable batches and links the [next detailed plan](docs/plans/environment-lifecycle.md).

## Current state

The design is merged. An [experimental research harness](research/platform-spike/README.md) runs local Gitea, Argo CD, Elasticsearch and Floci. The [runnable lab slice](lab/README.md) adds browser pages and search APIs over a frozen synthetic UK retail release. It compares query-understanding and ranking changes through the public APIs, with correlated diagnostic evidence for a result-preserving refactor and a deliberate rewrite.

- [Research results](docs/research/platform-spike.md): 20 warm lifecycle trials, API and analyser comparisons, isolation and failure recovery.
- [Proposed decision](docs/adr/ADR-0001-reconcile-environments-from-git.md): reconcile environments from Git-file ApplicationSets; use k3d provisionally.
- [Local access](research/platform-spike/README.md#personal-access): named Gitea and Argo CD administrator logins and browser URLs.
- Next: environment lifecycle and UI, index-change comparison, Gatling profiles and scale validation. Apple silicon remains untested.

## Repository workflow

Gitea is the primary remote for day-to-day branches and pull requests. The private GitHub repository holds an offsite copy of this project's Git history.

| Remote | Role | Location |
| --- | --- | --- |
| `github` | Offsite backup | [FinnNk/ephemeral-elastic-search-stack](https://github.com/FinnNk/ephemeral-elastic-search-stack) |
| `origin` | Primary Gitea remote | [Local project](http://127.0.0.1:31800/elastic-agent/ephemeral-elastic-search-stack) |

Use `origin` for normal fetch/push operations and `github` explicitly for backup pushes with GitHub App authentication. Back up each completed batch branch; no unattended schedule is configured. Gitea's database, datasets, reports and registry images need separate volume backup and restore arrangements.

Work in batches on a branch, commit each batch and obtain acceptance before merging to `main`.
