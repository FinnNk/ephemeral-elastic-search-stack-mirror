# Complete the Actions developer path and reconcile documentation

## Intent

Run routine Search API development and delivery through CI/CD, with no developer
kubeconfig. Make current guides agree with that workflow and the writing guidance.

## Constraints

- Preserve exact-commit evidence, separate deployment approval and immutable inputs.
- Use existing coordinator operations; expose no arbitrary commands or file paths.
- Keep Gatling responsible for load tests and the full production promotion gate.
- Preserve historical observations and imported attribution. Plans record their
  original stage; the roadmap owns current status.
- Human acceptance precedes installation. Do not claim pending code is live.

## Acceptance

| Area | Required result |
| --- | --- |
| Developer path | Actions submits previews, comparisons, promotion and rollback proposals, approved merges, verification and signed-evidence rechecks |
| Approval | Remote merge calls the existing protected merge path; missing approval cannot create a source status or deploy |
| Rollback | Fresh current-to-previous evaluation precedes the proposal; production uses the full load gate |
| Docs | Developer guides contain usable UI steps; cluster setup and recovery remain operator procedures |
| Consistency | Source templates, design, identity reference, plans and navigation agree on contracts and availability |
| Review | Record semantic findings separately from structural/link checks and live execution |

## Next batch

After acceptance, follow [activation](walkthrough-activation.md). Merge the updated
source workflow PR, install the matching control image, refresh
the exact client pin and rehearse the complete developer path through Actions.
Retain operation URLs, review identities and deployment verification. Do not
reuse the earlier CLI walkthrough as evidence for the new remote path.

## References

- [Delivery guide](../delivery.md)
- [Remote delivery contract](../remote-delivery.md)
- [Documentation review](../reviews/documentation-2026-10-05.md)
- [Technical authorship](../technical-authorship.md)
- `lab/delivery_operations.py`, `lab/delivery/ci/lab_delivery.py`
- `lab/delivery/workflows/delivery.yaml`, `lab/delivery_promote.py`
