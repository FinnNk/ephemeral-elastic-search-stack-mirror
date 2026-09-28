# Local HTTPS Git transport check — 28 September 2026

Environment: retained Windows x64 k3d `relevance-lab` cluster, Gitea 1.27.0, Argo CD 3.5.3, act-runner 3.5.0 and Python 3.13 control image. Synthetic fixture repositories only.

| Check | Observation |
| --- | --- |
| Certificate chain | Initial leaf lacked Authority Key Identifier; Python 3.13 rejected it. The replacement CA and leaf include Subject and Authority Key Identifiers. The authenticated control smoke check then passed. |
| Control runtime | The new digest-pinned image ran 4/4 Ready. Gitea identity, Elasticsearch, Nexus and retained state checks passed. `ls-remote origin HEAD` succeeded for environment-state, delivery-state and delivery-source over HTTPS. |
| Argo CD | The two ESO-owned repository URL fields reconciled from Floci Key Vault. After repository-server trust reload and hard refresh, 28 of 28 Applications were Synced and Healthy. |
| Runners | The two saved registration addresses changed to the internal HTTPS name. Gitea reported both repository-scoped runners online. |
| Delivery CI | Temporary delivery-source PR #6 produced successful PR-head run 23. Its job log contained the internal HTTPS Git URL and no certificate error. The PR was closed and its test branch deleted without merging. |
| Search-spike CI | Fixture PR #6 produced successful PR-head run 25 with the internal HTTPS Git URL in the job log and no certificate error. The PR remains open for review. |
| Browser ingress | All five host names passed SNI and CA-validated HTTP responses after the certificate replacement. |

The checks establish local Git/API transport and reconciliation. Search-spike `main` still contains the earlier HTTP workflow until fixture PR #6 is accepted. OCI push/pull, host bootstrap Git/API, browser drill-through and native Apple silicon trust were not checked in this batch.
