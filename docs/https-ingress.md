# Local HTTPS ingress

The lab exposes five retained web services through one Traefik ingress on loopback port `34443`. Traefik terminates TLS and routes by hostname to the existing Kubernetes Services. Gitea's public URL uses HTTPS; internal Git and container-registry paths keep their existing addresses so builds and deployments do not depend on workstation DNS or certificate trust.

| Service | Browser address | Backend |
| --- | --- | --- |
| Gitea | `https://gitea.localhost:34443/` | `platform/gitea-http:31800` |
| Argo CD | `https://argocd.localhost:34443/` | `argocd/argocd-server:80` |
| Lab control | `https://control.localhost:34443/` | `lab-control/lab-control:18082` |
| SigNoz | `https://signoz.localhost:34443/` | `lab-observability/signoz:8080` |
| Nexus UI | `https://nexus.localhost:34443/` | `platform/nexus:8081` |

## Install or reconcile

Use Python with [pinned certificate dependency](../lab/requirements-https.txt), Docker, kubectl, k3d and the lab's pinned Helm binary. Set `LAB_STATE_DIR` to the original retained `.lab` directory when running from another worktree.

```powershell
python -m pip install -r lab/requirements-https.txt
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/https_ingress.py install
python lab/https_ingress.py trust
python lab/https_ingress.py verify
```

`install` installs Traefik chart 41.6.0 in `lab-ingress`, creates a local CA and a 90-day server certificate, configures namespaced TLS Secrets and Ingresses, adds the scoped policy allowing Traefik to reach `lab-control`, exposes `127.0.0.1:34443` through k3d, then updates Gitea's `ROOT_URL`. Its Helm configuration keeps Gitea at one Pod with a recreate rollout because its local queue and SQLite files cannot be opened by two Pods concurrently. Re-running the command keeps the existing CA and certificate until the certificate has fewer than seven days left.

`trust` adds the CA to the current Windows user's certificate store, or the macOS login keychain. The CA private key and server key remain in ignored `.lab/https-ingress/`; do not commit or share them. Windows curl may need `--ssl-no-revoke` for this local CA. Git for Windows using its OpenSSL backend needs the CA explicitly for HTTPS Git, for example:

```powershell
git -c http.sslCAInfo="$env:LAB_STATE_DIR/https-ingress/root.pem" ls-remote https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack.git HEAD
```

The HTTP Gitea NodePort and internal Git, webhook and registry URLs remain available for existing automation. The Nexus Docker registry also keeps its existing HTTP address. This batch establishes a trusted browser-facing edge; moving build runners, OCI clients and service-to-service calls to HTTPS requires a separate trust and URL migration. Argo CD already has its own TLS-capable server; this local route uses its configured HTTP Service port behind Traefik.

The certificate is issued by a lab-only CA. In Azure, use the organisation's ingress and certificate automation; the namespaced routes and public URL contract can stay, while certificate issuance, DNS and TLS policy must be validated there. The [C4 deployment views](diagrams/index.html#system-architecture) show the ingress in local Kubernetes and the proposed AKS platform.

## Live check

On 28 September 2026, all five host routes passed SNI and CA-validated HTTPS requests. Gitea rolled out with the new public URL and one healthy Pod. Authenticated Git read the same merged `main` commit over the old HTTP address and new HTTPS address using the lab CA; all 28 Argo CD applications remained Synced and Healthy. Browser drill-through in the in-app browser could not be checked because its automation session failed to start. The [next validation batch](plans/https-client-transport.md) covers clients and remaining HTTP paths.
