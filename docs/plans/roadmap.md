# Lab delivery roadmap

This page owns current status. Individual plans record their original batch;
research and evidence retain the conditions of earlier checks. Their old “next
step” is not an instruction to repeat completed work.

## Current work

The [lab experience and Mac transfer](lab-experience-and-mac.md) batches are
prepared for review: shared design system, promotion controls in the release
tree, reconciled operator guides and Mac setup/transfer instructions. The
installed release dashboard remains read-only until these accepted batches
are activated. Native Mac execution and whole-lab restore remain outstanding.

## Completed delivery capabilities

- [Release dashboard](read-only-release-dashboard.md): PR #147 is merged and
  activated. Its installed projection and runtime smoke checks passed; build
  158 is verified in Integration and Staging and prepared in the inactive slot.
- [Final production release](production-blue-green.md): active and candidate
  APIs use the same frozen catalogue. Reviewed preparation, load/final relevance
  checks, route switching and rollback are implemented.
- [Notebook comparisons](delivery-notebook-comparisons.md) and the
  [browser view](notebook-browser-view.md): existing delivery environments and
  purpose-created environments can be compared; saved analysis can be viewed
  or downloaded.
- [Walkthrough feedback](walkthrough-feedback.md): named Actions workflows,
  eight-worker adaptive pacing, additional query suites, inference reuse,
  separate coverage/quality, RBO/Jaccard summaries, informational significance,
  readable timings, request successes and durable relevance decisions.
- [SigNoz repairs](signoz-dashboard-repairs.md),
  [Headlamp health checks](headlamp-health-probes.md),
  [Gitea 28.0.0](gitea-28-upgrade.md) and
  [restart-safe OIDC](oidc-node-startup.md): accepted operational corrections.
- [GitHub mirrors](../github-mirror.md): native Git push mirrors are configured;
  service databases and artefacts still need separate backups.

Plans below retain their original batch records. Their earlier review or next
steps do not supersede the current guides or authorise repeating completed runs.

## Current lab configuration

| Area | Current scope |
| --- | --- |
| Catalogue | Full English ESCI: 1,215,854 products and 1,000 queries; configurable 10,000-product/50-query demo subset |
| Judgements | Published labels plus cached model-4 predictions under the temporary authorised demo policy; live fallback abstains |
| Coverage | Saved recall has 81.22% demo coverage and 29.71% published-only coverage; new recall can change it |
| Identity | Keycloak sign-in for Headlamp, Argo CD, linked Gitea accounts and the control UI; the reviewed decision flow uses human OIDC requests and exact Gitea PR approvals |
| Serving | KServe 0.21 and supplied Headlamp KServe plugin dev.54; exact local asset/serving checks retained |
| Secrets and access | ESO reads Azure Key Vault through the local emulator; wildcard preview DNS and CA-verified browser HTTPS |
| Delivery | Gitea Actions, Nexus releases, reviewed desired state, Argo CD, Integration/Staging and two production slots |

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

### Walkthrough feedback completion

Lab PRs #138/#139 and delivery-source PR #33 are merged and activated. The
coordinator, focused workflows, merge restriction and dashboards are installed.
A verification-only Actions run completed through the coordinator, and build
163's preview exported search counters and propagated traces to SigNoz. See the
[activation evidence](walkthrough-feedback-activation.md) for measurements and
limits. The abstaining v1 judge remains active.

Next: resume the production resource investigation, then run the unchanged full
load gate and reviewed route switch. OpenCost installation remains a separate
proposed batch.

### SigNoz dashboard repairs

The [dashboard repair batch](signoz-dashboard-repairs.md) distinguishes browser
and probe activity from normal SLO traffic, removes interval warnings and adds
model-version selection. It also supplies coverage and gap-pool shift from the
current resolution path. Temporary dashboards and diagnostic metric transport
were checked; the merged definitions and coordinator are now installed.

A fresh comparison confirmed matching frozen and stored coverage: 0% for 40
cached abstentions, with no new inference. An optional-gate display fix awaits
review. Next: activate that fix, then resume the unchanged production load gate.
