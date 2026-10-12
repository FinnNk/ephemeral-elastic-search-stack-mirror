# Show comparison choices beside promotion actions

The Promotion controls panel must show what its action will compare before the
user starts a check. A separate list elsewhere on the release page does not
provide that context at the point of use.

Each action now lists its candidate build, selected variants, declared intents
and configuration hashes against the current target's default baseline build,
variant and hash. Stage selection changes the baseline. Rollback uses the retained
release as candidate; preparation explains that the comparison follows later.
Missing information is explicit. The coordinator still checks these identities
and the source-controlled intents before execution.

The screenshot also exposed disabled controls for a successful source build.
The dashboard projection omitted the build's `conclusion`, although the control
eligibility check used that field. The projection now carries the actual
provider conclusion; it does not treat unknown or failed builds as successful.
Observed baseline build numbers come from matching verified deployment receipts.

## Verification

All 44 selected unit fixtures passed, including the real dashboard-to-controls
handoff for a successful build, target-specific baselines and mixed intents.
The isolated Chrome fixture confirms the comparison inside Promotion controls,
stage switching, intent-free submission, approval selection, retries, keyboard
operation and mobile layout without page errors. Comparison groups constrain
their tables to the column so a narrow screen scrolls the table rather than
widening the page.

The earlier activation is complete: PR #181's runtime image is
`45835bb4feb483f8f96e6adeb6cfc4a509ea51c28bf71f7968d912caff213eca`.
Build 184's declared default is `ranker-a` with `ranking-change`. Delivery-source
PR #38 passed all gates after its required 1.1.2 patch bump, and its trusted client
digest matches merged main. These are earlier runtime observations, not evidence
that this comparison-panel update has been deployed.

## Next detailed plan

1. Review and accept the panel and build-status correction.
2. Publish and install the accepted control image once delivery work is idle.
3. Check build 184's live panel against current Integration and Staging baselines,
   then resume the walkthrough. Verify the current stage's eligibility reason;
   do not bypass review or promotion gates.
