# Control UI OIDC and recorded decisions

## Intent

Use named OIDC identities in the control UI. Readers inspect evidence;
administrators manage environments and record permitted decisions.

## Constraints

- Use OAuth2 Proxy for browser sign-in and secure session cookies.
- Verify signed tokens inside the control API: issuer, audience, expiry and
  group membership. Ignore submitted usernames and forwarded identity headers.
- Keep the existing state PVC, frozen reports, service credentials and
  operator CLI recovery. No data compatibility adapters.
- Obtain client and cookie secrets from Key Vault through ESO.
- Keep API authentication and reader restrictions in the application; proxy
  admission alone must not grant administrator access.

## Acceptance criteria

| Behaviour | Evidence |
| --- | --- |
| Login | Real authorisation-code callback for administrator and reader |
| Tokens | Reject expired, wrong-issuer, wrong-audience and forged tokens |
| Permissions | Reader can view reports; all mutating API methods return forbidden |
| Identity | New signed decisions retain issuer, immutable subject and display name; submitted reviewer cannot impersonate another user |
| Recovery | Operator CLI still works without browser identity service |
| Deployment | Preserve control state and image digest pins; reconciliation retains proxy and OIDC configuration |
| Documentation | Guides, C4 identity view and roadmap match active access boundaries |

## Implementation and further information

- `lab/control_oidc.py` and `lab/control_api.py`: application token verification
  and permissions; validate with signed RSA token fixtures and live callbacks.
- `lab/control-runtime`: multi-platform image publication and state-preserving
  deployment. `lab/https_ingress.py` owns the public control route.
- `lab/variant_gate_issue.py` and `lab/variant_gate.py`: verify an authenticated
  subject before issuing a synthetic demonstration decision; do not issue a
  real coverage override as part of authentication testing.
- [OIDC access](../oidc-access.md), [application integration](oidc-application-integration.md),
  [OAuth2 Proxy configuration](https://oauth2-proxy.github.io/oauth2-proxy/configuration/overview/).

After this batch, assess MLflow separately. A proxy must preserve API clients
and cannot supply application roles that a product does not support.

## Status

Control sign-in and reader permissions are implemented locally. Real callbacks,
signed-token rejection, direct-header rejection and worker service credentials
passed. The existing Deployment and state volume were retained; browser
rendering remains a manual check. See [evidence](../research/evidence/control-oidc.md).

Authenticated gate decisions are a separate review batch because they change
the signed approval contract and trusted source checker. Their acceptance
criterion above remains required; see the [next plan](oidc-recorded-decisions.md).
