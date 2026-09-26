# Ephemeral search relevance lab

This project is a planned home lab for comparing ecommerce search changes against a reproducible baseline. It will use synthetic UK retail data, a self-managed Elasticsearch cluster and short-lived Kubernetes workloads. The first dataset will contain 10,000 products and 50–100 judged queries. The prototype will remain in development until its design has been tested with 1,000,000 products and 1,000 queries.

The [prototype design](docs/prototype-design.md) defines the architecture, research questions, provisional quantitative targets, dataset contract, environment lifecycle, three comparison modes (relevance, result preservation and Gatling performance), frozen synthetic traffic profiles, scale tests and delivery batches. The early lab will use self-hosted Gitea for repositories, pull requests, builds and container images so it can demonstrate the complete source-to-disposal workflow locally. The design keeps a provider boundary for a later move to GitHub Enterprise. The research includes open source environment platforms and integration with Argo CD, which is already used in the target production system. This repository does not yet contain a runnable lab.

Browse the [architecture diagram gallery](docs/diagrams/index.html) or [diagram guide](docs/diagrams/README.md) for six Structurizr C4 views and seven interactive Archify views, with editable sources and rendering instructions.

## Current state

The design batch is committed for review. A short research and measurement batch will validate the environment management pattern before the runnable search slice. Setup instructions will be added when the commands and prerequisites can be verified on Windows and Apple silicon macOS.

## Repository workflow

Gitea will be the primary remote for day-to-day branches, pull requests and builds. The private GitHub repository will hold an offsite copy of this project's Git history.

| Remote | Role | Location |
| --- | --- | --- |
| `github` | Offsite backup | [FinnNk/ephemeral-elastic-search-stack](https://github.com/FinnNk/ephemeral-elastic-search-stack) |
| `origin` (planned) | Primary Gitea remote | Add after local Gitea setup |

Configure GitHub App authentication before the first GitHub push. Once Gitea is available, use `origin` for normal fetch/push operations and `github` explicitly for backup pushes. Define the backup schedule during Gitea setup. Object-storage datasets, reports and registry images need their own backup arrangements.

Work in batches on a branch, commit each batch and obtain acceptance before merging to `main`.
