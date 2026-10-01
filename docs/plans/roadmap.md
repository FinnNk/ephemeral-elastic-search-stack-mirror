# Lab delivery roadmap

The lab has demonstrated a million-product catalogue, 1,000 queries, frozen API comparisons, Gatling load profiles, index recovery, a 40-API fleet and a three-target release path. These are local measurements, not evidence that the same capacity or latency will hold on Apple silicon or Azure. The [design targets](../prototype-design.md#provisional-quantitative-targets) remain provisional.

The control-runtime consolidation and delivery rehearsal are merged to `main`. Earlier batch plans remain in this directory, with measured results such as the [million-product](../research/evidence/million-scale.md) and [control-runtime](../research/evidence/kubernetes-control-services.md) evidence. A merged implementation does not close a measurement or integration gate.

| Area | Demonstrated locally | Remaining gate |
| --- | --- | --- |
| Search and scale | 1M synthetic products, 1,000 queries, shared and dedicated indices, API relevance and result-preservation comparisons, Gatling profiles | Repeat timing samples and capacity checks where a percentile or target claim requires them; native and cloud verification |
| Lifecycle and recovery | Kubernetes `lab-control`, durable leases, expiry, deletion, interrupted-operation recovery, index reuse/clone/snapshot/rebuild; updated Pod created shared, dedicated and historical environments | Complete disposable activation and recovery rehearsal; repeat timing samples where a target claim requires them |
| Input and evaluation contracts | Independent manifests, producer/evaluator Jobs, retained observations and offline rescoring; deployed control selects hash-checked inputs and catalogue-only recipes by default. New 10k/1M indices, historical replay and deployed comparison have live checks. | Exercise an addendum-backed promotion through the same installed control path; validate external producer/evaluator boundaries on Azure |
| Judgement supply | MLflow registry, KServe Standard and a separate judgement API serve exact synthetic source scopes. A 10k/50-query and optional 1M/1,000-query pooled resolution ran against retained API observations; source labels won, all missing pairs abstained, and both sides used one frozen set. The 1M hash cache occupied 243 MB and restarted from retained state. | A reviewed non-abstaining model, active-recall API run, clean-cluster bootstrap, Apple silicon and Azure identity/storage. The 1M no-op report has 0.21% judged coverage and is not relevance evidence. |
| Delivery | Gitea Actions, Nexus images and release bundles, protected promotion PRs; merged-source 1M schema release promoted and rolled back through all three local targets with fresh direction-specific evidence | Validate GHES portability and repeat timing samples where a target claim requires them |
| Observability | Search API signal contract and SLO arithmetic; pinned SigNoz, ClickHouse, gateway and scoped log agents installed; search SLO and model-health dashboards; connected evaluator → judgement API → KServe trace; disposable Search API W3C trace proof; stored delivery and diagnostic search span/log correlation; digest-pinned finite Job logs; fail-closed seven-day fixtures; finite Gatling arrival ledger, independent readiness probe and SigNoz counter join; gateway outage leaves search serving; local New Relic profile checked against a mock endpoint | Redeploy older retained search releases for OTLP; continuous seven-day verified source coverage and bounded counter alignment; browser drill-through, instrumented release across all delivery targets and a valid overhead comparison |
| Platform | Gitea, Argo CD, Floci, SeaweedFS, Elasticsearch and ESO on the local host; 40 retained Kubernetes Secrets reconcile from Floci Key Vault; five web services pass CA-validated HTTPS through Traefik; control, Argo CD and both runners use verified HTTPS Git/API paths | OCI and host bootstrap HTTPS migration; search-spike fixture PR acceptance; Apple silicon, AKS, Azure Blob/Key Vault identity and New Relic validation |

The [reference-clarity audit](reference-clarity.md) tracks historical-schema and documentation cleanup separately from these delivery gates. It retains frozen replay without making old schemas the default path.

## Next batches

The [documentation authorship review](documentation-authorship.md) is accepted on main. D1, current operating guides, is accepted on main, including two maintained UI/notebook illustrations. [D2: evaluation and delivery](documentation-evaluation-delivery.md) is implemented for review. [D3: models and observability](documentation-model-observability.md) is implemented for review. [D4: design and navigation](documentation-design-navigation.md) is implemented for review. The next documentation batch is [D5: historical records and final review](documentation-historical-final-review.md). Canonical HTTPS control routing and secure session cookies remain a separate implementation gap; other validation gates below remain separate.

The project-side [developer guide and disconnected demo batch](developer-guide-demo.md) is accepted on main. It adds workstation trust instructions, explicit browser access, a separate in-memory search demo and illustrated delivery/evaluation guides. The source code change still needs exact-commit lab evidence before merge; mock demo results cannot satisfy that gate.

The [documentation relevance gate batch](documentation-relevance-gate.md) is accepted and active on source main. It retains application checks, exempts only the two source README paths and runs the relevance decision from the trusted target revision. Main protection requires both checks and review. The rebased README PR passed both checks and is merged to source main. The next step is the developer walkthrough. The [evidence](../research/evidence/documentation-relevance-gate.md) records the protected fixture controls and activation checks.

The [MLflow and KServe judgement coverage plan](mlflow-kserve-judgement-coverage.md) adds a two-stage relevance evaluation: capture both recall sets, resolve their union, freeze one judgement snapshot and score both sides. Its first model abstains on every pair. The local implementation batches are accepted on main; the existing control UI retains its selected-judgement route. The [local evidence](../research/evidence/mlflow-kserve-judgement-coverage.md) records the 1M cache correction and low coverage. This does not close the unrelated gates below.

The next judgement-specific batch is [control UI integration](judgement-control-integration.md): launch the verified resolver as a finite Job from retained observations and show frozen coverage and lineage in the UI.

The [model observability batch](model-observability.md) adds a source-controlled SigNoz dashboard, bounded inference and coverage metrics, an input-selection shift signal and connected judgement/KServe tracing. Its [local evidence](../research/evidence/model-observability-2026-09-29.md) shows the exact scope and older-release deployment caveat. Control UI integration remains the next judgement workflow batch.

The four [offline variant batches](offline-variants-and-gates.md) are merged on Gitea `main`: N-way capture and scoring, a selected-variant merge gate, a [live million-product proof](../research/evidence/offline-variants-million.md), and an [Argo-managed source CI rehearsal](../research/evidence/managed-variant-gate.md). The live model abstained on 10,946 gaps, leaving coverage below the 80% minimum; CI blocked the result. A separate, explicitly synthetic full-coverage fixture passed CI. The [operator decision rehearsal](variant-gate-operator-validation.md) is the next variant-specific check; it needs a real human release choice and better judged evidence. A two-version replacement needs no online traffic split. The GitHub offsite review stack remains open.

1. [SigNoz backend and signal transport](signoz-backend-and-investigation.md) is accepted on main. The backend, gateway and log agent are deployed; the agent organisation is bootstrapped and all three signal types have stored records.
2. [SigNoz account and SLO dashboard](signoz-connected-investigation.md) is accepted on main. The dashboard and synthetic interval checks are installed; account access follows the current operator guide.
3. [Finite Job telemetry](signoz-connected-runtime.md) is accepted on main; the producer and evaluator run as digest-pinned Jobs and their safe outcome logs reach SigNoz.
4. [Seven-day window assessment](signoz-window-coverage.md) is accepted on main; synthetic fixtures verify totals and unknown-on-gap behaviour.
5. [Connected investigation and overhead](signoz-investigation-overhead.md) is accepted on main with a finite live ledger/counter join, outage check and retained overhead runs. The four overhead runs missed the arrival gate, so the result is inconclusive.
6. [Merged-release investigation rehearsal](signoz-merged-release-rehearsal.md) closes the instrumented three-target, browser and valid overhead gates using a verified instrumented merged-source release.
7. [Native and cloud validation](native-cloud-validation.md): run the full lifecycle on Apple silicon and Azure/GHES, including New Relic ingestion.
8. [Azure Key Vault delivery](azure-keyvault-validation.md): prove the unchanged Kubernetes Secret targets with ESO's Azure provider, Workload Identity and real vault policy.
9. [HTTPS Git clients](https-client-transport.md) are implemented locally. Control, Argo CD and both runners use verified Gitea HTTPS; the search-spike fixture PR remains open.
10. [HTTPS OCI and host transport](https-oci-transport.md): move registry push/pull and host Git/API tools to verified TLS, then check webhooks and native workstation trust.

Each batch ends with evidence, an updated roadmap and the next detailed plan. Commit it to a branch and submit a PR; merge to `main` only after acceptance. A passing functional check does not establish relevance validity or performance capacity.

Documentation status was checked against Gitea PRs #32–#59: the implementation
batches listed above are merged. That does not imply their outstanding runtime
or cloud acceptance criteria passed. GitHub backup status is separate from the
primary implementation record.

Two editorial checks found implementation gaps: canonical HTTPS control
routing/session cookies, and unsupported non-empty filters accepted by the
capture contract. The latter must reject unsupported inputs before recording
observations; the current generated suites use empty filters. These need
separate code batches, not stronger wording in the guides.
