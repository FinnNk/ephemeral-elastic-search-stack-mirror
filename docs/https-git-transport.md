# Operate HTTPS Git clients

The control services, Argo CD and Gitea Actions runners use CA-verified HTTPS at `gitea-internal.lab-ingress.svc.cluster.local`. Workstation Git uses the public browser hostname; follow [workstation trust](workstation-access.md) for that connection.

| Client | CA and configuration |
| --- | --- |
| Control API/workers | Mounted `lab-internal-ca`; Python loads it and Git uses `GIT_SSL_CAINFO` |
| Argo CD | `argocd-tls-certs-cm` maps the internal hostname to the CA; ESO supplies repository credentials |
| Actions runners | Mounted CA, `SSL_CERT_FILE`, `GIT_SSL_CAINFO` and HTTPS runner registration |
| Delivery workflow | `SOURCE_BASE_URL` repository variable selects the source API/Git address |

TLS verification stays enabled. Changing the URL does not change credentials or the immutable image digests.

## Reconcile an existing lab

Prerequisites: installed service Deployments and repositories, the [HTTPS ingress](https-ingress.md), and a control image containing the current TLS helpers. Use PowerShell from the repository root. In another worktree, select the retained state directory explicitly.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
$kubeconfig = Join-Path $env:LAB_STATE_DIR kubeconfig.yaml
python lab/control-runtime/install.py migrate-git-remotes
python lab/https_git.py migrate
kubectl --kubeconfig $kubeconfig apply -f research/platform-spike/runner.yaml
kubectl --kubeconfig $kubeconfig apply -f lab/delivery/bootstrap/runner.yaml
python lab/runner_https.py migrate
```

| Step | Expected result |
| --- | --- |
| Migrate control remotes | Only the three known retained checkouts change; an unexpected remote is rejected |
| Migrate Argo CD | Vault-backed URLs, ApplicationSets and Applications change; the command waits for Synced and Healthy |
| Apply and migrate runners | Both retained runner registrations move to HTTPS and the delivery source URL variable changes |

If a step fails, inspect its error and service readiness before continuing. Use the [control smoke check](control-runtime.md#connect-and-check), Argo CD application health and runner status to verify consumers. A successful TLS fetch does not prove CI or a comparison completed.

## Certificate replacement

1. Reconcile ingress and distribute the new public CA to workstations using the [trust guide](workstation-access.md). Refresh user-owned Git bundles with `lab/git_ca.py` and update browser trust separately.
2. Wait for active control work to finish, then restart the control Pod so mounted CA files refresh:

   ```powershell
   kubectl --kubeconfig $kubeconfig -n lab-control rollout restart deployment/lab-control
   kubectl --kubeconfig $kubeconfig -n lab-control rollout status deployment/lab-control --timeout=180s
   ```

3. Rerun `python lab/https_git.py migrate` to refresh Argo CD trust and reconcile runner configuration as above.
4. Repeat the control smoke check, inspect Applications and run a source CI build when authorised.

Renewing a server certificate under the same CA does not require new URLs. Replacing the CA requires consumer trust updates.

## Current protocol inventory

| Connection | Transport |
| --- | --- |
| Browser ingress | TLS to Traefik; canonical control address is `https://control.localhost:34443` |
| Control, Argo CD and runners to Gitea | CA-verified internal HTTPS |
| Host bootstrap to Gitea NodePort | Loopback HTTP |
| Gitea/Nexus OCI push and pull | HTTP with explicit lab insecure-registry configuration |
| Traefik to web Services | Cluster HTTP |
| Floci, Nexus API and OTLP gateway | Separate cluster HTTP contracts |

Older fixture workflow revisions can retain their original HTTP fetch. Inspect the selected repository revision instead of inferring its protocol from an old PR number. [Dated transport evidence](research/evidence/https-git-transport-2026-09-28.md) records the tested runs; [OCI migration](plans/https-oci-transport.md) and native/cloud validation remain separate work.
