# ESCI v3 packaging evidence

Recorded 30 September 2026. This is installation evidence for the selected
**Larger v3 + learned score mapping** candidate. GPU inference and lab accuracy
qualification remain pending. The existing live model is unchanged.

## Selected assets

- Base: `Mapika/decider-4b`, revision `eb5fbdfc9448473ec25e399882912863afbdb70e`.
- LoRA: v3 role-cues prompt, 8,192 training rows, unmerged adapter;
  SHA-256 `227cfbeb71dc40c0737c372fb3bebb03738cf5b71e54e8be7d7a668678d71fee`.
- Mapping: `v3_8192:scores:C0.1`, four clipped-log probabilities, standardisation
  and logistic regression. No text features in this mapping.
- Policy: highest mapped probability at least 0.90, otherwise abstain.
- Asset release: `93ee12f782684f5213a5b5ff0205d0d2765554f42646d5294a65029704742c45`.
- Twelve asset files, **8,691,339,810 bytes**; weights and generated reference
  examples remain in ignored `.lab/esci-packaging/` storage.

The builder reads only the pinned local research pickle and exports the selected
model's numerical parameters. It does not include that pickle, its other models,
its source data or recorded query identifiers in the release.

## Completed verification

| Check | Result and scope |
| --- | --- |
| Release integrity | All asset sizes and SHA-256 values verified against the manifest |
| Mapping export | All 9,694 previously opened research rows reproduced; maximum absolute probability difference `4.440892098500626e-16` |
| Input references | 64 spread canaries match saved leaf-category model-input hashes; the prepared cohort's full-path text is not mistaken for the model input |
| Packaging tests | 8 passed, including a real local MLflow registration/download/reload/reuse test with a tiny synthetic bundle and stubbed engine |
| Bootstrap guard | 2 passed; replacement model rejected before the v1 bootstrap mutates cluster state |
| Existing judgement tests | 16 passed, including portable artefact hashes, configurable predictor timeout, source-label precedence, frozen-input validation and version-scoped caching |
| Full registered model | Version 2 downloaded and every asset verified; Windows and Linux model-tree SHA-256 values agree |
| Linux relocation | Full registered pyfunc loaded with networking disabled and GPU engine uninitialised; its Python modules came from the registered artefacts |
| Multipart transport | Generated 12 MiB probe uploaded/downloaded in 5 MiB chunks with matching checksum; no dataset examples used |
| Candidate manifests | Both ServingRuntime and InferenceService accepted by Kubernetes server dry-run; no candidate was deployed |

CPU tests ran on Windows with Python 3.12.8, MLflow 3.16.1, NumPy 1.26.4 and
scikit-learn 1.7.2. MLflow reports the intentionally absent GPU dependencies and
upstream signature/SQLAlchemy warnings. No CUDA inference was started.

## Registration and runtime

The full release is registered and verified against the lab's real MLflow
server. The first upload attempted presigned S3 URLs with a Kubernetes-only
hostname; its failure is retained locally. The installer now uses the reachable
MLflow proxy for uploads/downloads unless explicitly overridden. Windows output
also uses UTF-8 so MLflow's Unicode run links do not interrupt registration.

Two subsequent Windows port-forward transfers stalled. Their logs and failed
attempts were retained. Registration then succeeded through a CPU-only helper,
but proxy download exceeded the MLflow Pod's 2 GiB memory limit and caused an
OOM restart. That transfer was stopped. The updated helper uses the existing
k3d node's network with its own hosts-file mount, enabling presigned multipart
object-store transfers without changing node DNS or increasing registry RAM.
The artefact digest now sorts POSIX path strings explicitly: this preserves
the original Linux digest order while correcting Windows' case-insensitive
`Path` ordering. A regression test covers the `MLmodel` filename and identity
receipt exclusion.

The Linux CUDA runtime has a resolved dependency lock and separate Nexus image
publisher. The published image is
`nexus.localhost:18185/esci-judge@sha256:b3067043e3cea2a6afbec3810c5eec9b5a18315558909f972141a2c9d281fd1d`
(source digest `73766d2d1d34fb98a8dd839c8dc15d5ceec44a986f92f17fddac501cfa045719`).
The updated CPU API image is
`nexus.localhost:18185/relevance-judge:j1-b6a821a49492315e-amd64`.
Neither image has replaced the live service. CPU imports of Torch, Decider, PEFT
and the pyfunc passed in the final CUDA image with no GPU exposed. Registration
created and then successfully reused **`models:/synthetic-esci-judge/2`**.
The verified model-tree SHA-256 is
`ee4048a8ee758af4b4f697c63e921d4113b8bc95fa4e81728e881360405598f1`;
the wrapper/dependency implementation SHA-256 is
`dd8d66e84f55239475e99a4472368c202a8277d759372899afa5a8d5e38ea408`.

The full-size upload succeeded through the native helper's proxy route; the
verified full-size download used direct multipart object-store access. Direct
multipart upload was separately exercised with a generated 12 MiB artefact.
The final helper enables direct multipart transfer in both directions. The
MLflow Pod recovered from its OOM; its memory limit remains 2 GiB. Local failed
attempt logs and partial downloads are retained. The live service still pins
version 1. GPU qualification for version 2 remains explicitly pending.

## Remaining qualification

The lab's three k3d nodes currently advertise no NVIDIA GPU resource. GPU
passthrough/device-plugin configuration, exact-runtime canary checks (including
cold restart), memory/latency measurements and representative lab accuracy checks
are therefore outstanding. The laptop GPU remains allocated to the authorised
table-model experiment. There is no parallel GPU job for this package.

Promotion manifests require passing numerical evidence for the same registered
model and runtime image. The thresholds remain provisional for the lab: the
historical 96.59% selective accuracy at 37.17% coverage was measured on an
already-opened Amazon cohort, all accepted labels were Exact, and 12 accepted
pairs were published as Irrelevant. Avoiding Irrelevant-to-Exact errors remains
the priority. The result is not a guarantee of greater than 95% lab accuracy.

See [installation, qualification and rollback](../../esci-model-installation.md)
for reproducible commands. Model registration does not activate the service.
