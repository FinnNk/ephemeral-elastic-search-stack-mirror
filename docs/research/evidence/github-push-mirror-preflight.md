# GitHub push mirror preflight

Checked on 5 October 2026 with Gitea 1.27.0 and chart 12.7.0.

## Repository state

GitHub main was `5e902b87eb62f6e467f934601a3dbd87c30ad0b6`; Gitea main
was `750335ecaafebdc7bf69a5faacb5ff504d33b407`. They have different histories.
GitHub had 64 open backup PRs, including #101. No project push mirror existed.

The user authorised using new repositories and retaining the old backups until
mirroring works. No existing GitHub ref or PR was changed during preparation.
The App has Contents and Pull requests write permissions, but cannot create
repositories or read branch protection through the API. Browser automation was
unavailable, so empty destination creation remains a human setup step.

## Checks and limits

- The pinned helper source is `44092188bcdbbc209317424429489b2335793617`.
  AMD64 and ARM64 image builds succeeded.
  The final image is
  `nexus.localhost:18185/github-app-credential@sha256:cf2aaf315e138f3be886fba045ab3514cad13adfc592f9807f5ea0d41f30ab02`.
- The helper and ESO-managed App key were mounted into the existing Gitea
  deployment. OIDC mounts and existing chart settings were retained.
- A Git command inside Gitea obtained a fresh App token and read the private
  GitHub main ref. Its hash matched the API preflight above. No token was printed
  or written to a credential file.
- Four setup tests passed: populated-destination rejection, scoped authentication
  and native sync configuration, repeated setup, and invalid URL/path rejection.
  Ruff passed for the new Python files.
- A native mirror between two disposable local Gitea repositories was rejected
  with HTTP 401, `Permission denied`, during destination validation. Both test
  repositories were removed. No network restriction was relaxed for the test.

An actual GitHub mirror push and automatic event-driven update remain unchecked
until an empty destination is available. Image manifests do not establish native
Apple silicon installation or disaster recovery.
