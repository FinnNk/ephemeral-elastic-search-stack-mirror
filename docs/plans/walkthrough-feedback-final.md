# Complete the Production walkthrough feedback

## Scope

Publish the remaining feedback as a lab batch and a dependent delivery-source
data release. Build 207 remains active in Production; historical checks,
judgements and approvals remain unchanged.

| Feedback | Result |
| --- | --- |
| Advisory checks show no result | New approval PRs and reports show Passed, Failed, Review advised or Incomplete, followed by `(advisory)`; coverage and reasons remain visible |
| Additional sets lack judgements | 306 accepted Luna assessments provide 90% coverage per side for sneakers and Redis rewrites in the retained captures |
| A PR number is easy to misidentify | Approved-proposal selectors include release version, short source SHA and build; link to source-pinned release notes where available |
| An old deployment appears never released | A merged proposal no longer overwrites a retained earlier verification when another release is deployed |
| Plans must be composed again at each stage | Suggestions carry reviewed choices for the exact release in the immediately preceding stage; new required declarations remain required |
| Recording approval needs another click to run checks | The explicit **Record approval and start checks** action queues durable checks once per plan, with a separate record-only action |
| Fresh setup must include the changes | Seeds include queries, labels, model provenance, compressed inputs and captures, release notes and declarations; new servers start at 10 GiB |

Selections can be carried forward; approval and evidence cannot. The destination
baseline differs, so its new plan still receives exact-head human approval.
Changed candidate inputs, policy or protected standard sets prevent reuse. The
queued check also rejects a replaced plan before evaluation. Neither plan action
approves or deploys a release proposal.

## Judgement data and evidence

Luna judged the original query meaning and product details, without candidate
scores or ranking positions. Labels include positive and negative outcomes,
with a rationale and input hash for every assessed pair. Case-equivalent requests
have no conflicting labels for shared products. One deterministic pair per
query and side remains unjudged; the sampling does not depend on the assessment.

- Sneakers: 54 unique labels; 36 of 40 returned pairs judged per side.
- Redis rewrites: 252 unique labels; 162 of 180 returned pairs judged per side.
- The unchanged coverage requirement is 80%.

Re-scoring the packaged build 108/build 207 captures with these new labels
produces Passed (advisory) for both sets. This is a new offline measurement,
not a replacement for the completed Production evidence. New results may change
coverage. These accepted model labels remain advisory; they do not gain required
gate qualification through source acceptance. Protected standard checks and
latency budgets are unchanged.

The [data record](../../lab/delivery/bootstrap/evaluation/judgements/README.md)
links the file roles and provenance. Compressed original inputs and observations
allow coverage and scoring to be reproduced without a running lab or inference
service. Original ESCI notices and licences accompany the product extracts.

## Verification

The focused locked-uv run passed 186 tests. Targeted data and plan checks were
rerun after the final provenance and wording review. They cover advisory
pass/failure/incomplete outcomes, required
gate enforcement, packaged data hashes and scoring, carried selections, queued
check deduplication, changed-plan rejection, historical deployment state, release
identity and changelog lookup, fresh seeding, capacity resume and corporate trust.

Chrome fixture checks exercised the actual dashboard and result-page scripts.
They showed advisory outcomes and coverage, the release-labelled selector and
changelog link, carried choices, both approval actions and the submitted
`run_checks: true` request. The fixture cannot create live operations.

The new memory default follows the successful full Production run at 10 GiB.
Existing installations retain their recorded capacity when the option is omitted;
resuming does not resize them. The fresh guide plans 40 GiB for Docker Desktop.
These are Windows checks. A destructive fresh reinstall and native Mac load
acceptance were not performed.

## Acceptance and next steps

1. Merge the reconciled historical feedback record (#214), then lab #219.
   Activate the accepted control runtime when delivery/comparison work is idle.
2. Recheck the dependent delivery-source PR for version 1.2.6 against the activated
   loader before merging it. Its API behaviour and standard budgets are unchanged.
3. Use its new merged-source build and a new reviewed check plan for live
   comparisons. Suggested retirements distinguish old unlabelled copies from
   their labelled replacements; the reviewer confirms the decision.
4. Rehearse the documented fresh Mac install from the accepted GitHub mirror.
   No intermediate judgement import or model download should be needed.

## Reconciliation, 18 October

Main now includes source version 1.2.5, the branch/SHA preview workflow and the
code/documentation cleanup. The feedback branch preserves those changes and
includes the complete final canonical-byte correction. Its source-data dependency
is version 1.2.6; the unpublished 1.2.4 branch is not the release to merge.

All 285 combined feedback, promotion, preview, fresh-install and API tests passed.
The source branch's committed judgement-pack bytes match the fresh-install seed
exactly. Re-scoring confirms 54 sneakers labels and 252 Redis rewrite labels,
with 90% coverage on both sides for both retained captures. Source application,
chart, contract and CI/tooling files match accepted source main. The new source
comparison still requires the accepted loader to be activated before its gate
can be completed. Neither this reconciliation nor re-scoring changes live
Production or earlier evidence.

## Activation and handover, 19 October

Lab #214/#219 and source #45 are merged. The accepted control runtime is
activated and smoke-tested; its loaded additional judgement counts are 54
sneakers and 252 Redis labels. Source 1.2.6 passed comparison operation
`bff0300207a074a88980e4b7cd32bf38` after activation. These observations supersede
the merge/activation actions in the historical acceptance list above. They do
not change earlier evidence or assert a new Production deployment.

Continue with the [Mac handover](../mac-handover.md), including clean installation
and a new reviewed promotion to exercise the updated controls end to end.
