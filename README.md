# Ephemeral search relevance lab

A local Kubernetes lab for developing and comparing ecommerce search changes. It provides a Search API, a browser UI and reproducible evaluations over frozen synthetic UK retail data.

Use it to compare ranking changes, check that a change preserves results, or measure API performance with Gatling. Comparisons retain the deployed versions, inputs and reports so they can be repeated.

## Start here

| What you want to do | Guide |
| --- | --- |
| Understand the system | [Design](docs/prototype-design.md) and [diagram gallery](docs/diagrams/index.html) |
| Connect to an existing lab | [Workstation access and certificate trust](docs/workstation-access.md), then [lab workflows](lab/README.md) |
| Develop the Search API | [Source README](lab/delivery/bootstrap/README.md), also published in the lab's `delivery-source` repository |
| Compare variants and interpret the decision | [Variant evaluation](docs/variant-evaluation.md) |
| Build, promote or roll back a release | [Delivery](docs/delivery.md) |
| Install or operate the control services | [Control runtime](docs/control-runtime.md) |
| Contribute to this repository | [Contributors guide](CONTRIBUTING.md) |

The source README includes a disconnected mock demo. Evaluating a change requires the running lab; mock results cannot satisfy the relevance gate.

## What runs in the lab

[Floci](https://github.com/floci-io/floci-az) provides fake Azure services locally,
including Blob Storage for frozen data and reports, and Key Vault for secrets.
It lets the lab exercise Azure service contracts without an Azure subscription.

| Responsibility | Components |
| --- | --- |
| Source, CI and deployment | Gitea, Actions runners, Nexus and Argo CD |
| Search and environment management | Self-managed Elasticsearch, Search API workloads and Kubernetes control services |
| Frozen inputs and index recovery | Floci (fake Azure Blob Storage), index recipes and a local snapshot store |
| Judgement gaps | Separate judgement API, MLflow model registry and KServe inference |
| Observability | OpenTelemetry and SigNoz |
| Secrets and browser access | External Secrets Operator, Floci (fake Azure Key Vault) and local HTTPS ingress |

The lab supports 10,000-product/50-query and 1,000,000-product/1,000-query frozen releases. [Scale](docs/research/evidence/million-scale.md) and [40-environment isolation](docs/research/evidence/concurrency-isolation.md) checks have local evidence. Synthetic relevance scores demonstrate the workflow; they do not establish customer search quality.

The [roadmap](docs/plans/roadmap.md) records remaining validation. Native Apple silicon, Azure and GitHub Enterprise still need verification. The design targets those environments, but the local namespaces share one host and are not separate failure domains.

## Repository workflow

Gitea is the primary remote. GitHub holds an offsite copy of Git history.

| Remote | Use |
| --- | --- |
| `origin` | Day-to-day branches and PRs in [local Gitea](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack) |
| `github` | Explicit backup pushes to [GitHub](https://github.com/FinnNk/ephemeral-elastic-search-stack) using the configured GitHub App |

Work in batches on branches, commit each batch and obtain acceptance before merging to `main`. See [contribution and documentation review requirements](CONTRIBUTING.md).

Git backup does not include Gitea's database, datasets, reports or registry images. Those need separate storage backups.

Research decisions and recorded experiments are indexed under
[research](docs/research/README.md) and [local evidence](docs/research/evidence/README.md).
Use their conditions to interpret results; use the guides above for current procedures.
