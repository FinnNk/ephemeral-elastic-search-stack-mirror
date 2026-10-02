# Automatic preview URL checks — 2 October 2026

Local Windows/Docker/k3d checks cover DNS, HTTPS routing and namespace cleanup.
Native workstation resolver installation remains separate from direct DNS queries.

## Observed results

| Check | Result |
| --- | --- |
| Direct DNS | Gitea resolved to `127.0.0.1` over UDP; an unused preview name resolved over TCP. Both use loopback port 53. |
| Isolated routes | Two disposable namespaces returned different marker bodies over CA-verified HTTPS, using their own wildcard hostnames. These were HTTP fixtures, not search relevance evaluations. |
| Service removal | Its Ingress disappeared and the removed URL returned 404. |
| Namespace cleanup | Both disposable namespaces were removed; namespace-owned routes were removed with them. |
| Real Search API | Integration's new HTTPS hostname returned 200 from `/health`. Transport used loopback with the real SNI and Host name; this did not exercise Windows' native DNS. |
| RBAC | The router could not create Ingress resources in `default`. The control namespace manager can bind only its explicitly named roles, including the preview writer. |
| Control | The updated amd64/arm64 image rolled out; the installed smoke check matched the cluster, reached Elasticsearch, Gitea and Nexus, and retained 154 environment and 43 comparison records. |
| Ready link | The deployed UI rendered **Open search page** with the right URL against an intercepted synthetic API fixture. The agent's live account had no visible ready environments; this fixture is not a live retained-environment demonstration. |
| Tests | 4 routing/URL tests, 7 control API tests and 18 lifecycle tests passed. PowerShell syntax parsing reported zero errors. |
| Source README | PR #17, head `2e177570c393469060df5335168d59e0d0d74037`, passed build run 68 and relevance-gate run 69. The README-only exemption applied; no new relevance measurement is claimed. |

Raw records: [routing and cleanup](automatic-preview-urls.json),
[UI check](automatic-preview-ui.json), [source checks](automatic-preview-source-checks.json).

## Corrections and limits

The first CoreDNS start failed with `exec /coredns: operation not permitted`.
A disposable run of the pinned upstream image reproduced the failure with all
capabilities dropped and succeeded when only `NET_BIND_SERVICE` was added.
The final non-root DNS container keeps that one capability, following the
[upstream Helm security configuration](https://github.com/coredns/helm/blob/master/charts/coredns/values.yaml).
The routing container keeps all capabilities dropped.

An initial lifecycle-suite run passed 17 tests and errored once because the
required host Blob Storage forward was absent. With the forward restored, all
18 passed in 6.228 seconds. This is not a timing claim about environment creation.

The installer and route reconciler are running locally. Administrator-only
Windows NRPT installation and a subsequent native DNS/Git Credential Manager
check remain outstanding. macOS/Linux resolver integration has not been run
natively. This work does not demonstrate LAN access, Azure DNS integration,
load-test performance or a changed relevance result.

Follow [preview access](../../preview-access.md) for current operation and
[the batch plan](../../plans/automatic-preview-urls.md) for acceptance criteria.
