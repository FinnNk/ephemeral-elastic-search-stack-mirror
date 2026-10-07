# Install a fresh CPU search lab

Create a new lab with fresh credentials and certificates, the full English ESCI
catalogue, source CI, comparisons, notebooks and reviewed delivery promotions.
The installer also sets up Nexus, snapshot storage, the CPU abstaining judgement
service and OIDC sign-in for Gitea, Argo CD, Headlamp and the control UI.

Large research models, GPU jobs, SigNoz and the optional Headlamp development
testbed are not installed. Windows credentials and CA keys are not transferred.
The existing frozen lab judgements are restored with their original provenance;
model predictions remain distinguishable from published labels.

Recovery and data identity checks are tested on Windows. Native Mac installation
and corporate network access still need verification on the target laptop. Keep
the original lab available until the new installation passes its acceptance checks.

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
   python -m pip install -r lab/fresh-requirements.txt
   ```

   On a corporate network, pip and Docker Desktop must already trust the
   organisation's CA. The installer configures its own Python downloads and
   the k3d nodes; it does not change macOS Keychain or Docker Desktop trust.
   See [Docker's corporate CA instructions](https://docs.docker.com/engine/network/ca-certs/).

3. Use a clean checkout with no `.lab` directory and no `relevance-lab` cluster.
   If repeating the failed manual setup, use the reset procedure below first.
   The installer refuses existing state that it did not create.

Allocate at least 32 GiB to Docker Desktop and allow around 200 GB of free disk
space for source downloads, image builds, repositories and persistent data.
A 64 GB Mac is a practical starting point; these are planning allowances, not
measured Mac peaks. The application stage expands the owned agent from 4 GiB to
16 GiB; the server remains at 6 GiB. Nexus and its database add 4.5 GiB of limits.
See [resource guidance](mac-setup.md#allocate-resources) for the separate restored
lab topology, which includes optional services.

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

### Catalogue source downloads

The catalogue stage downloads retained datasets from the public
[FinnNk/esci-s release](https://github.com/FinnNk/esci-s/releases/tag/lab-sources-v1).
GitHub authentication is not required. Products and query/label Parquet files
have additional Zstandard compression; ESCI-S metadata is split into four chunks
and keeps its original compression. The total download is approximately 4.56 GB.

The installer checks each asset, reconstructs the original source files and
checks their original hashes before import. The frozen source identity, catalogue
and judgement manifests do not change. Verified originals in `.lab/esci-upstream`
are reused; completed chunks survive a failed download. A partial chunk is
downloaded again. Downloads show progress approximately every ten seconds.

For offline installation, copy all three original files (`products.parquet`,
`examples.parquet`, `esci-s.json.zst`) into `.lab/esci-upstream` and rerun the same
installation command. The originals occupy approximately 4.78 GB; downloaded
asset copies require up to another 4.56 GB. Do not reset the installation for an
upstream or GitHub access failure. Access to GitHub release downloads is still
required when originals have not been supplied locally.

When resuming an earlier foundation installation, the installer also reconciles
the ECK and Elasticsearch image sources in completed stages. It preserves their
release versions and Elasticsearch storage settings; the image-source change
can restart those workloads. There is no need to reset a cluster just to correct
a blocked registry.

To stop at a boundary, add `--through cluster`, `--through platform` or
`--through storage`. The default is `--through verify`, which continues through
the application stages. Use `--through access` for a foundation only; rerun without that option
to install the search applications. If the process was forcibly killed and a lock
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

Expect an answer of `127.0.0.1`. After full installation, retrieve the named
account's initial credentials:

```sh
python lab/install_oidc.py credentials --user finnnk
```

This command deliberately prints credentials. Keep them out of shared logs.
Open [Gitea](https://gitea.localhost:34443/),
[Argo CD](https://argocd.localhost:34443/),
[Headlamp](https://headlamp.localhost:34443/) and
[Search lab](https://control.localhost:34443/), then use OIDC sign-in.
A foundation-only installation can use `python lab/install_headlamp.py token`
until OIDC is installed. That command prints a short-lived token.

## Continue an existing foundation installation

From the repository root, activate the same Python environment, pull the merged
changes and install the application dependencies. On the corporate Mac from the
walkthrough:

```sh
git pull --ff-only
PIP_CERT="$PWD/.lab/host-ca-bundle.pem" python -m pip install -r lab/fresh-requirements.txt
python lab/fresh_install.py --corporate-ca '/Users/uk45858697/certs/Tesco Root CA.pem'
```

The CA bundle already exists after foundation setup. On another machine, use its
own corporate PEM path. Resume with the same registry and initial node-memory
options as the first run. The installer retains completed stages and retries the
failed stage; it does not reset the cluster.

## Installation stages and acceptance

| Stage | Result |
| --- | --- |
| Cluster, platform, storage, access | Ready nodes, Gitea, Argo CD, Elasticsearch, Floci, HTTPS, DNS and Headlamp. |
| Services | Owned Nexus/PostgreSQL and snapshot stores; External Secrets Operator. |
| Repositories | Private source/state repositories, scoped credentials and Actions runners. |
| Identity | Fresh local identity provider and named OIDC sign-in. |
| Catalogue | Locked ESCI source download, full 1,215,854-product release and 10,000-product demo release, restored frozen judgements and indexed data. |
| Images | Native CPU images with immutable Nexus digests and corporate trust, including Java trust for Gatling. |
| Judgements | Newly registered CPU abstaining model, MLflow, KServe and both judgement API profiles. |
| Baseline | Successful builds of the exact fresh source commits; initial integration, staging and production deployments. |
| Control and delivery | Control state PVC, comparison/notebook services, delivery coordinator, UI and authenticated Actions. |
| Verify | Healthy services, stored-label/abstention/invalid-input checks, control dependencies and all delivery targets verified. |

The full ESCI source download is approximately 4.8 GB. Import, publication,
indexing and the first image builds can take considerably longer than platform
setup. Do not start another installer while one is running. Completed image
builds and source commits are retained on retry. If CI fails, inspect its Actions
log and rerun the failed build before resuming; the installer requires a successful
push build for the exact source commit.

Completion prints **CPU search lab installed** and writes `.lab/fresh-ready.json`.
The final verification runs again on subsequent invocations. Check native browser
sign-in, create a small comparison, open its notebook and follow a reviewed
promotion using the [developer walkthrough](delivery.md). An
abstaining model can leave new judgement gaps; installation does not relax the
relevance gate or claim those gaps have been independently labelled.

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

Add `--include-stores` for a complete reset of the external Nexus/PostgreSQL and
snapshot containers and volumes created by this installer:

```sh
python lab/cleanup_fresh_install.py --delete --confirm relevance-lab --include-stores
```

Every store container identity is checked before any deletion starts. Foreign or
replaced stores are refused. Without this option, external stores are retained;
inspect their archived ownership record before trying another fresh installation.

Add `--purge-state` only when you also want to permanently remove generated
credentials, CA keys, kubeconfig and installer records. Cleanup refuses changed
node identities, extra nodes, worktree state, an active installer lock or an
installation without its ownership record. It reports remaining resources.
Cached images, corporate certificates, macOS trust and DNS resolver files are
retained. External stores are retained unless `--include-stores` is selected.
Cleanup never invokes a global Docker prune.

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
| `lab-control-namespace-manager` not found | Pull the current installer and rerun. DNS supports installation before the control runtime; its optional permission update is skipped until the role exists. |
| Installer ownership differs | Do not adopt another cluster or overwrite its credentials. Inspect the cleanup inventory and resolve the identity mismatch first. |

For an existing lab restoration, follow the separate [transfer runbook](lab-transfer.md).
