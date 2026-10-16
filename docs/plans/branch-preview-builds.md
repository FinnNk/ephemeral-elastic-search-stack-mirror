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

## Next detailed plan: acceptance and activation

1. Review and merge the delivery-source workflow/tooling PR, then the lab PR.
2. When delivery and comparison work is idle, publish/install the accepted
   control runtime using the existing update procedure.
3. Build one pushed branch without opening a PR. Verify its pinned SHA,
   preview version, Actions link, catalogue/Redis binding and storefront.
4. Repeat with an exact SHA; refresh during the build and confirm one dispatch.
5. Check early expiry on these disposable previews. Rehearse the same flow on
   the Mac during fresh-install acceptance.

Do not treat fixture checks as live release, model-quality or Mac evidence.
The [user guide](../branch-previews.md) owns steps and failure recovery.
