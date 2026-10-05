# Architecture diagrams

Open the [diagram gallery](index.html) in a browser, or start with the [system context](rendered/01-context.svg). These twenty-five views accompany the [prototype design](../prototype-design.md). The recovery views show implemented selection logic and the local deployment includes the verified S3 snapshot repository.

## Reading order

The local deployment places browser ingress in `lab-ingress`, control services
in `lab-control`, ESO in `lab-secrets` and SigNoz on a dedicated worker. The
[optional NVIDIA worker](../gpu-worker.md) serves qualified CUDA models; omit it
on Apple silicon. The CPU judgement API and registry remain available. The
[current operating guides](../../lab/README.md) explain access and procedures;
the [roadmap](../plans/roadmap.md) records measured proofs and remaining checks.

The gallery groups diagrams by task. The identifiers below remain stable.

### [System architecture](index.html#system-architecture)

| View | Contents | Editable source |
| --- | --- | --- |
| [01 · C4 system context](rendered/01-context.svg) | Lab users, platform engineers and supporting systems. | [Structurizr DSL](workspace.dsl) |
| [02 · C4 containers: control](rendered/02-control.svg) | Environment state, leases and deployment. | [Structurizr DSL](workspace.dsl) |
| [03 · C4 containers: evaluation](rendered/03-evaluation.svg) | API capture, shared index, workloads, optional exploratory notebook and diagnostics. The context view shows independent input and scoring owners. | [Structurizr DSL](workspace.dsl) |
| [05 · C4 local deployment](rendered/05-local.svg) | HTTPS ingress, Kubernetes control Pod, ESO, locally emulated Azure Key Vault, SigNoz, Headlamp, host Nexus/PostgreSQL and S3 storage. | [Structurizr DSL](workspace.dsl) |
| [09 · C4 identity](rendered/09-identity.svg) | Keycloak, group permissions, application sign-in and control API verification. | [Structurizr DSL](workspace.dsl) |
| [07 · C4 preview access](rendered/07-preview.svg) | CoreDNS, HTTPS ingress and namespace-scoped preview routing. | [Structurizr DSL](workspace.dsl) |
| [06 · C4 Azure deployment](rendered/06-azure.svg) | Ingress, GHES, Nexus, optional ACR, Blob Storage, Key Vault, AKS and OTel collection. | [Structurizr DSL](workspace.dsl) |

### [Observe lab activity](index.html#observability)

| View | Contents | Editable source |
| --- | --- | --- |
| [Investigate an SLO breach](interactive/observability-investigation.html) | Follow a search or operation through collection, SLO counts, trace/log correlation and frozen evidence. | [Archify workflow](archify/observability-investigation.json) |

### [Release delivery](index.html#release-delivery)

| View | Contents | Editable source |
| --- | --- | --- |
| [18 · C4 release delivery](rendered/18-delivery.svg) | Build, artefact verification, reviewed state, Argo deployment and API verification. | [Structurizr DSL](workspace.dsl) |
| [19 · Promote a release](interactive/release-promotion.html) | Frozen baseline/candidate checks, three targets and full-definition rollback. | [Archify workflow](archify/release-promotion.json) |

### [Environment lifecycle](index.html#environment-lifecycle)

| View | Contents | Editable source |
| --- | --- | --- |
| [04 · C4 dynamic: candidate creation](rendered/04-create.svg) | Gitea build, deployment and search readiness. | [Structurizr DSL](workspace.dsl) |
| [09 · Prepare both environments](interactive/change-to-comparison.html) | Both definitions are verified before the selected check runs. | [Archify workflow](archify/change-to-comparison.json) |
| [PR to verdict](interactive/pr-to-verdict.html) | A labelled Gitea revision resolves an exact build, two environments, four checks and PR report links. | [Archify workflow](archify/pr-to-verdict.json) |
| [08 · Reuse a frozen index](interactive/shared-index-reuse.html) | Separate definitions and APIs reference one shared index. | [Archify architecture](archify/shared-index-reuse.json) |
| [10 · Runtime lifecycle](interactive/environment-lifecycle.html) | Runtime removal retains the definition and its artefacts. | [Archify lifecycle](archify/environment-lifecycle.json) |

### [Schema and index recovery](index.html#schema-and-index-recovery)

| View | Contents | Editable source |
| --- | --- | --- |
| [Schema evolution](interactive/schema-evolution.html) | Old and new recipes drive separate indices over one frozen catalogue. | [Archify workflow](archify/schema-evolution.json) |
| [Live-index clone](interactive/live-index-clone.html) | An exact, write-blocked live copy becomes a dedicated index. | [Archify workflow](archify/live-index-clone.json) |
| [Snapshot restore](interactive/snapshot-restore.html) | A regular snapshot restores a separate index; recipe rebuild handles failure. | [Archify workflow](archify/snapshot-restore.json) |

### [Compare search changes](index.html#compare-search-changes)

| View | Contents | Editable source |
| --- | --- | --- |
| [07 · Compare relevance](interactive/evaluation-dataflow.html) | Every named variant produces retained API observations; an independent evaluator scores them against one selected judgement set. | [Archify data flow](archify/evaluation-dataflow.json) |
| [Variant merge gate](interactive/variant-merge-gate.html) | Match signed evidence to the selected source build, then record any bounded human exception. | [Archify workflow](archify/variant-merge-gate.json) |
| [Resolve judgement gaps](interactive/judgement-coverage.html) | Pool all returned pairs, ask the pinned model about missing labels, then freeze and score one set. | [Archify workflow](archify/judgement-coverage.json) |
| [Qualify judgement labels](interactive/label-qualification.html) | Disjoint development and confirmation cohorts, frozen class thresholds and eligibility review. | [Archify workflow](archify/label-qualification.json) |
| [11 · Verify unchanged results](interactive/result-regression.html) | Compare ordered API results, explain differences and record an exact-match verdict. | [Archify workflow](archify/result-regression.json) |
| [12 · Check API performance](interactive/performance-check.html) | Gatling replays pinned phases against each API; reports retain phase verdicts and capacity. | [Archify workflow](archify/performance-check.json) |

### [Prepare evaluation inputs](index.html#prepare-evaluation-inputs)

| View | Contents | Editable source |
| --- | --- | --- |
| [13 · Freeze traffic for replay](interactive/traffic-workload.html) | Generate synthetic pairs, select a profile and freeze the compiled schedule for both APIs. | [Archify workflow](archify/traffic-workload.json) |

The three core checks are **07 relevance**, **11 result preservation** and **12 performance**. View 09 prepares both frozen environments for any of them. View 13 prepares traffic for the performance check.

The Archify HTML files are standalone interactive viewers with theme, presentation, navigation and export controls. Static PNG previews are in `rendered/`. The C4 SVGs are scalable document assets, with a separate `-key.svg` legend for each view.

## Interpretation and scope

**Lab user** covers search engineers, ML engineers and data scientists with shared
lab capabilities. These overlapping roles are not access boundaries.

### Read the boundaries

| View convention | Meaning |
| --- | --- |
| C4 container | Runnable application or data store, not necessarily a Docker container |
| C4 relationship | Call or dependency; returned data can travel the other way |
| Archify data-flow arrow | Direction of data movement |
| Deployment instance | Placement/persistence of a C4 container; experiment boxes repeat per namespace |
| Shared-index boundary | Logical environment references, not ownership of the physical catalogue/index |
| Azure deployment | Proposed placement, not validated cloud networking, identity, sizing or disaster recovery |

Index, capture, scoring, load and notebook Jobs are finite. Producers publish on
demand; they are not continuously running catalogue services. Comparison Jobs
operate in lab-owned namespaces across participating environments. Azure load
generators reserve separate resources; the local host still shares resources.

### Workflow limits

- **Frozen comparisons:** A pairwise workflow verifies B and C definitions.
  N-way relevance capture verifies every named variant, with one required default
  and one metric baseline. Each pins image/configuration, index, catalogue and
  engine; the execution selects one frozen request suite. Compatible elements
  may be reused without merging the identities.
- **Relevance:** Final public API rankings are the black-box scoring surface.
  All selected recall sets can be pooled for missing judgements. Published labels
  take precedence. Model passes retain distinct provenance; exploratory selection
  may include unqualified predictions, while gate selection excludes them. The
  calibrated model labels or abstains. Freeze one selection before scoring every variant.
- **Diagnosis:** Grey-box records explain implemented pipeline stages; absent
  stages are unavailable. `_rank_eval`, profile, explain and analyser checks are
  component diagnostics. Collect costly replays separately from latency runs.
- **Result preservation:** Exact ordered top-10 equality determines unchanged
  results. RBO/Jaccard explain differences; incomplete responses cannot pass.
  Relevance judgements are unnecessary for this verdict.
- **Performance:** Gatling replays a frozen workload sequentially against B/C,
  normally three pairs in alternating order. Warm-up is excluded from measured
  percentiles. Normal/peak budgets, stress limits and recovery have separate
  outcomes. Unstable load or missing evidence is inconclusive; sharing an index
  does not isolate latency.
- **Traffic:** Queries come from the selected frozen ESCI suite; timestamps and frequencies are synthetic. Compilation pins windows,
  transformations, phase/request binding and arrival buckets. One-second buckets
  approximate source timing; exact event replay needs separate validation.
- **Lifecycle:** Diagrams show representative paths, not executable state
  machines. A leased runtime expires after 72 hours without genuine activity;
  polling does not extend it. Removal cancels dependent work but retains
  definitions, inputs and reports. Delivery targets do not expire.
- **Recovery:** Compatible API changes reuse indices; mappings create distinct
  recipes. Recovery selects exact reuse, live clone, regular snapshot, then
  pinned rebuild. Engine changes use a separate cluster. Host S3 survives
  Elasticsearch recreation but not host/volume loss.
- **PR workflow:** The local watcher polls opted-in `lab-evaluate` PRs and pins
  the exact successful build. Tool completion/status is not a relevance approval.
  Signed webhooks remain a migration option.
- **Release delivery:** Nexus retains immutable releases. Protected desired-state
  PRs require fresh, matching evidence and review. Argo deploys; the coordinator
  verifies the API. The three local targets share a cluster; a short Gatling
  delivery probe is not capacity evidence.
- **Human decisions:** Selected-variant evidence is bound to its source build.
  A bounded exception retains the reason and exact-head human approval in a Git decision PR. The coordinator signs its merged record without changing scores.
  Hard blocks remain blocked; source acceptance does not authorise deployment.

The [design](../prototype-design.md) owns requirements and targets. The
[variant guide](../variant-evaluation.md), [recovery guide](../index-recovery.md)
and [Gatling guide](../../lab/gatling/README.md) own the executable workflows.
The DSL owns C4 elements/relationships; Archify JSON owns process views. Edit
both sources when their represented relationship changes. This editorial review
changes explanations, not the model or rendered topology.

## Rebuild

Prerequisites: Node.js, Git, a working Docker daemon with Linux containers and, for Archify browser evidence, Chrome/Chromium. Run the commands from the repository root. Initial tool/image downloads need internet access; rendering uses local files. Tool versions are pinned in [tooling.json](tooling.json).

1. Fetch the pinned Archify checkout once. It stays inside the ignored `.diagram-tools` directory and requires no global skill installation or npm dependencies:

   ```sh
   git clone https://github.com/tt-a1i/archify.git .diagram-tools/archify
   git -C .diagram-tools/archify checkout 9e35d2b0b39b155553ba9fcfe0b4f2a5198dd993
   ```

2. Render and validate everything:

   ```sh
   node docs/diagrams/render.mjs --browser
   ```

   This validates the DSL, exports the model, applies [presentation layout](layout.mjs), renders nine C4 SVGs and PNG inspection copies, validates and delivers sixteen Archify HTML files, and captures browser evidence and static previews. It stops on a failing command. If Chrome is unavailable, omit `--browser` to render sources; browser receipts and preview PNGs then remain from their previous run and must be treated as stale until hashes match.

   For a focused rebuild, use `--c4` or `--archify`, optionally with `--browser`. The script checks the Archify commit before use. Docker pulls the pinned Structurizr image when missing. A Docker connection failure means the daemon must be started before retrying.

3. Inspect the results before committing. C4 PNGs are in the ignored `qa/c4/` directory; Archify screenshot/contact-sheet sidecars are beside the interactive files and ignored. Check long labels, boundaries, arrow routing and both themes. Record perceptual review separately from automated checks.

The Node entry point avoids shell-specific build commands. It has been exercised on Windows x64; Apple silicon execution remains a portability check. Structurizr exports include generation timestamps, so byte-identical SVGs are not promised across runs. Archify receipts bind each specification and HTML file by SHA-256. Presentation layout does not change the architectural model; it selects focused relationships and assigns positions. Regenerate exports rather than editing SVG or HTML directly.

## Validation and provenance

The retained rendering receipts record Structurizr validation for nine C4 views. Each recorded Archify artefact passed 9/9 showcase checks with zero errors and warnings, plus desktop browser checks at 1440×900, 1600×1000, 1920×1080 and 2048×1320. These checks validate the diagrams, not system behaviour. The [visual review record](receipts/visual-review.json) identifies the reviewed artefacts separately from the generated delivery and browser receipts.

Useful upstream references: [Structurizr DSL](https://docs.structurizr.com/dsl/language), [local binaries](https://docs.structurizr.com/binaries), [PNG/SVG export](https://docs.structurizr.com/export/png-and-svg) and [Archify](https://github.com/tt-a1i/archify). Archify's [MIT licence](notices/Archify-LICENSE.txt) and [third-party notices](notices/Archify-third-party.md) accompany the generated viewer code. No external brand marks are selected in these diagrams.
