# Lab identities and sessions

Sign in to the [control UI](https://control.localhost:34443/) with your lab
identity. Keycloak authenticates the user; the control API verifies the signed
token and applies its group permissions.

## Access rules

| Identity | Control access |
| --- | --- |
| `lab-readers` | View environments, search and inspect retained reports |
| `lab-admins` | Manage environments and comparisons; submit reviewed delivery operations |
| Neither group | Access denied |
| Actions delivery | Verified `lab-delivery-actions` OIDC client; delivery operations only |

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
role in another. The periodic watcher does not approve or automatically merge promotion PRs.
A submitted `merge-reviewed` operation uses the same coordinator to check the
existing separate approval, merge and verify deployment. The Actions credential
cannot manufacture an approval or administer other control resources.

A bounded relevance decision records the named user’s OIDC issuer and subject,
the exact comparison and its reason. The resulting desired-state PR retains
the decision in Git and requires the existing review checks. Signing in or
submitting a decision does not grant approval of the resulting PR. See
[recorded relevance exceptions](relevance-gate.md) for the bounds and workflow.

See [OIDC access](oidc-access.md), [control operations](control-runtime.md) and
[measured control access](research/evidence/control-oidc.md).
