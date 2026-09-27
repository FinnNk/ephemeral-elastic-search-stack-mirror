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

The v1 input envelope is a small JSON document with `kind`, `schema_version`, `content`, `dependencies`, `producer` and `record_count`. `content.object` is addressed by the unchanged file hash. An absent judgement is **unknown**; grade zero is an explicit non-relevant assessment. A catalogue may contain several countries, but each country has one currency. The validator streams catalogue records through a temporary SQLite identity index and checks duplicate IDs, judgement references, market context, frozen file hashes and traffic/query references. It validated the existing 1M pack without changing any input bytes.

## Publish independent inputs

```powershell
python data/generate_example.py --output .lab/releases/retail-gb-independent-example-v1
python data/publish.py --release-dir .lab/releases/retail-gb-independent-example-v1 --output .lab/artifacts/retail-gb-independent-example-v1 --producer independent-example-v1
python data/publish.py --release-dir .lab/releases/retail-gb-1m-v1 --output .lab/artifacts/retail-gb-1m-v1 --producer legacy-million-v1 --traffic lab/traffic/source-trace-million-v2.csv
```

Set `DATA_BLOB_CONNECTION_STRING` using the separately retained emulator credential, add `--blob-url http://127.0.0.1:14577/devstoreaccount1`, and the publisher stores both original files and manifests in Floci's `datasets` container. Repeating publication verifies the existing immutable objects. For Azure, use an HTTPS account URL and workload identity; the producer package does not assume an emulator key. The local emulator currently shares one account credential across producer and consumer roles, so it cannot demonstrate separate write scopes.

`python lab/publish_tool_images.py` publishes separate amd64/arm64 producer and evaluator images to Nexus. `python data/run_job.py` runs the example producer as a finite `lab-data` Job with no Kubernetes API token. Its policy permits DNS and Floci egress only; the temporary Blob credential and Job are removed afterwards. The retained image-pull secret and namespace support subsequent runs.

## Capture once, score again

New functional comparisons retain a `search-observation-set` Blob independently of the comparison report. The comparison API exposes its hash and Blob reference. The first demonstration also used `evaluation/import_legacy.py` to adapt a complete earlier report; it did not reinterpret or rewrite that report.

`evaluation/capture.py` accepts a selected query file and manifest, a catalogue manifest, and the names of two already frozen APIs. It verifies their catalogue hashes, sends the exact original requests through the existing finite comparison Job, and retains a new observation set. A three-query revised suite ran this way without another environment or index build. This explicit-input command is currently separate from the web UI's legacy release-based comparison selector.

The evaluator accepts observation, catalogue, query and judgement manifests plus a versioned specification. It rejects another catalogue/query suite, a mismatched judgement dependency, duplicate results, incomplete capture and a metric cut-off deeper than the captured list. It uses `ir-measures==0.4.3` with explicit nDCG, Judged and RR definitions. Missing labels remain unknown in the contract; the library treats them as zero for these metrics, so coverage is reported separately.

```powershell
$env:PYTHONPATH = (Resolve-Path .lab/python-libs).Path
python evaluation/offline.py --observations .lab/offline-7j/direct-observations-10k-v2.json --judgements .lab/releases/retail-gb-10k-v1/judgements.jsonl --judgement-manifest .lab/artifacts-v2/retail-gb-10k-v1/judgement-set.json --specification evaluation/specs/proxy-v1.json --catalogue-manifest .lab/artifacts-v2/retail-gb-10k-v1/catalogue.json --query-manifest .lab/artifacts-v2/retail-gb-10k-v1/query-suite.json --output .lab/offline-7j/direct-report-10k-v2.json
```

The independently built evaluator image also completed a 1,000-query rescore with Docker networking disabled. A synthetic assessor revision changed `S`/grade-2 labels to `E`/grade-3 without consulting API output; specification v2 added nDCG@5. The same observation bytes produced two separately retained reports. This demonstrates independent versioning, not improved or externally valid relevance.

`evaluation/run_job.py` also runs the image as a finite `lab-offline-evaluation` Job. It downloads six hash-checked Blob inputs, scores them with no Search API access and retains a new report. The Job has no Kubernetes API token; its policy allows only DNS and Floci egress. A 1,000-query Job reproduced the standalone report SHA-256 exactly. The temporary Blob Secret and Job are removed after completion.

For the million-product fixture, set `DATA_BLOB_CONNECTION_STRING` to the local Floci connection and run:

```powershell
python evaluation/run_job.py --observation-reference .lab/offline-7j/observations-v3.ref.json --specification-reference .lab/offline-7j/spec-v1.ref.json --catalogue-manifest .lab/artifacts-v2/retail-gb-1m-v1/catalogue.json --query-manifest .lab/artifacts-v2/retail-gb-1m-v1/query-suite.json --judgement-manifest .lab/artifacts-v2/retail-gb-1m-v1/judgement-set.json
```

The `.lab/` fixture and credential files are local ignored state; publish or fetch equivalent immutable references before using a clean checkout.

Delivery's [observation evidence policy](../lab/delivery/policies/observation-evidence-v1.json) checks exact environment/data/observation/judgement/specification/evaluator hashes, capture and evaluation age, required metrics, coverage and human review. `lab/attach_offline_evidence.py` takes the existing three-check evidence reference, retained offline report and policy references, and an explicit expected-input JSON file. It retains a new evidence version, verifies the policy bytes against the checked-in policy, and binds catalogue, query and observation hashes to the existing full relevance capture. Proposal validation repeats these checks. The legacy three-check path remains valid when no offline addendum is selected. A passing evaluation policy does not approve a release.

## Index and retention boundaries

Existing format-1 index recipes remain readable. Format 2 pins a catalogue manifest and product bytes without pinning query or judgement changes. A new v2 recipe is admitted only if its exact catalogue manifest is retained in Blob storage. A 10k dedicated-index preview using format 2 served search and was explicitly deleted. The 1M catalogue was published through the same envelope path; the existing shared index was not rebuilt for this contract demonstration.

Retain catalogue bytes/manifests, query and judgement versions, traffic/workload sources, observations, evaluation specifications/reports, evaluator and Search API image digests, index recipes/snapshots, desired-state revisions and verification reports for replay and rollback. Preview Jobs, Pods, temporary credentials and namespaces are disposable after their references are retained. Automatic artifact deletion remains disabled. Floci data, Nexus layers, Git, Elasticsearch snapshots and the control PVC require separate backups.
