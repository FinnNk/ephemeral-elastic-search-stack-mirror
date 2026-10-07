# Install a fresh lab foundation

Use this installer to create a new CPU cluster with new credentials and a new
lab certificate authority. It installs Gitea, Argo CD, ECK (the Elasticsearch
operator), an empty Elasticsearch cluster, Floci, HTTPS ingress, local DNS and
Headlamp. It does not copy Windows credentials, CA keys or large models.

**This is the platform foundation, not the complete search lab.** Catalogue
import, CI repositories/runners, Nexus, snapshot storage, judgement services,
OIDC and the delivery control runtime are separate configuration stages. The
installer reports this boundary at completion. Automated fresh setup for those
stages is still outstanding; do not follow historical experiment commands as a
substitute for a complete installation.

The recovery and cleanup logic has automated tests on Windows. The complete
installer has not been run on a native Mac. Keep the original lab available
until the new installation passes its acceptance checks.

## Prepare the Mac

1. Install Docker Desktop, start it, and install the host tools:

   ```sh
   brew install python@3.12 git k3d kubectl helm
   ```

2. Clone the accepted GitHub mirror and change to its repository root. Create
   a Python environment:

   ```sh
   python3.12 -m venv .venv
   . .venv/bin/activate
   python -m pip install -r lab/requirements-https.txt
   python -m pip install PyYAML==6.0.2
   ```

   On a corporate network, pip and Docker Desktop must already trust the
   organisation's CA. The installer configures its own Python downloads and
   the k3d nodes; it does not change macOS Keychain or Docker Desktop trust.
   See [Docker's corporate CA instructions](https://docs.docker.com/engine/network/ca-certs/).

3. Use a clean checkout with no `.lab` directory and no `relevance-lab` cluster.
   If repeating the failed manual setup, use the reset procedure below first.
   The installer refuses existing state that it did not create.

See [Mac resource guidance](mac-setup.md#allocate-resources) before extending
this small foundation to the complete lab. The two initial nodes have memory
limits of 6 GiB and 4 GiB; these do not size the full topology.

## Start or resume installation

From the repository root in macOS Terminal, with the venv active:

```sh
python lab/fresh_install.py
```

On a corporate network, supply your PEM bundle (replace the example path):

```sh
python lab/fresh_install.py \
  --corporate-ca "$HOME/certs/corporate-ca.pem"
```

Use your own corporate PEM path on another workstation. Keep it outside Git.
The installer adds it to existing public Python trust roots and mounts it into
both k3d nodes at creation. Certificate verification stays enabled. It downloads
the pinned Argo CD manifest through GitHub's API; this avoids the raw-content
hostname that failed certificate verification during the walkthrough.

Gitea defaults to its official Docker Hub repository, using the same immutable
28.0.0 image digest as `docker.gitea.com`. If that source is required locally,
select `--gitea-registry docker.gitea.com/gitea` on the first run.

ECK 3.5.0 and Elasticsearch 9.5.4 also use Elastic's official Docker Hub images,
with pinned multi-architecture digests. This avoids `docker.elastic.co`, which
returned HTTP 403 on the corporate network. Downloading manifests successfully
does not establish access to the container registry they name.

Expect named stages, streamed Helm/kubectl output, a progress message every
20 seconds during quiet commands, and elapsed timings after each stage. Initial
image downloads can take several minutes. Gitea has a ten-minute readiness
timeout. On failure, the installer prints pod status and Kubernetes events.

Rerun **the same command and options** after fixing the failure. Completed
stages are retained in `.lab/fresh-install.json`; the current cluster identity
and node readiness are checked again. The failed stage reconciles its partial
resources. New credentials are generated once and retained locally.

When resuming an earlier foundation installation, the installer also reconciles
the ECK and Elasticsearch image sources in completed stages. It preserves their
release versions and Elasticsearch storage settings; the image-source change
can restart those workloads. There is no need to reset a cluster just to correct
a blocked registry.

To stop at a boundary, add `--through cluster`, `--through platform` or
`--through storage`. The default is `--through access`. Later rerun with
`--through access` to continue. If the process was forcibly killed and a lock
remains, inspect the PID in `.lab/fresh-install.lock`; remove that lock only
after confirming no installer is running.

## Configure workstation access

After the `access` stage completes:

```sh
export LAB_STATE_DIR="$PWD/.lab"
python lab/https_ingress.py trust
```

macOS may ask for permission to trust the newly generated **public** lab CA.
Then configure the two resolver files using [workstation DNS](workstation-access.md#set-up-lab-dns-once).
DNS configuration comes after installation of the DNS service.

Check the server directly before diagnosing macOS name resolution:

```sh
dig @127.0.0.1 lab-dns-check.preview.relevance.test
```

Expect an answer of `127.0.0.1`. Open [Gitea](https://gitea.localhost:34443/),
[Argo CD](https://argocd.localhost:34443/) and
[Headlamp](https://headlamp.localhost:34443/). Named OIDC sign-in is not installed
at this stage; use Headlamp's explicit token command when needed:

```sh
python lab/install_headlamp.py token
```

This command deliberately prints a short-lived token. Never put it in an
installation log. Gitea's generated admin credentials are in
`.lab/credentials.json`; treat that file as private.

## Reset and check leftovers

For installations created by the new installer, inspect first:

```sh
python lab/cleanup_fresh_install.py
```

This is read-only. It lists the named cluster, possible leftover volumes,
external lab stores and resolver files. To delete the recorded fresh cluster
and its recorded named/anonymous node volumes, then archive its generated host state:

```sh
python lab/cleanup_fresh_install.py --delete --confirm relevance-lab
```

Add `--purge-state` only when you also want to permanently remove generated
credentials, CA keys, kubeconfig and installer records. Cleanup refuses changed
node identities, extra nodes, worktree state, an active installer lock or an
installation without its ownership record. It reports remaining resources.
Cached images, external stores, corporate certificates, macOS trust and DNS
resolver files are retained. It never invokes a global Docker prune.

For the **earlier manual attempt**, which has no ownership record, run these
commands on the Mac only after confirming this is the disposable new cluster:

```sh
k3d cluster delete relevance-lab
mv .lab ".lab-before-fresh-install-$(date +%Y%m%d-%H%M%S)"
unset SSL_CERT_FILE REQUESTS_CA_BUNDLE LAB_STATE_DIR
```

The archive contains secrets. Keep it private or remove it after you no longer
need it. Leave the corporate PEM and installed host tools in place. Run the
read-only cleanup command to inspect remaining containers and volumes. Do not
use this reset procedure on the original retained Windows lab.

## Diagnose a failed stage

| Symptom | Next action |
| --- | --- |
| Missing kubeconfig | The installer creates `.lab` before exporting it. Resume from `cluster`; do not hand-create empty kubeconfig files. |
| `ImagePullBackOff`, certificate error | Check the corporate PEM was supplied on the first run and Docker Desktop trusts the organisation's CA. |
| Image download returns HTTP 403 | The selected registry may be restricted. Confirm the permitted official source; extending a readiness timeout does not fix access denial. |
| Python certificate verification fails | Read the printed download hostname. Obtain the required CA chain for that hostname; do not disable verification. |
| Gitea readiness timeout | Inspect printed pod status/events for image pulls, PVC binding or restarts, then rerun. |
| DNS query times out | Complete the `access` stage and check `lab-dns` readiness and loopback UDP/TCP port 53 mappings. |
| Installer ownership differs | Do not adopt another cluster or overwrite its credentials. Inspect the cleanup inventory and resolve the identity mismatch first. |

For an existing lab restoration, follow the separate [transfer runbook](lab-transfer.md).
