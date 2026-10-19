# Dedicated Mac Git SSH access

## Outcome

Fresh Mac installation enables Gitea's built-in SSH listener on loopback and
registers a dedicated encrypted key to the named Gitea account. The existing Mac
lab can run the same setup without reinstallation. Browser sign-in and the
reviewed delivery workflow retain their current identities and permissions.

Use [Git over SSH](../gitea-ssh.md) for setup and recovery. The implementation
keeps server configuration, workstation files and CLI orchestration separate.

## Boundaries

- The fresh-install ownership and cluster identity must match. Delivery,
  lifecycle and source CI work must be idle before changing the server.
- Only loopback TCP 31822 is published, through the dedicated NodePort. Existing
  conflicting port mappings, services and custom SSH host-key settings are
  refused rather than replaced.
- The Gitea chart remains version 12.7.0, bound to its verified archive checksum.
  Downloads use the retained corporate/public CA bundle. Overrides change only
  SSH server settings and retain the chart's headless SSH service. A separate
  owned workstation service provides the NodePort.
  HTTPS URL maintenance also retains those settings rather than reapplying
  the original bootstrap values.
- Host trust compares the external key with the public key read through the
  owned cluster. The server's private host key stays in its persistent data.
- OpenSSH prompts for the client key passphrase. Apple SSH stores it in
  Keychain; the installer never receives it as an argument or saves it.
- Public-key registration authenticates as the named account, reuses an existing
  matching registration and refuses a conflicting title. No service account
  gets the developer's private key.
- Per-cluster SSH files and a scoped Include preserve existing personal keys
  and settings. Managed-file edits and symbolic links stop automatic replacement.
  Fresh cleanup retains workstation keys, configuration and Keychain entries.

## Verification

Windows fixture tests cover loopback enforcement, conflicting services/host-key
settings, active-work rejection, trusted-key comparison, chart integrity,
encrypted-key requirements, additive configuration and repeat setup, public-key
registration, native Keychain command selection, and noninteractive Git checks.
The combined SSH/fresh-install/application run passed 76 tests. Mac installer
tests verify SSH setup runs before final
verification, the explicit unattended skip, and removal of a stale ready marker
if SSH setup fails.

A render of the original SSH override confirmed a NodePort at 30022 targeting
the rootless listener on 2222, with the advertised host port 31822. That check
did not exercise upgrading the existing headless service; the follow-up below
corrects this gap. The image's tools were inspected read-only: it has `cat` and
`ssh-keygen`, but no `ssh-keyscan`. The verifier therefore reads only its public
host-key file rather than requiring another package in the container.

A disposable Gitea 28.0.0 pod accepted the named user's public key, reused the
same registration, verified host-key equality, and served a real SSH read and
clone. An empty commit was pushed over SSH and a PR was created in that isolated
repository. The pod namespace and its temporary port-forward were removed;
existing lab services were not reconfigured. Its test key was unencrypted and
disposable; this establishes Git transport and registration, not Apple Keychain
or production key-encryption behaviour.

The first disposable attempt hit an HTTP startup/port-forward race, corrected
with a readiness probe. A second exposed Windows MSYS path handling in the test
harness. The final run passed with POSIX paths, matching the Mac configuration
format. These failures did not require changes to running lab services.

## Next detailed plan

1. Accept and merge this batch and verify its GitHub mirror revision.
2. On the idle Mac lab, run the documented existing-install setup. Choose a
   passphrase, approve Keychain access and confirm the final SSH verification.
3. Verify a repeat setup reuses the key without modifying other SSH settings.
   Check a new Terminal/login session can use the key through Keychain/agent.
4. Clone the developer repository over SSH and push the intended empty change.
   Follow its source gate and reviewed Integration plan/deployment as usual.
5. On the next clean Mac installation, confirm the default installer includes
   this step without an additional operator setup command.

Native Mac execution, Keychain prompts/unlock, cold-session agent loading and a
fresh end-to-end installation remain acceptance checks. No Windows test is
presented as evidence that those have already passed.

## Mac chart-download follow-up

The first Mac upgrade stopped with HTTP 403 after the misleading rollout
message. At that point the direct Python chart download had not returned, so
Helm had not changed Gitea and key creation had not started. The response does
not establish whether the corporate network or upstream service rejected it.

Chart retrieval now uses Helm, matching the successful foundation installation,
with an isolated repository cache and the explicit retained CA bundle. The
archive checksum is unchanged. Download and rollout have separate progress
messages. All 78 targeted tests passed, including cache reuse, CA selection and
rejection of a changed download without caching it. A real Helm download on
Windows matched the pinned checksum; the corporate Mac network still requires
a retry. No running lab services were changed for this verification.

## Headless service upgrade follow-up

The Mac retry downloaded the chart, then Kubernetes rejected changing the
existing headless `gitea-ssh` service to NodePort. Setup now retains that service
and creates a separate `gitea-ssh-workstation` NodePort with the same pod selector.
The next Helm upgrade explicitly restores the headless settings retained in a
failed release. Existing workstation services must have this cluster's ownership
label before setup reuses them. No service deletion is required.

All 80 targeted tests passed. A disposable Kubernetes namespace reproduced the
old rejection, applied the corrected pinned-chart render over an existing
headless service without changing its UID, and created/reapplied the separate
NodePort. Rendering also covered the failed NodePort values followed by the fix.
The namespace was removed; retained lab services were unchanged. Mac SSH and
Keychain acceptance remain outstanding.
