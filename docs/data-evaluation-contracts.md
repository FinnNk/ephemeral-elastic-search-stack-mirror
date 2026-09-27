# Independent synthetic data and evaluation contracts

The `data/` package owns synthetic input generation, validation and publication. It imports neither the Search API nor the control runtime. The `evaluation/` package scores retained public-API observations. Delivery owns the separate promotion policy. All example inputs remain synthetic.

| Artifact | Stable identity and dependencies | Consumer |
| --- | --- | --- |
| Catalogue | Original product-file SHA-256, row count, country/currency and producer provenance | Pinned indexer and v2 index recipe |
| Query suite | Original request rows and SHA-256 | API capture Job and workload compiler |
| Judgement set | Query and product references, explicit grades 0–3, catalogue/query hashes | Offline relevance evaluator |
| Traffic trace | Timestamped query references, query-suite hash | Gatling workload compiler |
| Observation set | Both environment fingerprints, requests, ordered IDs, totals, errors, capture depth/time and worker provenance | Offline evaluator; no further Search API call |
| Evaluation specification | Metric names/cut-offs, macro aggregation and explicit unjudged policy | Versioned evaluator image |
| Evaluation report | Exact observation, judgement, specification and evaluator hashes; scores, coverage and completeness | Delivery policy and comparison history |
| Promotion policy | Required metrics, evidence age, coverage and human review rule; separate policy hash | Delivery validator |

The input envelope has `kind`, `schema_version`, `content`, `dependencies`, `producer` and `record_count`. `content.object` is addressed by the source file hash. `producer.source_release` identifies the synthetic source pack; publication does not read a combined release manifest. An absent judgement is **unknown**; grade zero is explicitly non-relevant. A catalogue may contain several countries, each with one currency. The validator streams records through a temporary SQLite identity index and checks IDs, references, market context and traffic/query links. It validated the existing 1M input bytes.

## Publish independent inputs

```powershell
python data/generate_example.py --output .lab/releases/retail-gb-independent-example-v2
python data/publish.py --input-dir .lab/releases/retail-gb-independent-example-v2 --output .lab/artifacts/retail-gb-independent-example-v2 --producer independent-example-v2 --source-release retail-gb-independent-example-v2
python data/publish.py --input-dir .lab/releases/retail-gb-1m-v1 --output .lab/artifacts/retail-gb-1m-independent-v2 --producer synthetic-million-v1 --source-release retail-gb-1m-v1 --traffic lab/traffic/source-trace-million-v2.csv
```

Set `DATA_BLOB_CONNECTION_STRING` using the separately retained emulator credential, add `--blob-url http://127.0.0.1:14577/devstoreaccount1`, and the publisher stores both original files and manifests in Floci's `datasets` container. Repeating publication verifies existing immutable objects. When an earlier publisher left no checksum metadata, the producer streams the retained bytes and checks their hash before reuse. For Azure, use an HTTPS account URL and workload identity; the producer package does not assume an emulator key. The local emulator currently shares one account credential across producer and consumer roles, so it cannot demonstrate separate write scopes.

`python lab/publish_tool_images.py` publishes separate amd64/arm64 producer and evaluator images to Nexus. `python data/run_job.py` runs the example producer as a finite `lab-data` Job with no Kubernetes API token. Its policy permits DNS and Floci egress only; the temporary Blob credential and Job are removed afterwards. The retained image-pull secret and namespace support subsequent runs. Set `LAB_STATE_DIR` to the existing ignored `.lab` directory when running from an isolated worktree. The Job avoids the dedicated observability worker because that worker does not share the application nodes' Nexus registry mapping.

`lab/default_inputs.json` pins the independent 10k and 1M catalogue, query and judgement manifest hashes used by the control UI and delivery comparisons. To recreate those exact manifests from the existing synthetic source bytes, set `DATA_BLOB_CONNECTION_STRING` and run `python lab/publish_default_inputs.py`. It checks the published hashes against the pinned defaults. The source bytes and previously retained manifests are unchanged.

## Capture once, score again

Functional comparisons retain a `search-observation-set` Blob independently of the comparison report. The comparison API exposes its hash and Blob reference. Older reports remain retained as evidence; new evaluations consume captured observations directly.

The control UI accepts a query-suite manifest SHA-256 for result preservation or relevance, and a matching judgement-set manifest SHA-256 for relevance. Blank fields use the pinned defaults shown in the UI. The controller reads manifests and content by hash from Floci, checks catalogue and query dependencies, and retains the selected hashes with each comparison. The Kubernetes control Pod completed result and relevance checks using a revised three-query suite and matching synthetic judgements against two APIs sharing one frozen index. Performance uses its separately pinned workload. See the [runtime evidence](research/evidence/runtime-consolidation-delivery.md).

`evaluation/capture.py` is the standalone capture route for a selected query file and manifest, catalogue manifest and two frozen API names. Its observation set can be rescored independently of the control UI. New environment and delivery definitions use the same pinned catalogue manifest, while functional checks can select a revised query and compatible judgement manifest without rebuilding an index.

The evaluator accepts observation, catalogue, query and judgement manifests plus a versioned specification. It rejects another catalogue/query suite, a mismatched judgement dependency, duplicate results, incomplete capture and a metric cut-off deeper than the captured list. It uses `ir-measures==0.4.3` with explicit nDCG, Judged and RR definitions. Missing labels remain unknown in the contract; the library treats them as zero for these metrics, so coverage is reported separately.

```powershell
$env:PYTHONPATH = (Resolve-Path .lab/python-libs).Path
python evaluation/offline.py --observations .lab/offline-7j/direct-observations-10k-v2.json --judgements .lab/releases/retail-gb-10k-v1/judgements.jsonl --judgement-manifest .lab/artifacts-v2/retail-gb-10k-v1/judgement-set.json --specification evaluation/specs/proxy-v1.json --catalogue-manifest .lab/artifacts-v2/retail-gb-10k-v1/catalogue.json --query-manifest .lab/artifacts-v2/retail-gb-10k-v1/query-suite.json --output .lab/offline-7j/direct-report-10k-v2.json
```

The independently built evaluator image also completed a 1,000-query rescore with Docker networking disabled. A synthetic assessor revision changed `S`/grade-2 labels to `E`/grade-3 without consulting API output; specification v2 added nDCG@5. The same observation bytes produced two separately retained reports. This demonstrates independent versioning, not improved or externally valid relevance.

`evaluation/run_job.py` also runs the image as a finite `lab-offline-evaluation` Job. It downloads six hash-checked Blob inputs, scores them with no Search API access and retains a new report. The Job has no Kubernetes API token; its policy allows only DNS and Floci egress. A 1,000-query Job reproduced the standalone report SHA-256 exactly. The temporary Blob Secret and Job are removed after completion. Both finite Jobs emit one structured outcome event to Kubernetes stdout. The scoped OTel log agent forwards it to SigNoz, with only Job identity, duration and immutable source/input/report hashes; the Jobs retain Blob-only network egress. The [runtime evidence](research/evidence/signoz-finite-jobs-2026-09-28.md) records the live run.

For the million-product fixture, set `DATA_BLOB_CONNECTION_STRING` to the local Floci connection and run:

```powershell
python evaluation/run_job.py --observation-reference .lab/offline-7j/observations-v3.ref.json --specification-reference .lab/offline-7j/spec-v1.ref.json --catalogue-manifest .lab/artifacts-v2/retail-gb-1m-v1/catalogue.json --query-manifest .lab/artifacts-v2/retail-gb-1m-v1/query-suite.json --judgement-manifest .lab/artifacts-v2/retail-gb-1m-v1/judgement-set.json
```

The `.lab/` fixture and credential files are local ignored state; publish or fetch equivalent immutable references before using a clean checkout.

Delivery's [observation evidence policy](../lab/delivery/policies/observation-evidence-v1.json) checks exact environment/data/observation/judgement/specification/evaluator hashes, capture and evaluation age, required metrics, coverage and human review. `lab/attach_offline_evidence.py` binds an offline report and its input hashes to existing comparison evidence. Proposal validation repeats these checks. The optional policy addendum has not yet replaced the original three checks in the control UI. A passing evaluation policy does not approve a release.

## Index and retention boundaries

Index recipe format 2 pins a catalogue manifest and product bytes independently of query and judgement changes. New environments and delivery definitions use format 2 by default. Before a recipe is admitted, the controller checks the retained manifest and streams its product bytes to verify size and SHA-256. A format-2 shared index has a recipe-derived name; API-only environments reuse that index. An explicitly selected format-1 recipe still supports historical frozen-index recovery under its original name.

Retain catalogue bytes/manifests, query and judgement versions, traffic/workload sources, observations, evaluation specifications/reports, evaluator and Search API image digests, index recipes/snapshots, desired-state revisions and verification reports for replay and rollback. Preview Jobs, Pods, temporary credentials and namespaces are disposable after their references are retained. Automatic artifact deletion remains disabled. Floci data, Nexus layers, Git, Elasticsearch snapshots and the control PVC require separate backups.
