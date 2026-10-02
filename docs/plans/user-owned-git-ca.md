# User-owned Git OpenSSL trust

Complete for review. The Windows host is configured and its TLS checks passed.

## Intent and constraints

Allow normal HTTPS Git commands after one workstation setup. Preserve standard
trusted roots, add only the public lab CA, leave Git's installation files unchanged
and keep browser/system trust separate. Do not disable TLS verification.

## Acceptance and results

| Work | Result |
| --- | --- |
| Build a user-owned bundle | Standard roots plus the lab root, deduplicated; private keys and malformed files rejected |
| Configure Git once | Global OpenSSL backend and CA file; existing repository overrides untouched |
| Refresh trust | Recorded base path is reused; regenerating from it replaces the helper-added lab root; source bundle unchanged |
| Verify locally | Three tests passed; live Gitea Git fetch and public HTTPS passed on Windows; helper runs without site packages |
| Explain access | Workstation setup, refresh/removal, browser separation and source README updated; Linux/macOS host execution unverified |

See [workstation access](../workstation-access.md) for commands and
[local evidence](../research/evidence/user-owned-git-ca.md) for conditions.
Source README changes receive their normal documentation-only gate decision.

The next detailed implementation plan remains
[canonical HTTPS control sessions](reference-https-control-session.md).
