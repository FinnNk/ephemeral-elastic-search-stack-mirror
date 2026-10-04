# Integrate the ESCI demo policy

Completed locally on 4 October 2026. The scoped demo policy and catalogue
change are on source main. A fresh comparison passed the trusted CI gate with
81.22% coverage on both variants. See [the evidence](../research/evidence/esci-demo-source-integration.md).

## Intent and constraints

- Obtain human acceptance of the implementation and source policy PRs before main merges.
- Verify the accepted verifier and policy before changing trusted CI pins.
- Keep the 80% coverage requirement and existing ranking and result checks.
- Preserve the original low-coverage report for source PR #19; publish new evidence for its new commit.
- Keep model predictions distinguishable from published labels and independently qualified judgements.
- Retain the Decider2B execution hold. This batch needs no new inference or GPU work.

## Acceptance criteria

| Check | Required result |
| --- | --- |
| Policy acceptance | Source PR #23 accepted on main; exact accepted files verified |
| Trusted pins | Repository CI pins match the accepted verifier and policy |
| Source PR #19 | Rebased on the accepted main; new build and image identity recorded |
| Evaluation | Fresh API capture meets 80% coverage for both selected variants and passes the scoped verifier |
| CI | Signed evidence binds to the new commit; a fresh current-base event passes |
| History | Old reports and the superseded PR #20 remain available |
| Review | Human acceptance of source PR #19; no automatic merge |

## Work sequence

1. Check the current PR and main state. Proceed with trusted-pin changes only after human acceptance of source PR #23.
2. Verify the accepted file hashes and update the protected CI variables.
3. Rebase PR #19 on accepted main and build its new image.
4. Capture baseline and candidate results through the public search API using the frozen demo snapshot.
5. Publish the signed new-commit report and trigger a fresh CI event. Do not rerun an event containing the old base commit.
6. Record results, update the roadmap and hand back PR #19 for review.

## Result and next batch

Source PR #23 was accepted before the trusted pins changed. PR #19 was rebased
without altering its three-file patch; build 95/1 and relevance 96/2 passed. The
human merged PR #19, and source main equals the evaluated commit. The old
29.71% coverage report remains unchanged.

The [next implementation plan](esci-qualified-defaults.md) restores qualified-only
defaults after investigation resumes. It requires independent quality evidence
and does not authorise the held role check.

## More information

- [Demo policy and measured results](../research/evidence/esci-demo-coverage.md)
- [Relevance gate and signed evidence](../relevance-gate.md)
- [Delivery procedure](../delivery.md)
- [Later batch: restore qualified-only defaults](esci-qualified-defaults.md)
