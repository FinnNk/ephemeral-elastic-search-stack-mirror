# Reference CI/CD

## Intent and boundaries

Build a release once, store it in Nexus, then promote the same digests through integration, staging and simulated production. Gitea Actions runs CI; reviewed Git changes authorise promotion; Argo CD deploys. The lab demonstrates the common Actions subset needed for a later GitHub Enterprise Server migration.

| Constraint | Implementation |
| --- | --- |
| Existing comparisons remain reproducible | Retain historical images, index recipes and frozen datasets; release manifests refer to immutable content. |
| Synthetic data only | Use the existing synthetic GB/GBP releases and judgements. |
| Shared Elasticsearch | Reuse verified compatible frozen indices. A schema change selects a separate index recipe; rollback restores the image and index selection together. |
| One local cluster | Stable targets use separate namespaces. They demonstrate promotion boundaries, not independent failure domains or production capacity. |
| Portable CI | Shared shell/Python entry points, explicit checkout SHA, basic jobs/steps/env/secrets. Provider-specific API calls stay in adapters. Do not depend on GitHub environment approvals. |
| Reviewable implementation | Stack one project PR per batch. Dedicated demonstration repositories exercise source and promotion merges without merging project implementation PRs. |
| Storage ownership | Nexus: images and release bundles. Floci Blob: frozen data and reports. SeaweedFS: Elasticsearch snapshots. |

## Delivery batches

| Batch | Intent | Acceptance criteria | Information |
| --- | --- | --- | --- |
| 7f: Nexus foundation | Persistent artifact service, repositories and separate identities | Pinned service starts; publisher writes and reader pulls; overwrites and reader writes fail; an artifact survives restart; Kubernetes can pull a private image by digest. | [Nexus plan](nexus-artifacts.md), existing `lab/snapshot_repository.py`, platform runner and cluster configuration. |
| 7g: Portable CI | Build immutable release bundles from exact source revisions | A real Gitea PR and merged source run use the shared workflow; tests fail closed; multi-platform images and checksummed deployment assets are published; release ID changes with content; no mutable tag is deployed. | [Portable CI plan](portable-ci.md), `lab/search-app`, `research/platform-spike/runner.yaml`, [developer loop](developer-evaluation-loop.md). |
| 7h: Promotion and deployment | PR-based promotion, evidence checks, Argo reconciliation and rollback | Same release reaches three targets; API result/relevance/Gatling evidence is recorded; failed and stale evidence block promotion; deploy health is distinct from evaluation; rollback restores the prior complete deployment; schema incompatibility is rejected. | [Promotion plan](promotion-deployment.md), [guide](../delivery.md), [evidence](../research/evidence/promotion-deployment.md). |
| 7i: Kubernetes controls | Host-independent runtime orchestration | Dedicated namespace, persistent control state, scoped runtime identity and interrupted-operation recovery; existing CI/CD ownership preserved. | [Control services plan](kubernetes-control-services.md). |
| 7j: Data and evaluation contracts | Separate input producers, execution, scoring and policy | Independently versioned artifacts; retained observations can be rescored without redeployment; schema-changing promotion and rollback exercise the release boundaries. | [Data/evaluation plan](independent-data-evaluation-contracts.md). |
| 7k: OTel observability | Connected activity and service-level investigation | SigNoz dashboard links SLO/error-budget breaches to traces and logs, including CI/deployment operations; New Relic mappings preserve signal meanings. | [Observability plan](otel-observability.md). |
| 8: Native and cloud validation | Validate platform boundaries outside this host after the local batches | Apple silicon run, GHES workflow run, Azure deployment, New Relic ingestion/correlation and capacity/cost evidence. These remain external gates. | [Native/cloud plan](native-cloud-validation.md). |

## Release and promotion contract

- A release pins source SHA, image digest, deployment bundle checksum, query assets and index recipe compatibility. Secrets and target-specific settings stay outside the release.
- CI for a PR checks its exact head. A merged source commit creates its own release and evidence when its SHA differs; PR evidence is not silently relabelled.
- A deployment records release ID, frozen dataset, concrete index recipe, settings and predecessor. Promotion reuses the release; it does not rebuild it.
- A promotion PR identifies source and target, their current revisions, the proposed deployment and report hashes. Changed source, target or report inputs invalidate approval evidence.
- Result-preserving changes require unchanged results. Intentional ranking changes require an explicit human review of frozen relevance evidence; synthetic scores alone do not establish improved relevance.
- CI may propose a promotion. The approved Git change authorises Argo CD to deploy. Readiness and an API smoke check produce deployment verification; only then is the next promotion eligible.
- No automatic artifact cleanup is enabled. Retention must include every historical comparison, live deployment and rollback reference.

## Provisional first-slice targets

| Measure | Initial target | Measurement boundary |
| --- | --- | --- |
| Cached CI to published release | Under 5 minutes | Runner job start to all release artifacts available. |
| Approved promotion to verified API | Under 2 minutes | Merge to Argo health and successful public API query, with a warm shared index. |
| Rollback to verified API | Under 2 minutes | Rollback merge to verification, retained image and index available. |
| Rebuilds during promotion | Zero | Identical image and bundle digests at every target. |
| Failure handling | All demonstrated negative cases block | Failed checks, stale evidence, incompatible schema and unauthorised artifact write. |

Record individual samples before claiming a percentile. GHES compatibility remains a design claim until a real GHES run passes.
