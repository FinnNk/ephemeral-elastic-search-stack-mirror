# Headlamp KServe plugin

Install the supplied `0.1.0-dev.29` plugin in Headlamp. Refresh
[Headlamp](https://headlamp.localhost:34443/) and open **KServe** in the sidebar.

## Intent and constraints

- Retain the supplied archive unchanged and verify its checksum during installation.
- Mount its JavaScript, metadata and translations read-only through a ConfigMap.
- Preserve OIDC, Kubernetes permissions and the existing Headlamp deployment.
- Keep the previous installation receipt as dated evidence.

## Acceptance and observed results

Verified on the Windows lab on 4 October 2026.

| Check | Result |
| --- | --- |
| Rollout | Replacement Pod ready |
| HTTPS discovery | Lists `headlamp-kserve`; lab CA verified |
| Served assets | All three files match the supplied archive exactly |
| Deployment and OIDC | Deployment identity and unrelated Pod configuration preserved |
| Permissions | No RBAC grants added |
| Rendered pages | Not checked; refresh Headlamp and open KServe manually |

An asset request timed out after rollout. The retry verified discovery and every
file. See the [verification receipt](../research/evidence/headlamp-kserve-plugin-dev29.json).
The retained runtime copy is `.lab/evidence/headlamp-kserve-plugin-dev29.json`.

## More information and next batch

- [Headlamp access and installation](../headlamp.md)
- [Plugin package and update procedure](../../lab/headlamp-plugins/README.md)
- [Next batch: integrate the ESCI demo policy](esci-demo-integration.md)

The plugin update does not resume the held model investigation.
