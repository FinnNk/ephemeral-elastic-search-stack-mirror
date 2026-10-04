# Developer walkthrough

Help a new contributor make and evaluate one small Search API change.

## Intent and constraints

Proceed one step at a time, with the user trying each step and giving feedback.
Explain what to do, what should appear and how to interpret it. Use the lab for
comparisons; the standalone demo is for disconnected development only.

## Acceptance

- The contributor can open the storefront and interpret its product count and results.
- They can find query understanding and ranking code, then make a small change on a branch.
- They can build and test it, open a source PR and inspect its deployed preview.
- They can understand the frozen comparison report, coverage limits and merge gate.
- Feedback on unclear instructions is addressed in reviewable batches.

## Progress and next step

The contributor has opened the full ESCI storefront, tried a search, updated a
clean checkout and found `understand()`. Its comment explains that `'none'`
records an unchanged query; a demo rewrite returns its own decision name.
The source copy, lab template and supplied rewrite patch are kept in sync.

Next, read `query_body()` together and explain how it builds the Elasticsearch
request. Then create a contributor branch and make one small query change,
with feedback between steps. Cloning and local image building have already
succeeded; continue from this point after the comment batch is accepted.

## References

- [Source contributors guide](../../lab/delivery/bootstrap/README.md#contributors-guide)
- [Search request contract](../search-request.md)
- [Evaluation runbook](../evaluation-runbook.md)
- [Variant evaluation](../variant-evaluation.md)
- [Technical authorship](../technical-authorship.md)
