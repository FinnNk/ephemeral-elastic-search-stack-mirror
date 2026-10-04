# Inspect the cluster with Headlamp

[Open Headlamp](https://headlamp.localhost:34443/) to inspect deployments, Pods,
events and logs. Use [OIDC sign-in](oidc-access.md) with your named lab account.
Argo CD owns Git-managed deployments and may revert direct edits to them.

1. Sign in and select a namespace, such as `lab-control`.
2. Open its workloads and select a Pod.
3. Inspect its events, containers and logs.

Administrators can change resources. Readers can inspect workloads but cannot
change them or read Kubernetes Secrets.

## Inspect KServe models

Refresh Headlamp after installation, then expand **KServe** in the sidebar.
Open **Overview** or **Inference Services** to inspect model deployments and
serving status. The plugin uses your signed-in Kubernetes permissions; it does
not grant extra access. Git-managed changes still belong in the source repository.

The lab includes the supplied `@headlamp-k8s/kserve` plugin, version
`0.1.0-dev.29`. Installation mounts its built files read-only and pins the archive
checksum. Reinstalling Headlamp or reconciling OIDC retains the plugin.

## Install or reconcile

Requires the running lab, Helm, kubectl, Python dependencies from
`lab/requirements-https.txt`, and [preview access](preview-access.md). Set
`LAB_STATE_DIR` to the retained `.lab` directory, then run from the repository:

```powershell
python lab/install_headlamp.py install
```

Expect a verified HTTPS response and the Headlamp URL. Installation pins the
chart and image, reuses the existing CA and refreshes lab DNS. It preserves OIDC
configuration when installed. On Linux or macOS, use `python3`.

## Recovery token

If OIDC is unavailable, request a one-hour lab administrator token:

```powershell
python lab/install_headlamp.py token
```

Copy it into Headlamp's token login field. Its identity is
`system:serviceaccount:lab-headlamp:headlamp-owner`, separate from the Headlamp
Pod and coding agent. Do not put the token in Git or screenshots. Request a new
token after it expires.

Headlamp's own service account has no cluster-wide workload role; shared
service-account authentication remains disabled. There is no permanent token
Secret or anonymous administrator access.

| Problem | Check |
| --- | --- |
| Name does not resolve | [Workstation DNS](workstation-access.md); reconcile installation to refresh lab DNS. |
| Certificate rejected | Workstation trust; keep TLS verification enabled. |
| UI unavailable | `headlamp` Deployment in `lab-headlamp`; Traefik in `lab-ingress`. |
| Forbidden response | Your OIDC group or recovery token's Kubernetes role. |

[Local OIDC evidence](research/evidence/local-oidc.md) covers real login callbacks
and live permissions. Apple silicon installation has not been tested.
