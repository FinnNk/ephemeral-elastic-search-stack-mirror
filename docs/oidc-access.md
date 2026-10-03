# Sign in to the lab with OIDC

Keycloak provides a local OpenID Connect (OIDC) identity provider. Use your named
account to sign in to Headlamp and Argo CD. Each application checks its own
permissions; signing in does not grant administrator access by itself.

![Lab identity and permissions](diagrams/rendered/09-identity.svg)

## First sign-in

Complete [workstation DNS and certificate trust](workstation-access.md) once.
The identity service uses the same lab root certificate.

1. From the lab repository, set `LAB_STATE_DIR` to the retained `.lab` directory.
   On this host, use PowerShell:

   ```powershell
   $env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
   python lab/install_oidc.py credentials --user finnnk
   ```

   On Linux or macOS, use `export LAB_STATE_DIR=/path/to/.lab` and `python3`
   instead. The command deliberately prints your temporary password: keep its
   output private.
2. Open [Headlamp](https://headlamp.localhost:34443/), choose OIDC sign-in, and
   enter the account name and temporary password. Set a new password when asked.
3. Open [Argo CD](https://argocd.localhost:34443/) and choose **Log in via Lab
   identity**. An existing Keycloak session can sign you in without another
   password prompt.

Gitea still uses its existing account and password. The OIDC account has the
same name but a separate password; account linking is a later integration.

| Account/group | Kubernetes through Headlamp | Argo CD |
| --- | --- | --- |
| `finnnk` / `lab-admins` | Cluster administrator | Administrator |
| `lab-reader` / `lab-readers` | View workloads; cannot read Secrets or mutate resources | Read-only; cannot sync |
| No lab group | No workload access | No application access |

Use `python lab/install_oidc.py credentials --user lab-reader` for the reader's
first sign-in. Password updates are stored in Keycloak, not written back to the
initial-password file. Reinstallation leaves existing passwords unchanged.

## Install and verify

Requires the running local lab, Headlamp, ESO/Key Vault delivery, HTTPS ingress,
automatic lab DNS, Helm, kubectl, Docker and Python dependencies from
`lab/requirements-https.txt`. Run from the repository root with `LAB_STATE_DIR`
set:

```powershell
python lab/install_oidc.py install
python lab/verify_oidc.py
```

The installer prints the service URLs and whether it restarted the Kubernetes
server. Adding authentication requires one server-only restart; repeating the
same configuration does not. It preserves the server volumes and workers,
including the optional GPU worker. Run it again after recreating a lab node;
node-local API-server configuration is not part of an experiment's frozen state.

The verifier uses disposable accounts and real login callbacks. Expect a JSON
report covering admin, reader, unassigned-user and wrong-audience checks. It
removes the probe accounts, probe client and temporary kubeconfig afterwards.
It does not change your password or run an application sync.

| Component | Configuration |
| --- | --- |
| Identity service | Keycloak 26.6.4 and PostgreSQL 17.6 in `lab-identity`; database on a PVC |
| Issuer | `https://identity.localhost:34443/realms/relevance-lab` |
| Client credentials | Azure Key Vault, locally emulated by Floci; ESO supplies Kubernetes Secrets |
| Bootstrap credentials | Ignored operator state and a bootstrap Secret |
| Kubernetes identity | Immutable subject, prefixed `lab-oidc:`; prefixed group claims |
| Headlamp | Native OIDC with PKCE; uses the user's token, not a shared privileged token |
| Argo CD | Native OIDC; group claims map to application roles |
| TLS | Existing root CA; verified discovery, token exchange and API access |

The pinned image manifests include amd64 and arm64. Installation on Apple
silicon remains untested. This provider is local to the lab; an organisation's
provider can later supply the same OIDC contracts with its own issuer, clients
and group mapping.

## Recovery

| Problem | Action |
| --- | --- |
| Name or certificate error | Run the checks in the workstation access guide. Do not disable TLS verification. |
| Login succeeds but access is forbidden | Check the user's realm group in Keycloak; sign in again after changing membership. |
| Identity service unavailable | Check `keycloak` and `keycloak-database` in `lab-identity`. Preserve the database PVC. |
| Need cluster access while repairing sign-in | Use the retained operator kubeconfig, or [Headlamp token recovery](headlamp.md#recovery-token). |
| Need identity administration | Run `python lab/install_oidc.py credentials --user bootstrap-admin`, then open [Keycloak administration](https://identity.localhost:34443/admin/). Keep this recovery account separate from everyday access. |
| Need Argo CD recovery | Use its retained local administrator account; automation credentials are unchanged. |

This batch does not add OIDC to Gitea, the control UI, MLflow, Nexus or SigNoz.
See the [next integration plan](plans/oidc-application-integration.md) and
[verification evidence](research/evidence/local-oidc.md).
