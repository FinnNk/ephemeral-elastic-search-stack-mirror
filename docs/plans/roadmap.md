# Lab delivery roadmap

This page owns current status. Individual plans record their original batch;
research and evidence retain the conditions of earlier checks. Their old “next
step” is not an instruction to repeat completed work.

## Current work

The [relevance change lifecycle diagram](relevance-sdlc-diagram.md) covers
source CI, frozen comparison, merge decisions and reviewed promotion, with
warm-run timing annotations and linked measurement boundaries. It is
linked from the gallery and delivery guide. Next: review the diagram and resume
the [sneakers walkthrough](sneakers-demo-walkthrough.md).

[Gitea 28.0.0](gitea-28-upgrade.md) is installed using the existing chart,
SQLite storage, OIDC and runners. Its complete stopped-server backup is retained
in ignored lab state. The image pin and operations guide are prepared for review.
Next, review this batch and [resume the relevance walkthrough](sneakers-demo-walkthrough.md).

[Restart-safe cluster identity](oidc-node-startup.md) restores the API server’s
issuer hostname through a k3d startup hook. Review the node restart evidence,
then resume the walkthrough.

Readable delivery results are deployed from accepted commit `d589859`.
Existing progress and report URLs serve the browser views; JSON remains available.
Runtime readiness and smoke checks passed.

Prominent merge-gate status and conditional decision links are deployed from
accepted commit `4115f78`; readiness and smoke checks passed.

[Report timings](report-timings.md) are prepared for review. Friendly reports
show operation duration, retained capture timing and request health; Gatling
views include workload duration with their existing latency and failure results.
Promotion and rollback operations expose retained check reports; deployment
verification has a release summary.
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
The [internal Envoy gateway](headlamp-gateway.md) adds the data plane for CPU
LLM routing tests. Next, [verify plugin workflows](headlamp-testbed-validation.md)
against a routed simulator.
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
| Serving | KServe 0.21 and supplied Headlamp KServe plugin dev.54; exact local asset/serving checks retained |
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

## Additional query judgement resolution

Implemented for review: exact-byte query registration, pooled gap resolution and
frozen labels for source PR additional suites. Friendly reports show inference
reuse, abstentions, errors and explicit nDCG availability. Standard gate inputs
and model thresholds are unchanged.

Next: accept and deploy the batch, then trigger a new source commit and inspect
the sneakers comparison. See the [batch plan](additional-query-judgements.md).

## Calibrated judgement API activation

Model version 4 is active through both judgement APIs using the already loaded
KServe predictor. Real inference and repeat reuse passed; accuracy remains
unqualified. The activation helper preserves caches and prevents bootstrap from
resetting the API model pin. See the [activation plan](calibrated-judge-activation.md).
Next: generate the fresh sneakers comparison and continue the developer walkthrough.

## Search capture success counts

Friendly reports include successful requests alongside attempts, retries and failures.
A recovered request counts once as a success. Next: review this batch, then resume
the sneakers walkthrough using the [report review plan](report-request-successes.md).

## Informational nDCG significance

Prepared for review: paired nDCG tests, 95% intervals, request grouping and Holm
adjustment in source, combined and promotion relevance reports. Gate policies
remain unchanged. Next: accept the batch and inspect a fresh comparison in the
walkthrough. See the [batch and next-step plan](ndcg-significance.md).

## Headlamp custom Prometheus plugin

Prometheus `0.9.1-kserve.1` is installed, replacing the bundled plugin. Headlamp
readiness, single-plugin discovery and all 21 served assets passed verification.
OIDC and existing Pod configuration were preserved. Next: review this batch and
test browser charts with the next supplied KServe plugin. See the
[installation and next-step plan](headlamp-prometheus-plugin.md).

## Headlamp KServe dev.54

The supplied dev.54 release is installed and retained with earlier local releases.
Headlamp readiness, exact KServe assets, unchanged Prometheus assets and repeated
server-side application passed verification. OIDC and other Pod settings were
preserved. Next: review the setup batch and test dev.54 in the browser. See the
[installation and next-step plan](headlamp-kserve-dev54.md).

## Runner startup recovery

The offline delivery runner has been restarted and the stale Nexus route repaired.
Startup and readiness checks are installed on both runner deployments and prepared for review.
The focused Nexus route repair preserves stored releases and identities.
Next: accept the recovery batch and resume the sneakers report review. See the [batch plan](runner-startup-health.md).

## Deferred comparison evaluator

Consolidate optional gap resolution and frozen scoring behind one comparison
evaluator; keep the metric scorer pure and retained comparisons repeatable.
Implementation and diagram changes are deferred at the user's request.
See the [recorded follow-up](walkthrough-feedback.md#deferred-comparison-evaluator-boundary).

## Explicit promotion gates in the SDLC diagram

The timeline separates each promotion gate from review, deployment and verification.
Integration and staging show short probes; the production gate shows normal/peak
Gatling load alongside result and relevance evidence. Warm timings now separate
evaluation from deployment. Next: review the diagram and continue the source
walkthrough using the [timeline plan](relevance-sdlc-diagram.md).

## Final production release

Implemented for review: a blue–green route switch with a final comparison against the
active production API. Both slots share a read-only catalogue; the control UI owns
preparation, release checks, progress and approved deployment. Existing normal/peak
Gatling gates remain required. See the [implementation and rehearsal plan](production-blue-green.md).
The isolated four-query Argo rehearsal passed without changing active production.
The release UI shows active production immediately, with build and source links.
Candidate values stay blank until preparation is deployed.
Deployment uses a dropdown of open production PRs approved at their current commit.
After acceptance, use the [next walkthrough plan](production-release-walkthrough.md)
with a different verified staging release.

### Production load investigation, 6 October

Build 158 reached verified integration, staging and the inactive production slot.
The full production load run completed, but build 108's evaluation preview was
OOM-killed at 96 MiB and missed the peak budget; build 158 passed. Release remains
blocked before the final comparison and route-switch proposal.

The user authorised a brief investigation and a 192 MiB experiment. Both
evaluation previews now have separately committed diagnostic manifests; active
production is unchanged. A short matched Gatling screen tests a difficult slice
of the frozen traffic without replacing the required full gate. Preserve failed
evidence and distinguish the resource experiment from a permanent default.

Next: use the measured diagnostic to choose the next resource check, then resume
the [production walkthrough](production-release-walkthrough.md#production-load-recovery)
through the unchanged full gate and reviewed route switch. Queue visibility,
idempotency, live logs, failure evidence and resource visibility are recorded in
the [walkthrough feedback](walkthrough-feedback.md).
