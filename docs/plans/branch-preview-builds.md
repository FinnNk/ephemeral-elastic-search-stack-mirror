# Branch/SHA preview builds

## Review batch

A human administrator can select a delivery-source branch or full commit SHA,
a catalogue and optional retained index recipe in the Search lab. Submission
pins the source and protected workflow commits. The coordinator follows one
Actions dispatch, verifies its release receipt and creates a 72-hour preview.
The preview cannot qualify as a merged-source promotion build.

The source workflow uses protected main tooling. Candidate tests have no
registry credentials or Docker socket. Hash-pinned uv dependencies use the
combined system, lab and corporate CA trust. Fresh-install source templates
include the same workflow and tooling as the source PR.

## Verification

- 73 focused locked-uv tests passed, covering exact pins, permissions,
  duplicate submissions, dispatch uncertainty, receipt identity and promotion
  exclusion, as well as existing API, release and seed behaviour.
- JavaScript syntax and native Git Bash shell syntax checks passed.
- A disposable private Gitea repository confirmed the actual dispatch run name,
  event, workflow path and head SHA. Its job was skipped; the repository was
  archived afterwards. This proves provider metadata, not a completed build.
- The isolated browser fixture checks request feedback, result links and
  refresh recovery. It makes no live lab deployment or build request.

## Next detailed plan: remaining acceptance

Lab #220 and delivery-source #44/#45 are merged. The current control runtime is
activated. On 19 October the user confirmed that the branch preview deployment
completed. This establishes that walkthrough outcome, not exact-SHA, expiry or
native Mac acceptance.

1. On the Mac, build a pushed branch without opening a PR. Check its pinned SHA,
   preview version, Actions link, catalogue/Redis binding and storefront.
2. Repeat with an exact SHA; refresh during the build and confirm one dispatch.
3. Expire a disposable preview early and confirm its deletion. Integration,
   Staging and Production must retain their separate ownership and controls.

Use the [handover](../mac-handover.md) for setup and retained work. The
[user guide](../branch-previews.md) owns steps and failure recovery.
