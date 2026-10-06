# Fill missing relevance labels

A ranking change may retrieve products outside the existing label pool. This workflow collects missing query/product pairs from **all** variants, asks a separate judgement service for labels and freezes one set before scoring. Published source labels take precedence. Each model pass retains its own predictions, abstentions and provenance behind the API.

The current judgement APIs use the CPU abstaining MLflow model version 1 served
by KServe. New pairs remain unknown when it abstains. The calibrated model
version 4 remains available as a separately installed GPU candidate; its saved
predictions retain their original identity. The full ESCI lab catalogue currently uses published labels plus cached model-4 predictions under a **temporary demo policy**. Strict gate selection excludes those predictions; demo reports disclose their unqualified accuracy.

## Services and outcomes

| Component | Responsibility |
| --- | --- |
| Judgement API | Verifies the selected frozen query/product pair; returns stored labels or model outcomes |
| MLflow | Holds numbered model versions; PostgreSQL metadata and separate S3 model artefacts |
| KServe Standard | Loads the exact model version and checks its artefact digest |
| Azure Blob Storage | Supplies hash-checked catalogue, queries and source labels |
| ESO | Supplies retained registry, storage and pull credentials |

These services are shared in `lab-models`, outside search experiment namespaces. Each prediction returns its model identity; the judgement service rejects a different identity.

| Outcome | Treatment |
| --- | --- |
| `labelled` with E/S/C/I | Grade 3/2/1/0 respectively; eligibility determines whether it can enter a gate snapshot |
| `abstain` | Unknown; remains unjudged |
| Inference failure | Recorded separately; evaluation is incomplete |

## Sources and selection

![Progressive judgement resolution](diagrams/rendered/judgement-coverage.png)

[Interactive workflow](diagrams/interactive/judgement-coverage.html) ·
[Editable source](diagrams/archify/judgement-coverage.json)

| Selection | Labels returned |
| --- | --- |
| `gate` (default) | Published and human labels, plus model labels explicitly qualified by the operator's pinned policy |
| `exploratory` | Also accepts unqualified candidate predictions |
| `demo` | Adds only model predictions authorised by the configured lab demo policy; they remain unqualified |

Published labels win, followed by human labels. Stored evidence lookup selects
the earliest accepted model pass allowed by the selection. Resolution uses the
active pinned model and policy for remaining pairs, reusing its saved inference
outcomes. Authorised imported demo labels remain available under their scoped
policy. Model versions do not overwrite each other.
A new pass targets unresolved pairs. Another model can judge a pair where an
earlier model abstained; an unchanged model reuses its saved abstention.

## Iterate on a search change

Each comparison searches all variants again, pools their returned pairs and
freezes one shared judgement set before scoring. Search results are never
reused by the inference cache.

| Change | Resolution behaviour |
| --- | --- |
| Same pair, model, runtime and protocol | Reuse saved probabilities or abstention |
| New recall pair or changed query/product input | Perform inference |
| Changed model artefact, runtime image, protocol or rubric | Perform inference under a new cache identity |
| Changed acceptance thresholds | Apply the pinned policy to saved probabilities; retain a separate decision |
| Earlier transient failure | Retry inference; failures are not cached as successful outcomes |
| Explicit fresh inference | Retain another attempt; ordinary resolution still uses the first successful outcome |

The identity covers the complete request, including filters, the product
document, model version and artefact, runtime image digest, protocol digest,
input contract and rubric. An unchanged input can be reused across dataset
releases after the service verifies it against the selected frozen sources.
Published and human labels take precedence, including during a fresh attempt.

The API requires a pinned `inference.json` beside `model.json`. Bootstrap
manifests supply it; the ESCI deployment renderer supplies it with live model
pins. Update these pins whenever the serving runtime or protocol changes.
An optional model policy `acceptance` holds the `esci-abstention-v1` thresholds;
its `policy_sha256` must match their canonical digest. Changing thresholds never
qualifies a model automatically. Demo decisions still require the scoped human
authorisation in the configured demo policy.

`POST /v1/judgements:resolve` accepts `fresh_inference: true` for a deliberate
new attempt. The evaluator and gap-pass runner expose `--fresh-inference`.
Use a new output directory for each evaluation: frozen artefacts cannot be
overwritten. API responses report `cache_hits`, `inferred_pairs` and whether
fresh inference was requested under `execution`.

## Read the search comparison

- **Search quality:** compare NDCG and other relevance scores within the report.
  All variants use the same frozen judgements.
- **Judgement coverage:** inspect published/model counts, abstentions and
  remaining gaps separately. Added labels are not evidence of better search.
- **Result changes:** use RBO and Jaccard to inspect changes independently of
  label availability.

When labels change, score both baseline and candidate against the new shared
set. Do not compare a new candidate score with a baseline scored against an
older judgement set. Frozen rescoring remains unchanged and performs no
inference. The [cache replay evidence](research/evidence/inference-reuse/README.md)
records the distinction between inference reuse and model-quality claims.

The API retains source identity, complete model identity, release and policy
hashes, pass identity, confidence, scores and inference time when supplied.
`POST /v1/judgements:records` returns every retained record for requested pairs;
`POST /v1/judgements:import` appends a frozen model pass. Imports cannot make model
predictions gate-eligible. Both require the exact source context and at most
128 records or pairs. Reimporting identical records is idempotent.

Use `--selection exploratory` with `judgements/evaluate.py` for exploratory
scores. Frozen rows retain provenance and eligibility. Reports identify their
selection and unqualified label count; the trusted merge gate rejects exploratory
reports. Strict gates reject unqualified labels. The temporary demo gate accepts only the exact model, source scope and acceptance policy recorded in its protected policy. A business override cannot authorise other model labels.

## Temporary ESCI demo labels

The default full-catalogue comparison uses the [demo policy](../judgements/policies/esci-lab-demo.json): Exact confidence at least **0.75**, and Substitute, Complement or Irrelevant at least **0.40**. Published labels always win. Predictions below their class threshold remain unknown.

The measured frozen recall set has **81.22% coverage**: 2,946 published labels and 5,107 model predictions over 9,915 returned pairs. Coverage measures labels available, not their correctness. New search results can lower coverage.

To replay a saved pass, use PowerShell from the reference repository root. `$savedPass` is the complete model-4 pass retained in `.lab/esci-packaging/progressive-20261003/first-pass/pass.json` on this lab host. Use a new output path. Set the retained state directory first:

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$savedPass = Join-Path $env:LAB_STATE_DIR 'esci-packaging/progressive-20261003/first-pass/pass.json'
python judgements/demo.py --saved-pass $savedPass --policy judgements/policies/esci-lab-demo.json --output "$env:LAB_STATE_DIR/esci-demo-coverage/pass.json"
```

Keep this command running in a separate PowerShell terminal from the reference repository root:

```powershell
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-models port-forward service/judgement-service-million 18089:18086 --address 127.0.0.1
```

Then import the replayed pass in the first terminal:

```powershell
python judgements/fill_gaps.py import --pass-file "$env:LAB_STATE_DIR/esci-demo-coverage/pass.json" --import-url http://127.0.0.1:18089/v1/judgements:import
```

Its Deployment mounts `judgement-demo-policy`. Imports validate the probabilities, label and policy pin; the original pass stays unchanged. The API continues to report model **1** as its abstaining inference fallback, while cached predictions retain model **4** in their provenance. No GPU is needed for replay or lookup.

Add `--selection demo` to the evaluation command below to select these cached labels. The control page already selects the published demo snapshot by default for `esci-gb-v1`; the small demo catalogue retains its published labels.

To restore strict behaviour, select the original published judgement manifest, remove `lab_demo_judgements` from the protected merge policy and update its trusted pin after review. Keep retained demo reports as evidence. See the [batch plan](plans/esci-demo-coverage.md) and [measured results](research/evidence/esci-demo-coverage.md).

## Install or verify

Operator prerequisites: bootstrapped lab, Nexus/storage/ESO, Python and the retained state directory. Use PowerShell from the repository root. Image publication and installation are separate from read-only verification.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
python lab/setup_judgement_stack.py --verify-only --million
```

On a new installation, first publish the source-matching image with `python lab/publish_judgement_image.py --platforms amd64`, then run `python lab/setup_judgement_stack.py --million`. Setup validates its image pin and configures cert-manager, KServe, MLflow, Secrets and the 10k source service. Add `--million` only when the 1M source is required; it shares the registry and predictor. Native arm64 requires its own verified image. Bootstrap refuses to reset an installed replacement model to the original abstaining version.

## Capture, resolve and score

First prepare `$inputDir`, `$manifestDir`, `$runDir` and the captured `observations.json` using the [evaluation runbook](evaluation-runbook.md). Use matching products, source labels and manifests. In a separate terminal, forward the **10k** service and keep it running:

```powershell
kubectl --kubeconfig $kubeconfig -n lab-models port-forward service/judgement-service 18086:18086 --address 127.0.0.1
```

For a 1M capture, use `service/judgement-service-million` instead. Port `18086` is also used by a host delivery coordinator; do not run that coordinator concurrently. Read the deployed pin, not a registry alias:

```powershell
$modelData = kubectl --kubeconfig $kubeconfig -n lab-models get configmap judgement-model-pin -o json | ConvertFrom-Json
$model = $modelData.data.'model.json' | ConvertFrom-Json
$catalogue = Get-ChildItem $inputDir -Filter 'products.jsonl*' | Select-Object -ExpandProperty FullName
python judgements/evaluate.py --observations "$runDir/observations.json" --specification evaluation/specs/proxy-v1.json --catalogue $catalogue --catalogue-manifest "$manifestDir/catalogue.json" --query-manifest "$manifestDir/query-suite.json" --source-judgements "$inputDir/judgements.jsonl" --source-manifest "$manifestDir/judgement-set.json" --output "$runDir/resolved" --resolve-url http://127.0.0.1:18086/v1/judgements:resolve --model-name $model.name --model-version $model.version --model-artifact-sha256 $model.artifact_sha256
```

The demo and full ESCI manifests currently share `judgement-model-pin`. Confirm the selected Deployment still references it before using those values. The input pack must contain exactly one product file.

| Output under `resolved/` | Purpose |
| --- | --- |
| `frozen/judgements.jsonl` | Source labels plus resolved labels; abstentions remain absent |
| `frozen/judgement-set.json` | Frozen dependencies and provenance |
| `frozen/resolution.json` | Attempt outcomes, identities and per-variant coverage |
| `evaluation.json` | Every variant scored against that same frozen set |

The command prints hashes, metrics and completeness. Inspect failures before trusting scores. Changed recall or model identity requires a new output directory. Frozen bytes cannot be overwritten by a conflicting replay.

## Replace or investigate the model

Follow [model installation](esci-model-installation.md) for packaging, qualification, activation and rollback. Change KServe's numbered version/digest and the judgement-service pin together. Published labels always win. Model evidence is retained under its full provenance and source scope; the active inference model remains explicit.

The predictor timeout defaults to eight seconds. `JUDGEMENT_PREDICT_TIMEOUT_SECONDS` accepts a positive value up to 600; `--resolve-timeout` defaults to ten and accepts up to 900. Slower candidate limits need measured validation, not just larger timeouts.

The [model dashboard](observability-backend.md#interpret-dashboards) shows outcomes, failures, latency and coverage. Select the model version to separate the current judge from historical activity. Gap-pool shift compares the frozen query-length mix with pairs sent for resolution, including cached outcomes; it is not training drift or accuracy. Coverage and shift are separated by label selection. The frozen resolution report owns exact pool counts. Trace context crosses the comparison, judgement API and KServe when they can reach the OTLP gateway. Telemetry excludes query text and product bodies.

After local storage/container recreation, `lab/setup_judgement_secrets.py` refreshes the model-store EndpointSlice; `lab/setup_nexus.py` refreshes Nexus connectivity. Azure uses platform endpoints and requires separate identity/storage validation.

The control UI still scores its selected frozen labels; automatic gap resolution is this separate workflow. [Dated execution evidence](research/evidence/mlflow-kserve-judgement-coverage.md) records coverage and topology limits.

## Run successive lab passes

Use the `$inputDir`, `$manifestDir`, `$runDir` and `$catalogue` values from
[Capture, resolve and score](#capture-resolve-and-score). Run PowerShell from the
repository root. Create a new pass directory for each model/policy attempt.

1. Freeze the unresolved pooled pairs:

   ```powershell
   $passDir = Join-Path $runDir judgement-pass-01
   python judgements/fill_gaps.py freeze --observations "$runDir/observations.json" --specification evaluation/specs/proxy-v1.json --catalogue $catalogue --catalogue-manifest "$manifestDir/catalogue.json" --query-manifest "$manifestDir/query-suite.json" --source-judgements "$inputDir/judgements.jsonl" --source-manifest "$manifestDir/judgement-set.json" --output "$passDir/inputs.json"
   ```

   Supply each earlier `pass.json` with `--previous-pass` to skip accepted
   predictions and retry remaining gaps. The command prints the gap count and
   frozen input hash.

2. Audit the queries against research reservations. Save `exclusions.json` in
   `$passDir`, containing `inputs_sha256` from step 1, `audit_complete: true` and
   the excluded `query_ids` array. Resolve reservation conflicts before
   inference. An empty exclusion list still requires a completed audit.

3. Start an isolated Judgement API with the candidate's pinned model and an
   explicit unqualified model policy, following [model installation](esci-model-installation.md).
   Set `$candidateUrl` to that API's forwarded address. Read its model identity,
   then run the pass:

   ```powershell
   $candidateUrl = 'http://127.0.0.1:18088'
   (Invoke-RestMethod "$candidateUrl/health").model | ConvertTo-Json | Set-Content "$passDir/model.json" -Encoding utf8
   python judgements/fill_gaps.py run --inputs "$passDir/inputs.json" --exclusions "$passDir/exclusions.json" --model "$passDir/model.json" --output "$passDir/results" --resolve-url "$candidateUrl/v1/judgements:resolve"
   ```

   The command prints batch progress and final counts. `results/pass.json`
   freezes every accepted label, abstention and failure. Incremental attempts
   remain available if the process stops; an incomplete pass cannot be imported.

4. Forward the matching shared service as above, then import the complete pass:

   ```powershell
   python judgements/fill_gaps.py import --pass-file "$passDir/results/pass.json" --import-url http://127.0.0.1:18086/v1/judgements:import
   ```

   Import appends evidence without activating that model. Evaluate with
   `--selection exploratory` to use the new predictions. Inspect source
   contributions and remaining gaps before choosing another model.

The [progressive pass plan](plans/esci-progressive-judgements.md) records the
current measured pass and its protected-query exception.

The current API database is `evidence.sqlite3`. Existing deployments create it
from frozen inputs instead of migrating the earlier disposable database. Old
model outcomes remain in their frozen experiment records. Delete an obsolete
cache only after confirming it contains no unique evidence you need to retain.

For controller installation or upgrades that preserve the selected model, see
[KServe installation](kserve-installation.md).

## Additional source queries

Source PR comparisons resolve the returned pairs for each additional query set
automatically. Exact query bytes are registered with the judgement service;
matching published requests reuse their reference labels. Other queries receive
stable identities tied to the frozen file. Products come from the pinned catalogue.

The coordinator freezes the resolution receipt and labels before scoring all
variants. Report-only suites may contain unqualified model labels, clearly marked
with their provenance. Required suites use qualified selection and still need
an authored reference-label file. The standard frozen gate suite is unchanged.

A report with no usable labels shows why nDCG cannot be calculated. A fully labelled
set containing only Irrelevant labels also cannot establish a positive ideal gain;
its coverage remains visible. Inference errors remain distinct from abstentions.
