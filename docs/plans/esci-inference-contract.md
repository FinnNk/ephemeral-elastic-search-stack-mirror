# Make ESCI inference reproducible

Status: next batch after the
[probability investigation](../research/evidence/esci-probability-diagnostics.md).
Version 2 remains inactive.

## Intent and constraints

Make a pair's judgement independent of the caller's batch size and prevent a
missing runtime dependency from silently changing its numerical execution.

- Retain the 0.0001 numerical tolerance, 0.90 acceptance threshold and 80%
  coverage gate. Do not tune them on these diagnostics.
- Preserve the failed version 2 release, archived scores and diagnostic attempts.
  A changed inference protocol receives new model/image identities and references.
- Generate references with the independent research loader under the declared
  protocol. Do not use the serving wrapper to create its own expected outputs.
- Exclude protected query reservations before every model call. Coordinate another
  checkpointed GPU window; keep the default CPU topology independent of it.
- Use the upstream FLA selection path. Do not ship the diagnostic monkeypatch,
  data compatibility adapters or a hidden fallback to another implementation.
- Finish numerical qualification before assessing label quality or activating a
  candidate. No new labels enter a frozen comparison during this work.

## Work and acceptance

| Work | Required result |
| --- | --- |
| Pin and validate the backend | Build the compiler and required headers into an immutable image; pin FLA/Triton; prove their imports work with the actual GPU. Missing prerequisites fail startup with a clear error. Record the selected implementation, not just installed versions |
| Choose one inference protocol | Test canonical singleton inference first, retaining batched HTTP requests but evaluating each pair independently. Measure repeat, order and cold-start stability, latency and peak memory. Compare fixed tensor geometry only if singleton inference has a material measured cost |
| Freeze the release contract | Declare context/truncation, padding, internal batch policy, dtype, attention implementation and relevant precision settings. Include them in immutable model/runtime identities and cache provenance |
| Generate independent references | Freeze inputs before inference; use the original research loader and chosen protocol in the pinned runtime. Retain source/runtime hashes and raw/mapped vectors. Do not overwrite historical references |
| Qualify serving | Use at least the 7,393 eligible pairs across 457 queries, plus the fast canaries. Batch, reversed and singleton HTTP requests, repeats and a fresh Pod must meet 0.0001 on every class probability with zero changed labels/abstentions |
| Verify failure and telemetry paths | Demonstrate an unavailable backend is rejected. Build the existing null-abstention telemetry fix into the new image and verify live OTLP export, including abstentions |
| Finish the batch | Remove candidates, confirm checkpointed research resume, update the roadmap and label-quality plan, commit and open the next stacked PR |

Record the singleton-versus-eight-pair cost on the same exposed inputs and GPU,
using warm repeats and the same verified assets. This measures judge inference;
it does not replace Gatling search load tests. Adopt extra batching machinery
only if its improvement justifies the complexity and it preserves per-pair
results.

If canonical singleton inference still fails repeat/cold-start stability,
investigate the responsible operation before generating a release. Do not mark
the model qualified merely because the old compiler failure is corrected.

## Sources

- [Diagnostic conclusions and evidence](../research/evidence/esci-probability-diagnostics.md).
- [Overall model qualification](esci-model-qualification.md) and
  [independent label quality](esci-label-quality.md).
- [Model installation](../esci-model-installation.md): registration, immutable
  assets, serving canaries and activation procedure.
- `judgements/esci/engine.py`, `release.py`, `contract.py`, `qualification.py`,
  `requirements.lock`, and `judgements/esci/Dockerfile`.
- `lab/diagnose_esci_parity.py`, `lab/probe_esci_runtime.py` and the ignored
  `esci-packaging/parity-diagnostic-20261002` records.
- Pinned Transformers `integrations/hub_kernels.py` fallback selection and
  `models/qwen3_next/modeling_qwen3_next.py`; Decider's collation and projection.
