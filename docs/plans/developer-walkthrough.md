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
clean checkout and read `understand()` and `query_body()`. They have created
`codex/walkthrough-trainers` and added the `trainers` → `running shoes` rewrite.
The source repository includes a copyable function in
`examples/trainers_rewrite.py`; the lab seeds the same example and contributor guide.

Next, build and run the application tests together, explain their output, then
add a focused check for the rewrite before committing the contributor's change.
Continue one step at a time with feedback. After the walkthrough, make one pass
over public-function comments, as requested by the contributor.

## References

- [Source contributors guide](../../lab/delivery/bootstrap/README.md#contributors-guide)
- [Search request contract](../search-request.md)
- [Evaluation runbook](../evaluation-runbook.md)
- [Variant evaluation](../variant-evaluation.md)
- [Technical authorship](../technical-authorship.md)
