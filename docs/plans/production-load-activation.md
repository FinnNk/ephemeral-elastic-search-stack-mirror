# Activate and measure the production load gate

Install the accepted coordinator revision and evaluate the walkthrough release
before proposing production deployment.

## Intent and constraints

- Begin after human acceptance of the [load-gate batch](production-load-gate.md).
- Publish the control image from that accepted revision and pin its digest.
- Preserve OIDC settings, the control PVC, targets and retained evidence.
- Let active operations finish before changing the control runtime.
- Use the existing ESCI index and merged-source release; do not rebuild either.
- Do not substitute the completed probe report or relax performance budgets.

## Steps and acceptance

| Step | Acceptance |
| --- | --- |
| Stage and install the accepted control image | All control containers use its digest and become ready |
| Read delivery status | Integration and staging remain verified on the walkthrough candidate; production remains on the pre-change baseline |
| Inspect installed CLI and policy | Production defaults to `production-load`; the pinned recipe matches the accepted bytes |
| Run production evaluation | Fresh result, relevance and paired 21-minute Gatling runs retain reports; every scheduled arrival completes |
| Propose deployment | Full-load evidence passes the production policy, or a failed budget is reported without proposing a passing promotion |
| Resume human walkthrough | Reviewer inspects the evidence and approves the proposal before merge and deployment verification |

At least 42 minutes of Gatling execution are required, plus setup and report
collection. These measurements demonstrate the local lab workload only.
If the laptop misses a budget, inspect phase statistics and arrival validity;
record the result before deciding whether the workload or implementation needs
adjustment.

## References

- [Delivery commands and phase budgets](../delivery.md#promote-a-merged-release)
- [Control runtime](../control-runtime.md)
- [Production gate implementation](../../lab/delivery_load_policy.py)
