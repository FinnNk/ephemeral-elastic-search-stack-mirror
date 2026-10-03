# Local OIDC sign-in

## Intent

Provide one local identity provider for named human access to Kubernetes through
Headlamp and to Argo CD. Keep machine credentials and recovery access separate.

## Constraints

- Keep the search/evaluation topology and existing CI credentials unchanged.
- Preserve the server container and its volumes; restart only that container
  when adding API-server authentication. Never recreate the GPU worker.
- Use native OIDC, verified HTTPS and group-based permissions.
- Keep passwords and client secrets out of Git and normal command output.
- Use Key Vault delivery for runtime/client secrets; retain bootstrap credentials
  only in ignored operator state. Do not reset existing users on reinstall.

## Acceptance

| Check | Required result |
| --- | --- |
| Identity service | Persistent realm, named owner and reader accounts; pinned amd64/arm64 images |
| Headlamp | Browser OIDC callback succeeds; user token is accepted by Kubernetes |
| Permissions | Admin can administer; reader can view but cannot mutate or read Secrets |
| Argo CD | Native OIDC login; groups map to admin/read-only roles |
| Boundaries | Wrong-audience and unauthorised identities are rejected; privileged shared Headlamp token remains disabled |
| Recovery | Existing operator kubeconfig and local Argo admin remain usable |
| Repeat install | Realm/client identities persist and server changes are idempotent |
| Documentation | Setup, first login, recovery and remaining integrations agree with measured behaviour |

## Sources

- `lab/install_headlamp.py`, `lab/https_ingress.py`, `lab/keyvault.py`.
- [Headlamp OIDC](https://headlamp.dev/docs/latest/installation/in-cluster/oidc/).
- [Kubernetes authentication](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#openid-connect-tokens).
- [Keycloak containers](https://www.keycloak.org/server/containers).
- [Argo CD user management](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/).

The next batch connects existing Gitea accounts and the control UI. MLflow and
edition-limited services require separate integration decisions.

## Result

Implemented and deployed; local login, permission, persistence and repeat-install
checks passed. [Evidence](../research/evidence/local-oidc.md) records their scope.
The branch is ready for review; native and enterprise checks remain untested.
