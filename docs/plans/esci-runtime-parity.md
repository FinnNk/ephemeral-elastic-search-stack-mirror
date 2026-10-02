# Diagnose ESCI serving probability differences

Status: next batch. Version 2 remains inactive after the
[failed serving attempt](../research/evidence/esci-serving-qualification.md).

## Intent and constraints

Find and correct the cause of the probability discrepancy between frozen
research scores and KServe. Keep the reference examples, 0.0001 tolerance,
abstention thresholds and 80% coverage gate unchanged.

- Start with CPU inspection; research has resumed and owns the GPU.
- Preserve every attempt. Do not replace references with the candidate's outputs
  or select favourable canaries.
- Treat kernel, batching and platform differences as hypotheses until measured.
- Changes to runtime code, dependency versions or inference settings require new
  immutable image/model identities as appropriate. Do not add compatibility adapters.
- Agree another checkpointed window only after a concrete diagnostic is ready;
  remove the candidate and return the GPU even if it fails.

## Work and acceptance

| Work | Result required |
| --- | --- |
| Compare implementation | Verify prompt/options, tokenisation, assets, adapter placement, evaluation mode, batching, package versions and kernel selection against the exact research provenance |
| Retain diagnostic outputs | Save aligned per-row raw and mapped scores locally, with input/reference hashes and runtime identity; keep examples out of Git and telemetry |
| Separate causes | Test score mapping on CPU independently; in the GPU window compare the same exposed inputs through research and container paths, with original batch context and singleton/reordered requests |
| Correct the runtime | Adopt a measured fix with one clear inference contract; retain the failed version and evidence |
| Repeat qualification | All 64 batch, singleton and reversed outputs meet 0.0001 tolerance with zero changed labels/abstentions; repeat after a fresh Pod startup |
| Verify telemetry and cleanup | Build the null-label metric fix into the new image, verify export, remove candidate and confirm research resume |

If measured batch sensitivity prevents the current contract from meeting its
criterion, record that result and propose a model/runtime revision explicitly.
Do not silently widen tolerance or mark the original version qualified.

After successful numerical checks, update the roadmap and proceed to
[independent label quality](esci-label-quality.md). Quality acceptance and model
activation remain separate decisions.

## Sources

- [Serving procedure](esci-serving-qualification.md) and its linked evidence.
- `judgements/esci/engine.py`, `contract.py`, `canaries.py`, `qualification.py`
  and the pinned `requirements.lock`.
- Ignored research `src/esci_gap_judge/model/inference.py`, `training.py`,
  round-2 `signals/v3_8192/confirmation-provenance.json` and frozen score files.
- [Overall model qualification](esci-model-qualification.md).
