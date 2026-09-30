# Install the v3 ESCI candidate through MLflow

This package installs **Larger v3 + learned score mapping** as a numbered MLflow
model. It contains the Decider 4B base, the unmerged 8,192-row v3 LoRA adapter,
the learned four-score mapping, the exact question and a versioned abstention
policy. The CUDA serving image is separate from the weights.

Registration is possible on a CPU machine. Activation requires a GPU and passing
serving checks. The current lab still serves the all-abstaining model: its k3d
nodes do not advertise `nvidia.com/gpu`. The ongoing table-model experiment uses
the laptop GPU; allow it to finish before running candidate inference.

## What the selected model promises

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
small MLflow wrapper and the CUDA image. Allow at least three copies of the model
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

Use PowerShell from this repository's root. Set `LAB_STATE_DIR` to the existing
lab state directory when working in a separate checkout. All paths below remain
outside Git under that directory.

```powershell
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
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

The release author can build from this machine's research checkout:

```powershell
& $py lab/install_judgement_model.py build --research-root "$env:LAB_STATE_DIR/esci-model-agent-repo" --output "$pack/esci-v3-score-map"
& $py lab/install_judgement_model.py inspect --bundle "$pack/esci-v3-score-map"
& $py lab/install_judgement_model.py canaries --research-root "$env:LAB_STATE_DIR/esci-model-agent-repo" --bundle "$pack/esci-v3-score-map" --output "$pack/canaries.json"
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

## 3. Register in the lab's MLflow

The existing [judgement stack](judgement-resolution.md#start-or-verify-the-stack)
must already be installed. Keep this port forward running in a second terminal:

```powershell
kubectl --kubeconfig "$env:LAB_STATE_DIR/kubeconfig.yaml" -n lab-models port-forward service/mlflow-mlflow 5000:5000
```

Then register the bundle. The server uses its existing object-store credentials;
the client does not need an S3 secret.
Keep transfers through the MLflow proxy: the lab's presigned S3 addresses resolve
inside Kubernetes and are not reachable directly from the laptop.

```powershell
& $py lab/install_judgement_model.py register --bundle "$pack/esci-v3-score-map" --tracking-uri http://127.0.0.1:5000 --receipt "$pack/registration.json"
```

This uploads a self-contained MLflow pyfunc and writes its version/digest receipt.
The active service and its model pin are unchanged. Repeat the command to verify
and reuse the registration. Keep the receipt beside the release. Protect registry
and object-store access: MLflow models include executable Python code.

## 4. Publish the separate runtime image

```powershell
& $py lab/publish_esci_image.py
$image = (Get-Content "$env:LAB_STATE_DIR/esci-image.json" -Raw | ConvertFrom-Json).image
& $py lab/install_judgement_model.py render --receipt "$pack/registration.json" --image $image --output "$pack/candidate.json"
```

The publisher uses the lab's existing Nexus publisher credentials without
printing them. It records the immutable registry digest in `esci-image.json`.
The image contains dependencies and serving code; it does not contain model
weights. The generated candidate has a separate service name and no live model
ConfigMap. Existing CPU images remain usable for MLflow, the storage initialiser
and the judgement API.

Publish the updated CPU API image too; it adds a configurable model-call timeout
while preserving the existing default for the all-abstaining model:

```powershell
& $py lab/publish_judgement_image.py --platforms amd64
$apiImage = (Get-Content "$env:LAB_STATE_DIR/judgement-image.json" -Raw | ConvertFrom-Json).image
```

## 5. Qualify on a GPU before promotion

First make a CUDA-capable node available to Kubernetes and confirm it advertises
`nvidia.com/gpu`. Configuring GPU passthrough/device plugins and restarting the
current lab are separate platform work. Do not start inference while the research
pipeline owns the laptop GPU.

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

Before applying, save the current InferenceService, `judgement-model-pin`
ConfigMap and replica counts for `judgement-service` and
`judgement-service-million` if present. Remove server-managed fields (`status`,
`metadata.managedFields`, `resourceVersion`, `uid`, timestamps) from saved
resource manifests intended for replay. Retain the previous ServingRuntime and
registered version.

Promotion has a short maintenance window:

1. Stop evaluation clients and scale the two judgement APIs to zero, preserving
   their original replica counts. This prevents calls with a mismatched pin.
2. Delete `inferenceservice/esci-v3-candidate` and wait for its Pod to terminate
   so the one GPU is free.
3. Apply `live.json`. It replaces the active InferenceService and the **shared**
   `judgement-model-pin` used by both API profiles.
   While the APIs remain scaled to zero, set their `judgement-service` and
   `fetch-source` container images to `$apiImage`, and set
   `JUDGEMENT_PREDICT_TIMEOUT_SECONDS=120` on the API containers. Use
   `kubectl set image` and `kubectl set env` against each existing Deployment;
   retain their original images/environment for rollback. Updating the complete
   bootstrap manifests here would restore the old model ConfigMap, so use these
   targeted Deployment updates.
4. Wait for `inferenceservice/synthetic-esci-judge` to become Ready. The predictor
   loads and warms the model before exposing `/health`. Verify its Pod image ID,
   model identity and predictions with the same qualification command through
   its forwarded service.
5. Restore the saved API replica counts. Confirm their new frozen source context
   names the selected model and run the pooled gap workflow against a new output
   directory. Recheck stored-label precedence and forged-record rejection.
   Include `--resolve-timeout 130` in the evaluator command so the caller allows
   the API to finish its model request.

If start-up, identity or qualification fails, keep the APIs stopped, reapply the
saved service and ConfigMap, wait for the previous predictor, then restore the
saved replicas. Previously frozen evaluations and version-scoped caches remain
available. There is no automatic cache rewrite or deletion.

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
& $py -m ruff check judgements/esci lab/install_judgement_model.py lab/publish_esci_image.py --ignore E402
```

The tests cover exported mapping parity, input text, abstention boundaries,
corrupt bundles, the pyfunc contract, real MLflow save/download/reload/reuse and
refusal of mismatched promotion evidence. The MLflow test uses a tiny synthetic
bundle and a stubbed inference engine; it does not claim GPU parity. See the
[implementation evidence](research/evidence/esci-model-bundle.md) for checks
actually executed, release identity and outstanding runtime work.
