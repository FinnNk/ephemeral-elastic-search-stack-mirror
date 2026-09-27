# Batch 7j: independent data and evaluation contracts

## Intent

Separate product, query, judgement and traffic producers from the search implementation and lab orchestration. Let the lab consume immutable artifacts and evaluator reports through explicit contracts. Preserve existing comparisons and make input versions independently selectable.

**Status: planned, after [Kubernetes control services](kubernetes-control-services.md).** This batch validates ownership, interchange and reproducibility mechanics. It does not establish the statistical validity of metrics or realism of synthetic judgements.

## Contracts

| Contract | Required contents | Producer and consumer |
| --- | --- | --- |
| Catalogue | Stable product IDs, schema reference, records, catalogue hash and provenance | Independent data producer → versioned indexer adapter |
| Query suite | Stable case IDs, original request, country/currency, filters and optional segments; query-suite hash | Query producer → API runner and workload compiler |
| Judgement set | Case/product IDs, labels, grading rubric and provenance; compatible catalogue/query references | Assessment producer → relevance evaluator |
| Traffic dataset | Timestamped request/case references, time basis and provenance | Traffic producer → frozen workload compiler |
| Search API adapter | Request construction and response extraction, versioned with the execution plan; preserve original inputs and caller-visible ordering | Reference search implementation → generic runner |
| Observation set | Both environment fingerprints, query/request references, ordered results, errors, captured depth and execution provenance | Runner → evaluator; immutable and independently retained |
| Evaluation specification | Metric identifiers, parameters, cut-offs, label/gain mapping, aggregation, unjudged/empty-result policy and evaluator implementation digest | Evaluation owner → evaluator |
| Evaluation report | Input/specification hashes, evaluator identity, per-case and aggregate results, units, completeness, coverage and error status | Evaluator → lab UI, comparison history and promotion validator |
| Promotion policy | Required report kinds, exact input matching, freshness, thresholds and reviewer requirements; policy version/hash | Delivery configuration → promotion validator |

Use existing JSONL/CSV formats and a small versioned manifest envelope: artifact kind, schema version, content hash, object reference, dependencies and producer provenance. Preserve richer retail fields through an explicit catalogue schema and indexer adapter. Support common query/relevance-assessment conventions through adapters: [BEIR's corpus/query/qrels separation](https://github.com/beir-cellar/beir/wiki/Load-your-custom-dataset) and [ir-measures inputs and measure definitions](https://ir-measur.es/en/latest/getting-started.html) provide useful starting points.

## Ownership and constraints

- **Independent producers:** move the existing synthetic generation/import/publication entrypoints into a separate package and finite jobs. Provide a `lab-data` job namespace for the example producers. They publish artifacts without importing the control API, search API or controller database. Separate repositories and always-running data services are optional future placements, not required by this contract.
- **Search implementation:** consumes catalogue records through its pinned indexer and accepts requests through its public API. It does not load evaluation judgements or choose evaluation policy. Search-specific field mappings and response parsing belong to versioned adapters, not generic orchestration.
- **Lab machinery:** discovers explicit artifact references, validates schema/hash/dependency compatibility, provisions resources, runs jobs and retains reports. Remove special behaviour selected by `retail-gb-10k-v1` or `retail-gb-1m-v1` names.
- **Evaluator:** retain the current libraries as the first implementation behind a file/job interface. Pin code/image and configuration. Publish producer and evaluator images independently of search and control images. Demonstrate a separately packaged invocation; do not build a plugin marketplace or general remote-execution service.
- **Storage:** Floci/Blob retains data, observations and reports; Nexus retains executable images and release bundles; SeaweedFS retains snapshots. Producer identities may publish their inputs, consumers read them, and report publication uses its own scope where the local service supports it. Document emulator permission gaps.
- **Compatibility:** keep old manifests, recipes, environments and reports unchanged and readable through a legacy adapter. New catalogue-only manifests stop judgement/query changes from changing index recipes. New contracts are additive and versioned; never silently reinterpret an old hash.
- **Synthetic-only lab:** all demonstration sources remain synthetic. External means outside the search/lab ownership boundary, not production data or an internet dependency.

## Versioning and execution

| Definition | Pins | Changes that do not require replacing it |
| --- | --- | --- |
| Frozen environment | Software release, catalogue, index recipe, engine and search configuration | New judgements, metric parameters or query cases |
| Comparison execution | Both frozen environments, query suite, request adapter, relevant traffic/workload and execution settings | Later rescoring of already retained observations |
| Evaluation | Observation hashes, judgement set when needed, evaluation specification and evaluator digest | A new evaluation produces a new report; it never rewrites the previous one |
| Promotion proposal | Exact deployment pair, required reports and policy revision | None of its pinned inputs may change silently before approval/merge |

Result preservation consumes both ordered observation sets without judgements. Relevance consumes observations and a judgement set. Performance consumes the frozen workload and measured execution records. Offline rescoring is allowed only when the retained data supports the requested calculation: top-ten observations cannot supply top-100 results, and changed load schedules require another execution.

## Work and acceptance criteria

1. **Publish explicit schemas and examples.** Validate artifact identity, duplicate IDs, referential integrity, compatible catalogue/query versions, hashes and supported contract versions before execution. Record unknown/unjudged separately from an explicitly non-relevant label. Reject incomplete report imports rather than granting a passing gate.
2. **Extract producers and adapters.** Publish the existing frozen inputs through the new manifest layer without changing their bytes. Publish a third small synthetic catalogue/query pack under different IDs through the same path without editing controller conditionals. Demonstrate that the producer runs independently of the control Pod.
3. **Separate capture and scoring.** Persist reusable observations; run the current evaluator as an independent packaged job against artifact references. The lab receives the report contract without importing generator code or individual metric implementations. Preserve API result ordering and label-derived scoring semantics explicitly.
4. **Demonstrate independent releases.** Publish revised synthetic judgements and a changed evaluation specification, rescore the same observations, and retain both old and new reports. Assert zero API calls, environment redeployments or index builds during supported rescoring. Changing queries creates another execution but reuses the same frozen environments.
5. **Connect delivery policy.** Validate exact report/specification/policy references. A report for another catalogue, query suite, environment pair or policy input cannot authorise the current proposal. Policy evaluation and human approval remain distinct from report calculation.
6. **Exercise schema and release ownership end to end.** In the isolated delivery repositories, build a release with a compatible new schema recipe, propose/deploy it, then restore the complete previous release/recipe through rollback. Use fresh executions where required. This demonstrates independently versioned software, data, schema and desired-state contracts; no claim of improved relevance is required.
7. **Document retention dependencies.** Catalogue the references needed for comparison replay, rescoring and rollback, including image layers and evaluator versions. Add a read-only inventory/report of missing references and disposable artifacts. Automatic deletion remains disabled until a separate retention policy is accepted.
8. **Synchronise the model.** Update the design, operating guide, C4 evaluation and deployment views, and Archify data preparation/evaluation/promotion workflows. Show independent producer ownership, two frozen APIs, retained observations and separate evaluation/policy steps. Update the roadmap, refresh the detailed external-validation plan and open the batch PR.

## Where to find more information

- [Topology and contract assessment](local-reference-boundaries.md), [design](../prototype-design.md#frozen-dataset-contract), [CI/CD contract](reference-ci-cd.md)
- `lab/release.py`, `lab/release_million.py`, `lab/traffic.py`: reference synthetic producers
- `lab/compare_search.py`, `lab/control_comparison.py`, `lab/evaluate_relevance.py`: present dataset-name branches, combined input loading and metric calculation
- `lab/evaluation_job.py`, `lab/evaluation_worker.py`: current API request/response and job boundary
- `lab/index_recipe.py`, `lab/shared_index.py`, `lab/index_recovery.py`: historical recipes and retained index selection
- `lab/lifecycle.py`, `lab/delivery_runtime.py`, `lab/delivery_gates.py`: current release allowlists, deployment identity and promotion checks
- [Historical recipe evidence](../research/evidence/historical-index-recipes.md), [delivery evidence](../research/evidence/promotion-deployment.md), [next external validation](native-cloud-validation.md)
