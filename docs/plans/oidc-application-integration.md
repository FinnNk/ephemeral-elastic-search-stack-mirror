# Extend named sign-in to lab applications

## Intent

Extend the local OIDC provider to existing Gitea accounts and the control UI.
Keep permissions, recorded human decisions and machine credentials explicit.
This is the next identity batch; it does not replace the label-quality work.

## Constraints

- Link existing Gitea users deliberately; never create a second owner account
  or change repository ownership through automatic email matching.
- Use native OIDC where supported. Use a maintained OIDC proxy only where it
  provides the required identity and permission contract.
- Validate issuer, audience and signatures. Strip untrusted identity headers
  at the ingress before forwarding authenticated claims.
- Keep CI tokens, service credentials and emergency operator access separate.
- Preserve recorded approvals; bind new decisions to the authenticated subject.
- Keep the current reference contracts clean; add no legacy-data adapters.

## Acceptance criteria

| Behaviour | Required evidence |
| --- | --- |
| Gitea account linking | Existing owner signs in through OIDC; repository ownership and permissions unchanged |
| Control UI | Named human sign-in; anonymous requests denied where authentication is required |
| Decisions | Recorded override identifies the authenticated subject; cannot impersonate another user through submitted fields |
| Permissions | Reader can view evidence but cannot create, delete, promote or approve |
| Recovery | Local emergency access documented and demonstrated |
| Automation | Existing source builds, deployments and judgements remain operational |
| Documentation | Current guides and identity diagrams match implemented boundaries |

Assess MLflow access separately. Nexus Community and SigNoz Community do not
provide the same native OIDC integration as their paid editions. Compare a
proxy's access boundary with each product's own roles before adopting it; a
proxy login alone does not establish application-level authorisation.

## More information

- [Current identity access](../oidc-access.md) and [evidence](../research/evidence/local-oidc.md).
- `lab/install_oidc.py`, `lab/gitea.py`, `lab/control_api.py` and the current
  control-session/approval implementation.
- [Gitea authentication](https://docs.gitea.com/administration/authentication/).
- [SigNoz SSO](https://signoz.io/docs/manage/administrator-guide/sso/overview/).
- [Nexus OIDC](https://help.sonatype.com/en/openid-connect.html).
