# Bind gate decisions to lab identities

## Intent

Record who authorised an evaluation exception using the OIDC issuer and
immutable subject. Keep the display name for people reading the report.

## Constraints

- Use the existing Keycloak provider and standard device authorisation for the
  operator CLI; do not collect a provider password in the lab application.
- Verify signed tokens, issuer, audience, expiry and administrator group before
  signing a decision. Submitted reviewer fields cannot select the identity.
- Retain report, policy, source revision, selected variant and substantive reason
  in the signed receipt. Keep HMAC keys in Key Vault.
- Update the current receipt contract and trusted checker together. Add no
  compatibility adapters; retain historical evidence as historical evidence.
- Test with explicitly synthetic decisions. Do not issue a real coverage
  exception or approve a release during authentication verification.

## Acceptance criteria

| Behaviour | Required evidence |
| --- | --- |
| Named decision | Receipt contains verified issuer, subject and display name |
| Permissions | Reader and unassigned identities cannot sign an exception |
| Binding | Renamed display user keeps subject identity; submitted name cannot impersonate |
| Integrity | Wrong source, report, policy, variant or modified identity invalidates the receipt |
| CI | Matching trusted checker accepts only the current contract and intended synthetic exception |
| Recovery | Operator service credentials and stored reports remain intact |
| Documentation | CLI instructions, contracts, identity diagram and roadmap agree |

## Implementation and further information

- `lab/variant_gate_issue.py`: CLI authentication and key retrieval.
- `lab/variant_gate.py`: signed approval construction and verification.
- `lab/delivery`: source checker templates, qualification and publishing.
- `lab/control_oidc.py`: issuer, audience, signature and permission verification.
- [Variant evaluation](../variant-evaluation.md), [identity boundary](../identity-boundary.md)
  and [application integration](oidc-application-integration.md).

After this batch, assess MLflow access separately. Nexus and SigNoz access
boundaries require product-specific review; a proxy alone does not add roles.
