# Check delivery from the developer workstation

Take the next accepted search change through Actions and reviewed deployments.
Use the installed remote commands; the developer needs no kubeconfig.

The previous `trainers` rewrite is already on source main. Use a fresh related
phrase, such as `gym trainers`, for the next change. Keep the deployed rewrite
and begin by checking the user's clean checkout and pulling accepted main.

## Constraints

- Complete the workstation sign-in with the user's own lab identity. Do not
  record credentials, access tokens or device codes in evidence.
- Keep separate exact-head deployment approval. A submitted workflow is not a
  successful evaluation or an approved deployment.
- Retain the standard 80% coverage requirement, the scoped demo judgement
  allowance and the full staging-to-production Gatling gate.
- Do not promote the disposable activation fixture. Preserve its failed gate
  and published reference provenance in the retained report.

## Procedure and acceptance

| Step | Expected result |
| --- | --- |
| From `delivery-source`, run `python ci/lab_delivery.py login` with the lab CA configured | The browser approves device sign-in; the workstation stores and refreshes its token |
| Submit a preview from the workstation and follow its progress URL | Ready storefront, exact source commit and expiry; no cluster command |
| Open a real source change | Fresh comparison, preview/report links and an exact-commit backend gate |
| Propose integration through **Lab delivery** | Retained evaluation and a separate desired-state PR |
| Review that PR and submit **merge-reviewed** | The approved head is merged and the deployment is verified |
| Repeat for staging and production | Correct source-target order; production requires fresh full Gatling evidence |

Use one step at a time during the walkthrough. Record UI or instruction feedback
for a review batch. Stop at a failed gate and explain its report rather than
creating an approval or changing policy to make the rehearsal pass.

## References

- [Remote commands and Actions](../remote-delivery.md)
- [Promotion procedure](../delivery.md#promote-a-merged-release)
- [Certificate and DNS setup](../preview-access.md)
- [Activation evidence](../research/evidence/walkthrough-activation.md)
