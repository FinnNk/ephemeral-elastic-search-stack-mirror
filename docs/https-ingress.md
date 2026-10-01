# Local HTTPS ingress

The lab exposes five retained web services through one Traefik ingress on loopback port `34443`. Traefik terminates TLS and routes by hostname to the existing Kubernetes Services. Gitea's public URL and in-cluster Git clients use HTTPS. Container registries retain their HTTP addresses until the [OCI transport batch](plans/https-oci-transport.md).

| Service | Browser address | Backend |
| --- | --- | --- |
| Gitea | `https://gitea.localhost:34443/` | `platform/gitea-http:31800` |
| Argo CD | `https://argocd.localhost:34443/` | `argocd/argocd-server:80` |
| Lab control | `https://control.localhost:34443/` | `lab-control/lab-control:18082` |
| SigNoz | `https://signoz.localhost:34443/` | `lab-observability/signoz:8080` |
| Nexus UI | `https://nexus.localhost:34443/` | `platform/nexus:8081` |

For workstation Git and browser trust on Windows, Linux and macOS, follow [Connect a workstation](workstation-access.md).

## Install or reconcile

Use Python with [pinned certificate dependency](../lab/requirements-https.txt), Docker, kubectl, k3d and the lab's pinned Helm binary. Set `LAB_STATE_DIR` to the original retained `.lab` directory when running from another worktree.

```powershell
python -m pip install -r lab/requirements-https.txt
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/https_ingress.py install
python lab/https_ingress.py trust
python lab/https_ingress.py verify
```

`install` installs Traefik chart 41.6.0 in `lab-ingress`, creates a local CA and a 90-day server certificate, configures namespaced TLS Secrets and Ingresses, adds the scoped policy allowing Traefik to reach `lab-control`, exposes `127.0.0.1:34443` through k3d, then updates Gitea's `ROOT_URL`. It also exposes Gitea as `gitea-internal.lab-ingress.svc.cluster.local` and distributes the CA to the client namespaces. Its Helm configuration keeps Gitea at one Pod with a recreate rollout because its local queue and SQLite files cannot be opened by two Pods concurrently. Re-running the command keeps a current CA and certificate; certificates lacking key identifiers are replaced so Python 3.13 can validate the chain.

For the older research bootstrap, `python lab/https_ingress.py bootstrap-gitea` installs only the Gitea browser route and internal name before the other web Services exist. Run the full `install` action after those Services are available.

`trust` adds the CA to the current Windows user's certificate store, or the macOS login keychain. The CA private key and server key remain in ignored `.lab/https-ingress/`; do not commit or share them. Windows curl may need `--ssl-no-revoke` for this local CA. Git for Windows using its OpenSSL backend needs the CA explicitly for HTTPS Git, for example:

```powershell
git -c http.sslCAInfo="$env:LAB_STATE_DIR/https-ingress/root.pem" ls-remote https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack.git HEAD
```

The [Git client guide](https-git-transport.md) covers the in-cluster Gitea runners, control runtime and Argo CD. The HTTP Gitea NodePort remains available to host bootstrap scripts and older fixture revisions. Nexus and Gitea OCI registries still use HTTP. Argo CD's browser route uses its configured HTTP Service port behind Traefik.

The certificate is issued by a lab-only CA. In Azure, use the organisation's ingress and certificate automation; the namespaced routes and public URL contract can stay, while certificate issuance, DNS and TLS policy must be validated there. The [C4 deployment views](diagrams/index.html#system-architecture) show the ingress in local Kubernetes and the proposed AKS platform.

## Live check

On 28 September 2026, all five host routes passed SNI and CA-validated HTTPS requests. Gitea rolled out with the new public URL and one healthy Pod. Authenticated Git read the same merged `main` commit over the old HTTP address and new HTTPS address using the lab CA. After the Git client migration, all 28 Argo CD applications returned to Synced and Healthy. Browser drill-through in the in-app browser could not be checked because its automation session failed to start.
