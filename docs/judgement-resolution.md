# Fill missing relevance labels

A ranking change may retrieve products outside the existing label pool. This workflow collects missing query/product pairs from **all** variants, asks a separate judgement service for labels and freezes one set before scoring. Stored source labels take precedence.

The initial model abstains on every pair. It demonstrates inference wiring without improving coverage; a reviewed replacement may supply labels.

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
| `labelled` with E/S/C/I | Grade 3/2/1/0 respectively |
| `abstain` | Unknown; remains unjudged |
| Inference failure | Recorded separately; evaluation is incomplete |

## Install or verify

Operator prerequisites: bootstrapped lab, Nexus/storage/ESO, Python and the retained state directory. Use PowerShell from the repository root. Image publication and installation are separate from read-only verification.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
python lab/setup_judgement_stack.py --verify-only
```

On a new installation, first publish the source-matching image with `python lab/publish_judgement_image.py --platforms amd64`, then run `python lab/setup_judgement_stack.py`. Setup validates its image pin and configures cert-manager, KServe, MLflow, Secrets and the 10k source service. Add `--million` only when the 1M source is required; it shares the registry and predictor. Native arm64 requires its own verified image. Bootstrap refuses to reset an installed replacement model to the original abstaining version.

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

The 10k and million manifests currently share `judgement-model-pin`. Confirm the selected Deployment still references it before using those values. The input pack must contain exactly one product file.

| Output under `resolved/` | Purpose |
| --- | --- |
| `frozen/judgements.jsonl` | Source labels plus resolved labels; abstentions remain absent |
| `frozen/judgement-set.json` | Frozen dependencies and provenance |
| `frozen/resolution.json` | Attempt outcomes, identities and per-variant coverage |
| `evaluation.json` | Every variant scored against that same frozen set |

The command prints hashes, metrics and completeness. Inspect failures before trusting scores. Changed recall or model identity requires a new output directory. Frozen bytes cannot be overwritten by a conflicting replay.

## Replace or investigate the model

Follow [model installation](esci-model-installation.md) for packaging, qualification, activation and rollback. Change KServe's numbered version/digest and the judgement-service pin together. Source labels always win; inferred labels are cached under that exact model and source scope.

The predictor timeout defaults to eight seconds. `JUDGEMENT_PREDICT_TIMEOUT_SECONDS` accepts a positive value up to 600; `--resolve-timeout` defaults to ten and accepts up to 900. Slower candidate limits need measured validation, not just larger timeouts.

The [model dashboard](observability-backend.md#interpret-dashboards) shows outcomes, failures, latency and coverage. Input shift compares query-length buckets with the attempted pair mix; it is not training drift or accuracy. Trace context crosses evaluator, judgement API and KServe when the evaluator can reach the OTLP gateway. Telemetry excludes query text and product bodies.

After local storage/container recreation, `lab/setup_judgement_secrets.py` refreshes the model-store EndpointSlice; `lab/setup_nexus.py` refreshes Nexus connectivity. Azure uses platform endpoints and requires separate identity/storage validation.

The control UI still scores its selected frozen labels; automatic gap resolution is this separate workflow. [Dated execution evidence](research/evidence/mlflow-kserve-judgement-coverage.md) records coverage and topology limits.
