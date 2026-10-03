# Diagnose ESCI serving probability differences

Status: diagnostics and investigation complete. The
[results](../research/evidence/esci-probability-diagnostics.md) identify a missing
compiler, silent FLA fallback and separate batch-size sensitivity. Version 2
remains inactive. Runtime correction and qualification continue in the
[next batch](esci-inference-contract.md).

## Intent and constraints

Find the cause of the probability discrepancy between frozen
research scores and KServe. Keep the reference examples, 0.0001 tolerance,
abstention thresholds and 80% coverage gate unchanged.

- Start with CPU inspection; coordinate a checkpointed research hold for GPU work.
- Preserve every attempt. Do not replace references with the candidate's outputs
  or select favourable canaries.
- Treat kernel, batching and platform differences as hypotheses until measured.
- Changes to runtime code, dependency versions or inference settings require new
  immutable image/model identities as appropriate. Do not add compatibility adapters.
- Agree another checkpointed window only after a concrete diagnostic is ready;
  remove the candidate and return the GPU even if it fails.

## Larger diagnostic

Use all **7,393 eligible pairs across 457 queries** in the exposed confirmation
cohort. Exclude 2,301 pairs/143 queries overlapping the current final reservation;
normalise query membership with the research's pinned normalisation function.
No additional SPECIALIST-01 overlap remains. Freeze the inputs and exclusions
before inference, with source and registration hashes.

| Run | Pairs | Purpose |
| --- | ---: | --- |
| Batch, repeated batch and reversed order | 7,393 each | Distribution of research/serving differences, repeatability and ordering sensitivity |
| Singletons, repeated singletons | 1,024 each | Request-size sensitivity and repeatability; deterministic rounds across all eligible queries |
| Investigation probes | 512 in 64 complete original groups | Compare raw and mapped scores in original research batch context; no protected companion inputs |

Retain every returned vector locally. Report median, p95, p99 and maximum
absolute difference, the fraction exceeding 0.0001, winning-class changes,
acceptance changes and label/abstention changes. Use 5,000 whole-query bootstrap
replicates, fixed seed 20261002, for pair-weighted rates and signed class means.
Intervals describe variation across this exposed cohort; they do not establish
quality or representativeness for production traffic.

Report these diagnostics to the user before moving to causal investigation.
Keep the numerical criterion and 0.90 policy unchanged. During a bounded,
checkpointed GPU window, run the deployed candidate first, remove it, then run
standalone research/container probes on the fixed original groups. Return the
GPU and verify research resume after all phases, including failures.

## Findings and remaining acceptance

| Work | Result required |
| --- | --- |
| Compare implementation | Inputs, question and 512 token fingerprints match. Original and serving loaders give identical batched raw scores in the current runtime |
| Retain diagnostic outputs | All five HTTP passes and controlled raw/mapped vectors retained locally; aggregate evidence contains run and asset hashes |
| Separate causes | Mapping matches independently. Missing compiler causes FLA import failure and a silent PyTorch fallback; compiler-equipped normal FLA selection exactly reproduces 512 archived batched vectors |
| Correct the runtime | Diagnostic correction measured; not deployed. FLA batch-to-singleton sensitivity still changes three of 512 decisions. The next batch must define one reproducible inference contract |
| Repeat qualification | Outstanding: broad sample and fast canaries must meet 0.0001 with zero changed decisions across request arrangements and fresh Pod startup |
| Verify telemetry and cleanup | Candidate/Pods and diagnostic containers removed; active version 1 verified; GPU returned. Live export verification belongs to the new runtime batch |

If measured batch sensitivity prevents the current contract from meeting its
criterion, record that result and propose a model/runtime revision explicitly.
Do not silently widen tolerance or mark the original version qualified.

After the [inference-contract batch](esci-inference-contract.md) passes numerical checks, proceed to
[independent label quality](esci-label-quality.md). Quality acceptance and model
activation remain separate decisions.

## Sources

- [Serving procedure](esci-serving-qualification.md) and its linked evidence.
- `judgements/esci/engine.py`, `contract.py`, `canaries.py`, `qualification.py`
  and the pinned `requirements.lock`.
- Ignored research `src/esci_gap_judge/model/inference.py`, `training.py`,
  round-2 `signals/v3_8192/confirmation-provenance.json` and frozen score files.
- [Overall model qualification](esci-model-qualification.md).
