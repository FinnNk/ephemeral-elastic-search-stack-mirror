# Access lab services over HTTPS

Traefik routes five lab browser hostnames through loopback port `34443` and terminates TLS with a local certificate authority (CA). Trust the public CA certificate using [workstation access](workstation-access.md) before opening the services.

| Service | Browser address | Behaviour |
| --- | --- | --- |
| Gitea | `https://gitea.localhost:34443/` | Public repository and account UI |
| Argo CD | `https://argocd.localhost:34443/` | Deployment UI |
| Control | `https://control.localhost:34443/` | Route exists; the installed API redirects to its canonical HTTP localhost address |
| SigNoz | `https://signoz.localhost:34443/` | Observability UI |
| Nexus | `https://nexus.localhost:34443/` | Repository administration UI |

These names address the current machine, not a laptop on the LAN. Use the [control forward](control-runtime.md#connect-and-check) for the current control UI; its [session boundary](identity-boundary.md) explains the HTTPS limitation.

## Install or reconcile ingress

Operator prerequisites: bootstrapped service namespaces, Docker, kubectl, k3d, the pinned lab Helm binary and Python. Use PowerShell from the repository root. In another worktree, point `LAB_STATE_DIR` at the retained state directory.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python -m pip install -r lab/requirements-https.txt
python lab/https_ingress.py install
```

Installation prints TLS/HTTP verification results for the configured routes. It installs pinned Traefik, creates or reuses the CA and 90-day server certificate, applies namespaced routes and TLS Secrets, exposes the host port and updates Gitea's public URL. A current valid certificate is retained on repeat runs.

Keep CA and server private keys in ignored `$env:LAB_STATE_DIR/https-ingress/`. Share only `root.pem`. Initial research bootstrap can use `bootstrap-gitea` before other service namespaces exist; use full `install` once all five services are available.

## Verify and recover

```powershell
python lab/https_ingress.py verify
```

Expect one verification line per configured service. This checks the certificate, SNI hostname and initial HTTP response. It accepts a redirect and does not prove login, final routing or browser drill-through.

| Failure | Recovery |
| --- | --- |
| Connection refused | Check Traefik readiness and k3d's host-port mapping; confirm Docker and the cluster are running. |
| Certificate not trusted | Import the existing public CA using the workstation guide. Do not disable TLS verification. |
| Certificate expired or incomplete | Reconcile installation, then distribute the renewed CA if it changed. |
| Route redirects incorrectly | Check that service's public URL and Host validation; TLS termination alone does not change application routing. |

The script's `trust` action installs browser/system trust on Windows and macOS. Git's OpenSSL backend uses the separate user-owned bundle described in [workstation access](workstation-access.md#configure-git-once-with-a-user-owned-bundle). Linux trust is a separate workstation procedure. If the CA changes, follow [Git client recovery](https-git-transport.md#certificate-replacement) as well.

## Transport boundaries

Browser TLS ends at Traefik; the hop to web Services is cluster HTTP. Internal Gitea Git/API clients use a separate CA-verified HTTPS name. Host bootstrap scripts and OCI registries still have explicit local HTTP paths; [Git transport](https-git-transport.md) lists them.

The local CA and loopback DNS are lab choices. Azure needs the organisation's DNS, ingress and certificate automation. The [deployment views](diagrams/index.html#system-architecture) show placement; [dated transport evidence](research/evidence/https-git-transport-2026-09-28.md) records verified scope without claiming every browser workflow is complete.
