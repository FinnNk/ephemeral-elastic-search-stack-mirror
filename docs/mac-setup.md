# Prepare a Mac for the lab

For a new installation with fresh credentials and certificates, start with
[fresh installation](fresh-install.md). Its resumable installer automates the
CPU search lab with fresh identities, repositories and frozen ESCI data.

Use this guide to prepare an Apple silicon or Intel Mac for restoring an existing
lab using [the transfer runbook](lab-transfer.md). Installing the tools and
cloning Git do not restore the lab's databases or stored artefacts.

The host commands below use macOS Terminal and Python 3.12 or later. Native Mac
startup and restoration have not been tested. Complete the acceptance checks
before treating the transferred lab as ready for a demonstration.

## Install the host tools

1. Install the matching Apple silicon or Intel build of
   [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/).
   Start Docker Desktop and enable its command-line tools. Use Linux containers.
2. With [Homebrew](https://brew.sh/) available, install the host tools:

   ```sh
   brew install python@3.12 git k3d kubectl helm
   ```

   The source host uses k3d 5.9.0 and K3s 1.35.8. Keep the K3s version during
   restoration; upgrading the cluster is a separate operation. A newer host
   tool is not evidence that the retained lab has been tested with it.
3. Clone the accepted lab repository from its GitHub mirror, or transfer a clean
   checkout over a trusted connection. This avoids depending on local Gitea
   before it is restored. Change to the repository root and create a host venv:

   ```sh
   python3.12 -m venv .venv
   . .venv/bin/activate
   python -m pip install -r lab/requirements-https.txt
   python -m pip install PyYAML==6.0.2
   python -m pip install -r lab/requirements-azure.txt
   export LAB_STATE_DIR="$PWD/.lab"
   python lab/mac_preflight.py --target arm64 --output "$PWD/mac-host-check.json"
   ```

   On an Intel Mac, use `--target amd64`. Expect all five host tools to be
   available and `python_supported: true`. This check does not create a cluster.
   Host installers use matching retained executables or tools on `PATH`; copied
   Windows `.exe` files are not used on macOS.

## Allocate resources

The current CPU nodes have Docker memory limits totalling 30 GiB: 6 GiB for the
server, 4 GiB for the main agent, 12 GiB for observability and 8 GiB for the
optional Headlamp testbed. Nexus and its database add 4.5 GiB of limits. These
are configured limits, not measured simultaneous usage or a Mac minimum.

A 64 GB Mac is the practical starting point for the complete CPU topology.
On a smaller laptop, agree a reduced topology before restoration; omit optional
testbed and historical preview workloads first. Do not shrink database volumes
or assume that the current 50 GB Docker VM allocation fits a 32 GB laptop.
Leave memory for macOS and inspect actual pressure after startup.

The inventory records 15 PVCs requesting 70 GiB altogether, plus three external
Docker data volumes. Their requested capacities do not measure bytes in use.
Allow space for the restored data, archive copies and image cache. Inspect the
transfer archive sizes before choosing Docker Desktop's disk allocation.

## Prepare the cluster

For an **empty rehearsal cluster**, the retained base configuration can be used:

```sh
k3d cluster create --config research/platform-spike/k3d.yaml \
  --servers-memory 6g --agents-memory 4g
mkdir -p "$LAB_STATE_DIR"
k3d kubeconfig get relevance-lab > "$LAB_STATE_DIR/kubeconfig.yaml"
kubectl --kubeconfig "$LAB_STATE_DIR/kubeconfig.yaml" get nodes
```

Expect the server and main agent to be Ready. The base configuration does not
install the full platform. For a transfer, follow the runbook's stopped-target
restore sequence before starting application writers. Do not run the historical
research bootstrap against restored repositories: it creates initial accounts
and repositories rather than reconciling a complete existing lab.

The k3d configuration selects the native K3s image. It disables bundled Traefik;
the lab installs its own Traefik chart. Envoy remains a separate optional testbed
gateway. There is no need to consolidate them during the transfer.

## Configure browser and developer access

After restoring ingress, identity and registry services:

1. Trust the transferred public CA in your login keychain:

   ```sh
   python lab/https_ingress.py trust
   ```

   macOS may request permission. Retain the existing CA to keep the restored
   issuer and service certificates consistent.
2. Configure only the two lab domains using
   [the macOS resolver instructions](workstation-access.md#set-up-lab-dns-once).
   Docker Desktop must allow the loopback DNS mapping on TCP and UDP port 53.
   If the mapping fails, inspect Docker Desktop's privileged port settings and
   existing listeners; do not change the laptop's ordinary DNS server.
3. Verify native resolution and HTTPS:

   ```sh
   python lab/https_ingress.py verify
   git ls-remote https://gitea.localhost:34443/elastic-agent/delivery-source.git HEAD
   ```

   Expect native name-resolution and certificate checks to pass, then a commit
   and `HEAD` from Git. Apple Git can use Keychain trust. An OpenSSL-backed Git
   needs its own CA bundle; see [Git trust](workstation-access.md#configure-git-once-with-a-user-owned-bundle).
   Do not copy the Windows global Git configuration or disable TLS checks.
4. Open [Control](https://control.localhost:34443/),
   [Gitea](https://gitea.localhost:34443/) and
   [Headlamp](https://headlamp.localhost:34443/). Use the retained named identity.
   A token-only Headlamp session is not a successful OIDC restoration.

Daily development and reviewed promotion use the control pages or Actions
workflows. `kubectl` remains an operator and recovery tool, not a required step
for taking a search change to production.

## Use CPU inference

Do not create the NVIDIA worker, GPU device plugin or GPU exporter on the Mac.
Apple's GPU is not an NVIDIA CUDA device inside Docker Desktop. Retain model
artefacts for later use, but keep CUDA-dependent test services inactive.

The abstaining judge has an amd64/arm64 image. Verify that the restored judgement
API points to that retained judge and that its model/cache identity is unchanged.
Do not substitute a different model, lower the gate or treat cached experimental
labels as ground truth to compensate for missing GPU hardware.

## Verify the transferred lab

Use the [transfer acceptance checklist](lab-transfer.md#accept-the-mac-lab).
The 6 October Windows checks establish image metadata, host-tool fallback and
SQLite archive behaviour. They do not establish native Mac performance, Keychain
trust, DNS routing, binary database compatibility or complete recovery.
