# GitHub push mirror preflight

Checked on 5 October 2026 with Gitea 1.27.0 and chart 12.7.0.

## Before activation

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

## Activation results

The owner created three empty repositories, granted the App access and changed
their visibility to private. Native mirrors were enabled on 5 October 2026.

| Gitea source | GitHub destination | Initial branch/tag refs | Main commit |
| --- | --- | --- | --- |
| `ephemeral-elastic-search-stack` | `FinnNk/ephemeral-elastic-search-stack-mirror` | 4 | `750335ecaafebdc7bf69a5faacb5ff504d33b407` |
| `delivery-source` | `FinnNk/delivery-source-mirror` | 11 | `715a2a3ed6df60d8acaf85cb7a767413c97dc6a4` |
| `delivery-state` | `FinnNk/delivery-state-mirror` | 52 | `c44b026c407b0bf91912aa55ff8e0f30700215ec` |

All initial branch and tag hashes matched.
All mirrors reported no error, with sync on commit enabled and a one-hour
interval. The GitHub App key is supplied through ESO; mirror URLs contain no
credentials.

An ordinary Git push created a temporary branch in each Gitea repository.
Without an explicit mirror sync, the same ref appeared on GitHub. The polling
checks returned after 7.875, 5.500 and 4.218 seconds respectively. These are
individual check timings after the push command returned, not latency targets.

Deleting those branches did not trigger an immediate mirror update. The first
lab check waited 90 seconds; the subsequent checks waited at least 15 seconds.
Explicit full syncs then removed them and left no mirror error. The configured
hourly full sync provides the periodic path; waiting for its timer was not part
of this check. No temporary branch remains in either remote.

The existing GitHub backup and its PRs were not changed. Gitea PRs 114 and 115
were still open during activation; mirrors back up review branches too, without
merging them into main. GitHub PR or review replication, native Apple silicon
installation and recovery from a lost host remain outside these checks.
