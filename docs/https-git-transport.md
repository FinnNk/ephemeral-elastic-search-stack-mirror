# HTTPS Git clients in the local lab

Gitea runners, the control runtime and Argo CD read Gitea through `https://gitea-internal.lab-ingress.svc.cluster.local`. Traefik routes that name to the existing Gitea Service. The certificate covers both the internal name and the five browser names; the lab CA remains outside Git in `.lab/https-ingress/`.

| Client | Trust and address |
| --- | --- |
| Control API and workers | Mounted `lab-internal-ca` ConfigMap; Python loads it for Gitea requests, Git uses `GIT_SSL_CAINFO` |
| Argo CD | `argocd-tls-certs-cm` maps the internal hostname to the CA; the two repository credentials remain in Floci Key Vault via ESO |
| Gitea Actions runners | Mounted CA, `SSL_CERT_FILE` and `GIT_SSL_CAINFO`; retained `/data/.runner` registrations use the internal HTTPS address |
| Delivery workflow | `SOURCE_BASE_URL` repository variable points to the internal HTTPS address; the workflow still accepts a GHES source URL when moved |

The runner and Argo CD retain their existing credentials. TLS verification stays enabled. Search images and Nexus releases are still addressed by their immutable OCI digests.

## Reconcile an existing full lab

Run from the repository root in PowerShell, with `LAB_STATE_DIR` set to the retained `.lab` directory. Install the HTTPS ingress before changing clients. The [control runtime guide](control-runtime.md) covers publishing and applying a new digest-pinned control image; the image must contain `lab/gitea_tls.py` and the current Git URL settings.

```powershell
$env:LAB_STATE_DIR = (Resolve-Path .lab).Path
python lab/https_ingress.py install
python lab/https_ingress.py trust
python lab/control-runtime/install.py migrate-git-remotes
python lab/https_git.py migrate
kubectl --kubeconfig .lab/kubeconfig.yaml apply -f research/platform-spike/runner.yaml
kubectl --kubeconfig .lab/kubeconfig.yaml apply -f lab/delivery/bootstrap/runner.yaml
python lab/runner_https.py migrate
```

`migrate-git-remotes` changes only the three known retained control checkouts and rejects an unexpected remote. `https_git.py` updates the two vault-backed Argo CD repository URLs, the ApplicationSets and existing Applications, then waits for Synced and Healthy. `runner_https.py` changes only the saved runner address, restarts both runners and updates the delivery workflow's source URL variable. Run these commands after the related Deployments and repositories exist.

If the lab CA is replaced, run `trust` again on the workstation, restart the control Pod to remount the ConfigMap, and rerun `https_git.py migrate` so Argo CD reloads its trust. The same CA bundle supports certificate renewal without changing client URLs. The certificate generator includes Subject and Authority Key Identifiers for Python 3.13 validation.

## Current protocol inventory

| Path | Current transport | Next step |
| --- | --- | --- |
| Browser to Gitea, Argo CD, control, SigNoz and Nexus UI | HTTPS at Traefik | Validate native Apple silicon workstation trust |
| Control, Argo CD and runners to Gitea Git/API | CA-verified HTTPS | Search-spike fixture PR #6 must merge before its default-branch workflow also fetches over HTTPS |
| Host bootstrap scripts to Gitea NodePort | Loopback HTTP | Provide a reliable host DNS and CA path, then migrate the scripts |
| Runner and Kubernetes nodes to Gitea/Nexus OCI registries | HTTP with explicit local insecure-registry configuration | [OCI transport batch](plans/https-oci-transport.md) |
| Traefik to in-cluster web Services | Cluster HTTP | Keep this trusted lab hop visible in the topology; decide its Azure policy separately |
| Floci, Nexus API and OTLP gateway within the cluster | Cluster HTTP | Review with the Azure service contracts; these are separate from Git and OCI transport |

## Live check

On 28 September 2026, the control Pod was 4/4 Ready. Its authenticated Gitea smoke check passed, and all three retained Git checkouts fetched `HEAD` over HTTPS. All 28 Argo CD Applications returned to Synced and Healthy after the CA and source change. Both Gitea runners reported online with HTTPS registration addresses. A temporary delivery-source PR completed CI successfully with an HTTPS Git fetch and was closed without merging. Search-spike fixture PR #6 completed its HTTPS Git fetch and build successfully; it remains open for review so the default branch still contains the earlier HTTP fetch. The [retained evidence](research/evidence/https-git-transport-2026-09-28.md) records the run IDs and checks.

These checks prove the local Git paths. They do not establish TLS for OCI push/pull, host bootstrap scripts or Apple silicon.
