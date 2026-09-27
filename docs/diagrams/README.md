# Architecture diagrams

Open the [diagram gallery](index.html) in a browser, or start with the [system context](rendered/01-context.svg). These seventeen views accompany the [prototype design](../prototype-design.md). The recovery views show implemented selection logic and the local deployment includes the verified S3 snapshot repository.

## Reading order

The gallery groups diagrams by task. The identifiers below remain stable.

### [System architecture](index.html#system-architecture)

| View | Contents | Editable source |
| --- | --- | --- |
| [01 · C4 system context](rendered/01-context.svg) | Lab users, platform engineers and supporting systems. | [Structurizr DSL](workspace.dsl) |
| [02 · C4 containers: control](rendered/02-control.svg) | Environment state, leases and deployment. | [Structurizr DSL](workspace.dsl) |
| [03 · C4 containers: evaluation](rendered/03-evaluation.svg) | Frozen data, snapshots, search APIs and diagnostics. | [Structurizr DSL](workspace.dsl) |
| [05 · C4 local deployment](rendered/05-local.svg) | Host control process and S3 store, k3d services and experiment workloads. | [Structurizr DSL](workspace.dsl) |
| [06 · C4 Azure deployment](rendered/06-azure.svg) | GHES, ACR, Blob Storage and AKS. | [Structurizr DSL](workspace.dsl) |

### [Environment lifecycle](index.html#environment-lifecycle)

| View | Contents | Editable source |
| --- | --- | --- |
| [04 · C4 dynamic: candidate creation](rendered/04-create.svg) | Gitea build, deployment and search readiness. | [Structurizr DSL](workspace.dsl) |
| [09 · Prepare both environments](interactive/change-to-comparison.html) | Both definitions are verified before the selected check runs. | [Archify workflow](archify/change-to-comparison.json) |
| [PR to verdict](interactive/pr-to-verdict.html) | A labelled Gitea revision resolves an exact build, two environments, four checks and PR report links. | [Archify workflow](archify/pr-to-verdict.json) |
| [08 · Reuse a frozen index](interactive/shared-index-reuse.html) | Separate definitions and APIs reference one shared index. | [Archify architecture](archify/shared-index-reuse.json) |
| [10 · Runtime lifecycle](interactive/environment-lifecycle.html) | Runtime removal retains the definition and its artifacts. | [Archify lifecycle](archify/environment-lifecycle.json) |

### [Schema and index recovery](index.html#schema-and-index-recovery)

| View | Contents | Editable source |
| --- | --- | --- |
| [Schema evolution](interactive/schema-evolution.html) | Old and new recipes drive separate indices over one frozen release. | [Archify workflow](archify/schema-evolution.json) |
| [Live-index clone](interactive/live-index-clone.html) | An exact, write-blocked live copy becomes a dedicated index. | [Archify workflow](archify/live-index-clone.json) |
| [Snapshot restore](interactive/snapshot-restore.html) | A regular snapshot restores a separate index; recipe rebuild handles failure. | [Archify workflow](archify/snapshot-restore.json) |

### [Compare search changes](index.html#compare-search-changes)

| View | Contents | Editable source |
| --- | --- | --- |
| [07 · Compare relevance](interactive/evaluation-dataflow.html) | Baseline and candidate rankings are scored against frozen judgements. | [Archify data flow](archify/evaluation-dataflow.json) |
| [11 · Verify unchanged results](interactive/result-regression.html) | Compare ordered API results, explain differences and record an exact-match verdict. | [Archify workflow](archify/result-regression.json) |
| [12 · Check API performance](interactive/performance-check.html) | Gatling replays pinned phases against each API; reports retain phase verdicts and capacity. | [Archify workflow](archify/performance-check.json) |

### [Prepare evaluation inputs](index.html#prepare-evaluation-inputs)

| View | Contents | Editable source |
| --- | --- | --- |
| [13 · Freeze traffic for replay](interactive/traffic-workload.html) | Generate synthetic pairs, select a profile and freeze the compiled schedule for both APIs. | [Archify workflow](archify/traffic-workload.json) |

The three core checks are **07 relevance**, **11 result preservation** and **12 performance**. View 09 prepares both frozen environments for any of them. View 13 prepares traffic for the performance check.

The Archify HTML files are standalone interactive viewers with theme, presentation, navigation and export controls. Static PNG previews are in `rendered/`. The C4 SVGs are scalable document assets, with a separate `-key.svg` legend for each view.

## Interpretation and scope

**Lab user** covers search engineers, ML engineers and data scientists. They share the same lab capabilities; the [design document](../prototype-design.md#goal-and-boundaries) records the overlapping roles.

- **C4 structure:** a container means a runnable application or data store, not necessarily a Docker container. The two container views are focused subsets of one model. Relationships describe calls/dependencies; arrow direction is not necessarily the direction of returned data. The Archify data-flow arrows show data movement.
- **Deployment:** these views deliberately show placement and persistence without interaction arrows. Instances refer back to the same C4 containers. Experiment boxes are templates repeated per namespace, not a fixed count or a capacity claim. Index-build, evaluation and Gatling jobs are finite. Comparison jobs span both environments and run in a separate lab-owned namespace. The Azure comparison workers reserve load-generator resources. The dataset and workload generator runs on demand to publish synthetic data, traces and compiled workloads; it is not a continuously deployed service.
- **Evaluation:** the public search API is the black-box surface. Original queries pass through query understanding, retrieval and final reranking before scoring, result comparison or performance measurement. Grey-box traces explain pipeline changes; Elasticsearch `_rank_eval`, profile and explain are optional white-box diagnostics. Collect expensive diagnostic replays separately from latency measurements. The C4 view uses one Search API container type; the Archify comparison expands it into separate baseline and candidate instances.
- **PR workflow:** the local watcher polls only open PRs carrying `lab-evaluate`; it pins the head SHA and successful build digest, then posts report links and check status. A signed webhook and build callback remain migration options, not part of the measured local path. Functional checks run in one bounded in-cluster evaluator Job per suite. The relevance report pins judgement provenance and shows unjudged IDs; it does not turn synthetic proxy scores into a quality approval.
- **Frozen environments:** each comparison records two immutable definitions, B and C. Each pins its API image, query assets/configuration, index, dataset and engine version. The workflow resolves both runtimes and checks each against its own definition before evaluation. Both receive the same frozen queries and request context; relevance scoring uses the same judgements. Reports retain both fingerprints and separate results.
- **Result regression:** the same comparison runner checks whether a change preserves final ordered product IDs for every query at a pinned depth. RBO, Jaccard and rank moves explain differences. Exact equality passes; any difference fails; missing or invalid responses make the run incomplete. This workflow needs no relevance judgements. The [design contract](../prototype-design.md#result-regression-preserve-ranking-and-membership) defines scope and edge cases.
- **Performance:** Gatling jobs replay one compiled workload against B and C sequentially, repeating three pairs with alternating order. Warm-up precedes normal, sustained-peak or stress/recovery phases. Normal/peak budgets produce phase verdicts; stress reports sustainable load, the first breach and recovery. Unstable or incomplete runs are inconclusive. Shared indices do not isolate performance. The [Gatling contract](../prototype-design.md#performance-check-the-search-api-with-gatling) defines resources, thresholds and artifacts.
- **Traffic preparation:** all queries and timestamps are synthetic. A frozen trace feeds a versioned profile recipe; compilation freezes windows, transformations, phases, request bindings and arrival buckets into one artifact used by both APIs. One-second buckets are the initial approximation; exact event timing needs a validated spike. Reports retain planned and actual arrivals. The [traffic contract](../prototype-design.md#frozen-traffic-and-workload-contract) owns these definitions.
- **Shared-index example:** the boundaries group logical environment references, not storage locations. Definitions remain in retained storage. B and C use different API images and the same pinned query assets, index, dataset and engine. Both API deployments use scoped read-only access to index i1. The dataset and index sit outside the environment boundaries. These identifiers are illustrative. A mapping change requires a separate index from the same dataset.
- **Fast creation:** API/query/ranking changes reuse a compatible read-only frozen index. Mapping/analyser changes use a dedicated index from the same immutable catalogue. When an exact recipe-marked live copy exists, the control plane can clone it. A configured, verified regular snapshot can restore a missing copy; otherwise the pinned recipe rebuilds it. Engine-version experiments need an exceptional separate cluster, omitted from the normal deployment views. A shared cluster still requires scoped credentials and contention measurements.
- **Snapshot placement:** the local S3 service runs in host Docker with its own volume, outside the Elasticsearch Pod and data PVC. This survives Elasticsearch cluster recreation on the same host. It does not survive host or Docker-volume loss. The Azure Blob snapshot container in view 06 is proposed and still requires compatibility testing.
- **Lifecycle:** the diagram shows the normal path and one representative indexing failure/retry path. It is not a complete executable state machine. Explicit deletion must also work before readiness and after failures. A ready environment has a 72-hour lease extended by genuine activity; polling does not extend it. Closing a PR does not immediately delete its environment. The same lifecycle applies independently to baseline and candidate runtimes. Active comparisons renew both leases; manual deletion cancels dependent comparison jobs. Frozen definitions, referenced images/assets, canonical datasets and reports survive removal. Recreating a runtime uses its retained definition; it may reuse or rebuild compatible index artifacts.
- **Migration:** local Gitea services and the future enterprise services fulfil the same logical source/build contracts. CI workflows, event adapters and registry migration still require work. The Azure view is a placement proposal, not a network, identity, disaster-recovery or production sizing design. The organisation's GitHub Enterprise hosting and registry remain open choices.

The [design document](../prototype-design.md) owns requirements and target values. The [DSL](workspace.dsl) owns C4 elements and relationships. Archify sources own the complementary process views; edit both when a change affects both. Component-level C4 diagrams should follow the implementation's actual module boundaries once those exist.

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

   This validates the DSL, exports the model, applies [presentation layout](layout.mjs), renders six C4 SVGs and PNG inspection copies, validates and delivers ten Archify HTML files, and captures browser evidence and static previews. It stops on a failing command. If Chrome is unavailable, omit `--browser` to render sources; browser receipts and preview PNGs then remain from their previous run and must be treated as stale until hashes match.

   For a focused rebuild, use `--c4` or `--archify`, optionally with `--browser`. The script checks the Archify commit before use. Docker pulls the pinned Structurizr image when missing. A Docker connection failure means the daemon must be started before retrying.

3. Inspect the results before committing. C4 PNGs are in the ignored `qa/c4/` directory; Archify screenshot/contact-sheet sidecars are beside the interactive files and ignored. Check long labels, boundaries, arrow routing and both themes. Record perceptual review separately from automated checks.

The Node entry point avoids shell-specific build commands. It has been exercised on Windows x64; Apple silicon execution remains a portability check. Structurizr exports include generation timestamps, so byte-identical SVGs are not promised across runs. Archify receipts bind each specification and HTML file by SHA-256. Presentation layout does not change the architectural model; it selects focused relationships and assigns positions. Regenerate exports rather than editing SVG or HTML directly.

## Validation and provenance

The initial batch passed Structurizr validation and rendering for six C4 views. Each Archify artifact passed 9/9 showcase checks with zero errors and warnings, plus desktop browser checks at 1440×900, 1600×1000, 1920×1080 and 2048×1320. These checks validate the diagrams, not system behaviour. The [visual review record](receipts/visual-review.json) identifies the reviewed artifacts separately from the generated delivery and browser receipts.

Useful upstream references: [Structurizr DSL](https://docs.structurizr.com/dsl/language), [local binaries](https://docs.structurizr.com/binaries), [PNG/SVG export](https://docs.structurizr.com/export/png-and-svg) and [Archify](https://github.com/tt-a1i/archify). Archify's [MIT licence](notices/Archify-LICENSE.txt) and [third-party notices](notices/Archify-third-party.md) accompany the generated viewer code. No external brand marks are selected in these diagrams.
