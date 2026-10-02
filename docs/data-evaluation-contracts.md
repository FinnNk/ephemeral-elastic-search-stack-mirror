# Frozen inputs and evaluation contracts

Products, queries, labels and traffic are supplied independently of the Search API. Their manifests identify the exact bytes and dependencies. Evaluation captures public API results once, then scores those saved observations without issuing another search request.

The default products, queries and labels come from ESCI, with ESCI-S metadata and documented lab augmentations. Arrival times and the independent example pack are synthetic. [Catalogue setup](esci-catalogue.md) describes source selection and pricing. Missing labels mean **unknown**; grade zero explicitly means non-relevant.

## Contracts

| Artefact | Pins | Consumer |
| --- | --- | --- |
| Catalogue | Product-file hash, row count, country/currency and producer | Indexer and index recipe |
| Query suite | Original requests and content hash | API capture and workload compiler |
| Judgement set | Explicit grades 0–3 and catalogue/query hashes | Relevance evaluator |
| Traffic trace | Timestamped query references and query-suite hash | Gatling compiler |
| Observation set | Named variants, environment/configuration/image identities and returned IDs/totals | Offline evaluator |
| Evaluation specification | Metrics, cut-offs, aggregation and unjudged policy | Pinned evaluator |
| Report | Observation, label, specification and evaluator hashes; scores and coverage | Comparison history and decision policy |
| Decision policy | Required evidence, coverage, thresholds, age and permitted exceptions | Trusted gate or promotion validator |

Input envelopes contain `kind`, `schema_version`, `content`, `dependencies`, `producer` and `record_count`. `producer.synthetic` states whether the pack is wholly synthetic; published packs must include `producer.sources`. Published labels retain E/S/C/I assessments and grades 3/2/1/0. `content.object` names hash-addressed source bytes. Label and traffic manifests reference the original query hash; labels also reference the catalogue hash. A catalogue can contain multiple countries with one currency per country.

The `data/` package generates and validates inputs without importing search or control code. `judgements/` resolves missing labels. `evaluation/` scores captured results. Delivery owns release policy separately.

## Generate and publish an input pack

Use PowerShell from the repository root. Python needs the dependencies in `lab/requirements-azure.txt`; evaluation also needs `lab/requirements-eval.txt`. Choose a new output directory rather than replacing frozen bytes.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$pack = Join-Path $env:LAB_STATE_DIR releases/retail-gb-independent-example-v2
$manifests = Join-Path $env:LAB_STATE_DIR artifacts/retail-gb-independent-example-v2
python data/generate_example.py --output $pack
python data/publish.py --input-dir $pack --output $manifests --producer independent-example-v2 --source-release retail-gb-independent-example-v2
```

The example writes 12 products, three queries and rules-based labels. Publication validates IDs, markets and references and prints content/manifest hashes. This first command pair creates local manifests only.

For Blob publication, ask the operator for the local Blob Storage emulator connection string through their secret channel and set it without printing it:

```powershell
$blobConnection = Read-Host 'Local Blob Storage emulator connection string' -AsSecureString
$env:DATA_BLOB_CONNECTION_STRING = [System.Net.NetworkCredential]::new('', $blobConnection).Password
python data/publish.py --input-dir $pack --output $manifests --producer independent-example-v2 --source-release retail-gb-independent-example-v2 --blob-url http://127.0.0.1:14577/devstoreaccount1
```

Keep the operator's Blob Storage emulator port-forward on port `14577` running. Existing objects must match; a conflict fails rather than replacing them. Clear `DATA_BLOB_CONNECTION_STRING` when finished. Azure publication uses an HTTPS account URL and workload identity instead of the emulator credential.

For the default catalogue, follow [ESCI catalogue setup](esci-catalogue.md). The importer retains source checksums, selection rules and augmentation counts. Publication carries that provenance into each independent manifest.

`lab/default_inputs.json` owns control/delivery defaults. `lab/publish_default_inputs.py` republishes those exact source manifests and checks their expected hashes; a different producer does not automatically replace those defaults.

## Capture once, score again

Follow the [evaluation runbook](evaluation-runbook.md) for complete commands and input origins. The current observation contract is `search-variant-observation-set`: two or more named variants, one default and one independently selected metric baseline. A replacement release uses two pinned deployments; compatible configurations may share a runtime/index.

The evaluator checks catalogue/query/label dependencies, duplicate or incomplete results and metric depth. It uses pinned `ir-measures` definitions. Missing labels remain unknown, although the metric library scores them as zero; read coverage alongside every relevance score.

The control UI scores its explicitly selected frozen labels. The separate [judgement workflow](judgement-resolution.md) pools missing pairs from all variant result lists, freezes one resolved label set and scores every variant against it. A changed recall set produces new evidence, leaving earlier reports intact.

## Exploratory notebooks after a comparison

Select the packaged notebook in the [lab workflow](../lab/README.md#download-exploratory-analysis), or run it against a saved evaluation report using the runbook. Reuse the maintained illustrations there.

Papermill runs the selected `lab/notebooks/` file as a finite Kubernetes Job. It receives a read-only report URL, no Kubernetes API token or write credential, a five-minute deadline and Blob-only egress. Its output is retained by hash. Notebook failure is separate from the comparison verdict and cannot change a gate decision.

To install support, publish with `python lab/notebook/publish.py`, then run `python lab/install_notebooks.py` and update the [control image](control-runtime.md#update-an-existing-runtime). The publisher writes `notebook-image.json` in retained state. Adding a notebook requires code review, a Papermill `parameters` cell and a rebuilt control image; arbitrary filenames outside the packaged set are rejected.

## Retention and finite Jobs

Retain catalogue/query/label/traffic manifests and bytes, observations, specifications, reports, model/image identities, recipes/snapshots and desired-state verification records. Runtime namespaces, temporary credentials and completed Jobs are disposable. Blob, Nexus, Git and the control PVC need separate backups.

The catalogue-only recipe keeps index identity independent of query and label revisions. The controller verifies its catalogue bytes before reuse or rebuild. Historical restore uses the explicitly retained recipe, never today's mapping by assumption.

Producer/evaluator Jobs use separate namespaces, scoped Blob access and no Kubernetes API token. They emit safe outcome/hash logs through the scoped log agent. The local Blob Storage emulator (Floci) shares an account credential and cannot prove independent Azure write scopes. See [finite-Job evidence](research/evidence/signoz-finite-jobs-2026-09-28.md) and [contract evidence](research/evidence/independent-data-evaluation-contracts.md) for dated scope.
