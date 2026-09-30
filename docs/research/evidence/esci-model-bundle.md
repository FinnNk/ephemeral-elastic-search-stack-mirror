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
| Existing judgement tests | 15 passed, including the configurable predictor timeout, source-label precedence, frozen-input validation and version-scoped caching |

CPU tests ran on Windows with Python 3.12.8, MLflow 3.16.1, NumPy 1.26.4 and
scikit-learn 1.7.2. MLflow reports the intentionally absent GPU dependencies and
upstream signature/SQLAlchemy warnings. No CUDA inference was started.

## Registration and runtime

The large-file registration is being verified against the lab's real MLflow
server. The first upload attempted presigned S3 URLs with a Kubernetes-only
hostname; its failure is retained locally. The installer now uses the reachable
MLflow proxy for uploads/downloads unless explicitly overridden. Windows output
also uses UTF-8 so MLflow's Unicode run links do not interrupt registration.

The Linux CUDA runtime has a resolved dependency lock and separate Nexus image
publisher. Final image publication, CPU import verification and registration
identity are recorded here after those operations finish.

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
