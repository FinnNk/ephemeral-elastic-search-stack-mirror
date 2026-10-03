# Headlamp KServe plugin

## Intent and constraints

Install the supplied built plugin in the existing Headlamp Pod. Preserve OIDC,
Kubernetes permissions and the read-only container filesystem. Retain the
archive and checksum so installations do not depend on the workstation folder.

## Acceptance and observed results

| Check | Result |
| --- | --- |
| Headlamp rollout and HTTPS | Passed locally |
| Plugin discovery and served files | All three files match the supplied archive exactly |
| Headlamp and OIDC reconciliation | Plugin retained; OIDC client configuration preserved |
| Permissions | No RBAC grants added; shared service-account login remains disabled |
| KServe resources | One InferenceService exists in the lab |
| Rendered pages | Not checked: browser automation could not start; refresh Headlamp and open KServe manually |

The runtime receipt is retained at `.lab/evidence/headlamp-kserve-plugin.json`.
See [Headlamp access](../headlamp.md) and `lab/headlamp_plugin.py` for installation.
The next detailed batch remains [Gitea and control UI OIDC](oidc-application-integration.md).
