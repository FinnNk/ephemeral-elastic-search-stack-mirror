# Check version 2 in KServe

Status: attempt finished; numerical checks failed. See the
[results](../research/evidence/esci-serving-qualification.md). The
[larger diagnosis](../research/evidence/esci-probability-diagnostics.md) identifies
kernel fallback and batch-size sensitivity. The next batch qualifies an
[explicit inference contract](esci-inference-contract.md).

## Intent and constraints

Demonstrate that the exact registered version 2 model reproduces its independent
reference outcomes through KServe. This is numerical serving qualification;
label quality on current gaps remains a separate acceptance step.

- Use the separate `esci-v3-candidate` service. Do not change the active model pin.
- Use release `93ee12f782684f5213a5b5ff0205d0d2765554f42646d5294a65029704742c45`
  and CUDA image `b3067043e3cea2a6afbec3810c5eec9b5a18315558909f972141a2c9d281fd1d`.
- Use the existing 64 frozen-research canaries, not newly selected favourable examples.
- Retain every attempt. Keep the 0.0001 probability tolerance and acceptance policy fixed.
- Use MLflow's direct multipart download to the cluster-reachable object store.
  Use 16 MiB download chunks within the initializer's 2 GiB memory limit.
  Do not route full weights through the 2 GiB MLflow Pod.
- Return the GPU to research after the bounded serving window, including after failure.

## Procedure and acceptance

1. Confirm the research hold in its session and that its GPU workers have exited.
   The owner preserves checkpoints and resumes through its qualification-window helper.
2. Deploy the generated candidate onto the optional worker. Record actual Pod
   image ID, registered model identity and startup outcome.
3. Forward the candidate Pod's HTTP port and use the fixed predictor contract
   `/v1/models/judgement-model:predict`. The service and registry names are
   independent of this route. Run batch, singleton and reversed canaries. All three must meet tolerance,
   with zero changed labels or abstentions.
4. Delete the candidate Pod, wait for a fresh ready Pod and repeat with a new
   evidence filename. Verify the actual image identity again.
5. Remove the candidate and confirm its GPU allocation is released. Ask the
   research session to resume from its retained checkpoint and verify progress.
6. Record evidence, update the roadmap and detailed quality-qualification plan,
   commit the batch and open a PR stacked above the worker PR.

## Next: label quality

Before new quality inference, audit normalised query overlap against LoRA
training, mapping fitting/tuning and research reservations. The research final
assessment and SPECIALIST-01 remain reserved. Choose separate confirmation
queries and representative human-labelled lab gaps. Fix precision/error criteria
before opening their results, and report coverage alongside uncertainty and
Irrelevant-to-Exact errors. Do not infer quality from serving parity.

See [model installation](../esci-model-installation.md),
[overall qualification](esci-model-qualification.md) and
`judgements/esci/qualification.py`.
