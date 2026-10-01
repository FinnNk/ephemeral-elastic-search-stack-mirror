# Lab identities and sessions

Sign in to the control UI with your own local Gitea account. The control service asks Gitea to verify the credentials and uses its returned login and administrator flag to decide which environments you can manage.

## Access rules

| Identity | Control access |
| --- | --- |
| Ordinary Gitea user | Read, search, compare, renew and delete their own environments |
| Gitea administrator | Manage all environments and inspect their retained reports |
| Automation account | Acts under its own identity; it does not become the human owner |

The password is used only for the Gitea verification request. It is not written to SQLite, Git, reports or the browser response; the UI clears the password field after sign-in.

| Session behaviour | Current implementation |
| --- | --- |
| Lifetime | Random token, held in memory, expires after 12 hours |
| Cookie | Host-only, `HttpOnly`, `SameSite=Strict`, path `/`; no `Secure` flag |
| End of session | Logout, expiry or control process restart |
| Account deactivation | Not rechecked during an existing session |

## Browser and network boundary

The Kubernetes installer binds the API to `0.0.0.0` inside its Pod. A scoped NetworkPolicy permits the configured lab clients and ingress; this is not a host-loopback server. The installer sets `LAB_CONTROL_PUBLIC_URL=http://localhost:18082` and the API checks that Host header.

Use the [loopback port forward](control-runtime.md#connect-and-check) and open `http://localhost:18082/`. A different Host causes a GET redirect to the canonical HTTP address; other requests receive HTTP 421. The configured HTTPS ingress route does not change that canonical URL or add the cookie's `Secure` flag. Do not describe it as an end-to-end HTTPS control session.

The lab's remaining identity limits are canonical HTTPS routing, secure cookies, account revocation and an enterprise identity flow. Documenting these limits does not change the running configuration.

## Separate service accounts

| Service | Human and automation distinction |
| --- | --- |
| Gitea/control | Personal account for interactive use; `elastic-agent` for agent work |
| Nexus | Personal administrator, setup administrator, `lab-publisher` for CI and `lab-reader` for deployment pulls |
| Delivery review | Human release review is separate from the proposing/validating agent |
| Demonstration approvals | `lab-admin` is used only by the explicitly invoked simulation harness; those approvals are labelled simulated |

Nexus credentials are not Gitea credentials. CI receives no Nexus administrator password. The delivery watcher does not approve or merge promotion PRs. Local administrators can change protection settings; enterprise migration must apply the organisation's real identities and reviewer policy.

The [adapter](../lab/control_identity.py) returns only `{username, is_admin}` to the [control API](../lab/control_api.py). A GHES implementation should use approved OAuth/OIDC, stable subject IDs and explicit role mapping. A Gitea login name is sufficient for this lab but is not an enterprise-stable subject ID.

The [dated identity checks](research/evidence/lifecycle-measurement/README.md) demonstrate owner isolation and administrator cleanup. They do not establish personal-account sign-in or enterprise SSO.
