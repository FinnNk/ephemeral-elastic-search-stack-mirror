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

The contributor has built the application, passed all 17 tests, committed and
pushed the change, and opened source PR #26. Its declared intent is
`ranking-change`. Release CI passed; relevance CI is waiting for a report for
that exact commit.

The [PR preview correction](pr-build-previews.md) makes the ordinary delivery CLI
accept verified PR builds while keeping promotion restricted to merged source.
A preview of the contributor's build is ready; the installed control runtime
still needs this correction after review.

Next, open the candidate preview together and try `trainers`, then compare it
with the baseline before running the frozen evaluation. The 1,000-query suite
contains no exact `trainers` query; explain that limit before interpreting its
report. Do not describe an unchanged general suite as evidence that this rewrite
improves relevance.

Continue one step at a time with feedback. At the end, add a copyable test snippet
and comments on the intended use of both examples, then review public-function
comments in one pass. Keep this collected feedback together unless a substantial
issue blocks the walkthrough.

## References

- [Source contributors guide](../../lab/delivery/bootstrap/README.md#contributors-guide)
- [Search request contract](../search-request.md)
- [Evaluation runbook](../evaluation-runbook.md)
- [Variant evaluation](../variant-evaluation.md)
- [Technical authorship](../technical-authorship.md)
