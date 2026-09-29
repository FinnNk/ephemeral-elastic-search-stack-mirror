# Judgement gap resolution

This workflow fills gaps exposed by a baseline or candidate's returned products. All inputs and existing labels are synthetic. The first registered model abstains on every gap, so it exercises the model path without increasing coverage.

## Local topology

| Component | Role | Retained state |
| --- | --- | --- |
| MLflow | Registered model versions | PostgreSQL metadata; S3 artefacts under a separate `mlflow/` prefix |
| KServe Standard | Loads and serves an exact registry version | Initialiser checks the model artefact SHA-256 before readiness |
| Judgement API | Verifies frozen pairs; returns stored labels or model outcomes | SQLite source labels, model labels and attempt receipts on a PVC |
| Floci Blob | Provides catalogue, query suite and original labels | Content-addressed manifests and bytes |
| ESO and Floci Key Vault | Delivers registry, object-store, Blob and Nexus credentials | Kubernetes Secrets refreshed from retained vault entries |

The API and model run in `lab-models`, outside experiment namespaces. A search environment is not held up by model start-up. The service uses a shared frozen source; 10k source import is retained across Pod restarts. Inference requests contain the original query and selected product record. The service rejects IDs or record bytes that differ from the pinned source. A missing pair is never inferred from a Search API response alone.

## Start or verify the stack

From the repository root, set `LAB_STATE_DIR` to the existing lab state directory if using a separate worktree. Publish the image whose source-derived tag appears in `judgements/kubernetes/*.yaml`, then run:

```powershell
python lab/publish_judgement_image.py --platforms amd64
python lab/setup_judgement_stack.py
python lab/setup_judgement_stack.py --verify-only
python lab/setup_judgement_stack.py --million
```

The setup command checks the lab cluster, configures the Nexus image mirror, installs pinned cert-manager, KServe and MLflow Helm charts, syncs credentials through ESO, applies the versioned manifests, registers the all-abstaining model and runs a live smoke check. `--million` also starts a second source-scoped judgement API for the frozen 1M catalogue; it shares MLflow and KServe with the 10k service. On an existing cluster the command reconciles the same resources. Its image pin check fails if source code changes without publishing and updating the manifest tag. The current image is x86; build and check an arm64 or multi-platform image before running on Apple silicon.

## Capture, resolve and score

1. Capture baseline and candidate ordered results with `evaluation/capture.py` or select a retained `search-observation-set`. Keep the matching catalogue and query manifests.
2. Forward the cluster-only API for a local run: `kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-models port-forward service/judgement-service 18086:18086`.
3. Run `judgements/evaluate.py` with `--observations`, `--specification`, `--catalogue`, `--catalogue-manifest`, `--query-manifest`, `--source-judgements`, `--source-manifest`, `--output`, `--resolve-url http://127.0.0.1:18086/v1/judgements:resolve`, and the exact `--model-name`, `--model-version` and `--model-artifact-sha256` from `judgement-model-pin`.

The output directory contains `frozen/judgements.jsonl`, `frozen/judgement-set.json`, `frozen/resolution.json` and `evaluation.json`. The command prints metric, coverage and input hashes. The frozen set retains every source label, even if that pair was outside the current recall pool. `resolution.json` records each attempted gap, input hash, outcome and per-side coverage. `evaluation.json` scores both sides against the same set. Inference failure marks that report incomplete; an abstention leaves the pair unknown and lowers judged coverage.

Run again with another observation set and a new output directory when recall changes. Existing output bytes are immutable: a conflicting replay fails. This also catches an inference outcome that changed despite the same pinned source and model identity.

## Replace the model

Register a new model version in MLflow with the same input/output contract: each pair produces `labelled` plus `E`, `S`, `C` or `I`, or `abstain`. Pin the numbered version and artefact digest in the KServe `storageUri` and judgement-service model ConfigMap. Deploy and verify both pins together. The storage initialiser refuses changed model bytes; every prediction includes the verified identity, which the judgement API checks. A registry alias can select a version for a future deployment, but an evaluation records the exact version and digest.

The numeric grade mapping is `I=0`, `C=1`, `S=2`, `E=3`. No label is inferred from abstention or a failed call. New model labels are cached only under that exact version and frozen source scope. Source labels always take precedence.

## Limits of this slice

- The existing control UI continues to score its selected judgement manifest. The two-stage workflow is a separate command over retained API observations; its hashes and coverage are directly inspectable.
- The 10k/50-query and 1M/1,000-query retained comparisons have been exercised through the deployed stack. The 1M run exposed very low coverage under the all-abstaining model; its scores are not relevance evidence. Apple silicon build, Azure identity/storage and a non-abstaining model remain validation work.
- Local MLflow is memory-heavy; the [measured sample](research/evidence/mlflow-kserve-judgement-coverage.md) is an operating observation, not a capacity claim. Environments should reuse the shared model service instead of starting one registry and predictor per experiment.
