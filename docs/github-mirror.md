# GitHub backup mirrors

Gitea owns branches, reviews and merges. Its native push mirrors copy Git history
to private GitHub repositories after a push, with an hourly retry as a fallback.
Developers work in Gitea; they do not create a second backup PR.

All three mirrors are enabled. Initial branch and tag hashes match Gitea, and
ordinary Git pushes reach GitHub automatically.

## What is backed up

| Gitea repository | GitHub mirror | Contents |
| --- | --- | --- |
| `ephemeral-elastic-search-stack` | [Lab mirror](https://github.com/FinnNk/ephemeral-elastic-search-stack-mirror) | Lab code, configuration and documentation |
| `delivery-source` | [Source mirror](https://github.com/FinnNk/delivery-source-mirror) | Search API code and CI workflows |
| `delivery-state` | [State mirror](https://github.com/FinnNk/delivery-state-mirror) | Reviewed deployments and recorded relevance decisions |

Mirrors copy branches, tags and commits. They do not copy Gitea PR discussions,
reviews, accounts, Actions logs, Blob data, Nexus artefacts or the control volume.
Those need separate backups.

The mirrors are private to preserve the lab's existing visibility. Public
mirrors also work, but expose every mirrored branch, tag and commit. Choose
public visibility only when that publication is intended.

Use empty destinations when setting up another mirror. Gitea force-pushes mirror
refs; do not develop or merge changes in a destination repository. The old backup
repository remains retained until its owner removes it.

## Configure a mirror

Run these operator commands from the **lab repository**, with `LAB_STATE_DIR`
pointing to retained lab state. Developers do not need to perform this setup.

1. Create an empty private GitHub repository: no README, licence or `.gitignore`.
   Grant the existing GitHub App access to it. The App needs **Contents: write**;
   repositories containing `.github/workflows` also need **Workflows: write**.
   Keep review protection on Gitea. GitHub destination rules must allow the App
   to push and update mirrored refs.
2. Build the helper image and install it. This uses the existing App private key
   as bootstrap input; ESO then supplies it from Azure Key Vault to Gitea.

   ```powershell
   $env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
   python lab/github-mirror/publish.py
   $image = (Get-Content "$env:LAB_STATE_DIR/github-mirror/image.json" | ConvertFrom-Json).image
   python lab/github_mirror.py install --image $image --private-key 'D:\codex\.secrets\ephemeral-elastic-agent.2026-09-26.private-key.pem'
   ```

   The image contains AMD64 and ARM64 builds. Installation preserves the existing
   Gitea chart settings and enables no mirror by itself.
3. Add the destination. Replace `OWNER/REPOSITORY` with the empty GitHub repository.

   ```powershell
   python lab/github_mirror.py add --source ephemeral-elastic-search-stack --target https://github.com/OWNER/REPOSITORY.git --app 5088896 --installation 165239445
   python lab/github_mirror.py status --source ephemeral-elastic-search-stack
   ```

   Setup refuses a populated destination. Repeat it with the other source names
   and their own destinations when those repositories are selected for backup.
4. In Gitea, open **Settings → Repository → Mirror Settings**. Check the last
   update and any error. Compare GitHub and Gitea branch and tag hashes, then
   confirm a fresh Gitea branch push appears automatically on GitHub.

The Python commands use the lab's normal dependencies and state directory on
Linux and macOS too; use that host's lab checkout, state path and private-key
path. Native Linux/macOS installation has not been checked.

## Authentication and recovery

Gitea performs the pushes. The pinned open source
[GitHub App credential helper](https://github.com/bdellegrazie/git-credential-github-app)
obtains a new installation token when Git requests credentials. The repository's
Git configuration scopes it to its destination URL. Tokens are not saved in
mirror passwords, Git URLs or files.

If a sync fails, check App installation access, permissions and destination
branch rules first. After correcting them, select **Synchronise Now** in the
repository's mirror settings. Removing the push mirror stops automatic backup;
it does not delete either repository.

Branch deletion alone did not trigger an immediate sync in the local check.
The next full sync removes deleted refs. Use **Synchronise Now** when immediate
cleanup is needed; the configured hourly schedule provides periodic full syncs.

See the [setup plan](plans/github-push-mirrors.md),
[verification record](research/evidence/github-push-mirror-preflight.md) and
[Gitea mirroring documentation](https://docs.gitea.com/usage/repository/repo-mirror/).
