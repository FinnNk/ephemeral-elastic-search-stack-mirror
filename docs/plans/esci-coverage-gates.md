# Published-label coverage and gates

Status: proposed; policy changes require review before implementation.

## Intent

Use the ESCI catalogue in developer and merge workflows without presenting incomplete relevance scores as conclusive evidence. Result preservation compares returned IDs and order; relevance decisions additionally depend on adequate judgements.

## Constraints

- Retain all 1,000 selected test queries, published assessments and frozen source hashes.
- Do not fabricate labels, select only favourable queries, reuse search responses or silently lower thresholds.
- Pool every variant's recall set symmetrically before judgement resolution. Record inference, abstentions, errors and model identity separately from published labels.
- Keep the default and selected baseline explicit. Human business overrides must remain recorded; they cannot turn incomplete evidence into a passing technical check.
- Use current contracts directly. Regenerate disposable artefacts rather than adding compatibility layers.

## Proposed steps

1. Trace the coverage verdict through the trusted source gate and documented evaluation intents. Identify which checks actually need labels.
2. Rehearse pooled resolution on the full catalogue with the abstaining model. Measure gap counts and duration; verify that coverage remains honest.
3. Propose separate requirements: exact result preservation for a behaviour-preserving change; label coverage, relevance bounds and decision evidence for ranking changes. Show the effect on the existing policy before requesting approval.
4. If approved, implement that policy distinction and exercise passing, changed-result, incomplete-capture, low-coverage and recorded-override cases against exact source heads.
5. Update source gate documentation, diagrams, the roadmap and the next walkthrough plan. Open one reviewable PR per completed batch.

## Acceptance criteria

| Area | Required result |
| --- | --- |
| Evidence | Published labels, inferred labels and unknown pairs remain distinguishable and reproducible |
| Result preservation | Every selected query makes fresh requests; incomplete capture blocks; order/set differences are reported and gated |
| Relevance | Scores and coverage use the same frozen judgement snapshot for every variant; insufficient evidence remains explicit |
| Policy | Approved intent-specific requirements are enforced by trusted CI, with an exact-head build/report attestation |
| Decisions | Permitted overrides retain actor, reason, bounds and evidence; non-overridable checks still block |
| Walkthrough | A new contributor can run baseline-versus-change and interpret its report without operator-only shortcuts |

## Where to look

- [Catalogue evidence](../research/evidence/esci-catalogue.md), including source PR #19 and CI run 83.
- [Variant evaluation](../variant-evaluation.md) and [judgement resolution](../judgement-resolution.md).
- `lab/delivery_gates.py`, `evaluation/offline.py`, `judgements/prepare.py` and the generated delivery-source gate template in `lab/setup_delivery.py`.
- [Technical authorship](../technical-authorship.md).
