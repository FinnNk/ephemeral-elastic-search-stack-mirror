# Install a fresh CPU search lab

Use the [locked uv environment](python-environments.md) for host Python commands.

Create a new lab with fresh credentials and certificates, the full English ESCI
catalogue, source CI, comparisons, notebooks and reviewed delivery promotions.
The installer also sets up Nexus, snapshot storage, the CPU abstaining judgement
service, shared Redis rewrite datasets, small simulated monthly and event catalogues
and OIDC sign-in for Gitea, Argo CD, Headlamp and the control UI.

The delivery-source seed includes a semantic version. Baseline publication and
final verification require versioned delivery releases with exact source commits;
an unversioned Integration, Staging or Production target fails verification.
See [release versions and identities](delivery-versioning.md#identity-and-ordering).

Large research models, GPU jobs and the optional Headlamp development testbed
are not installed. SigNoz is an optional follow-on installation using the demo
profile below. Windows credentials and CA keys are not transferred.
The existing frozen lab judgements are restored with their original provenance;
model predictions remain distinguishable from published labels.

Recovery and data identity checks are tested on Windows. An earlier Mac CPU
installation reached verification after repairs. A clean installation of the
current revision without intermediate patching, and its performance on the
target laptop, still need acceptance. Keep the original lab available until the
new installation passes its checks. Start with the [Mac handover](mac-handover.md)
to retain unfinished work and verify the mirror before cloning.

## Prepare the Mac

1. Install Docker Desktop, start it, and install the host tools:

   ```sh
   brew install uv git k3d kubectl helm
   ```

   Check that Docker Desktop's CLI tools include Buildx:

   ```sh
   docker buildx version
   ```

   Expect a Buildx version. If it is unavailable, enable Docker Desktop's CLI
   tools, or install `docker-buildx` with Homebrew and follow its plugin-directory
   instructions. Confirm the command works before starting installation.

2. Clone the accepted GitHub mirror and change to its repository root. Create
   the locked Python environment:

   ```sh
   uv sync --locked
   ```

   On a corporate network, configure [uv certificate trust](python-environments.md#corporate-certificates)
   before the first sync. Docker Desktop must also trust the organisation's CA. The installer configures
   its own Python downloads and
   the k3d nodes; it does not change macOS Keychain or Docker Desktop trust.
   See [Docker's corporate CA instructions](https://docs.docker.com/engine/network/ca-certs/).

3. Use a clean checkout with no `.lab` directory and no `relevance-lab` cluster.
   If repeating the failed manual setup, use the reset procedure below first.
   The installer refuses existing state that it did not create.

Allocate at least 40 GiB to Docker Desktop and allow around 200 GB of free disk
space for source downloads, image builds, repositories and persistent data.
A 64 GB Mac is a practical starting point; these are planning allowances, not
measured Mac peaks. The application stage expands the owned agent from 4 GiB to
16 GiB; the server starts at 10 GiB. Nexus and its database add 4.5 GiB of limits.
See [resource guidance](mac-setup.md#allocate-resources) for the separate restored
lab topology, which includes optional services.

For sustained load demonstrations, check memory headroom inside the k3d server
as well as Docker Desktop. A node can reclaim cached index pages and swap even
when Elasticsearch is below its own memory limit. The server's initial ceiling
can be selected with `--server-memory`; resuming an existing installation does
not resize it. The [node-memory investigation](plans/es-node-memory-headroom.md)
records the paired trial and the full Production retry that passed at 10 GiB
with unchanged budgets. This is the new server default; native Mac load
validation remains necessary. Resuming preserves existing node limits.

The seeded source repository includes the sneakers and Redis rewrite queries,
accepted advisory judgements, model provenance and source-pinned release notes.
They need no additional service or model download. See the
[additional judgements](../lab/delivery/bootstrap/evaluation/judgements/README.md)
for coverage and the [release check plan](release-check-plans.md) workflow.

## Start or resume installation

From the repository root in macOS Terminal, after `uv sync --locked`:

```sh
uv run --locked python lab/fresh_install.py
```

On a corporate network, supply your PEM bundle (replace the example path):

```sh
uv run --locked python lab/fresh_install.py \
  --corporate-ca "$HOME/certs/corporate-ca.pem"
```

Use your own corporate PEM path on another workstation. Keep it outside Git.
The installer adds it to existing public Python trust roots and mounts it into
both k3d nodes at creation. Certificate verification stays enabled. It downloads
the pinned Argo CD manifest through GitHub's API using the configured trust
bundle.

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

If an operator port (`14577` or `19200`) is reported as occupied on the Mac,
inspect the listener before stopping anything:

```sh
lsof -nP -iTCP:14577 -sTCP:LISTEN
```

Use `19200` instead when that is the named port. If the output identifies an old
`kubectl port-forward` for this installation, stop that specific forward and
resume. The installer does not kill other processes. Its Unix port check permits
recently closed sockets to be reused between stages; an active listener still
blocks installation. If no listener is listed, rerun the same command with the
current installer. The completed catalogue stage is retained.

The image stage uses an isolated Docker login configuration. It retains CLI
plugin search paths and the selected local Docker daemon, without copying your
stored registry credentials or credential helpers. Buildx availability is
checked before login or image builds. An explicit `DOCKER_HOST` is retained;
a selected Docker Desktop context is resolved to its local socket. A selected
remote context is refused instead of silently building against another engine.

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

### Resume after a checkout line-ending mismatch

If a Mac run reports **Generated dated catalogue differs from its committed
input pins**, pull the accepted portability fix and rerun the same installation
command with the same options. Do not use `--record-pins` or reset the cluster.
The catalogue stage resumes using the retained upstream downloads.

The original ESCI importer and other checksum-bound producer sources are stored
with their exact frozen bytes. Git preserves those bytes on every host. Their
CRLF line endings are intentional: converting them to LF changes the raw source
hash recorded by existing releases.

For a failed fresh installation made with the earlier LF checkout, the installer
recognises the known importer hash and verifies all base catalogue files. It
restores metadata only if the result matches the exact original frozen manifest.
It retains old metadata and affected local dated/seasonal outputs under
`.lab/portability-recovery`, then regenerates those derived outputs against the
unchanged committed pins. Product, query and judgement bytes in the base releases
are not rewritten. Existing Blob objects remain immutable.

An unexpected importer, changed data file or additional metadata difference is
rejected. Keep that error and its preceding output for diagnosis; this recovery
does not accept arbitrary new datasets or compression differences. Native Mac
acceptance remains required after the Windows reproduction.

### Git SSH access on macOS

Immediately before final verification, the installer enables loopback Gitea SSH
and sets up a dedicated encrypted key for the named account. Run installation
in an interactive macOS Terminal: choose a non-empty key passphrase when asked,
then supply it to Apple SSH for storage in Keychain. Existing SSH keys and
configuration are retained. Subsequent Git connections use the key without a
Gitea password; browser sign-in continues to use the lab identity.

Expect **Verified password-free Git access to delivery-source over SSH**. Use
`relevance-lab-gitea:elastic-agent/delivery-source.git` for your developer clone,
or Gitea's displayed SSH URL. The setup verifies the SSH host key against the
owned cluster and writes `.lab/git-ssh.json`; it does not change merge gates.

For an already installed Mac lab, run `uv run --locked python
lab/setup_gitea_ssh.py install` after pulling the accepted change and waiting for
jobs/comparisons to finish. No cluster reset is needed. See [Git over SSH](gitea-ssh.md)
for the upgrade, changed-password prompt, files retained and verification.

Use `--skip-git-ssh` only when deliberately installing unattended, then complete
SSH setup in Terminal later. Automatic Keychain setup is macOS-only; the same
installer on other hosts retains its existing authentication path.

## Configure workstation access

After the `access` stage completes:

```sh
export LAB_STATE_DIR="$PWD/.lab"
uv run --locked python lab/https_ingress.py trust
```

macOS may ask for permission to trust the newly generated **public** lab CA.
Approve the prompt, then restart your browser before opening the lab pages.
Then configure the two resolver files using [workstation DNS](workstation-access.md#set-up-lab-dns-once).
DNS configuration comes after installation of the DNS service.

Check the server directly before diagnosing macOS name resolution:

```sh
dig @127.0.0.1 lab-dns-check.preview.relevance.test
```

Expect an answer of `127.0.0.1`. After full installation, retrieve the named
account's initial credentials:

```sh
uv run --locked python lab/install_oidc.py credentials --user finnnk
```

This command deliberately prints credentials. Keep them out of shared logs.
Open [Gitea](https://gitea.localhost:34443/),
[Argo CD](https://argocd.localhost:34443/),
[Headlamp](https://headlamp.localhost:34443/) and
[Search lab](https://control.localhost:34443/), then use OIDC sign-in.
A foundation-only installation can use `uv run --locked python lab/install_headlamp.py token`
until OIDC is installed. That command prints a short-lived token.

## Continue an existing foundation installation

From the repository root, pull the merged
changes and install the application dependencies. On macOS, replace the
illustrative certificate path below with your organisation's PEM bundle:

```sh
git pull --ff-only
SSL_CERT_FILE="$PWD/.lab/host-ca-bundle.pem" uv sync --locked
uv run --locked python lab/fresh_install.py --corporate-ca "$HOME/certs/Corporate Root CA.pem"
```

The combined host CA bundle already exists after foundation setup. The corporate
PEM path is an example, not a supplied file. Resume with the same registry and initial node-memory
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

### Ready to create and promote a PR

A completed installation includes the source repository, CI runners, registry
credentials, protected source merge gates, delivery authentication, control UI
and initial Integration, Staging and Production releases. No separate operator
activation or workflow setup should be needed before using delivery.

Finish workstation DNS and browser CA trust, retrieve the new named account and
follow [Make and evaluate a change](delivery.md#make-and-evaluate-a-change).
After merging that PR and its successful merged-source build, use
[the release tree](delivery.md#promote-from-the-release-tree) to review plans and
promote through all three stages. These reviews and approvals are part of the
release process, not missing installation work. Optional SigNoz can be added
separately without blocking the delivery workflow.

The final installer verification checks ready services and versioned targets.
Acceptance additionally requires a real new PR and a full reviewed promotion
on the Mac. If that requires manual runner registration, gate installation,
Actions credential configuration or coordinator activation, treat it as an
installer defect; retain the failure and fix the setup before repeating it.

## Reset and check leftovers

For installations created by the new installer, inspect first:

```sh
uv run --locked python lab/cleanup_fresh_install.py
```

This is read-only. It lists the named cluster, possible leftover volumes,
external lab stores and resolver files. To delete the recorded fresh cluster
and its recorded named/anonymous node volumes, then archive its generated host state:

```sh
uv run --locked python lab/cleanup_fresh_install.py --delete --confirm relevance-lab
```

Add `--include-stores` for a complete reset of the external Nexus/PostgreSQL and
snapshot containers and volumes created by this installer:

```sh
uv run --locked python lab/cleanup_fresh_install.py --delete --confirm relevance-lab --include-stores
```

Every store container identity is checked before any deletion starts. Foreign or
replaced stores are refused. Without this option, external stores are retained;
inspect their archived ownership record before trying another fresh installation.

Add `--purge-state` only when you also want to permanently remove generated
credentials, CA keys, kubeconfig and installer records. Cleanup refuses changed
node identities, extra nodes, worktree state, an active installer lock or an
installation without its ownership record. It reports remaining resources.
Cached images, corporate certificates, macOS trust, DNS resolver files,
workstation SSH keys/configuration and Keychain entries are retained. External stores are retained unless `--include-stores` is selected.
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

## Add demo observability

After completing the fresh CPU installation, run from its repository root in
the same Python environment:

```sh
export LAB_STATE_DIR="$PWD/.lab"
uv run --locked python lab/observability/install.py --profile demo
```

This uses the retained corporate CA bundle, native control image and pinned
SigNoz chart. It installs on existing CPU nodes without adding a worker. Allow
approximately 6 GiB of additional steady-state memory headroom, and preferably
8 GiB during installation for migration jobs and startup bursts. These are
trial allocations for demonstrations, not measured minimum requirements.
ClickHouse requests 1 GiB and 0.5 CPU, with limits of 4 GiB and 2 CPUs. Its
internal server memory ceiling is 3 GiB. Health checks allow five seconds per
response; sustained liveness failure for approximately two minutes still
restarts the container. This avoids repeatedly restarting it during brief
background merge stalls while keeping readiness checks active.
PVC requests total 12 GiB: ClickHouse 10 GiB, ZooKeeper 1 GiB and SigNoz state
1 GiB. Images and container logs require additional host disk space. Local-path
PVC requests do not enforce a hard host-directory disk quota.

Open [SigNoz](https://signoz.localhost:34443/), create your first administrator
account and complete organisation setup. In **Settings**, set and confirm:

| Signal | Retention |
| --- | --- |
| Logs | 7 days |
| Traces | 7 days |
| Metrics | 30 days |

Retention is a required UI step; the installer does not authenticate as you or
change an existing organisation's retention. Organisation setup is required
before the backend accepts telemetry. The demo gateway samples 20% of traces;
application/Gatling metrics and selected structured logs are not sampled.
Automatic span-derived metrics describe sampled traces. Use the application's
request counters and retained Gatling reports for complete performance counts.

### Install the current dashboards

After creating the SigNoz organisation, keep a diagnostic connection running in
another terminal from the repository root:

```sh
kubectl --kubeconfig .lab/kubeconfig.yaml -n lab-observability port-forward svc/signoz 18090:8080
```

Use a short-lived administrator session token for this new SigNoz organisation;
see [dashboard access](observability-backend.md#interpret-dashboards). In the
original terminal on macOS, read it without putting it in shell history:

```sh
read -rs 'SIGNOZ_ACCESS_TOKEN?SigNoz administrator session token: '
printf '\n'
export SIGNOZ_ACCESS_TOKEN
uv run --locked python lab/observability/setup_dashboards.py
unset SIGNOZ_ACCESS_TOKEN
```

The command creates or updates both dashboards from this checkout and registers
their IDs with the control runtime. It prints the public IDs and retains them in
`.lab/observability-dashboards.json`; it does not retain the token. Stop the
port-forward when finished and refresh any open operation page. Its observability
link now uses this installation's search dashboard. Until registration succeeds,
the link opens SigNoz's home page and explains that setup is incomplete.

### Check the installed changes

A new installation builds its control image from the current checkout and seeds
`delivery-source` with the current Search API, gate configuration and chart.
Update to the latest merged `main` before starting. Completed installer stages
are retained on resume; pulling new source does not rebuild an already completed
image stage or replace an existing source repository.

| Area | Included by the current fresh setup |
| --- | --- |
| Promotion controls and reports | Latest-attempt actions, readable release identities, live evaluation progress and retained Gatling reports |
| Promotion checks | Mandatory standard query sets, selected additional sets, per-variant relevance checks before performance and the short probe's 20-second warm-up / 30-second measurement |
| Search telemetry | Endpoint, release/environment attributes and collector network access in both delivery and exploratory environment charts |
| Logs | Structured events with trace/span IDs and matching metric drill-through fields, in both observability profiles |
| Dashboards | Current definitions, installed and registered by the command above after organisation setup |

After creating an environment, run a small comparison or search, select its
namespace and a recent time range in SigNoz, and confirm metrics, traces and
structured logs. The smaller profile samples traces, so an individual request
need not have a retained trace. No legacy-baseline repair helper is required for
new environments; those use the current chart from their first deployment.

The command preserves persistent data on repeat runs and refuses larger existing
PVCs rather than trying to shrink them. Do not use this profile to resize the
original retained Windows backend. The standard profile remains available for
its dedicated observability worker. See [observability operations](observability-backend.md)
for diagnostic access and interpretation. Dashboard IDs belong to the new
installation; the registration command above uses the IDs returned by SigNoz.

Before choosing a smaller permanent disk budget, measure idle storage growth
and one bounded Gatling run. Keep spare space for database merges. Native Mac
readiness and ingestion still need verification on the target.

If installation times out, inspect the pods before retrying:

```sh
export KUBECONFIG="$PWD/.lab/kubeconfig.yaml"
kubectl -n lab-observability get pods
kubectl -n lab-observability logs chi-signoz-clickhouse-cluster-0-0-0 \
  -c signoz-clickhouse-udf-init --previous --tail=80
```

An `argument list too long` error in the ClickHouse init container indicates an
older installer embedded the CA bundle in its shell command. Pull the latest
code and rerun `uv run --locked python lab/observability/install.py --profile demo`. The current
installer reads the trusted CA file already present in the native image.
Keep the existing installation and volumes; a reset or image rebuild is not
required for this repair.

On demo retries, the installer saves the previous migration Job's available
logs in `.lab/observability-demo/previous-migrator.log` and recreates that Job.
It applies ClickHouse settings before waiting for migrations, so an unavailable
database cannot block its own repair through a pre-upgrade hook. Installation
still requires successful migration completion and ready backend workloads.

## Diagnose a failed stage

| Symptom | Next action |
| --- | --- |
| Missing kubeconfig | The installer creates `.lab` before exporting it. Resume from `cluster`; do not hand-create empty kubeconfig files. |
| `ImagePullBackOff`, certificate error | Check the corporate PEM was supplied on the first run and Docker Desktop trusts the organisation's CA. |
| Image download returns HTTP 403 | The selected registry may be restricted. Confirm the permitted official source; extending a readiness timeout does not fix access denial. |
| Python certificate verification fails | Read the printed download hostname. Obtain the required CA chain for that hostname; do not disable verification. |
| Gitea readiness timeout | Inspect printed pod status/events for image pulls, PVC binding or restarts, then rerun. |
| Registry login to `gitea.localhost:31800` resolves to `127.0.0.1` and is refused | Pull the current installer and resume. The baseline stage restores the in-cluster Gitea DNS rewrite, preserving other rules. After changing that route it retries the failed push build once for the same source commit. A second failure stops for inspection in Actions. |
| Delivery bootstrap reports `No module named 'evaluation'` | Pull the current installer and resume with the same options. Child scripts receive the repository import path; completed builds and installation stages are retained. |
| PR comparison fails because `gate/selection.json` is absent | Fresh repositories include this file. In an existing source repository, add the [gate selection example](../lab/delivery/bootstrap/gate/README.md#prepare-your-pr) on the PR branch, choose its intent, commit and push. Rerunning installation preserves existing source files. |
| `Argo/API verification did not complete` during baseline | Read the reported Argo or serving-verification state. The fresh installer creates and waits for its in-cluster search probe before bootstrap. Pull the current installer and resume; inspect application status and pod events if verification still fails. |
| DNS query times out | Complete the `access` stage and check `lab-dns` readiness and loopback UDP/TCP port 53 mappings. |
| `lab-control-namespace-manager` not found | Pull the current installer and rerun. DNS supports installation before the control runtime; its optional permission update is skipped until the role exists. |
| Installer ownership differs | Do not adopt another cluster or overwrite its credentials. Inspect the cleanup inventory and resolve the identity mismatch first. |

For an existing lab restoration, follow the separate [transfer runbook](lab-transfer.md).

## Release checks after installation

The control runtime includes [reviewed release check plans](release-check-plans.md).
The initial baseline needs no promotion plan. For later promotions, suggest and
review a plan in the release dashboard, approve the exact delivery-state PR head
and record it. No additional service or installation flag is required. Standard
query sets remain compulsory for every selected variant.

### Branch previews

Fresh source repositories include the protected workflow and tooling for [building a preview from a branch or SHA](branch-previews.md). Use **Build and create preview** in the control UI after verification. It reuses the installed runner, shared data and corporate/lab CA trust; no PR is required for the preview.
