# ESCI demo coverage

Measured on 4 October 2026 on the Windows lab. The human authorised reduced confidence thresholds to unblock ESCI demonstrations while independent model-quality investigation remains unfinished.

## Decision and result

| Item | Value |
| --- | --- |
| Catalogue | Full English US ESCI catalogue: 1,215,854 products; GBP lab pricing preserves numeric amounts |
| Query suite | 1,000 frozen queries; top 10 results |
| Model | `synthetic-esci-judge/4`, calibrated classifier |
| Acceptance | Exact ≥0.75; Substitute, Complement and Irrelevant ≥0.40 |
| Replay | 6,920 saved predictions; no new inference or GPU work |
| Accepted predictions | E: 2,974; S: 1,181; C: 170; I: 782 |
| Remaining abstentions | 1,813; 49 excluded specialist pairs stay excluded |
| Captured-pair coverage | **8,053 / 9,915 = 81.22%**: 2,946 published labels + 5,107 model predictions |
| Quality status | Model predictions remain unqualified and `gate_eligible: false` |
| Strict selection | Excludes the demo predictions; published coverage remains 29.71% on this recall set |

Coverage counts available labels, not correct labels. The higher Exact threshold limits additional Exact claims; it does not establish a harmful-error rate. New recall can lower coverage.

## Frozen identities

| Artefact | SHA-256 |
| --- | --- |
| Model artefact | `6a4d9dc3ff4edb2ea9c3f071fc64973724b9a90f6db8f71d5aa85102e9e6dc2f` |
| Original prediction pass | `7b97216d7ab32ffc6831a478ab64fd10c5c7908976ced3f65893de4dfa11c92e` |
| Demo acceptance policy | `115f725f9c66c867f6db65b48b6103b6ba487e4dfc5d58f0cbbec722a165cb17` |
| Replayed pass | `0892d3f498de955e7d501d5c225acfa4b2d7441033206f201e6f1f9b30a53349` |
| Frozen judgement rows | `1fdfc905cd2a58027198f40fcfa8ccf0d454f9b2229bc8bc5240cec3b0e2003d` |
| Default judgement manifest | `ee2c9c9cdc835604b74dd368381061f5c227689ea6ad736ed76c7b9fe25d4b8b` |

The snapshot contains 24,088 rows, including the entire published query-label pool. Published labels take precedence. Rows, manifest and replay pass are retained in Azure Blob Storage, emulated locally by Floci.

## Runtime and gate verification

- The million-product Judgement API imported all 6,920 replay records alongside the original pass. A new image rollout retained the source records.
- Cached records identify model **4**; the live inference fallback still identifies model **1** and abstains. No registry alias or fallback was silently changed.
- The control default selects the new hash-checked demo snapshot. Reports disclose demo use and published/model contributions.
- The protected demo gate checks exact catalogue, query suite, rubric, model, acceptance-policy hash and recorded human authorisation. Unqualified predictions cannot enter strict selection.
- The coverage requirement remains **80%**; normal ranking and result-preservation rules still apply. No business override receipt was issued.
- **68 focused tests passed**, including changed scope/model/policy/authorisation rejection, replay boundaries, source precedence, persistence and report provenance.

Fresh captures used the actual baseline and candidate images in separate Argo-managed namespaces, each with an explicit default variant. All three comparisons returned 8,053 judged pairs out of 9,915 on each side. The installed control comparison also completed all 1,000 queries with the same source counts.

| Source PR | Evidence and CI | Merge action |
| --- | --- | --- |
| #23 | Release92/1 and relevance93/2 passed; scoped verifier also passed locally | Review this policy update first |
| #20 | Fresh image capture and relevance85/2 passed under its current target | Closed as superseded by #23; branch and review history retained |
| #19 | Fresh image capture passed locally; original commit-bound low-coverage report preserved | Rebase after #23 acceptance and publish final evidence for the new commit |

CI above used the existing trusted target. The proposed scoped verifier was also checked against the same actual reports; its trusted repository pins remain unchanged until acceptance. See the [validation receipt](esci-demo-coverage.validation.json). Source PR #23 carries the protected policy/verifier update; trusted repository pins are updated only after its target files are accepted on main.

## Limits and follow-up

The acceptance thresholds are a human-authorised demo compromise, not quality qualification. No independent actual-gap human references were added. The Decider2B survey remains held for review; broader research was not restarted.

Native Apple silicon and Azure identity/storage behaviour were not exercised. Recreating empty storage requires retained prediction evidence; published ESCI alone cannot regenerate these model labels. See [snapshot retention](../../data-evaluation-contracts.md#retain-the-esci-demo-snapshot).

Use [the restore plan](../../plans/esci-qualified-defaults.md) to return to qualified-only defaults. The original published manifest and historical reports remain available.

## Accepted source integration

The subsequent [source integration](esci-demo-source-integration.md) verified the
accepted policy, updated trusted CI pins and captured fresh results for the
rebased catalogue change. Relevance run 96/2 passed; source PR #19 is merged.
The earlier measurements and CI conditions above remain their original evidence.
