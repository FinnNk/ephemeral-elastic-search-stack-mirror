# Use Git over SSH on the Mac

Use a dedicated encrypted SSH key for Git clone, fetch and push. Browser sign-in
still uses **lab-identity**. Gitea maps the SSH key to your named account and
applies the same repository permissions and branch protection.

## Install on an existing fresh lab

Run this in macOS Terminal from the accepted lab repository checkout. Finish
active Actions jobs, comparisons and delivery operations first; setup checks
for active work before enabling the Gitea listener.

```sh
git pull --ff-only
export LAB_STATE_DIR="$PWD/.lab"
uv sync --locked
uv run --locked python lab/setup_gitea_ssh.py install
```

Setup requires the ownership record from `fresh_install.py`. It preserves the
current Gitea data, browser access and other Helm settings. Enabling SSH can
restart Gitea and update the k3d load balancer; it does not rebuild the cluster.
Its external TCP listener is bound only to `127.0.0.1:31822`.

Setup downloads the pinned chart through Helm, using the retained corporate CA
bundle when present, and verifies its checksum before changing Gitea. If this
download fails, no server or key changes have been made. After pulling a fix or
restoring network access, rerun the same setup command; no cleanup is needed.

When prompted, choose and confirm a **non-empty key passphrase**. SSH then asks
for that passphrase when adding the key to the agent and macOS Keychain. Approve
any Keychain access prompt. The passphrase is not saved in the lab state or
passed as a command argument. Apple SSH retrieves it from Keychain for later
Git connections using `UseKeychain` and `AddKeysToAgent`.

Expect **Verified password-free Git access to delivery-source over SSH** and a
clone command. Setup verifies the endpoint's public host key against the public
key read through the owned cluster before adding trust. It does not accept an
unverified `ssh-keyscan` result or disable host-key checks.

The named Gitea password is used only to register the public key during setup.
If you changed that password after installation, use:

```sh
uv run --locked python lab/setup_gitea_ssh.py install --prompt-gitea-password
```

This prompts privately for the current **Gitea** password, not the Control
identity password, and does not save the entered value.

## Clone or update your developer checkout

Use the generated alias:

```sh
git clone relevance-lab-gitea:elastic-agent/delivery-source.git
```

The standard SSH clone URL shown by Gitea also works: the scoped configuration
matches both `relevance-lab-gitea` and `gitea.localhost`, using the dedicated key
and port. It does not rewrite HTTPS URLs or change global Git authentication.

To switch an existing **developer checkout**, run inside that checkout:

```sh
git remote -v
git remote set-url origin relevance-lab-gitea:elastic-agent/delivery-source.git
git ls-remote origin HEAD
```

Confirm `origin` is the intended `delivery-source` repository before changing
it. Leave the installer's `.lab` checkouts and the runtime's service credentials
alone. Git may still need your workstation author name/email; SSH authenticates
transport and does not choose commit authorship.

## What setup retains

| Location | Contents |
| --- | --- |
| `~/.ssh/relevance-lab/id_ed25519-<cluster-UID>` | Dedicated encrypted private key and accompanying `.pub`; the private key stays on the Mac. |
| `~/.ssh/relevance-lab/config-<cluster-UID>` | Settings for the two lab SSH host names, including Keychain and strict host verification. |
| `~/.ssh/relevance-lab/known-hosts-<cluster-UID>` | Public host key verified against the owned Gitea pod. |
| `~/.ssh/config` | An added `Include` line; existing bytes remain, with a backup before the first edit. |
| `.lab/git-ssh.json` | Verification receipt and public fingerprints, with no private key or passphrase. |

Repeated setup reuses the same key and existing Gitea registration. Existing
personal keys are not replaced. A new cluster identity gets new files; older
keys and configuration are retained. Cleanup of a fresh lab does not remove
workstation keys, Keychain entries or unrelated SSH configuration.

Unexpected changes to managed files, existing explicit lab host settings,
symbolic links in managed paths, an occupied port or a different server key
stop setup for inspection. Do not delete existing SSH trust to suppress the
failure; compare the reported lab identity and retained files first.

## Fresh installation and verification

On macOS the fresh installer runs this setup immediately before final
verification, after source CI, identity and delivery services are ready. Run it
from an interactive Terminal. An unattended installation can explicitly use
`--skip-git-ssh`, then run the setup command above before switching Git to SSH.
That option does not claim SSH access is ready. Other host platforms retain
their existing Git authentication; automatic workstation Keychain setup is
currently macOS-only.

From the lab repository, check the installed SSH access without creating a key
or changing server settings:

```sh
uv run --locked python lab/setup_gitea_ssh.py verify
```

Setup verifies a read through the registered key. Confirm write access during
the normal walkthrough by pushing the empty-change branch and opening its PR.
Source CI and reviewed promotion still run their usual checks; SSH does not
provide a bypass.
