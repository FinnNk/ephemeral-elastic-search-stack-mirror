# Complete the coverage decision

Status: the tooling-only maintenance proof passed protected CI in source PR
#22. Human acceptance, accepted-pin installation and the real ESCI decision
remain outstanding.

## Intent

Unblock result-preserving delivery work with honest evidence. Keep the 80%
coverage requirement for ranking changes and qualify any additional model labels
before using them in a merge gate.

## Constraints

- A PR cannot replace its own trusted checker or protected code/policy pins.
- Keep published labels, model predictions and human labels distinguishable.
- Do not label unknown pairs Irrelevant or use model agreement as ground truth.
- Preserve frozen unsuccessful experiments; reserve fresh confirmation for new
  model or acceptance-rule development.
- Use a separate synthetic benchmark only for a tooling-only maintenance PR.
  It does not establish ESCI quality or justify an application change.

## Work and acceptance

| Work | Acceptance |
| --- | --- |
| Trusted checker rollout | A main-based tooling-only PR passes the existing checker on genuine captured API results; application, chart and index contract trees are unchanged |
| Independent fixture | Freeze all query/product labels and their explicit modelling rules before capture; retain input hashes and exact image/build evidence |
| Install accepted pins | After human merge, verify the accepted main checker and policy bytes before updating protected pins |
| Re-evaluate source PRs | Restore the real ESCI variant selection when rebasing application work; capture exact source builds against the ESCI baseline and retain qualified-source-only reports |
| Human coverage decision | Only strict result preservation can request a signed exception; record actual coverage, reviewer and reason; no automatic approval |
| Residual model choice | Assess whether a complementary model has credible non-Exact precision; otherwise propose a stronger supervised model or independently reviewed labels |

A result-preservation exception does not open the gate for a ranking change.
If the development policy fails, do not reuse its confirmation results to tune
another rule and claim independent confirmation.

## More information

- [Quality evidence](../research/evidence/esci-label-quality.md)
- [Assessment contracts and commands](../model-label-quality.md)
- [Quality plan](esci-label-quality.md)
- [Human decisions](../evaluation-runbook.md#human-exceptions)
- Source CI: the delivery-source `.github/workflows/relevance.yaml`,
  `lab/variant_gate.py` and `lab/delivery/policies/variant-merge-v1.json`.
