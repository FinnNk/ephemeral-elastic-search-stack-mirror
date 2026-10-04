# Lab delivery roadmap

This page owns current status. Individual plans record their original batch;
research and evidence retain the conditions of earlier checks. Their old “next
step” is not an instruction to repeat completed work.

## Current work

The developer walkthrough completed build 108 through integration, staging and
simulated production. The owner confirmed the rewrite in all three storefronts.
Production used the full Gatling gate; desired-state PR 16 was approved, merged
and verified. This proves the installed CLI path, not the pending Actions path.

| Batch | State | Next action |
| --- | --- | --- |
| Examples, similarity summaries and additional query sets | Implemented in the lab review stack | Review and accept; standard and explicitly required extra suites remain independent |
| Remote Actions and fresh source comparisons | Implemented, not installed | Merge accepted source templates and install the matching coordinator |
| Adaptive pacing | Eight workers; isolated overload trials and a fresh 1,000-query Job checked | Activate with the accepted control image; Gatling unchanged |
| Provider selection and byte pins | Checked against Gitea receipts and fresh Windows checkout bytes | Retain exact source/client/policy pins during activation |
| Complete Actions delivery and documentation reconciliation | [Current review batch](developer-delivery-docs.md) | Review approved merge, verification, rollback and gate-check submissions in updated source PR 27 |
| Activation rehearsal | [Next detailed plan](walkthrough-activation.md) | Rehearse a fresh PR and the complete developer path without kubectl after acceptance |

Source PR 27 passed release CI and the installed relevance gate after a fresh
1,000-query exact-image capture. Its base predates the new source contract, so
that capture used the existing operator publication procedure. Follow-up source
changes need their own exact-commit evidence; the parent verdict cannot cover
a different head. See [verification](../research/evidence/walkthrough-feedback-verification.md).

## Current lab configuration

| Area | Current scope |
| --- | --- |
| Catalogue | Full English ESCI: 1,215,854 products and 1,000 queries; configurable 10,000-product/50-query demo subset |
| Judgements | Published labels plus cached model-4 predictions under the temporary authorised demo policy; live fallback abstains |
| Coverage | Saved recall has 81.22% demo coverage and 29.71% published-only coverage; new recall can change it |
| Identity | Keycloak sign-in for Headlamp, Argo CD, linked Gitea accounts and the control UI; recorded exceptions still use verified Gitea identity |
| Serving | KServe 0.21 and supplied Headlamp KServe plugin dev.29; exact local asset/serving checks retained |
| Secrets and access | ESO reads Azure Key Vault through the local emulator; wildcard preview DNS and CA-verified browser HTTPS |
| Delivery | Gitea Actions, Nexus releases, reviewed desired state, Argo CD and three local namespaces |

Demo model predictions remain **unqualified**. The coverage minimum is still
80%; only the exact authorised source/model/policy scope receives the demo
allowance. The Decider2B execution remains held for human review. No new GPU
survey or threshold change is authorised by the developer workflow work.

## Remaining validation

| Area | Evidence available | Remaining work |
| --- | --- | --- |
| Search and scale | Million-product synthetic scale trials, full ESCI captures and a 40-API isolation trial | Repeat timings where percentile claims need support; native and cloud capacity |
| Lifecycle and recovery | Durable leases, deletion, interrupted-operation handling and index reuse/clone/snapshot/rebuild | Disposable clean-cluster recovery and complete activation rehearsal |
| Input contracts | Independent manifests, retained observations and finite producer/evaluator Jobs | External producer/evaluator boundaries on Azure and addendum-backed promotion |
| Judgement quality | Frozen numerical parity checks and category/CPU surveys | Independent actual-gap quality evidence, harmful-error support and qualified-only defaults before model qualification claims |
| Observability | SigNoz search/model dashboards, trace/log correlation, SLO arithmetic and finite arrival ledger | Continuous seven-day verified coverage, bounded counter alignment, instrumented three-target/browser rehearsal and valid overhead measurement |
| Portability | Multi-platform image manifests and local Gitea workflow execution | Native Apple silicon, AKS, GHES adapter/protection, Azure workload identity/storage and New Relic ingestion |
| Transport | Browser and internal Gitea HTTPS | OCI and selected host bootstrap HTTP paths; local HTTP is still an explicit lab boundary |

Use the [evidence index](../research/evidence/README.md) for measurements and
their limits. A successful local run does not establish cloud capacity, valid
model accuracy or a percentile target.

## Follow-up plans

- [Activation and developer rehearsal](walkthrough-activation.md)
- [Qualified-only labels](esci-qualified-defaults.md)
- [Instrumented delivery and overhead](signoz-merged-release-rehearsal.md)
- [Native/cloud validation](native-cloud-validation.md)
- [Azure Key Vault validation](azure-keyvault-validation.md)
- [HTTPS OCI transport](https-oci-transport.md)

Work on a branch, commit the batch and open a PR. Update this roadmap and the
next detailed plan before review. Merge only after human acceptance. GitHub
backup review batches remain separate from primary Gitea acceptance.
