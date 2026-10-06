# Gitea 28 upgrade

## Intent and constraints

Upgrade the server to stable 28.0.0 using the existing 12.7.0 chart, SQLite PVC,
OIDC settings, Actions runners and GitHub push mirrors. Pin the multi-platform
rootless image by digest. Preserve repositories, PR history and Actions evidence.

## Acceptance

- Confirm no active delivery operations or Actions runs before stopping Gitea.
- Stop the server, back up the complete PVC to ignored host state and check
  archive readability and SQLite integrity before permitting database migration.
- Retain the old Helm values and deployment for recovery.
- Upgrade with existing values and verify the API version and rollout readiness.
- Check repository/PR counts, Git transport, OIDC sign-in, Actions and push mirrors.
- Inspect startup logs for migration and egress-policy issues introduced in 28.
- Update the fresh-install image pin and operator guide; keep historical evidence.

## Recovery

Database migrations may prevent a simple image downgrade. Stop Gitea and restore
its complete pre-upgrade PVC backup and old Helm values together before starting
the old image. Preserve the failed upgraded data separately before replacement.
Backup files contain credentials and stay in ignored `.lab` state.

## Result

Installed 28.0.0. The full stopped-server backup passed archive and SQLite
checks. OIDC, HTTPS Git, a repository-scoped Actions run, signed local webhook
delivery and all three GitHub mirrors passed. All six repositories and 193 PRs
remain present. See [retained evidence](../research/evidence/gitea-28-upgrade.json).
A full backup restore was not rehearsed.

## Next

Review this upgrade batch, then resume the relevance walkthrough. See the
[Gitea operations guide](../gitea-upgrade.md) for retained backup locations and
[official upgrade guidance](https://docs.gitea.com/installation/upgrade-from-gitea/).
