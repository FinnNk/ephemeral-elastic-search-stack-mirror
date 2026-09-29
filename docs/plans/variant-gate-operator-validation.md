# Follow-up batch: operator decision rehearsal

## Intent

Validate the human exception path with a real Gitea administrator after the reference and delivery-source PR stacks are accepted. Keep the measured verdict and business decision separate.

## Constraints

- Use a new synthetic evaluation with adequate judged coverage and a bounded, genuinely negative selected-variant result. The current abstaining model cannot supply that evidence.
- A reviewer must decide whether the change merits an exception. Automation must not issue an approval on their behalf.
- Authenticate the reviewer through their own Gitea account. Do not use the lab agent identity as the human decision-maker.
- Bind the receipt to the exact source commit, selected variant, report, policy and build receipt. Retain the reason and measured loss.
- Keep the source SHA unchanged while issuing evidence and rerunning CI. Preserve the existing Gitea PR and CI history.

## Acceptance

1. Without an exception, the complete bounded-negative report returns `decision_required` and prevents merging.
2. A Gitea administrator can review the report, give a substantive reason and issue one signed receipt. An ordinary account, forged receipt, changed report, different variant or changed source SHA fails.
3. The unchanged CI run returns `approved_exception`; the verdict still shows the negative metric delta and links to the reviewer and approval hash.
4. The review record distinguishes the automated metric result from the human release choice. No fixture score is presented as a quality finding.

## Where to look

- [Managed gate rehearsal](../research/evidence/managed-variant-gate.md)
- [Variant evaluation and gate](../variant-evaluation.md)
- [Trusted receipt issuer](../../lab/variant_gate_issue.py)
- [Gate policy](../../lab/delivery/policies/variant-merge-v1.json)
