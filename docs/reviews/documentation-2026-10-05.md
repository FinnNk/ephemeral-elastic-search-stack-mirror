# Documentation reconciliation — 5 October 2026

Current guides now separate Search API development from lab administration.
The developer path uses Actions and durable coordinator operations; cluster
installation and recovery remain operator tasks. The new remote path is pending
review and activation, not already running in the lab.

## Review and corrections

This pass follows the [earlier authorship review](documentation-2026-10-01.md).
The [inventory](documentation-inventory-2026-10-05.csv) records each owned
Markdown file and review depth. Historical evidence received context/navigation
checks, not a new verification of its measurements. Imported notices remain intact.

| Finding | Correction |
| --- | --- |
| Delivery guides still required developer kubectl steps | Actions covers previews, comparisons, promotion/rollback proposals, approved merges, verification and evidence rechecks |
| Contributor README offered port forwarding as ordinary access | Use automatic HTTPS URLs; ask the operator to repair DNS or trust |
| Developer and operator evidence publication were mixed | Developer guide owns the normal path; runbook covers standalone studies and recovery |
| Walkthrough described production as unfinished | Record completed build 108 promotion; Actions activation is the next rehearsal |
| Roadmap accumulated conflicting status claims | One current table and remaining validation; old batch plans retain their stage |
| Accepted gate policy was described as prepared | Explain current bounds and protected coordinator installation without implying approval |
| Design, identity and ingress references disagreed | Correct view counts, demo-label scope, canonical HTTPS and scoped Actions operations |
| Evaluator examples used the earlier specification | Use the current `proxy-v2.json` specification |
| Example build IDs predated the comparison contract | Use placeholders with the exact source of their values |

## Verification and limits

- 26 focused software tests passed for queue identity/retry/recovery, remote
  merge rejection, rollback sequencing and existing delivery gates. These do
  not establish a live Actions deployment.
- Local Markdown targets and anchors were checked across the tracked inventory;
  inbound links to renamed delivery sections were repaired. Bootstrap README
  source paths refer to their published repository layout.
- Delivery, remote commands, variant evaluation, roadmap and source README
  rendered in headless Edge with one title, no viewport overflow and loaded
  images. Their openings were inspected separately from structural checks.
- Existing diagrams represent the same source/comparison/review/Argo topology.
  Their labels do not prescribe kubectl. No diagram asset or previous visual
  receipt is relabelled as newly validated.

Source templates are copied to the source PR. Its new commit needs a fresh build
and exact-image comparison; the earlier report cannot cover it. Source CI is
recorded with the PR, separately from this writing review. The accepted control
image stays installed until human review permits activation.
Linux/macOS command execution, GHES integration and the complete new Actions path
remain live checks in [activation](../plans/walkthrough-activation.md).
