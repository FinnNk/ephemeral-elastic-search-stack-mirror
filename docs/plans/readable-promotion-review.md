# Make promotion evidence suitable for human review

The current overview identifies configurations mainly by hashes and puts useful
measurements behind separate links. Lead with the decision a reviewer needs to
make: which target build is being replaced, which build and behaviour replace it,
what changed in search quality/results, how well results are labelled and whether
the measured performance budgets passed.

## Scope

- Link baseline and candidate builds and show recorded versions, variants,
  catalogue, completion time and actual field weights. Label absent metadata
  honestly instead of resolving it from a newer deployment.
- Summarise each variant's frozen relevance, result-regression and performance
  reports on the overview. Keep detailed reports and JSON available. Hashes remain
  in expandable evidence details. Missing summaries are not presented as passing.
- Give promotion PRs readable titles, a release comparison, plain-language
  intents, configuration descriptions, source/build/dashboard links and approval
  instructions. Keep exact identities in a details section.
- Indent newly written desired-state proposal, target, slot and history JSON.
  Leave canonical fingerprint inputs and immutable artefacts unchanged.

## Verification and activation

All 36 selected description, gate and production fixtures passed in the locked
Windows uv environment. Formatting tests parse the new JSON and confirm identical
canonical hashes. The proposal fixture exercises the generated title/body and
written JSON. Chrome fixtures cover overview measurements and links, hidden
hashes, unavailable data, existing report types and mobile overflow. Inspect the
synthetic desktop/mobile screenshots; these do not establish live gate results.

After acceptance, activate the report UI and update open desired-state PR #25
before approval. Preserve any human body edits. Formatting its existing JSON
requires a new commit and fresh exact-head validation; keep semantic values and
frozen evidence unchanged. Record both old and new heads in the recovery operation.
Do not merge or deploy the proposal. Then return to the review walkthrough.
