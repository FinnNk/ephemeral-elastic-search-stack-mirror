# Local OIDC verification

On 3 October 2026, the Windows/x64 lab completed native OIDC login through
Headlamp and Argo CD. Keycloak 26.6.4 uses a persistent PostgreSQL 17.6 database.
The [machine-readable receipt](local-oidc.json) records source hashes and results.

| Identity | Headlamp/Kubernetes | Argo CD |
| --- | --- | --- |
| Administrator | Login and namespace listing passed; may read Secrets and create ConfigMaps | Login passed; may sync applications |
| Reader | Login and listing passed; Secret reads rejected; ConfigMap creation denied | Login passed; sync denied |
| Unassigned user | Login passed; namespace and Secret access rejected; creation denied | Login passed; no visible applications; sync denied |
| Other application's token | Rejected by the Kubernetes API | Not applicable |

These checks used disposable users, actual authorisation-code callbacks,
Kubernetes permission reviews and Argo CD's permission API. They did not deploy
or sync an application. Probe users, the negative-test client and the temporary
kubeconfig were removed. Passwords and tokens are absent from the receipt.

## Reconciliation and recovery

- One server-container restart installed API-server OIDC arguments. The server
  volumes, workers and native GPU research processes were preserved.
- Repeated installation reported `server_restarted: false` and retained the same
  user and client IDs. Reinstalling Headlamp retained OIDC sign-in.
- Restarting Keycloak preserved those IDs and the subsequent login checks passed.
- The retained operator kubeconfig remained usable. Headlamp's shared privileged
  service-account mode stayed disabled; token and local Argo recovery access
  remain available.
- Database and client credentials use existing Key Vault/ESO delivery. Bootstrap
  and initial human passwords remain in ignored operator state.

Six focused tests passed: two OIDC security guards and four existing preview
routing tests. Ruff passed for the changed Python modules. Structurizr validated
nine C4 views; identity and local deployment renders were inspected.

Native Apple silicon, a real Azure/enterprise provider, human first-password
updates and integrations with the remaining applications were not tested.
Use the [access guide](../../oidc-access.md) for current instructions and the
[next identity plan](../../plans/oidc-application-integration.md) for boundaries.
