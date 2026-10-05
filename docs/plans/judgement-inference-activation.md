# Activate and rehearse inference reuse

## Intent

After human acceptance, deploy the merged judgement API and report UI and check
iteration through the normal developer workflow.

## Constraints

- Retain source labels, frozen reports and the scoped demo policy.
- Keep model-4 quality unqualified and research surveys held.
- Verify predictor image/protocol identity before issuing API inference pins.
- Preserve protected-query exclusions in any model-4 inference rehearsal.
- Do not silently activate a new model or relax a gate during API deployment.

## Acceptance criteria

1. The deployed API reports its model and inference identity through `/health`.
2. Repeating a bounded approved recall pool makes no new inference calls,
   including for abstentions.
3. A search change retrieves new pairs while unchanged pairs reuse predictions.
4. A fresh attempt is retained separately; an ordinary repeat returns the
   original successful outcome.
5. A comparison displays separate coverage and scores both variants against
   its one shared frozen set. Frozen rescoring leaves artefact bytes unchanged.
6. Runtime/model readiness and source precedence remain intact.

Use [Inference reuse evidence](../research/evidence/inference-reuse/README.md)
as the local baseline and [Fill missing relevance labels](../judgement-resolution.md)
for the request contract. Record the merged commit, deployed image and bounded
inputs. This live rehearsal is outstanding; the existing replay does not claim
deployment to the shared API.
