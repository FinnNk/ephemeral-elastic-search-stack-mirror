# Trusted gate maintenance — 3 October 2026

## Result

[Delivery-source PR #22](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/22)
passed release run 88 and relevance run 89, attempt 2/job 99. The accepted
main checker and protected pins evaluated genuine API results for the exact
candidate build. The PR did not execute its own revised checker or policy.
No protection, trusted pin or human approval was changed.

This is a tooling-only proof. It does not establish ESCI label quality or meet
the 80% coverage requirement for a search ranking change.

## Frozen benchmark

| Item | Evidence |
| --- | --- |
| Scope | Only checker, policy, selection and gate documentation changed; `app`, `chart` and `contracts` Git trees match accepted main |
| Inputs | 12 synthetic products, three queries; all 36 query/product grades fixed before capture |
| Ground truth | Explicit product-kind modelling rules; no model-generated or post-capture labels |
| Capture | Separate Argo-managed baseline and candidate APIs; exact built images and a shared immutable index |
| Results | 12 returned pairs per variant; all judged; nDCG 1.0 for both, zero changed ordered lists or total counts |
| Candidate | Source `1b8abc0830aab87bfc96ef7860135d982e1715d2`, build `88-1`, image digest `34426b0cecaa9d58c72d818098214d4d39185d3e11b7a6eaf2ab7569d1d20571` |
| Evidence | Signed exact-build report published to Nexus; existing trusted checker returned `pass` |

The original tiny pack lacked the `brand` field required by the unchanged API,
so its first capture failed. That pack and failure were preserved. A fresh pack
adds the declared `North` brand and retains the same predetermined labels.
Both APIs successfully served that replacement. The current independent
example generator and guide now use a new immutable release with that field;
six existing producer-contract tests passed.

[File hashes](gate-maintenance-benchmark.json) identify the retained ignored
receipts under `gate-maintenance-20261003`. The signed report hash is
`4e0a87c518d3461f0ff9f253b4a9f21435bca6b7a432596e51978ec177c9c2b3`;
the observation hash is
`353c6e599de95038427cc746472b3aa1c28a2a907d2041a6b16c5ca286d75d86`.
The small sample verifies CI integration; its synthetic grades do not measure
customer relevance.

## Acceptance and next step

Review and merge the maintenance PR before updating trusted pins to its
accepted main bytes. Then re-evaluate the real ESCI source build. A low-coverage
exception requires strict result preservation and a recorded human decision;
it does not qualify model labels. Source PRs #20/#21 contain overlapping checker
work; reconcile them after acceptance to preserve the new guards.
See the [next batch plan](../../plans/esci-quality-next.md).
