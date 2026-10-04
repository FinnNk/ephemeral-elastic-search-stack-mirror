# Temporary ESCI demo coverage

Use published ESCI labels and the current calibrated model to unblock local demonstrations at **80% judged coverage**. Model accuracy remains unqualified; this batch records the human-authorised quality exception explicitly.

## Intent and constraints

- Keep the full English ESCI catalogue and GBP lab pricing.
- Replay saved model-4 probabilities; no new model, fitting, research survey or GPU run.
- Keep Exact acceptance at 0.75; use 0.40 for Substitute, Complement and Irrelevant. Retain abstentions below these thresholds.
- Published labels win. Retain model identity, probabilities, input hashes and acceptance-policy provenance.
- Preserve the 49 excluded specialist pairs and all protected research artefacts.
- Keep strict `gate` selection separate from `demo`. Demo labels remain `gate_eligible: false`.
- Authorise demo evidence only for the exact catalogue, query suite, model and policy in the protected merge policy. Keep the 80% coverage and ranking/result-preservation rules.
- Retain the Decider2B execution hold and require human acceptance before main merges.

## Acceptance criteria

| Check | Required result |
| --- | --- |
| Saved-score replay | Complete original pass; accepted class counts and coverage reproducible |
| Frozen comparison | At least 80% of each variant’s returned pairs judged |
| Source precedence | Published labels retained; model labels and authorisation distinguishable |
| Strict selection | Demo predictions excluded; no claim of independent quality qualification |
| Demo gate | Matching signed evidence passes normal comparison rules; other policies, models or scopes rejected |
| Lab use | New immutable judgement manifest selected by the control default; API exposes source records |
| Reference documentation | Current guides, report text, source gate guide and diagrams describe the temporary policy |
| Review | Lab and source PRs, separate GitHub backup batch, roadmap and follow-up plan |

## Implementation

1. Freeze the demo acceptance policy and replay the existing 6,920 predictions.
2. Add explicit demo selection and scoped gate validation, with rejection tests.
3. Regenerate an immutable mixed-source judgement set and publish it to Azure Blob storage in the lab.
4. Deploy the updated Judgement API, import demo evidence and verify source precedence and persistence.
5. Evaluate the frozen API observations and activate the control default. Prepare the trusted source gate update and fresh commit-bound evidence.
6. Record measured results, review the guides, commit and open PRs.

## More information

- [Current measured pass](../research/evidence/esci-progressive-judgements.md)
- [Judgement API](../judgement-resolution.md)
- [Merge gate](../relevance-gate.md)
- [Model quality requirements](../model-label-quality.md)
- [Held role check](esci-role-check-execution.md)

The [source integration](esci-demo-integration.md) is complete: the accepted policy and catalogue change are on source main, with fresh passing CI evidence. The [next implementation plan](esci-qualified-defaults.md) returns to qualified-only defaults after independent quality investigation; it does not automatically accept a new model or restart the held survey.
