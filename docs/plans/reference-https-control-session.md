# Canonical HTTPS control sessions

## Intent

Make the installed control service's redirects and session cookies match its
published HTTPS address. This closes the remaining runtime finding from the
documentation review.

## Constraints

- Keep the Kubernetes control service, ingress and Gitea identity contract.
- Use the existing lab CA and verified HTTPS clients; do not disable verification.
- Set `Secure` cookies when the configured public origin is HTTPS. Preserve the
  deliberate loopback HTTP development route without trusting arbitrary proxy headers.
- Do not rewrite historical transport evidence or add old-configuration adapters.

## Work and acceptance

| Work | Acceptance criterion |
| --- | --- |
| Inspect public-origin and canonical-host configuration | Installed HTTPS requests stay on the canonical HTTPS origin |
| Bind cookie security to the configured public origin | Login through ingress produces a `Secure`, `HttpOnly`, `SameSite` session cookie |
| Check identity, logout and rejected hosts | Normal login/logout works; an untrusted Host cannot redirect or establish a session |
| Exercise the loopback developer route | Its documented access works without weakening ingress settings |
| Update guides and retain live evidence | Commands, endpoint and cookie claims agree with the tested deployment |

Submit a separate PR after tests and a disposable/live routing check. No merge
or runtime change is included in the filter-support batch.

## Sources

- [HTTPS ingress](../https-ingress.md) and [control operation](../control-runtime.md).
- [Documentation findings](documentation-authorship.md).
- `lab/control_api.py`, `lab/control_identity.py`, control deployment and ingress configuration.
