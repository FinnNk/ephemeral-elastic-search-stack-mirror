# Integrate the ESCI demo policy

Accept the scoped demo policy, then publish fresh evidence for the remaining
storefront change. The lab already serves the full ESCI catalogue with the
human-authorised demo judgement snapshot.

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
| Review | PR #19 ready for human acceptance; no automatic merge |

## Work sequence

1. Check the current PR and main state. Proceed with trusted-pin changes only after human acceptance of source PR #23.
2. Verify the accepted file hashes and update the protected CI variables.
3. Rebase PR #19 on accepted main and build its new image.
4. Capture baseline and candidate results through the public search API using the frozen demo snapshot.
5. Publish the signed new-commit report and trigger a fresh CI event. Do not rerun an event containing the old base commit.
6. Record results, update the roadmap and hand back PR #19 for review.

## More information

- [Demo policy and measured results](../research/evidence/esci-demo-coverage.md)
- [Relevance gate and signed evidence](../relevance-gate.md)
- [Delivery procedure](../delivery.md)
- [Later batch: restore qualified-only defaults](esci-qualified-defaults.md)
