# Reuse inference during search development

## Intent

Avoid repeating model inference when new searches return unchanged inputs.
Keep judgement coverage distinct from search quality and preserve reproducible
frozen rescoring. This batch follows the owner's approval to implement both.

## Constraints

- Search every variant afresh; do not reuse search responses.
- Pin complete inputs, model artefact, runtime image, protocol and rubric.
- Cache successful abstentions; retry transient failures.
- Retain fresh attempts without replacing the first successful default.
- Published/human labels remain authoritative. Qualification and scoped demo
  authorisation remain separate from confidence thresholds.
- Preserve frozen evidence and research reservations. No compatibility adapter
  or conversion of older prediction records into cache entries is introduced.
- Keep experimental/model coverage distinct from independently qualified labels.

## Acceptance criteria

| Behaviour | Evidence |
| --- | --- |
| Repeated inputs avoid inference, including after restart | Seven focused tests and the 6,920-pair replay |
| Model/runtime/input changes invalidate reuse | Identity and frozen-input tests |
| Changed thresholds reuse scores and retain new decisions | Policy test and replay with 5,107 accepted labels |
| Failures retry; concurrent calls do not duplicate inference | Retry and concurrent-request tests |
| Fresh attempts preserve the ordinary default | Changed-outcome test with two retained attempts |
| Every variant uses one frozen judgement set | Existing pooled-resolution and frozen-scoring tests |
| Coverage is presented separately | Browser report check and regenerated workflow |
| Both CPU architectures remain deployable | Published immutable judgement image pins |

## Further information

- Behaviour and request options: [Fill missing relevance labels](../judgement-resolution.md).
- Measured results and limits: [Inference reuse evidence](../research/evidence/inference-reuse/README.md).
- API/cache: `judgements/service.py`, `judgements/inference_cache.py`.
- Deployment pins: `judgements/kubernetes/`, `judgements/esci/deployment.py`.
- Report: `lab/control-ui.html`; frozen scoring: `evaluation/offline.py`.
- Next batch: [Activate and rehearse inference reuse](judgement-inference-activation.md).
