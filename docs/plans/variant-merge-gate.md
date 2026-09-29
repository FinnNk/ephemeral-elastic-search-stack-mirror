# Next batch: selected variant merge gate

## Intent

Turn a frozen multi-variant report into a merge decision for one or more declared variants. Keep measured results separate from the decision to release a variant. A proposed production replacement becomes the new default only after promotion, regardless of whether it was tested online.

## Constraints

- Pin the source revision, observation, judgements, evaluation specification, evaluator, variant identities and policy. The gate must fail if any reference changes or evidence is incomplete.
- Compare selected variants with the report's named baseline. Require a versioned policy for metric, judged coverage, exact-result change and an outer exception bound. Do not choose a winning variant after looking at the results.
- Return distinct `pass`, `decision_required`, `approved_exception`, `blocked` and `invalid` states. A human exception must never overwrite the measured result.
- The approval must bind the exact report and policy hashes, selected variant, reviewer, reason and source revision. PR-controlled unsigned content cannot grant approval.
- Keep the CI command independent of Gitea event shapes so the source workflow can move to GitHub Enterprise.

## Acceptance

1. A two-variant replacement and a three-variant ranking change produce deterministic gate receipts.
2. A small negative result inside the exception band requires a recorded approval; a more negative result stays blocked.
3. Changed evidence, forged approval, wrong selected variant, missing coverage and incomplete capture cannot pass.
4. The portable release workflow builds the exact PR source, then fetches signed evaluation evidence from Nexus by that source SHA and invokes the gate. Tests cover each state; a declared selection with missing evidence fails.

## Where to look

- [Variant contract](../variant-evaluation.md)
- [Current release workflow](../../lab/delivery/workflows/release.yaml)
- [Frozen evaluator](../../evaluation/offline.py)
