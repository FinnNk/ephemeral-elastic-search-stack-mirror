# Install the v3 ESCI candidate through MLflow

This package installs **Larger v3 + learned score mapping** as a numbered MLflow
model. It contains the Decider 4B base, the unmerged 8,192-row v3 LoRA adapter,
the learned four-score mapping, the exact question and a versioned abstention
policy. The CUDA serving image is separate from the weights.

Registration is possible on a CPU machine. Activation requires a GPU and passing
serving checks. The retained installation evidence records an all-abstaining live model and no
Kubernetes GPU allocation. Check current node capacity and competing GPU work
before qualification; registration alone does not activate the candidate.

## Candidate behaviour and evidence

The initial policy emits its highest-scoring label when the mapped probability
is at least **0.90**; otherwise it abstains. On the already-opened Amazon research
cohort, this operating point accepted **37.17%** of pairs at **96.59%** accuracy
(9,694 total pairs; query-bootstrap accuracy interval **95.54–97.51%**). All accepted
labels were Exact; **12 Irrelevant pairs were accepted as Exact**. The threshold
was examined retrospectively. These figures do not establish greater than 95%
accuracy on the lab's synthetic UK catalogue.

The mapping transforms the four Decider probabilities with clipped logarithms,
standardisation and a multinomial logistic model. Only its numerical parameters
are exported. The training pickle, source examples and query identifiers stay in
ignored research storage. This release uses no embeddings or tabular foundation
model. It does not use the merged checkpoint, whose earlier parity check failed.

Inputs are the query, product title and final taxonomy element. A product's
`category` string is used when no `taxonomy_path` array is present. Model errors
remain errors; abstention never becomes Irrelevant. Existing source labels take
precedence, cached results remain scoped to the exact model version and frozen
source, and the existing 80% judged-coverage gate remains in force.

## Files, identities and capacity

| Item | Purpose |
| --- | --- |
| `judgements/esci/` | Input contract, score mapping, pyfunc, release verification and serving checks |
| `lab/install_judgement_model.py` | Build, inspect, register, export canaries, qualify and render manifests |
| `lab/publish_esci_image.py` | Build Linux x86 CUDA runtime and publish a Nexus digest |
| `judgements/esci/requirements.lock` | Resolved Python 3.12/Linux dependency versions |
| Ignored release directory | Base weights, adapter, mapping, policy and per-file SHA-256 manifest |
| Ignored registration receipt | Numbered MLflow URI, model-tree digest and implementation digest |

The built assets occupy **8,691,339,810 bytes (8.69 GB / 8.09 GiB)**, excluding the
small MLflow wrapper and the CUDA image (Docker reports **3.39 GB**). Allow at least three copies of the model
during registration/download/staging, plus the source checkpoint, runtime image
and registry storage. The storage initialiser stages a download before copying it
to `/mnt/models`; budget at least 18 GB of temporary space for that step.
KServe's default model volume is per Pod, so a replacement Pod downloads again.
A persistent shared model cache is not included in this change.

The candidate requests one NVIDIA GPU, two CPUs and 16 GiB host RAM, with a 24 GiB
RAM limit. These are initial resource settings, not measured serving capacity.
The laptop has 16 GB VRAM; inference uses BF16 and batches of at most eight pairs
internally. The API accepts at most 128 pairs and serialises GPU calls. CUDA
graphs are disabled. The Linux image and batch shape need independent numerical
qualification before activation; CPU packaging checks do not establish that
this serving configuration fits the GPU or reproduces research scores.

The assets, wrapper and runtime each have separate identities. Changing the
wrapper/dependency lock or assets creates a new registration identity; changing
the image produces a new digest. A repeated registration of identical assets and
wrapper reuses its numbered version. No mutable `latest` alias is used for
evaluation. Registration verifies the uploaded bytes by downloading them again.

## 1. Set up the release tools

Prerequisites: Python tooling (`uv`), the installed judgement stack, Docker for
image publication, and either a complete candidate bundle or its pinned research
assets. Use PowerShell from this repository's root. Set `LAB_STATE_DIR` to the existing
lab state directory when working in a separate checkout. All paths below remain
outside Git under that directory.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
$pack = Join-Path $env:LAB_STATE_DIR 'esci-packaging'
uv venv "$pack/.venv" --python 3.12
uv pip install --python "$pack/.venv/Scripts/python.exe" mlflow==3.16.1 numpy==1.26.4 scikit-learn==1.7.2 pytest==8.4.2 ruff==0.13.2
$py = "$pack/.venv/Scripts/python.exe"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:MLFLOW_HTTP_REQUEST_TIMEOUT = '600'
$env:MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR = 'false'
$env:MLFLOW_ENABLE_PROXY_MULTIPART_UPLOAD = 'false'
$env:MLFLOW_ENABLE_PROXY_MULTIPART_DOWNLOAD = 'false'
```

The small CPU environment intentionally lacks Torch. MLflow therefore reports
dependency differences during packaging. Inference uses the separately built
image and its locked dependencies. To resolve that lock again explicitly:

```powershell
uv pip compile judgements/esci/requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --no-header --no-annotate --emit-index-url --output-file judgements/esci/requirements.lock
```

A changed lock needs a new image, registration and serving qualification.

## 2. Build once, or obtain the existing bundle

Choose one route:

| Route | Required input |
| --- | --- |
| Install a supplied bundle | Complete portable bundle and its file-hash manifest from the model author; copy it to `$pack/esci-v3-score-map` and run `inspect` |
| Build the research candidate | Checkout containing the pinned base weights, adapter, saved predictions and learned mapping expected by `judgements/esci/release.py` |

The research assets are not generated by cloning this repository. Obtain them
from the model author; the builder rejects another revision. For the build route:

```powershell
$researchRoot = Read-Host 'Absolute path to the pinned model research checkout'
```

Then:

```powershell
& $py lab/install_judgement_model.py build --research-root $researchRoot --output "$pack/esci-v3-score-map"
& $py lab/install_judgement_model.py inspect --bundle "$pack/esci-v3-score-map"
& $py lab/install_judgement_model.py canaries --research-root $researchRoot --bundle "$pack/esci-v3-score-map" --output "$pack/canaries.json"
```

The builder accepts the pinned adapter and frozen mapping source only. The bundle
is a portable directory: copy it intact to another machine, inspect it and use
the registration command below. The original research checkout is unnecessary
for ordinary installation. Serving reference canaries contain source examples;
keep them local and outside Git. Export compares the numerical mapping against
all 9,694 saved predictions and checks the sampled v3 input hashes.

A completed bundle can be reused. A partial or changed bundle fails verification;
preserve it for diagnosis and choose a new output directory. Do not overwrite
canaries or failed qualification evidence.

## 3. Publish the runtime and API images

The existing [judgement stack](judgement-resolution.md#install-or-verify)
must already be installed. Publish the separate CUDA runtime:

```powershell
& $py lab/publish_esci_image.py
$image = (Get-Content "$env:LAB_STATE_DIR/esci-image.json" -Raw | ConvertFrom-Json).image
```

The publisher uses the lab's existing Nexus publisher credentials and records
the immutable registry digest in `esci-image.json`. The image contains
dependencies and serving code. Model weights are stored separately in MLflow.
Publish the updated CPU API image too; it adds a configurable model-call timeout
while preserving the default for the all-abstaining model:

```powershell
& $py lab/publish_judgement_image.py --platforms amd64
$apiImage = (Get-Content "$env:LAB_STATE_DIR/judgement-image.json" -Raw | ConvertFrom-Json).image
```

## 4. Register in the lab's MLflow

Use the local helper on this Windows/k3d installation. Two full-size transfers
through `kubectl port-forward` stalled during verification. The helper keeps
large transfers on the lab's Docker network:

```powershell
& $py lab/register_esci_local.py --bundle "$pack/esci-v3-score-map" --receipt "$pack/registration.json" --image $image
```

It runs without GPU access, mounts the bundle and source read-only, and shares
the existing `k3d-observability-0` node's network namespace. A hosts-file mount
inside the helper resolves the MLflow and object-store services. Chunked,
presigned transfers go directly to the object store, preserving MLflow's
allowed-host check and avoiding its 2 GiB server-memory limit. No node hosts
file or registry resource settings are changed.
The downloaded, verified MLflow directory is retained under
`$pack/registration-tmp`; the receipt records its host path for offline checks.

This uploads a self-contained MLflow pyfunc and writes its version/digest receipt.
The server uses its existing object-store credentials; the client needs no S3
secret. Repeat the command to verify and reuse the registration. Keep the receipt
beside the release. The active service and its model pin are unchanged.

For another installation with a directly reachable tracking endpoint, the
portable registration command is:

```powershell
& $py lab/install_judgement_model.py register --bundle "$pack/esci-v3-score-map" --tracking-uri $trackingUri --receipt "$pack/registration.json"
```

Set `$trackingUri` to that installation's reachable MLflow URL before running the
portable command, for example with `Read-Host`. Large-file transport outside
the supplied local helper requires separate verification: presigned addresses
must be reachable, and proxying this model caused an OOM in the lab's 2 GiB
MLflow Pod. The local helper explicitly enables direct multipart transfer.

Generate candidate manifests after registration:

```powershell
& $py lab/install_judgement_model.py render --receipt "$pack/registration.json" --image $image --output "$pack/candidate.json"
```

The candidate uses a separate service name and has no live model ConfigMap.
Existing CPU images remain usable for MLflow and the storage initialiser.

## 5. Qualify on a GPU before promotion

First make a CUDA-capable node available to Kubernetes and confirm it advertises
`nvidia.com/gpu`. Configuring GPU passthrough/device plugins and restarting the
lab are separate platform work. Confirm the GPU is available before inference.

```powershell
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" get nodes -o 'custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu'
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" apply -f "$pack/candidate.json"
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" -n lab-models wait --for=condition=Ready inferenceservice/esci-v3-candidate --timeout=20m
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" -n lab-models get pods -l serving.kserve.io/inferenceservice=esci-v3-candidate -o json
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" -n lab-models port-forward service/esci-v3-candidate-predictor 18087:80
```

Check the ready Pod's actual image ID against `$image` and retain its spec/status
with the evidence. Use a separate terminal while the port forward remains open:

```powershell
& $py lab/install_judgement_model.py qualify --endpoint http://127.0.0.1:18087/v1/models/esci-v3-candidate:predict --canaries "$pack/canaries.json" --receipt "$pack/registration.json" --image $image --output "$pack/qualification.json"
```

The check compares independent saved research scores with batch, singleton and
reversed-order requests. Every arrangement must agree within **0.0001** mapped
probability and have **zero** changed labels or abstentions. A failed check exits
non-zero and retains its results. Do not loosen this gate or silently change the
policy. The image digest in the qualification command is operator-supplied; the
separate Pod image-ID check is required to tie it to the actual runtime.

Repeat after a cold Pod restart with a new evidence filename. Numerical agreement
is separate from accuracy: inspect representative labelled lab pairs, acceptance
coverage and Irrelevant-to-Exact errors before describing the model as meeting a
lab precision target. The generated manifest gates on the supplied numerical
evidence; it does not certify a lab accuracy SLA.

## 6. Promote and retain rollback

Only a passing qualification for the same assets, MLflow identity and image can
render live pins:

```powershell
& $py lab/install_judgement_model.py render --receipt "$pack/registration.json" --image $image --qualification "$pack/qualification.json" --output "$pack/live.json"
```

Before applying, stop evaluation clients and save the current resources and
replica counts. Use the existing `$pack`, `$apiImage` and `$kubeconfig` from above.
The following records only APIs actually installed:

```powershell
$backup = Join-Path $pack ('rollback-' + (Get-Date -Format yyyyMMdd-HHmmss))
New-Item -ItemType Directory -Path $backup | Out-Null
$deployments = kubectl --kubeconfig $kubeconfig -n lab-models get deployments -o json | ConvertFrom-Json
$apis = @($deployments.items | Where-Object { $_.metadata.name -in @('judgement-service', 'judgement-service-million') })
$replicas = @{}
foreach ($api in $apis) { $replicas[$api.metadata.name] = $api.spec.replicas }
$replicas | ConvertTo-Json | Set-Content -Encoding utf8 "$backup/replicas.json"
$resources = @('inferenceservice/synthetic-esci-judge', 'configmap/judgement-model-pin') + @($apis | ForEach-Object { 'deployment/' + $_.metadata.name })
foreach ($resource in $resources) {
    $saved = kubectl --kubeconfig $kubeconfig -n lab-models get $resource -o json | ConvertFrom-Json
    $saved.PSObject.Properties.Remove('status')
    foreach ($field in @('managedFields', 'resourceVersion', 'uid', 'creationTimestamp', 'generation')) { $saved.metadata.PSObject.Properties.Remove($field) }
    $saved | ConvertTo-Json -Depth 100 | Set-Content -Encoding utf8 (Join-Path $backup ($resource.Replace('/', '-') + '.json'))
}
```

Check every export succeeded and retain the previous ServingRuntime and MLflow
version. This is a short maintenance procedure, not a rolling two-model rollout:

1. Scale the installed APIs to zero and confirm their Pods terminate:

   ```powershell
   foreach ($api in $apis) { kubectl --kubeconfig $kubeconfig -n lab-models scale deployment/$($api.metadata.name) --replicas=0 }
   kubectl --kubeconfig $kubeconfig -n lab-models get pods
   ```

2. Free the one GPU and apply the qualified live service and **shared** model pin:

   ```powershell
   kubectl --kubeconfig $kubeconfig -n lab-models delete inferenceservice/esci-v3-candidate --wait=true
   kubectl --kubeconfig $kubeconfig -n lab-models get pods
   kubectl --kubeconfig $kubeconfig apply -f "$pack/live.json"
   ```

   Wait for the candidate Pod to disappear before starting the active predictor.
3. Update each API's actual application-container name and its `fetch-source`
   image. Do not reapply the bootstrap manifests, which contain the old model pin:

   ```powershell
   foreach ($api in $apis) {
       $name = $api.metadata.name
       $container = @($api.spec.template.spec.containers)[0].name
       kubectl --kubeconfig $kubeconfig -n lab-models set image deployment/$name "$container=$apiImage" "fetch-source=$apiImage"
       kubectl --kubeconfig $kubeconfig -n lab-models set env deployment/$name --containers=$container JUDGEMENT_PREDICT_TIMEOUT_SECONDS=120
   }
   kubectl --kubeconfig $kubeconfig -n lab-models wait --for=condition=Ready inferenceservice/synthetic-esci-judge --timeout=20m
   kubectl --kubeconfig $kubeconfig -n lab-models get pods -l serving.kserve.io/inferenceservice=synthetic-esci-judge -o json
   kubectl --kubeconfig $kubeconfig -n lab-models port-forward service/synthetic-esci-judge-predictor 18087:80
   ```

4. Verify the actual predictor image ID and model identity. In another prepared
   terminal, repeat numerical qualification against the live service:

   ```powershell
   & $py lab/install_judgement_model.py qualify --endpoint http://127.0.0.1:18087/v1/models/synthetic-esci-judge:predict --canaries "$pack/canaries.json" --receipt "$pack/registration.json" --image $image --output "$pack/live-qualification.json"
   ```

5. Only after successful checks, restore the saved API replicas:

   ```powershell
   foreach ($name in $replicas.Keys) { kubectl --kubeconfig $kubeconfig -n lab-models scale deployment/$name --replicas=$($replicas[$name]) }
   ```

   Confirm the new frozen source context names the selected model. Run the
   [pooled gap workflow](judgement-resolution.md#capture-resolve-and-score) in a
   new output directory with `--resolve-timeout 130`. Recheck source-label
   precedence and forged-record rejection.

If startup, identity or qualification fails, keep APIs stopped. Restore the saved
service and ConfigMap first, wait for the previous predictor, then apply the
saved Deployment files (which restore images, environment and replicas):

```powershell
kubectl --kubeconfig $kubeconfig apply -f "$backup/inferenceservice-synthetic-esci-judge.json" -f "$backup/configmap-judgement-model-pin.json"
kubectl --kubeconfig $kubeconfig -n lab-models wait --for=condition=Ready inferenceservice/synthetic-esci-judge --timeout=20m
Get-ChildItem -LiteralPath $backup -Filter 'deployment-*.json' | ForEach-Object { kubectl --kubeconfig $kubeconfig apply -f $_.FullName }
```

Inspect readiness and the restored model identity before resuming clients.
Previously frozen evaluations and version-scoped caches remain available;
there is no automatic cache rewrite or deletion.

`setup_judgement_stack.py` is the original v1 bootstrap, including a smoke check
that expects every gap to abstain. It now refuses to reset a replacement model.
Use this guide for replacement verification and rollback. Platform-wide
reconciliation with an arbitrary replacement model remains separate work.

## Verification and remaining work

Run the CPU checks from the repository root:

```powershell
uv pip install --python $py -r lab/requirements-azure.txt -r lab/requirements-eval.txt
& $py -m pytest -q judgements/esci/test_release.py
& $py -m unittest discover -s lab -p test_esci_bootstrap_guard.py -v
& $py -m unittest discover -s judgements -p 'test_*.py' -v
& $py -m ruff check judgements/esci lab/install_judgement_model.py lab/publish_esci_image.py lab/register_esci_local.py --ignore E402
```

The tests cover exported mapping parity, input text, abstention boundaries,
corrupt bundles, the pyfunc contract, real MLflow save/download/reload/reuse and
refusal of mismatched promotion evidence. The MLflow test uses a tiny synthetic
bundle and a stubbed inference engine; it does not claim GPU parity. See the
[implementation evidence](research/evidence/esci-model-bundle.md) for checks
actually executed, release identity and outstanding runtime work.
