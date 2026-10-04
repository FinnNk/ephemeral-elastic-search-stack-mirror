# Developer walkthrough

Help a new contributor make and evaluate one small Search API change. Proceed
one step at a time, explaining what to do, what should appear and how to read it.

## Completed walkthrough

The contributor made the `trainers` → `running shoes` rewrite, built and tested
it, opened source PR 26, compared the two storefronts and merged the source.
Build 108 was evaluated, approved and verified in integration, staging and
simulated production. The contributor confirmed the same products and order
in each target. Production used the accepted full Gatling gate, not a probe.

The frozen general suite has no exact `trainers` query; an unchanged general
score does not establish that the rewrite improves relevance. The feedback
batches add an explicit query set, similarity summaries, copyable snippets and
Actions-based delivery. Source PR 27's discovered rewrite test passed; see the
[verification record](../research/evidence/walkthrough-feedback-verification.md).

## Next rehearsal

After review, follow [activation](walkthrough-activation.md). Repeat the developer
path using Actions for previews, comparisons, promotion proposals and approved
deployment completion. No contributor step should require a kubeconfig.

Acceptance requires useful public links, fresh exact-commit evidence, separate
and combined query-set metrics, clear gate outcomes and retained deployment
verification. Cluster repair stays an operator responsibility.

## References

- [Source contributors guide](../../lab/delivery/bootstrap/README.md#contributors-guide)
- [Delivery](../delivery.md)
- [Variant evaluation](../variant-evaluation.md)
- [Technical authorship](../technical-authorship.md)
