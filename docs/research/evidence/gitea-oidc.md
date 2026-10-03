# Native Gitea OIDC verification

Checked on 3 October 2026 against Gitea 1.27.0, chart 12.7.0 and the existing
Keycloak realm. No label-model or GPU work was interrupted.

| Behaviour | Observed result |
| --- | --- |
| Real OIDC callback | Keycloak sign-in returned to Gitea's account-linking page |
| Existing-account proof | Wrong Gitea password rejected; correct password linked the account |
| Repeat sign-in | A fresh cookie session signed in through OIDC without linking again |
| Identity | Existing Gitea user ID retained |
| Permissions | Installer adds no group-to-admin or team mapping; existing Gitea roles retained |
| Automation | Agent API requests and protected repository reads still succeed |
| TLS | Discovery and token exchange use the lab CA; no verification bypass |

`lab/verify_gitea_oidc.py` creates disposable Gitea and Keycloak identities and
removes both afterwards. Aggregate results are retained in
`.lab/oidc/gitea-verification.json`. No passwords, tokens or source data appear
in this record.

The owner confirmed successful OIDC sign-in with the existing Gitea account.
Local recovery access and machine credentials remain available. Browser
automation was unavailable; the automated callback and account-linking checks
used a cookie-aware HTTPS client and native HTML forms. The owner completed
the real browser sign-in separately.
