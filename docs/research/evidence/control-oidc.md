# Control UI OIDC verification

Checked on 3 October 2026 against Keycloak 26.6.4 and OAuth2 Proxy 7.15.5.
The control image was published as a manifest containing amd64 and arm64
images. Native Apple Silicon operation was not tested.

| Check | Observed result |
| --- | --- |
| Real administrator callback | Signed subject matched the disposable Keycloak user |
| Real reader callback | Signed subject matched; environment listing succeeded |
| Reader mutation | Create and delete requests returned HTTP 403 |
| Anonymous request | Redirected to the identity-provider sign-in page |
| Spoofed forwarded identity | Direct backend request returned HTTP 401 |
| Token fixtures | Expired, wrong-issuer, wrong-audience and forged tokens rejected |
| Session isolation | A local cookie did not bypass OIDC verification |
| Service credentials | Existing control smoke check passed for Gitea, Elasticsearch and Nexus |
| Deployment | Control Deployment UID and volume definitions retained; repeated reconciliation passed |

Thirteen API and signed-token tests passed. Live callback checks used disposable
accounts and a cookie-aware HTTPS client; the accounts were removed afterwards.
Aggregate results are in `.lab/oidc/control-verification.json`. No password,
token or session cookie is published.

The live control image is
`nexus.localhost:18185/lab-control@sha256:70ee751eb4744bc8302e53fd4cfcab4dba9c487a79f0b16e80aa767fde758e80`.
C4 identity and local/Azure placement diagrams were exported and inspected.
Application browser rendering remains unverified because desktop browser automation was
unavailable. These checks establish authentication and permissions; they do not
qualify label predictions or issue a gate exception.
