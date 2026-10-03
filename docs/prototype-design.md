# Ephemeral search relevance lab: prototype design

## Goal and boundaries

An engineer or data scientist can create a search environment from a frozen dataset, change query/ranking behaviour or index design, compare it with a known baseline, and remove or recreate it on demand. The lab runs locally on Kubernetes and should have a clear path to self-managed Elasticsearch on Azure Kubernetes Service (AKS).

For the lab, **Lab user** covers search engineers, ML engineers and data scientists with the same workflow and capabilities. Search engineering includes relevancy and general software engineering; data science includes ML engineering and data science. These roles overlap and do not define ownership or access boundaries.

The local demonstration covers the complete source-to-disposal lifecycle. It uses a self-hosted Gitea instance for repositories, pull requests and build automation, with Nexus for new delivery artefacts; no external Git provider is required for the core workflow. The eventual target uses GitHub Enterprise. Provider-specific authentication, event payloads and status reporting must therefore sit behind a small integration boundary.

| Scope | Required scale |
| --- | --- |
| Default catalogue | 1,215,854 English ESCI products; 1,000 test queries |
| Optional demo subset | Configurable; initially 10,000 products and 50 test queries |
| Local demonstration | Two or three concurrent environments |
| Control-plane validation | Evidence for at least 40 concurrent environments |

Forty environments are a design and scale-validation requirement, not a promise that one laptop can host forty full copies of Elasticsearch or the catalogue.

Experiments may change the search API, its query-understanding pipeline, Elasticsearch queries and ranking, mappings or the engine version.

The core checks are **relevance**, **result preservation** and **performance**. Pairwise checks compare two frozen definitions through their public APIs; N-way relevance evaluation compares every named variant with its selected baseline. Each mode retains its own verdict.

Provisional first-slice targets on a warm local cluster:

- Create an API, query-understanding or ranking-only environment against an existing frozen index in **p50 ≤ 60 seconds and p95 ≤ 120 seconds**.
- Create an index-changing environment, including reindexing the selected demo catalogue (initially 10,000 products), in **p95 ≤ 5 minutes**.
- Go from an accepted Gitea pull-request update through tests, image build and deployment to the first correct candidate search in **p95 ≤ 8 minutes**.
- Remove an environment on demand, including its dedicated index where applicable, in **p95 ≤ 5 minutes**.
- Publish a cached CI release in **under 5 minutes**, and verify an approved promotion or rollback in **under 2 minutes** with retained artefacts and a warm compatible index. Promotion performs **zero rebuilds**.
- Preserve identical ordered top-10 product IDs for every frozen query after a behaviour-preserving change.
- Sustain **10 search requests/second** for five measured minutes per side with **p95 ≤ 250 ms**, **p99 ≤ 500 ms** and **< 1% failed requests**, under the constant-rate Gatling smoke profile below. Trace-derived normal, peak and stress profiles have separate durations and budgets.

These remain provisional acceptance targets. The [platform research](research/platform-spike.md) measured warm creation at p50 7.54 seconds / p95 8.16 seconds over 20 diagnostic trials. The [roadmap](plans/roadmap.md) links later million-product, lifecycle, 40-environment and delivery measurements; a single successful run does not establish p95. The detailed target table defines their conditions.

This is a relevance lab, not a production commerce platform. Products, queries and labels use published ESCI data, enriched with ESCI-S metadata. Prices retain their numeric USD amount but use GBP; missing prices, stock and popularity use documented lab assumptions. Traffic timing is synthetic. Source hashes and augmentation rules travel with each frozen release. See [catalogue setup](esci-catalogue.md).

## Architecture

The local reference runs on Kubernetes. The [diagram gallery](diagrams/index.html) contains eight Structurizr C4 views and fifteen Archify views; [the diagram guide](diagrams/README.md) identifies their sources and scope. Azure placement remains proposed.

![C4 system context: lab users and supporting platforms](diagrams/rendered/01-context.svg)

| Responsibility | Component | Lab code/boundary |
| --- | --- | --- |
| Kubernetes | k3d; kind was also tested in the original research | Bootstrap and capacity settings; native Apple silicon still needs verification |
| Elasticsearch | Self-managed cluster managed by ECK | Recipe-addressed indices, scoped credentials and a separate-cluster path for engine changes |
| Deployment | Argo CD Git-file ApplicationSets and Helm | Publish reviewed desired state with bounded conflict retries |
| Environment control | UI/API, lease worker, PR watcher and delivery coordinator in `lab-control` | One active Pod, persistent SQLite state and writer coordination; host bootstrap/recovery |
| Source/build | Gitea Actions and runner; Nexus images, bundles and receipts | Provider-specific API/status calls; a common Actions subset for later GHES verification |
| Frozen inputs/reports | Azure Blob Storage (Floci emulator in the lab) | Independent producer contracts and immutable hashes |
| Index snapshots | SeaweedFS S3 on host Docker with its own volume | Regular snapshots, separate from Elasticsearch data PVCs and environment leases |
| Judgement supply | Separate API, MLflow registry and KServe Standard | Stored labels first; pinned inference for gaps; the default model abstains |
| Scoring | Independent evaluator using established IR metrics | Frozen API observations, selected labels/specification, per-variant reports |
| Performance | Gatling open-source Java SDK in finite Jobs | Compiled arrival workloads, paired runs and validity/budget comparison |
| Exploratory analysis | Papermill notebook Job | Selected notebook consumes the retained report; output cannot change the verdict |
| Observability | OTel SDKs/Collector, scoped stdout collection and SigNoz | Connected signals and dashboards; New Relic exporter/query migration boundary |

Argo CD owns declared environment workloads. The control service owns leases,
comparison records and desired-state publication. Kubernetes Jobs perform bounded
indexing, capture, scoring, load tests and notebook execution. Add another workflow
engine or queue only when measured retries, fan-out or contention justify it.

| View | Question |
| --- | --- |
| [Control containers](diagrams/rendered/02-control.svg) | Who owns environment state and deployment? |
| [Evaluation containers](diagrams/rendered/03-evaluation.svg) | How do independent inputs reach capture and scoring? |
| [Local deployment](diagrams/rendered/05-local.svg) | Which services persist and where do Jobs run? |
| [Release delivery](diagrams/rendered/18-delivery.svg) | How does reviewed state reach a verified API? |
| [Azure deployment](diagrams/rendered/06-azure.svg) | Which local boundaries map to future cloud services? |

### Source and release lifecycle

1. The engineer changes the Search API, configuration or index contract in Gitea.
2. CI tests the exact source revision and publishes immutable Nexus images,
   bundles, descriptors and a build receipt.
3. Leased experiments select an exact successful build and frozen index recipe.
   Argo reconciles the API and any indexing work; the control service verifies readiness.
4. A comparison verifies all participating definitions, captures public API
   results and retains its mode-specific report. Optional analysis runs afterwards.
5. The source merge gate checks exact-commit signed evidence. A bounded human
   exception records the decision and reason; it does not edit scores.
6. After source merge, a separate build produces the merged-source release.
   Reviewed desired-state PRs promote its same digest through integration,
   staging and simulated production. Argo deploys; the coordinator verifies.
7. Rollback selects the previous complete definition and fresh reverse-direction
   evidence. Leased previews can be deleted or expire; stable targets do not expire.

See [delivery](delivery.md), [variants and decisions](variant-evaluation.md) and
[the operator runbook](evaluation-runbook.md) for executable procedures. A passing
source check does not itself approve a deployment. The three targets share one
local cluster; they are not separate failure domains.

Gitea is the primary remote; GitHub is an offsite backup. Dataset bytes belong in
object storage, not Git. The original `search-spike` path uses retained Gitea
registry builds; new reference delivery uses Nexus. Images and input artefacts
must survive runtime deletion for recreation to work.

### Isolation and platform selection

| Change | Runtime/index approach |
| --- | --- |
| API/query/ranking | Separate API namespace/credentials; reuse a compatible read-only frozen index |
| Mapping/analyser | Dedicated index from the same immutable products and a new recipe |
| Elasticsearch engine | Exceptional separate cluster; slower creation and another licensed cluster where licences are required |

Namespaces do not isolate Elasticsearch data or performance. Index-level roles,
scoped credentials, network policy and resource settings enforce the normal
boundary. Shared-cluster contention must be measured before interpreting latency.
The lab does not need document-level security or searchable snapshots.

The implemented Argo-native approach follows the [platform research](research/platform-spike.md).
[Okteto/Uffizzi](research/okteto-uffizzi.md) and
[Lifecycle/Signadot/Coolify](research/lifecycle-signadot-coolify.md) remain dated
selection studies, not installation choices still awaiting a decision. A future
Lifecycle fork could replace some lab control code only after demonstrating
Gitea integration, the lease policy and single Argo deployment ownership.

[ADR-0001](adr/ADR-0001-reconcile-environments-from-git.md) records Git-file
reconciliation. Its recorded formal status remains Proposed; the implementation
has adopted the approach. The [ADR index](adr/README.md) distinguishes those facts.
Licensing terms and permitted production features require organisational review;
sharing indices reduces cluster count, not contractual uncertainty.

### Azure boundary

| Local contract | Eventual service | Remaining validation |
| --- | --- | --- |
| Azure Blob Storage (Floci emulator): datasets, traffic, workloads and runs | Azure Blob Storage | Workload Identity, read authorisation and immutable publication |
| Azure Key Vault (Floci emulator) → adapter → ESO → Kubernetes Secrets | Azure Key Vault → ESO Azure provider → the same Secret targets | Real identity, permissions and rotation; [secret guide](keyvault-secrets.md) |
| Traefik and local CA | AKS ingress and certificate issuer | Certificate trust, route and client verification |
| Gitea APIs/Actions/statuses | GitHub Enterprise | Runner labels, event/status API mapping and branch protection |
| Nexus | Nexus; ACR optional | Registry transport and target infrastructure |
| Regular S3 snapshots | Azure Blob snapshot repository | Repository compatibility and restore timings |
| SigNoz behind OTel gateway | New Relic behind OTel gateway | Tenant ingestion, temporality/resets, dashboards and connected investigation |

Floci's tested Blob path is useful for the lab. Its snapshot API failed
Elasticsearch repository verification; it is not the working snapshot store.
The Key Vault adapter models secret retrieval, not Azure identity enforcement.
Bootstrap exceptions remain explicit.

Traefik exposes Gitea, Argo CD, control, SigNoz, Nexus and Headlamp browser routes through
local HTTPS. The control canonical-URL redirect and non-`Secure` session cookie
remain an implementation gap; [HTTPS operation](https-ingress.md) records the
actual boundary. Native Apple silicon and Azure/GHES execution remain unverified.

## Frozen dataset contract

Catalogues, query suites, judgements and traffic have independent manifests.
An environment pins software, catalogue and index inputs. An execution pins
requests and workload; evaluation pins observations, labels and metric specification.
Producer and evaluator Jobs use separate images and contracts. Rescoring retained
observations does not search again or rebuild an index. The
[input contract](data-evaluation-contracts.md) owns the canonical schemas.

Each independent input has a content-addressed object and manifest. A source pack groups inputs for import and provenance; an environment pins the catalogue and index recipe, while an evaluation separately pins queries and judgements. Source metadata records:

- Source revisions/checksums, importer hash, selection rules and deterministic augmentation seeds.
- Schema version, country `GB`, source locale `en-US` and currency `GBP`.
- Product and query counts; file paths, byte sizes and SHA-256 hashes.
- Source field provenance and any generated prices, stock or popularity assumptions.
- Original query text/context, selected test split, published graded labels and known coverage limits. Keep original input separate from any API-produced normalisation or rewrite.
- Optional synthetic click, add-to-basket and purchase events with an explicit behavioural model.

The default importer preserves English ESCI product text, queries and labels, and joins ESCI-S metadata by ASIN and source market. [The source lock](../data/esci-sources.json) pins revisions and checksums. Missing prices and stock use the documented [lab rules](esci-catalogue.md).

Product and release rules:

- **Product fields:** Product records have stable IDs and realistic fields: title, description, brand, category hierarchy, attributes, price with currency, availability, popularity and country.
- **Price and market:** Prices are integer minor units. Country and currency remain explicit fields even though the first release is UK/GBP.
- **Determinism:** Fixed time and seed prevent stock, promotions and popularity from drifting between runs.
- **Release immutability:** The importer must not regenerate a release in place: a changed input produces a new manifest and hashes.

Query and judgement rules:

- **Query coverage:** Use a mixture of common head queries, long-tail attribute queries, category browsing, misspellings, synonyms, ambiguous terms and zero-result cases.
- **Judgements:** Judgements are graded and keyed by query ID and product ID. Record published label provenance and any inferred label lineage; offline agreement does not establish customer benefit.
- **Held-out evaluation:** Keep a held-out query subset so tuning against the visible set does not silently become the only reported outcome.

| Frozen index identity | Pinned inputs |
| --- | --- |
| Recipe | Catalogue manifest/product bytes, full mapping/settings, expected count, indexer source/image and Elasticsearch version |
| Environment | Recipe, API image/configuration and source identities; its fingerprint identifies the complete definition |
| Snapshot | One index, recipe/product hashes, engine version and ordered ID sample; no restored global state or aliases |

A schema change produces a new recipe and index name. It cannot overwrite the
historical definition. API-only candidates reuse a compatible index; mapping
experiments use dedicated indices.

Recovery selects **verified reuse → exact live clone → compatible regular
snapshot → pinned rebuild**. Remove a partial failed clone/restore before rebuild.
The API binds only after count, mapping/settings, write block and ordered sample
checks. The [recovery guide](index-recovery.md) owns the procedure and diagnostics.

Snapshots survive the 72-hour environment lease. They accelerate restoration;
the immutable products and recipe remain authoritative. The local `lab-s3`
repository has passed verification, but its host-local volume is not an offsite
backup. Engine/snapshot version compatibility and Azure restoration remain
separate checks. [Recovery diagrams](diagrams/index.html#schema-and-index-recovery)
show schema evolution, clone and snapshot paths.

### Frozen traffic and workload contract

| Artifact | Purpose |
| --- | --- |
| **Traffic trace** | Records synthetic query/timestamp pairs |
| **Profile recipe** | Selects and transforms the trace |
| **Compiled workload** | Binds the requests, arrival schedule and phases that Gatling will execute |

Each is versioned independently of the frozen catalogue, references its inputs by hash and survives environment deletion.

![Synthetic traffic is frozen, transformed into a workload and replayed against baseline and candidate](diagrams/rendered/traffic-workload.png)

The traffic compiler assigns synthetic timestamps and frequencies to selected ESCI queries. Recipes cover head/long-tail frequency, repeated queries, bursts, quiet periods and peak load. It preserves query text and request context. A future generator may use approved aggregate traffic statistics as modelling inputs; the lab does not ingest production request records.

A trace contains stable event IDs, elapsed arrival offsets, query IDs and request context. An illustrative event is:

```json
{"event_id":"e000042","offset_ms":190,"query_id":"q0017","country":"GB","currency":"GBP"}
```

- **Request binding:** Query IDs resolve to frozen original text and market context. Caller filters follow the [Search API filter contract](search-request.md) and are forwarded unchanged to every variant. Capture verifies the echoed filters. Pagination remains outside the request contract.
- **Ordering:** Preserve duplicate queries and simultaneous events; event ID breaks equal-timestamp ties deterministically.
- **Validation:** Validate non-negative ordered offsets and all query references.
- **Counts:** Record both unique query count and event count: 1,000 unique queries may produce many more load-test requests.
- **Model limits:** Pairs alone do not establish sessions, personalisation or navigation; additional behaviour needs its own documented synthetic model.

| Artifact | Pinned inputs and output |
| --- | --- |
| Trace manifest | Generator revision, schema, seed, duration, event count, catalogue/query hashes and distribution assumptions |
| Profile recipe | Source windows, phase boundaries, warm-up policy, scaling method, duration, bucket width, connection policy, timeouts, budgets and stop conditions |
| Compilation | Compiler version and seed; immutable request data, per-phase arrivals and a manifest with hashes written to `workloads/` |

Both B and C receive exactly the same compiled artefact; neither samples or regenerates traffic during the run.

- **Clock:** Use offsets from a monotonic run/phase start to schedule requests. The fixed business clock used for catalogue state remains a separate input.
- **Initial scheduling:** A timestamp in a Gatling feeder supplies data; it does not schedule traffic. Initially compile one-second buckets into Gatling open injection steps and phase-specific feeder data, preserving bucket counts and query mix with a deterministic within-bucket order and placement.
- **Event binding:** Bind each planned arrival to an event ID and request before dispatch; concurrent feeder consumption must not silently move queries between phases or buckets. Validate this binding in the implementation spike.
- **Gatling interfaces:** Gatling provides [feeders](https://docs.gatling.io/concepts/session/feeders/) and [open injection profiles](https://docs.gatling.io/concepts/injection/); preparation supplies their shared schedule.

Replay accuracy and limits:

- **Approximation:** Bucket replay approximates the source trace and can smooth sub-second bursts.
- **Timing evidence:** Record source-to-compiled timing changes separately from compiled-to-actual scheduling error. Compare source, compiled and observed arrival counts, query frequencies and repeat intervals.
- **Finer timing:** Reduce the bucket width when a profile depends on shorter bursts. Event-timed replay is a later option, gated by a scheduling-accuracy and generator-overhead spike; it is not a capability claimed by the initial design.
- **Late arrivals:** Late arrivals remain visible, and a pinned lateness rule marks an unreliable run inconclusive rather than silently dropping requests or dispatching a catch-up burst.

## Environment lifecycle and API

Each participating runtime follows the [environment lifecycle](diagrams/interactive/environment-lifecycle.html): provisioning, frozen-index reuse, representative failure/retry and disposal. Its scope notes are in the [diagram guide](diagrams/README.md#interpretation-and-scope).

- **Request inputs:** An environment request names a dataset release, search API image digest, query-understanding asset and configuration revisions, ranking configuration, index design revision and, normally, the shared Elasticsearch version.
- **Frozen definition:** The immutable environment definition pins these inputs; its fingerprint identifies an exact build. Store that definition with the retained artefacts.
- **Runtime instance:** A running namespace is an instance of the definition, with its own state and lease.
- **Safe reuse:** Creating the same fingerprint twice should be safe and reuse existing immutable index artefacts where possible.
- **Metadata:** A namespace label and metadata record carry the owner, fingerprint and expiry.

States: `requested` → `provisioning` → `indexing` → `ready`; any active state may become `failed` or `deleting`.

- **Deletion:** `deleted` is terminal for that runtime instance. Its frozen definition, referenced images and query assets, canonical dataset and saved reports persist.
- **Recreation:** A new request can name a retained recipe SHA-256 from a previous environment. The lab loads the complete recipe from Blob storage and rebuilds a missing index from its pinned catalogue and indexer. A shared index with a conflicting schema fails closed; dedicated indices can coexist under separate names.
- **State evidence:** The API exposes errors and timings for every state transition.

Current control endpoints (authenticated unless noted):

| Endpoint | Purpose |
| --- | --- |
| `GET /api/datasets` | List immutable releases and their manifests |
| `POST /api/environments` | Create or reuse an environment from a release and revisions |
| `GET /api/environments` and `GET /api/environments/{id}` | List state, URL, timings and expiry |
| `DELETE /api/environments/{id}` | Remove an environment on demand |
| `POST /api/environments/{id}/activity` | Record genuine use and extend expiry |
| `GET /api/environments/{id}/search` | Proxy the small search API for the UI |
| `POST /api/comparisons` and `GET /api/comparisons/{id}` | Run and inspect a baseline/candidate comparison; pin mode (`relevance`, `result-regression` or `performance`); performance also pins recipe and compiled-workload hashes |

- **Lease:** Expiry starts 72 hours after creation. Genuine activity extends it to 72 hours after the last use; passive health checks and background polling do not.
- **Cleanup:** The continuously running lease worker scans leases, marks expired environments for deletion, removes their namespaced resources and credentials, and reconciles partial failures. Manual deletion uses the same idempotent cleanup path.
- **Job TTL:** Deleting a completed Kubernetes Job with `ttlSecondsAfterFinished` is separate from the environment lease; that native TTL does not expire namespaces or long-running Deployments. See [Kubernetes Job TTL](https://kubernetes.io/docs/concepts/workloads/controllers/job/).

Shared immutable indices may outlive one environment while another uses them. Reference counts must be derived from live environment records before deleting an index. The first implementation may retain shared baseline indices until an explicit garbage-collection operation, provided it reports their storage use.

## Search and comparison

| Mode | Decision | Evidence |
| --- | --- | --- |
| [Relevance](diagrams/interactive/evaluation-dataflow.html) | Does the candidate improve judged search relevance? | Final API rankings scored against frozen judgements; per-query gains and losses |
| [Result preservation](diagrams/interactive/result-regression.html) | Did ordering or membership change? | Exact ordered-ID equality; RBO, Jaccard and rank moves |
| [Performance](diagrams/interactive/performance-check.html) | Does the candidate meet the load profile and performance budgets? | Gatling latency, throughput, failed requests and repeatable B/C deltas |

![Named frozen variants produce public API results for one evaluator](diagrams/rendered/evaluation-dataflow.png)

A pairwise check names frozen baseline B and candidate C definitions. N-way relevance capture names two or more variants, one required runtime default and one metric baseline; default and baseline may differ. Each participating definition pins its API image/configuration, index, catalogue and engine. Verify every runtime against its own definition before capture. Variants can share one deployment or compatible index; shared resources do not merge their identities.

The local control UI offers a **quick** 50-query result preflight and a **full** frozen suite. An in-cluster evaluation Job sends each request through both public APIs, records the ordered responses and cleans up after a bounded run. The query inspector shows changed queries, largest relevance losses, ordered results and selected diagnostic records. The complete content-addressed report remains downloadable. A labelled Gitea PR can trigger this sequence against an exact successful build; the [PR-to-verdict workflow](diagrams/interactive/pr-to-verdict.html) shows the local polling, two environments, checks and report links. The PR status reports tooling completion, while relevance interpretation remains a review decision.

Both APIs receive the same frozen original queries and request context. Relevance comparisons score their final results against the same frozen judgements; result-regression comparisons check whether those results changed; performance comparisons replay the same workload separately against each API. The comparison record retains both definition fingerprints, runtime IDs, evaluation-input hashes, responses and diagnostics. Creating a comparison must not silently substitute the latest baseline or candidate.

For standalone variant evaluation, capture every named Search API result list before resolving judgements. The variant set requires one runtime default and one evaluation baseline; they may differ. Pool distinct query–product pairs across all variants through the deepest metric cut-off. The independent judgement service returns stored published labels first and asks a pinned MLflow model served by KServe about gaps. The default model abstains on every gap. Exploratory passes can add predictions from other pinned models while preserving each source, version, policy and confidence. Published labels take precedence. Gate selection excludes unqualified predictions; exploratory selection can use them. Freeze the selected judgement set and attempt receipt, then score every variant against that one set. A changed recall set gets a new snapshot and report. An abstention is unknown, whereas `I` is an explicit irrelevant judgement. [The contract](judgement-resolution.md#capture-resolve-and-score) records the hashes and coverage.

Variants can share compatible immutable resources. In the [API-only example](diagrams/interactive/shared-index-reuse.html), separate API deployments read one frozen index. One API can also serve several pinned ranking configurations. A mapping change builds a different index from the same dataset. The [variant evaluation](diagrams/interactive/evaluation-dataflow.html) shows the named result paths; the [merge gate](diagrams/interactive/variant-merge-gate.html) shows source-bound evidence and the recorded release decision.

- **Baseline:** Start with a search API that performs simple query normalisation and a BM25 baseline using a documented mapping, analysers and query template.
- **Query understanding:** Candidate API versions may change spelling correction, tokenisation, intent or entity detection, synonym expansion, query rewriting and context handling before Elasticsearch receives a request.
- **Retrieval and ranking:** Candidates may also change field boosts, filters, rescoring and business signals. A later candidate may change mappings or add a reranking stage.
- **Versioned assets:** Pin dictionaries and models as versioned assets; avoid hidden calls to external services during a reproducible comparison.
- **API contract:** The current API returns ordered IDs, public product fields, total matches and elapsed time, plus selected variant/configuration identity. Rank follows list position; scores are not public fields. It accepts explicit country/currency and supports GB/GBP. Query rewrites and reranking are possible candidate changes, not active stages in the baseline.

Relevance evaluation follows these rules:

- **Inputs:** A relevance evaluation pins one dataset, query suite and judgement release and sends the same original request and context through every named **public search API** variant.
- **Judgement limits:** The report identifies the published or inferred judgement source, hashes, coverage of each returned top ten and unjudged IDs. Published labels cover the selected query/product pool, not every possible retrieved result. The separate resolution workflow can ask a model about gaps in all selected recall sets before scoring; the all-abstaining model adds no labels. Coverage below 80% on either side marks the relevance claim insufficient and does not alter the result-change verdict.
- **Captured response:** The evaluation client records the response actually returned to the caller, including ordered product IDs, zero results, errors and client-observed duration.
- **Scoring:** Judgements are joined to those final product IDs; an established metrics library calculates end-to-end nDCG@10, MRR, precision/recall at selected cut-offs and per-query regressions.
- **Coverage:** Report zero-result and failure rates separately so failures cannot disappear from metric denominators. Include category, intent and head/long-tail slices.
- **Decision metric:** Public API results provide the black-box comparison, including query understanding or reranking changes outside Elasticsearch. The merge gate compares selected variants with the named baseline under one frozen specification and coverage policy; a bounded human exception records the reason without changing measured scores.

### Black-box, grey-box and white-box evidence

Use three evidence layers:

| Layer | Observation point | Purpose and examples |
| --- | --- | --- |
| **Black box — decision metric** | Original request → public search API → final customer-visible response | Final ranked product IDs against frozen judgements; nDCG@10, MRR, recall/precision, zero-result and error rates, client-observed latency. This layer determines relevance under the selected frozen labels, or result preservation using exact ordered-ID equality, RBO and Jaccard. |
| **Grey box — stage diagnosis** | Correlated, versioned API trace or structured diagnostic record for the same request | Query normalisation, detected intent/entities, rewrite and synonym choices, filters, Elasticsearch request or template fingerprint, pre/post-retrieval candidate IDs, reranker input/output, stage durations and fallbacks. Stage-level recall or loss can explain where a regression appeared; a trace is never substituted for the final API response. |
| **White box — component diagnosis** | Direct, pinned Elasticsearch request against a known index and mapping | `_rank_eval`, `_profile`, `_explain` and analyser inspection where useful. These answer questions about retrieval and ranking *inside Elasticsearch*; they do not measure API query understanding, result merging, application filters or reranking. Run costly diagnostics separately or on a selected query sample so they do not distort black-box latency. |

- **Correlation:** For relevance and result preservation, every black-box request receives a correlation ID.
- **Retained evidence:** Save its original input, final response and optional diagnostic record together with the dataset/query hashes, judgement hash when used, fixed clock and context, API image digest, query assets, configuration, index/mapping fingerprint and engine version.
- **Diagnostic capture:** Diagnostic capture should be versioned and opt-in or sampled, with a check that enabling it does not alter the returned ordering.
- **Missing stages:** If a candidate cannot emit a particular stage, mark that stage unavailable rather than inventing a comparable value.
- **Original and rewritten requests:** Preserve the original request and raw Elasticsearch request separately: one API change may legitimately produce different Elasticsearch inputs for the same original query.

Comparison execution and reporting:

- **Request order:** For functional checks, interleave baseline and candidate requests or randomise their order. Performance uses the sequential paired-run protocol below.
- **Shared resources:** Record cache state and shared-cluster contention, and keep each mode's verdict separate. A contended shared cluster is useful for correctness comparisons but cannot by itself establish a performance improvement.
- **Report navigation:** For relevance comparisons, the report UI should lead with the black-box scorecard, then allow per-query inspection of grey-box traces and optional white-box Elasticsearch diagnostics.
- **API-only changes:** An API-only regression must be visible even when `_rank_eval` on an unchanged Elasticsearch query and index reports no difference. Elasticsearch's [ranking evaluation API](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval) remains a useful component diagnostic, never the source of the end-to-end score.

### Result regression: preserve ranking and membership

![Frozen baseline and candidate APIs return ordered product IDs for an exact-match check](diagrams/rendered/result-regression.png)

Use the [unchanged-results workflow](diagrams/interactive/result-regression.html) when a refactor, dependency update or other change should preserve search results. It uses the same frozen B/C definitions, readiness checks, API calls and comparison runner. Select `result-regression` as the comparison mode; relevance judgements are optional and do not determine this verdict. API query understanding, filtering and reranking are included because the runner compares final public API responses.

1. Pin both definitions, the query suite, request context, comparison depth and evaluator version. Start with **K = 10** and the full frozen query suite; repeat at the 1,000-query scale milestone. Both sides use the same catalogue release, original inputs, UK/GBP context, fixed clock and random seeds where applicable.
2. Capture the ordered product IDs returned by each API, up to K, for every query. Preserve actual API order; do not sort or deduplicate responses to make them match. Pin a stable tie-break rule. Check repeated baseline runs for instability before interpreting candidate differences.
3. Compare each pair and retain the differences below. Summaries include changed-query count/rate and the worst affected queries; averages cannot hide an individual failure.
4. Record **unchanged** only when every query has two valid responses with identical ordered ID lists. Any list difference records **changed**. A missing, erroneous, partial or malformed response makes the run **incomplete** and blocks a pass; retain any differences already found.

| Check | Meaning and initial policy |
| --- | --- |
| Exact ordered-ID equality at K | Acceptance check: zero changed queries across the complete suite. Covers both membership and order within the captured depth. |
| Jaccard@K | Set intersection divided by set union. Detects membership changes and ignores ordering. Two successful empty lists score 1 by convention; one empty and one non-empty score 0. |
| Rank-biased overlap (RBO) | Top-weighted ranking similarity. Initially use the extrapolated variant on captured lists with **p = 0.9**; pin the library version, variant and depth. Mark comparisons involving an empty list unavailable for RBO and retain the exact verdict and Jaccard. |
| Added/removed IDs and rank moves | Per-query evidence, including changed top result and transitions to or from zero results. |

- **Jaccard:** Jaccard similarity is one minus Jaccard distance; the [SciPy definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jaccard.html) also documents the empty-set convention.
- **RBO:** RBO has distinct lower-bound and extrapolated estimates; see the [RBO implementation reference](https://github.com/dlukes/rbo) and its linked paper.
- **Implementation:** The evaluation dependencies pin an established RBO implementation; retain that pin and its settings with each report.
- **Verdict limits:** A similarity score close to 1 does not establish exact equality. If a later experiment allows tolerances, pin those thresholds and label its verdict **within tolerance**, keeping it distinct from **unchanged**.

Response validity and scope:

- **Short responses:** Short, complete responses are valid when fewer than K products match.
- **Duplicates:** Duplicate IDs are invalid under the unique-product response contract.
- **Empty results:** Count successful empty pairs separately so their agreement cannot conceal poor query coverage.
- **Scope:** The claim covers the frozen queries and captured depth only; it does not assert equal scores, product fields, unseen result tails, judged relevance or non-functional behaviour.

Result-preservation evidence and acceptance:

- **Evidence:** Retain both fingerprints, query/context hashes, evaluator image, metric settings, gate policy, raw responses, per-query differences and verdict.
- **Report:** The report UI should lead with the result-regression verdict in this mode, with links to grey-box traces for changed queries.
- **Acceptance examples:** Demonstrate an unchanged API refactor, an order-only change (Jaccard remains 1), a membership change and an incomplete run. All four must produce the expected outcome before this workflow is accepted.

### Performance: check the search API with Gatling

![Pinned baseline and candidate APIs receive sequential Gatling load tests before performance thresholds are checked](diagrams/rendered/performance-check.png)

Use the [Gatling workflow](diagrams/interactive/performance-check.html) for latency, throughput and failure checks.

- **Runner:** Start with the **Gatling open-source Java SDK**, one load-generator process per Kubernetes Job, committed simulations and a pinned JDK/build/runtime image.
- **Load and assertions:** Gatling supports local execution and reports; its [injection model](https://docs.gatling.io/concepts/injection/) controls arrivals, and [assertions](https://docs.gatling.io/concepts/assertions/) check response-time and failure budgets.
- **Coordination:** The initial design needs no Gatling Enterprise service or distributed load coordinator.
- **Portability:** Verify the runner image natively on amd64 and arm64 during portability testing; cross-architecture emulation is unsuitable for benchmark evidence.

Load-test preparation and artefacts:

- **Preparation:** The [traffic-preparation workflow](diagrams/interactive/traffic-workload.html) freezes a trace and compiles the selected recipe before the lab schedules load jobs through its existing desired-state path.
- **Execution and comparison:** Gatling creates traffic and per-run evidence; the evaluation job compares the completed reports. Use the upstream runner and report format, with a small versioned adapter for comparison summaries.
- **Source and artefacts:** Keep simulations, build dependencies and workload manifests in Gitea; retain logs, HTML reports and summaries in Azure Blob Storage, with the same contracts after migration to GitHub Enterprise and Azure Blob Storage.

Run the performance check in this order:

1. **Pin the test.**

   - Record B/C fingerprints, catalogue and query hashes, original request/context, an immutable request schedule, simulation revision, Gatling/JDK versions, runner image, thresholds and timeouts.
   - Resolve or compile the frozen workload under the traffic contract above. Both sides replay that same artefact, including head/long-tail, misspelling and zero-result cases.
   - Use one request per virtual user with an open arrival model so a slow response does not silently reduce offered load.
   - Record actual arrival timing and completion counts.

2. **Reserve comparable resources.**

   - Hold one performance slot per shared Elasticsearch cluster using the lab's metadata lease.
   - Both runtimes must be ready, with fixed equal API replica counts and resource budgets; pin shard layout, engine settings, placement and cache policy.
   - Suspend competing lab indexing and comparisons for the isolated profile.
   - Measure host, generator, API and Elasticsearch CPU, memory, GC and throttling. A namespace alone does not provide performance isolation.
   - On Azure, place the generator on separate reserved workers; laptop runs remain host-specific evidence.

3. **Warm and measure each side separately.**

   - Select a constant-rate or trace-derived profile from the table below.
   - The constant-rate smoke profile retains a 30-second ramp, 60-second warm-up and 300 seconds of steady traffic at 10 requests/second against the full ESCI catalogue, returning top 10.
   - Warm each side immediately before measuring it.
   - Use distinct request names for warm-up and measured traffic within the same process, and scope assertions to measured requests.
   - Keep a fixed connection/reuse policy and let outstanding requests finish within a pinned drain timeout.
   - Do not flush a shared cache as a shortcut to a cold test. Cold starts, sustained peak and stress/recovery use separate profiles with their own budgets and duration.

4. **Repeat paired runs.**

   - Run B then C, C then B, B then C: three runs per side, without concurrent load on B and C.
   - Use the same warm-up, request schedule and resource limits each time, and wait for resource activity to settle between runs.
   - Collect all six reports.
   - Expensive profile/explain and full trace replay are disabled during measurement; use a separate diagnostic replay for investigation.

5. **Assess validity, then budgets.**

   - Report measured p50/p95/p99, offered and achieved rates, successful throughput, timeouts and failed checks, plus paired deltas and variation between repeats.
   - Enforce normal/peak acceptance budgets with Gatling assertions and relative budgets in the report comparator.
   - For stress, retain per-step budget breaches as capacity evidence rather than treating the first expected breach as failure of the entire campaign.
   - Do not average percentiles into a claimed pooled percentile. Report each run and the median of the three paired p95 percentage changes explicitly.

#### Traffic profiles and phases

Default to separate normal, sustained-peak and stress/recovery checks, each with its own warm-up. A combined run is also possible when the recipe explicitly preserves phase order, carries cache state forward and reports each phase separately.

| Profile | Trace preparation | Measurement and outcome |
| --- | --- | --- |
| Warm-up | Select a representative window preceding the measured traffic, preserving repeated queries and timing. Pin its duration and request mix. | Establish the declared cache/runtime state; exclude its requests from acceptance latency percentiles. Record warm-up failures and abort if the declared readiness condition is not reached. |
| Normal load | Select a typical synthetic window with its varying arrival rate and query mix. | Apply pinned latency, failure and relative B/C budgets. The constant-rate 10 requests/s profile remains a separate smoke check. |
| Sustained peak | Extend a busy period with seeded blocks of synthetic traffic that preserve bursts and changing popularity. | Apply peak-specific budgets across the full hold period; report latency/failure time series and resource drift. Avoid looping a tiny hot-query sample that artificially improves cache hits. |
| Stress | Increase arrivals in declared steps while retaining the selected mix. Pin each step's hold time and target-resource stop limits. | Report the highest tested load that meets the budget, the first breaching step and its limiting resource. Reaching the intended breaking point is a capacity observation, not an automatic normal-load failure. |
| Recovery | Return to the pinned normal profile after stress. | Measure time until latency, errors and resource/backlog indicators meet recovery budgets for a declared stable interval. If a stop condition prevents recovery, report it as unmeasured. |

| Scaling method | Effect |
| --- | --- |
| **Compress time** | `new offset = original offset / factor`; also shortens query-repeat intervals |
| **Increase volume over the same duration** | Uses seeded arrival generation to add requests without shortening the chosen test duration |

Record the selected method. Neither transformation can preserve every property of the original trace. Freeze the derived output and document changes to burstiness, ordering, repetition and cache working set.

Extending peak load uses a pinned block-selection method and seed, with continuity at block boundaries checked before execution.

| Initial recipe phase | Provisional duration and load |
| --- | --- |
| Normal | Five measured minutes |
| Sustained peak | Fifteen measured minutes |
| Stress | Two-minute holds at 1×, 1.5×, 2× and 3× the selected normal rate |
| Recovery | Five minutes after stress |

These are provisional profile durations, not capacity claims. Define peak intensity, phase budgets, warm-up length, stop limits and recovery interval before a run; they remain hardware-calibration decisions. A short smoke run does not establish sustained-peak or endurance behaviour.

- **Continuous phases:** Compile continuous phases onto one arrival timeline when requests may span boundaries. Attribute responses to the phase in which their request was scheduled and retain actual start/end times.
- **Drain boundaries:** For deliberate drain boundaries, Gatling's [sequential scenarios](https://docs.gatling.io/concepts/injection/#sequential-scenarios) wait until the preceding users finish; this is not a fixed-time phase transition. Pin which transition policy applies.
- **Arrival independence:** No request waits for an earlier response before its planned arrival.
- **Saturation:** Load-generator saturation makes a run inconclusive; target saturation under valid load supplies the stress result.

#### Constant-rate smoke policy

| Initial performance policy | Provisional threshold or rule |
| --- | --- |
| Absolute budget, each measured run | p95 ≤ 250 ms, p99 ≤ 500 ms, failed requests < 1%; applies to both B and C |
| Relative budget | Median paired candidate p95 increase ≤ 10% over B; retain all three deltas |
| Workload delivery | 3,000 measured requests per side per run at 10 arrivals/second; at least 99% of scheduled requests started within the measured interval; retain late arrivals and drain outcomes |
| Repeatability | Baseline p95 spread `(max − min) / median` ≤ 10%; greater variation makes the comparison inconclusive |
| Successful response | Expected HTTP status and valid search response contract; check failures count as failed requests, even for HTTP 200 |
| Verdict | **Pass** when validity and all budgets hold; **fail** for a valid run breaching a budget; **inconclusive** for missing evidence, generator saturation, uncontrolled competing load or unstable conditions |

These thresholds are starting hypotheses for the constant-rate smoke profile.

- **Smoke duration:** Its full six-run check takes roughly 39 minutes of ramp, warm-up and measurement, plus readiness, settling, drain and reporting; the 15-minute functional-comparison target does not apply.
- **Trace-profile duration:** Trace-profile duration is calculated from its compiled phases, repetitions and drain policy.
- **Scale validation:** At 1,215,854 products and 1,000 unique queries, rerun the fixed-load profile before increasing offered load in a separate capacity sweep.
- **Query counts:** A query suite contains unique inputs; a load test repeats them according to its pinned frequency model.
- **Calibration:** Calibrate thresholds from measured hardware evidence rather than assuming production capacity from a laptop result.

Performance evidence and verdicts:

- **Retained artefacts:** Retain per-run Gatling logs and HTML/assertion reports, source trace, recipe and compiled-workload hashes, planned/actual arrival records, all fingerprints, machine/node and resource settings, cache/warm-up policy, monitoring evidence and comparison verdict.
- **Error evidence:** Preserve timeout/error samples without logging every response body on the load generator.
- **Validity and saturation:** Missing instrumentation or load-generator exhaustion blocks a performance pass; target-system saturation under a valid offered load breaches an acceptance budget or records a stress capacity limit, according to the pinned phase policy.
- **Contention experiments:** Intentional contention uses a named, reproducible background-load profile, separate from the isolated comparison.
- **Independent verdicts:** A functional failure remains visible in its own mode even if performance passes.

Run management and acceptance:

- **Lease and slot:** An active comparison renews both environment leases and holds its performance slot until all load stops.
- **Deletion and recovery:** Manual environment deletion cancels dependent jobs and releases the slot after termination; stale slot leases are reconciled after controller or job failure. Save partial evidence as inconclusive.
- **UI:** The UI selects a trace and recipe, previews phase rates/durations and expected request counts, then displays queued/running state, phase verdicts, stress capacity/recovery, per-side reports and test conditions.
- **Verdict examples:** Demonstrate a passing baseline-equivalent run, a deliberately slower candidate that fails, and an interrupted or overloaded-generator run that is inconclusive.
- **Replay acceptance:** Also verify identical compiled bytes and event bindings for B/C, warm-up exclusion, a sustained-peak hold, a stress threshold breach and recovery. Compare observed arrival patterns with the compiled schedule before accepting trace replay.

The UI has four small views:

- Dataset catalogue.
- Environment list, creation and deletion.
- Side-by-side search.
- Comparison report with mode selection, per-query inspection and Gatling report links.

The control UI supports the core paired workflow. Advanced variant capture, pooled judgement resolution and release operation use the documented operator tools; the UI does not yet integrate every standalone path.

## Startup and scale validation

Keep Kubernetes, ECK, shared Elasticsearch, storage and registry services warm.
API-only changes reuse a compatible frozen index; mapping changes run indexing
or exact restoration. Cache immutable images where practical.

| Measure | Record |
| --- | --- |
| Environment startup | Request → namespace, index build/restore, first correct end-to-end search |
| Source lifecycle | Accepted source update → tests/build/push → first correct candidate search |
| Removal | Request → resources/credentials/dedicated index removed |
| Conditions | Cold/warm state, hardware/architecture, dataset, shard layout, cache policy and competing load |
| Deployment latency | Git publication, explicit refresh/polling and Argo reconciliation separately |

[Restore research](research/index-restoration-options.md) and
[S3 lifecycle evidence](research/evidence/durable-snapshot-repository.md) retain
clone/snapshot timings and their different conditions. A live clone needs its
source; a regular snapshot does not. Neither host-local repository proves cloud
restore latency. [The roadmap](plans/roadmap.md) owns current measurements and
remaining validation.

### Provisional quantitative targets

These are **design hypotheses, not measured performance or service promises**.

- **Revision policy:** Change them after the research spike and each scale run, retaining the previous value and evidence in the decision record.
- **Default conditions:** A target is tested on a warm cluster with images present unless labelled cold.
- **Startup boundary:** For environment startup, measure from accepted API request to a successful end-to-end search, not merely a running Pod.
- **Startup/removal sample:** Use at least 20 repetitions for startup/removal p95 figures and record failures rather than excluding them.
- **Search latency:** Search latency uses the separate Gatling sampling protocol.
- **Indexing and comparison sample:** For larger indexing and comparison runs, repeat at least three times and publish all results.

| Outcome | Early target | Measurement and limit |
| --- | --- | --- |
| API/query/ranking-only environment, 10,000 products | p50 ≤ 60 s; p95 ≤ 120 s | Shared index already present; local machine; request to first correct search |
| Gitea PR build → first correct candidate search, 10,000 products | p95 ≤ 8 min | Warm runner and cluster; start at accepted PR update, include test, image build/push and environment start; record build and provision phases separately |
| Index-changing environment, 10,000 products | p95 ≤ 5 min | New mapping and full reindex; request to first correct search |
| API/query/ranking-only environment, 1,215,854 products | p95 ≤ 2 min | Shared million-product index already present; suitable test cluster |
| Index-changing environment, 1,215,854 products | ≤ 20 min per run | Full reindex from frozen objects on a documented test cluster; revise after first bulk-index measurement |
| Complete 1,000-query functional comparison | ≤ 15 min per run | Two ready versions queried through their public APIs; final top 10, relevance or result-preservation metrics and persisted report; exclude index build, performance load tests and optional white-box diagnostics |
| API performance, constant-rate smoke | 10 requests/s for 300 measured seconds; p95 ≤ 250 ms, p99 ≤ 500 ms, failures < 1%; median paired p95 increase ≤ 10% | Full ESCI catalogue, three controlled B/C pairs, valid generator and stable baseline; see the Gatling profile above |
| On-demand removal | p95 ≤ 5 min | Request to namespace resources and dedicated indices gone; shared frozen index deliberately retained |
| Lease expiry | Start cleanup within 10 min of expiry; finish within 15 min | 72 h after last genuine use; no extension from polling or health checks |
| Control-plane capacity | 40 simultaneous API/query-only environments, ≥ 95% ready within 5 min of their requests | Suitable multi-node test cluster; all 40 must run a real search; record p95, errors, CPU, memory and API load |
| Isolation | Zero successful cross-environment index reads or writes in the access test suite | Test Elasticsearch credentials, Kubernetes RBAC and network reachability |
| Reproducibility | Identical product/query hashes and identical ordered top-10 results on two clean builds of the same fingerprint | Pin data, configuration and engine version; latency is excluded |
| End-to-end metric coverage | API-side query-understanding change that alters final results is detected in the black-box comparison even if the Elasticsearch index is unchanged | Keep a deliberately different API candidate in the evaluation walkthrough; show final-result and stage evidence side by side |
| Result-preservation verification | Zero changed queries for a behaviour-preserving API refactor; detect deliberate order and membership changes; incomplete runs never pass | Compare final ordered top-10 IDs across the frozen suite; retain RBO, Jaccard and per-query differences; no NFR thresholds |
| Source-to-preview traceability | 100% of ready candidate environments link a source SHA, image digest, dataset hash and comparison-compatible configuration fingerprint | Check through the UI and API; reject mutable-only references |
| Local full-lifecycle demonstration | One Gitea PR changing API behaviour and one changing an index, each built, deployed, evaluated and removed without an external Git service | Record stage timings and failures; this is an acceptance gate rather than a speculative latency target |

For the 40-environment exercise, keep API/query-only workloads small and share the frozen index. Also model the disk and indexing cost of 40 distinct million-product mappings; do not infer that the API/query-only result proves that scenario is affordable. Establish a separate capacity limit for simultaneous reindex jobs from measured throughput and cluster headroom.

Scale gate for the completed prototype:

1. Generate, hash, store and reload a 1,215,854-product release with 1,000 judged queries.
2. Build both a baseline and a mapping-changing candidate index; run relevance and result-preservation checks, plus compiled normal, sustained-peak and stress/recovery Gatling profiles; record duration, disk, memory and metrics. Use separate expected outcomes for each mode; an intentional ranking change need not preserve results.
3. Prove two or three environments on the local machine, including on-demand deletion, expiry and activity extension.
4. Exercise 40+ **lightweight environment control records and Kubernetes deployments** on a suitable test cluster or capacity model, then document measured API and reconciliation behaviour. Do not present metadata-only simulation as proof that forty full search workloads fit.
5. Repeat bootstrap and core workflow on Apple silicon macOS. Use multi-architecture images and avoid architecture-specific binaries or Windows-only scripts.
6. Test cluster-level resource contention and establish when to move from shared indices to separate clusters for valid performance comparisons.

## Delivery batches and acceptance

The [roadmap](plans/roadmap.md) owns implementation status and remaining gates;
individual plans preserve the intent and acceptance criteria of each review batch.
The [documentation plan](plans/documentation-authorship.md) tracks the current
clarity review separately.

Finish a batch on a branch, commit it, update the roadmap and next detailed plan,
and open a PR. Merge after acceptance. Local implementation acceptance does not
close native/cloud, measurement or human-decision checks.

## Decisions to verify during implementation

- Verify the provisional k3d bootstrap natively on Apple silicon. k3d and kind passed the Windows cross-node NetworkPolicy/RBAC probes on the 96 GiB / 32-logical-CPU host; the research report records actual timings and resource use.
- Extend the successful Floci Blob/hash/conditional-create checks with negative SAS and expiry tests. Keep canonical objects immutable; the tested Floci version cannot serve as an Elasticsearch snapshot repository.
- Validate which index-level security privileges and ECK configuration are available under the organisation's intended self-managed licence. A shared cluster reduces cluster count; it does not itself settle contractual licensing terms.
- Validate Gatling image portability, report parsing, event-to-arrival binding and generator headroom; calibrate bucket width, scheduling lateness, phase budgets and noise thresholds on the documented hardware.
- Choose the metadata store for the 40+ environment path after measuring SQLite contention and deployment topology. The API must keep its metadata behind a repository interface so a PostgreSQL migration is straightforward if needed.

## References

- [Floci AZ repository](https://github.com/floci-io/floci-az)
- [ECK installation](https://www.elastic.co/docs/deploy-manage/deploy/cloud-on-k8s/install)
- [ECK licence management](https://www.elastic.co/docs/deploy-manage/license/manage-your-license-in-eck)
- [Elasticsearch aliases](https://www.elastic.co/guide/en/elasticsearch/reference/current/aliases.html)
- [Elasticsearch ranking evaluation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval)
- [Elasticsearch Azure snapshot repository](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/azure-repository)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
