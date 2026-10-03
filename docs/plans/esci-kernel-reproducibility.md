# Freeze ESCI kernel configurations

Status: completed. [Full serving evidence](../research/evidence/esci-frozen-kernels.md)
records six successful 7,393-pair HTTP passes, including a fresh Pod. Candidate
version 4 remains inactive pending [independent label assessment](esci-label-quality.md).

## Intent and constraints

Make independently generated reference scores agree with KServe after a fresh
start. Controlled replay reproduces the observed drift by changing the
normalisation and output kernel settings; fixing the reference profile restores
agreement on the 256-pair controls and full 7,393-pair request-thread diagnostic. A stable response within one process is insufficient
evidence.

- Keep the 0.0001 tolerance, 0.90 acceptance threshold and 80% coverage gate.
- Preserve every failed release and diagnostic output. A changed protocol gets
  new model, image and reference identities.
- Use only exposed diagnostic queries. Protect the research final assessment and
  specialist reservations; obtain an explicit checkpointed GPU handover.
- Generate expected scores with the original research loader, independently of
  the serving wrapper. Keep raw scores and inputs in ignored evidence storage.
- Use supported upstream configuration where possible. Do not ship diagnostic
  monkeypatches, data adapters or silent numerical fallbacks.
- Keep the default CPU lab independent of the optional NVIDIA worker.

## Work and acceptance

| Work | Required evidence |
| --- | --- |
| Freeze the reference profile | Include the six observed kernel configurations and their hardware/runtime requirements (initially RTX 4090 Laptop GPU, CUDA 12.4 and the pinned FLA/Triton stack) in the immutable bundle, alongside the existing input and precision protocol. A new profile creates new release, registration and image identities |
| Reject incomplete configuration | Validate the profile before importing FLA. Check actual selected settings after warmup and reject absent, incompatible or unexpected kernel configurations; upstream cache modes otherwise permit retuning |
| Generate independent references | Run the original research loader under the same declared profile on the frozen eligible inputs. Record profile, source, runtime and reference hashes; preserve version 3's failed evidence |
| Verify cold-start stability | Repeat isolated processes and a fresh KServe Pod. Check probabilities and actual returned labels/abstentions against the independent references |
| Qualify the full release | All 7,393 eligible pairs across 457 queries must meet the tolerance with no changed decisions for batch, reversed and singleton HTTP requests, repeats and a fresh Pod. Smaller controls establish diagnosis only |
| Measure the cost | Record warm inference time and peak allocated memory on the same inputs; retain singleton execution unless a more complex policy offers a meaningful improvement without numerical drift |
| Finish | Remove candidates, verify GPU handback, update the roadmap and label-quality plan, commit and open a PR |

Do not assess label quality, activate the candidate or use it to unblock a merge
gate while numerical agreement fails. If the available GPU window ends first,
record the unresolved checks and arrange the next window before more inference.

## Sources

- [Inference-contract plan](esci-inference-contract.md) and
  [larger probability diagnostics](../research/evidence/esci-probability-diagnostics.md).
- [Independent label qualification](esci-label-quality.md) and
  [model installation](../esci-model-installation.md).
- `lab/probe_esci_kernel_selection.py`, `lab/probe_esci_request_execution.py`,
  `lab/generate_esci_references.py`,
  `judgements/esci/runtime.py`, `engine.py`, `qualification.py` and `Dockerfile`.
- Ignored `esci-packaging/inference-contract-20261003` references, HTTP captures,
  kernel probes and runtime logs.
- [FLA environment settings](https://github.com/fla-org/flash-linear-attention/blob/main/ENVs.md)
  and [Triton autotuning](https://triton-lang.org/main/python-api/generated/triton.autotune.html).
  Check the installed pinned implementations before adopting their settings.
