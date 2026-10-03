# Inspect the cluster with Headlamp

[Open Headlamp](https://headlamp.localhost:34443/) to inspect deployments, Pods,
events and logs in the lab. Use it to investigate workloads; Argo CD remains the
owner of Git-managed deployments. Direct edits to those resources may be reverted
by Argo CD.

## Sign in

Complete [workstation DNS and certificate trust](workstation-access.md) once.
From the lab repository root, select the retained state directory and request a
token. On the current host, run in PowerShell:

```powershell
$env:LAB_STATE_DIR = 'D:\codex\Ephemeral Elasticsearch\.lab'
python lab/install_headlamp.py token
```

On Linux or macOS, use `export LAB_STATE_DIR=/path/to/retained/.lab` and
`python3 lab/install_headlamp.py token`. The command needs Python, kubectl and
access to the retained kubeconfig.

1. Copy the printed token into Headlamp's token login field and sign in.
2. Select a namespace, such as `lab-control`, and open its workloads.
3. Select a Pod to inspect its events or logs.

The token expires after one hour. If requests fail with an authentication error,
run the command again and sign in with the new token. Treat the token as a
credential: do not commit it or include it in screenshots.

The human identity is `system:serviceaccount:lab-headlamp:headlamp-owner`, with
administrator access to this lab cluster. It is separate from coding-agent and
Headlamp Pod identities. Headlamp's own service account has no cluster-wide
workload role. There is no permanent token Secret or anonymous administrator
login. This token login does not reuse your Gitea account.

## Install or reconcile

Prerequisites: the running lab, Helm, kubectl, Python with
`lab/requirements-https.txt`, and installed [preview access](preview-access.md).
From the repository root, select `LAB_STATE_DIR` as above, then run:

```powershell
python lab/install_headlamp.py install
```

Expect a TLS/HTTP verification line and the Headlamp URL. Installation pins the
upstream chart and an image digest supporting Linux amd64 and arm64, creates
`lab-headlamp`, adds the HTTPS route, and refreshes lab DNS. It reuses the existing
CA, so no new certificate import or hosts-file change is needed. No plugin
manager, persistent storage or additional identity provider is installed.

| Problem | Check |
| --- | --- |
| Name does not resolve | Run the workstation DNS check; reconcile installation to refresh the lab DNS configuration. |
| Certificate rejected | Follow the workstation trust guide; keep TLS verification enabled. |
| UI unavailable | Check the `headlamp` Deployment in `lab-headlamp` and Traefik in `lab-ingress`. |
| Forbidden response | Check the token's Kubernetes role; request a new owner token for lab administration. |

Local verification covered Pod readiness, DNS, CA-verified HTTPS, anonymous
rejection and authenticated namespace listing. Apple silicon installation has
not been tested.

[Upstream installation](https://headlamp.dev/docs/latest/installation/in-cluster/)
explains Headlamp's Kubernetes deployment and token authentication.
