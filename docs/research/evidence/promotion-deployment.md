# Promotion and deployment evidence

**Historical run — 27 September 2026.** Host-process placement, HTTP transport, target state and unmerged project PRs below describe this demonstration. Later batches moved control into Kubernetes and added HTTPS. Use the [current delivery guide](../../delivery.md) for operation.

Executed on 27 September 2026 against local Gitea, Nexus, Argo CD and the shared Elasticsearch cluster. All products, queries and traffic were synthetic. The desired-state PRs below belong to the isolated `delivery-state` demonstration repository; project implementation PRs remain unmerged.

## Measured walkthrough

| Check | Result |
| --- | --- |
| Baseline and candidate | Successful merged-source builds 15 and 17; distinct image/release digests, the same deployment bundle and baseline recipe |
| Frozen scale | 1,000,000 products; 1,000 queries; UK/GBP |
| Result preservation, forward and rollback | 1,000/1,000 queries completed in each direction; zero changed ordered results |
| Relevance, both directions | Full suites completed; both sides nDCG@10 0.979894, Judged@10 1.0. Candidate-derived synthetic judgements remain a proxy, not independent quality validation |
| Paired Gatling delivery probe | Same workload and successful warmup; 20 measured requests per side at 2 rps. Forward p95 44/48 ms; rollback 38/36 ms; no failed requests |
| Integration promotion, [PR #1](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/1) | Merge to verified API: **6.265 s** |
| Staging promotion, [PR #3](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/3) | **4.141 s** |
| Simulated production, [PR #4](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/4) | **4.110 s** |
| Promotion rebuilds | **Zero**; source Actions run count stayed at six; all three targets declared the identical candidate deployment |
| Rollback, [PR #5](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/5) | **4.266 s**; prior image/configuration/index recipe and API fingerprint restored |
| Expiry and recreation | Expired preview namespace removed; 1,000,000-product index retained; recreated preview had the identical fingerprint |
| Unit suite | `python -m unittest discover -s lab -p 'test_*.py'`: **71 passed**, 6.756 s on the final code |
| Coordinator | `watch --once` passed; hidden watcher started for validation, deployment verification and expiry |

These are individual warm timing samples. The ten-second Gatling probe demonstrates the delivery gate; it provides no sustained-capacity or percentile-stability claim. Longer load evidence remains in the [million-product batch](million-scale.md).

The two software releases intentionally preserve API behaviour; their source revisions differ in the delivery contract. This run demonstrates build-once promotion and rollback, not a new ranking-quality improvement. The live rollback used a shared unchanged recipe. Historical-schema reconstruction and snapshot recovery have [separate evidence](index-recovery-workflows.md); a complete schema-changing promotion/rollback remains a useful GHES/native validation case.

## Negative cases and evidence

| Boundary | Observed rejection |
| --- | --- |
| Merge without review | Protected `delivery-state/main` denied the attempt before simulated approval |
| Competing proposal | After integration merged, [PR #2](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/2) failed validation because desired-state main changed; closed unmerged |
| Historical incompatible schema | Real retained `title-keyword-v1` million-product recipe rejected by the baseline release contract before deployment |
| Failed/incomplete/stale checks | Focused tests rejected changed results under preservation intent, 999/1,000 queries, failed Gatling, an old baseline, expired evidence and a changed intent |
| Changed PR head | Validation test rejected a head change without publishing a success status for the new head |
| Artifact integrity | [CI tests](portable-ci.md) rejected altered contracts, traversal and mutable images; [Nexus probes](nexus-artifacts.md) rejected overwrite and unauthorised writes |

Approvals in the live harness were explicitly labelled **automated demonstration approvals** by the separate `lab-admin` identity. They do not record human acceptance of synthetic relevance scores or project implementation PRs.

Sanitised records:

- [Promotions and stale proposal](promotion-deployment/promotion.json)
- [Rollback](promotion-deployment/rollback.json)
- [Frozen evaluation summaries and report hashes](promotion-deployment/checks.json)
- [Expiry/recreation](promotion-deployment/preview-lifecycle.json)
- [Schema rejection](promotion-deployment/incompatible-schema.json)

Full query and Gatling reports remain immutable in Floci, referenced by these hashes. Current target state after the demonstration is **integration/staging: build 17; simulated production: build 15**. Two frozen previews remain under 72-hour leases. Stable targets are persistent.

## Limits and next batch

The coordinator uses one host process and local verification records; full host-loss recovery and multi-replica control are not implemented. Gitea and Nexus use trusted local identities and private HTTP endpoints. Native Apple silicon, real GHES protections/workflows and Azure identity/capacity need the [next detailed plan](../../plans/native-cloud-validation.md). The [operating guide](../../delivery.md) describes review, rollback and recovery commands.
