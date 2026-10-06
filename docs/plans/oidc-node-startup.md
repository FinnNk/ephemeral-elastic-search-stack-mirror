# Keep cluster sign-in working after node restarts

## Intent and constraints

Restore the API server's identity hostname before Kubernetes starts. Keep the
existing issuer, TLS verification, group permissions, accounts and cluster data.
Use k3d's existing startup hooks; do not add a host watcher or another service.

## Acceptance

| Check | Required result |
| --- | --- |
| Repair an existing node | Mapping is applied immediately without restarting Kubernetes |
| Repeat the repair | Exactly one owned mapping; Docker's other hosts entries preserved |
| Validate Linux files | Hook and mapping use LF line endings, including when installed from Windows |
| Restart the real node | Hook runs before k3s; the identity mapping survives Docker regenerating hosts |
| Fresh authenticated callback | Headlamp can list namespaces after restart; reader access to Secrets remains denied |
| Document browser recovery | Start login from Headlamp's Sign In button and keep the original window open |

The hook is copied into the existing container and survives container and Docker
restarts. Recreating the container requires installation again. Recreating the
OIDC edge Service with a new IP requires the focused repair command.

## Evidence

See [restart verification](../research/evidence/oidc-node-startup.json) for the
node identity, mapping, restart and callback checks. This is a local restart
rehearsal, not a second Windows reboot or a test of container recreation.

## Next batch

Review this repair and the relevance lifecycle diagram, then resume the
[sneakers walkthrough](sneakers-demo-walkthrough.md).

## Further information

- [Sign-in and recovery](../oidc-access.md#repair-api-server-identity-resolution).
- Installer: `lab/install_oidc.py`, `server_resolution` and `server_configuration`.
- Startup hook: `lab/oidc-node-startup.sh`.
- Callback verifier: `lab/verify_oidc.py`.
