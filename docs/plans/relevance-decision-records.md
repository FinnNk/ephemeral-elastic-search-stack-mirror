# Relevance decisions in Git

## Intent

Let a developer accept a bounded relevance regression without changing the evaluated source commit. Keep the reason, measured results and human approval in `delivery-state`, then issue the signed receipt used by the merge gate.

## Constraints

- The frozen report, source head, baseline, selection, build and installed policy must still match.
- Only `decision_required` variants can receive an exception. Coverage failures and regressions outside the exception bounds remain blocked, apart from the existing explicit unchanged-results coverage exception.
- A human administrator requests the decision and approves its exact PR head. An Actions identity cannot supply that human decision.
- Decision PRs change one decision file; they cannot change deployments.
- The coordinator signs receipts only after the decision is merged. Deployment reviews and the staging load gate remain separate.
- Use the existing repositories, OIDC identity and delivery coordinator. Add no data compatibility adapters.

## Acceptance criteria

1. The comparison links to an authenticated decision form showing the measured result.
2. The form creates a decision PR containing exact evidence hashes, the reason and named reviewer.
3. An approved, merged decision produces a receipt bound to its Git commit and rechecks the source gate.
4. Stale evidence, extra file changes, missing approval and machine-authored requests fail closed.
5. CLI and Actions can complete the reviewed decision without `kubectl`.
6. Focused tests cover successful processing, invalid decisions and retry after merge.
7. Guides and workflow diagrams describe the same procedure.

## References

- [Variant evaluation](../variant-evaluation.md)
- [Remote delivery](../remote-delivery.md)
- Policy: `lab/delivery/policies/variant-merge-v1.json`
- Existing gate: `lab/variant_gate.py`
- Fresh source comparisons: `lab/delivery_source_comparison.py`
- Provider and coordinator: `lab/delivery_provider.py`, `lab/delivery_operations.py`

The preceding activation batch remains under review. This implementation is stacked on it; runtime activation follows acceptance.

## Review batch

Implementation is complete in the review branch. The matching [source PR 29](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/29) updates Actions, the remote client, verifier, immutable receipt fetcher and gate guide. Runtime activation remains the [next batch](relevance-decision-activation.md).

Verification: 72 focused Python tests passed, including an actual disposable Git repository, stale-binding rejection, exact named review checks, post-merge recovery, machine rejection and durable queue behaviour. Changed Python modules passed Ruff. A headless Chrome fixture checked the decision form's measurements, exact submission and machine exclusion. Archify delivery and four browser size/theme checks passed; the 1440×900 light image was inspected.

These checks use isolated data and API fixtures. No real human exception was created, no decision was approved on the user's behalf, and the new runtime has not been installed. The current policy thresholds and production target are unchanged.
