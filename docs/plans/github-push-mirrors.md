# Enable native GitHub push mirrors

## Intent and constraints

Replace manual backup PRs with Gitea's native push mirrors. Gitea remains the
review authority. Use empty private destinations, preserving the existing
GitHub repository until automatic backup has been verified.

- Keep the existing GitHub App identity. Obtain fresh installation tokens with
  the pinned open source credential helper, rather than storing an expiring token.
- Supply its key through Azure Key Vault and ESO; retain only bootstrap input
  outside the cluster. Add no custom mirror scheduler.
- Mirror Git refs only. PR and non-Git storage backups remain separate work.
- Do not overwrite the current backup main or close its review stack during setup.
- Keep source and deployment approval gates unchanged.

## Acceptance criteria

| Check | Expected result |
| --- | --- |
| App authentication inside Gitea | Private repository refs are readable; tokens and key stay out of output and Git |
| Populated destination | Setup refuses it before enabling a native mirror |
| First sync | All selected source branch and tag hashes match the empty destination |
| Automatic update | A fresh Gitea push reaches GitHub without a manual script or backup PR |
| Repeat setup | Existing mirror remains singular and its configuration is preserved |
| Recovery | A failed sync is visible in Gitea; manual retry works after correction |
| Portability | Helper image has AMD64 and ARM64 manifests; native host checks are reported separately |

## Current status and next batch

The helper is installed and the three private mirrors are enabled. Initial
branch/tag hashes matched, and ordinary temporary-branch pushes appeared on
GitHub automatically. Full syncs removed the deleted branches; deletion alone
did not trigger immediate sync. Four setup safety tests and Ruff passed.

The old backup remains untouched. Its removal is an owner action, not part of
mirror activation. The next batch is the [developer workstation walkthrough](remote-delivery-user-check.md).
The [verification record](../research/evidence/github-push-mirror-preflight.md)
retains revisions and the distinction between automatic and explicit syncs.

## References

- [Operator guide](../github-mirror.md)
- `lab/github_mirror.py`, `lab/test_github_mirror.py`
- `lab/github-mirror/Dockerfile`, `lab/github-mirror/publish.py`
- [Gitea push mirror behaviour](https://docs.gitea.com/usage/repository/repo-mirror/)
