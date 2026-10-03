# Lab identities and sessions

Sign in to the [control UI](https://control.localhost:34443/) with your lab
identity. Keycloak authenticates the user; the control API verifies the signed
token and applies its group permissions.

## Access rules

| Identity | Control access |
| --- | --- |
| `lab-readers` | View environments, search and inspect retained reports |
| `lab-admins` | Create, compare, renew and delete environments |
| Neither group | Access denied |
| Automation | Existing scoped service credentials; separate from browser sign-in |

The API checks the issuer, audience, expiry, signature and group claims. It
retains the immutable subject alongside the display name in the authenticated
session response. Forwarded usernames and groups cannot grant access. Reader
searches do not extend environment leases.

## Browser sessions

| Behaviour | Implementation |
| --- | --- |
| Login | OAuth2 Proxy authorisation-code flow with PKCE and nonce verification |
| Cookie | Host-only `__Host-lab-control`; `Secure`, `HttpOnly`, `SameSite=Lax` |
| Lifetime | One hour; refreshed after five minutes of activity |
| Sign out | Clears the control cookie; the Keycloak SSO session may remain |
| Group changes | Existing tokens retain claims until renewed or expired; this is not immediate revocation |
| API | Independently verifies the ID token forwarded by the proxy |

Traefik routes the canonical HTTPS address to OAuth2 Proxy. The proxy sends
requests to the private control Service. A direct API request still needs a
valid token. The lab CA verifies discovery, signing-key access and token
exchange. Readiness probes remain available inside Kubernetes.

The operator CLI and retained administrator kubeconfig provide recovery when
the identity service is unavailable. An unconfigured standalone control process
can use local Gitea sessions; the installed OIDC API rejects those cookies.

## Separate service accounts

| Service | Human and automation distinction |
| --- | --- |
| Gitea | Linked personal account; `elastic-agent` for agent work |
| Control | Named Keycloak identity; scoped Gitea and Nexus credentials for workers |
| Nexus | Personal administrator, setup administrator, `lab-publisher` and `lab-reader` |
| Delivery review | Human release review is separate from the proposing agent |
| Demonstration approvals | Explicitly invoked simulation accounts; labelled simulated |

Gitea retains its own repository permissions after account linking. Control
permissions come from Keycloak groups. A role in one product does not grant a
role in another. The delivery watcher does not approve or merge promotion PRs.

Recorded gate exceptions still use the existing verified Gitea approval CLI.
Binding new decisions to an OIDC issuer and subject is the next integration
batch; browser access alone does not change that contract.

See [OIDC access](oidc-access.md), [control operations](control-runtime.md) and
[measured control access](research/evidence/control-oidc.md).
