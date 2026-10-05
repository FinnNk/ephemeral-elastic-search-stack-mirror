# Lab delivery roadmap

This page owns current status. Individual plans record their original batch;
research and evidence retain the conditions of earlier checks. Their old “next
step” is not an instruction to repeat completed work.

## Current work

Readable delivery results are deployed from accepted commit `d589859`.
Existing progress and report URLs serve the browser views; JSON remains available.
Runtime readiness and smoke checks passed.

Prominent merge-gate status and conditional decision links are deployed from
accepted commit `4115f78`; readiness and smoke checks passed.

[Report timings](report-timings.md) are prepared for review. Friendly reports
show operation duration, retained capture timing and request health; Gatling
views include workload duration with their existing latency and failure results.
Next, [activate and check timings](report-timings-activation.md).

Registry setup now discovers Docker-backed cluster workers instead of naming
three fixed nodes. The testbed installer applies it after adding its worker.
The affected preview recovered; the source comparison resumed fresh capture.
This repair is prepared for review. Next, continue the
[sneakers walkthrough](sneakers-demo-walkthrough.md).

Copyable [sneakers demo snippets](../../lab/delivery/bootstrap/examples/sneakers/README.md)
are published in the lab bootstrap template and await source-repository review.
The gate guide now explains per-variant intent and the requirement for every
selected variant to pass or receive an allowed exception.
Next, resume the step-by-step developer walkthrough and review its comparison.


The optional [Headlamp plugin testbed](../headlamp-testbed.md) is installed on
an additional 8 GiB CPU worker: KServe LLM APIs/controller and presets, Knative
with internal Kourier, KEDA and bounded Prometheus. Both lab judgement models
remain Ready. Headlamp already runs the latest checked release, 0.45.0.
Next, [verify plugin workflows](headlamp-testbed-validation.md) against these APIs.
[Judgement inference reuse](judgement-inference-reuse.md) is merged. A 6,920-pair replay reused every prediction and abstention after restart
and threshold changes, with zero new score-provider calls. Coverage now has its
own report section; variants still share one frozen judgement set.
Next: [activate and rehearse the merged API](judgement-inference-activation.md).

The developer walkthrough completed build 108 through integration, staging and
simulated production. The owner confirmed the rewrite in all three storefronts.
Production used the full Gatling gate; desired-state PR 16 was approved, merged
and verified. The accepted remote workflow is now installed. A disposable
source PR and Actions rehearsals verified fresh comparisons, independent extra
query gates, preview creation, deployment proposals and approval enforcement.
See the [activation evidence](../research/evidence/walkthrough-activation.md).

| Batch | State | Next action |
| --- | --- | --- |
| Examples, similarity summaries and additional query sets | Installed; report-only and required-set live checks completed | Use separate and combined reports; required suites remain independent |
| Remote Actions and fresh source comparisons | Installed; exact-commit comparison and scoped submissions checked | Rehearse the user's next change through reviewed deployments |
| Adaptive pacing | Eight workers; fresh 1,000-query captures and bounded transient recovery checked | Retain fresh requests and diagnostics; Gatling unchanged |
| Provider selection and byte pins | Checked against Gitea receipts and fresh Windows checkout bytes | Retain exact source/client/policy pins during activation |
| Actions delivery and documentation | Installed; preview, verification, promotion/rollback proposals and signed gate rechecks exercised | Review the bootstrap corrections found during activation |
| Durable relevance decisions | Accepted and installed; runtime files and protected pins verified | Rehearse a fresh human-reviewed decision using the [activation plan](relevance-decision-activation.md) |
| GitHub backup | Three native mirrors enabled; refs and automatic pushes verified | Use Gitea for reviews; retain the old backup until the owner removes it |
| Developer workstation rehearsal | [Next detailed plan](remote-delivery-user-check.md) | Complete device sign-in and a fresh human-approved deployment through Actions |

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
| Identity | Keycloak sign-in for Headlamp, Argo CD, linked Gitea accounts and the control UI; the reviewed decision flow uses human OIDC requests and exact Gitea PR approvals |
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
| Lifecycle and recovery | Durable leases, deletion, interrupted-operation handling and index reuse/clone/snapshot/rebuild; remote activation checked | Disposable clean-cluster recovery and workstation sign-in rehearsal |
| Input contracts | Independent manifests, retained observations and finite producer/evaluator Jobs | External producer/evaluator boundaries on Azure and addendum-backed promotion |
| Judgement quality | Frozen numerical parity checks and category/CPU surveys | Independent actual-gap quality evidence, harmful-error support and qualified-only defaults before model qualification claims |
| Observability | SigNoz search/model dashboards, trace/log correlation, SLO arithmetic and finite arrival ledger | Continuous seven-day verified coverage, bounded counter alignment, instrumented three-target/browser rehearsal and valid overhead measurement |
| Portability | Multi-platform image manifests and local Gitea workflow execution | Native Apple silicon, AKS, GHES adapter/protection, Azure workload identity/storage and New Relic ingestion |
| Transport | Browser and internal Gitea HTTPS | OCI and selected host bootstrap HTTP paths; local HTTP is still an explicit lab boundary |

Use the [evidence index](../research/evidence/README.md) for measurements and
their limits. A successful local run does not establish cloud capacity, valid
model accuracy or a percentile target.

## Follow-up plans

- [Developer workstation and Actions rehearsal](remote-delivery-user-check.md)
- [Qualified-only labels](esci-qualified-defaults.md)
- [Instrumented delivery and overhead](signoz-merged-release-rehearsal.md)
- [Native/cloud validation](native-cloud-validation.md)
- [Azure Key Vault validation](azure-keyvault-validation.md)
- [HTTPS OCI transport](https-oci-transport.md)

Work on a branch, commit the batch and open a PR. Update this roadmap and the
next detailed plan before review. Merge only after human acceptance. Gitea owns
review and acceptance. Native GitHub mirroring replaces separate backup PRs.
