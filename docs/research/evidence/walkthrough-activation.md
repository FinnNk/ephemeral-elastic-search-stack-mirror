# Developer delivery activation — 5 October 2026

The accepted coordinator and source workflows were installed and exercised in
the local lab. Source comparisons and manual Actions submissions used the
public HTTPS control API. Operator installation used cluster access.

## Runtime and retained state

| Input | Observed identity |
| --- | --- |
| Accepted lab main | `4c9f8747d3aae6f53dbdbf61ae3caeff36269348` |
| Accepted source main / release build | `0e0d29f43a821d92d472e755b13dc3fe59f389fc` / 113 |
| Installed multi-platform control image | `nexus.localhost:18185/lab-control@sha256:7e1c96c074c1080a7fbb23172df58cd605889670a34e81f5ba27cd121ceff629` |
| Preserved control Deployment UID | `8e13c499-37b2-484b-8bee-5cff05afb246` |
| Preserved bound state PVC UID | `8d230ba2-7b24-4735-b69d-6674d887a5df` |
| Protected remote client SHA-256 | `253b5bd45a4a4d6e886dfa0e68e4a7f2e4c57c6c44bb4eb7538fa1db7941aae5` |

The running API reports the installed image digest as its telemetry version.
Source Actions retains its scoped delivery credential; evaluator and reviewer
signing keys are mounted into the coordinator through External Secrets instead.

## Fresh source comparisons

Disposable [source PR 28](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/28)
first selected four report-only queries, then added a required sparse set. Its
search code and standard ranking settings were unchanged.

| Case | Exact source head | Result |
| --- | --- | --- |
| Report-only trainers queries | `87fc5bb714e6c788fba24acd004bdec3e9450b1a` | Automatic comparison passed; 1,000 standard and four extra query cases |
| Required sparse published references | `a09f369f261e168d91cfc9ad949af47ec9be0271` | Standard suite passed; required extra set blocked the merge gate |

The standard suite returned 9,915 results per variant, with 8,053 judged:
**81.2204% demo coverage**. Both variants scored nDCG@10 0.702599. RBO@10
with p=0.9 and Jaccard@10 were 1.0. These unchanged rankings validate the
comparison mechanics, not improved relevance or model accuracy.

The four report-only queries had no reference labels. Their relevance scores
remain unavailable; they contribute similarity results to the combined summary,
which reports 1,004 query cases and 1,000 cases with relevance scores. Combined
metrics do not determine the gate.

The required set retained one original published ESCI Complement label for
`t28 turbo`, product `B00MQ6Y0I4`. One of ten returned results was judged,
so its **10% coverage** blocked the gate independently of the standard suite's
demo allowance. Actions gate-check retained that blocked verdict.

Both standard captures used eight workers and made 1,000 fresh requests to
each API. Capture durations were 30.907 and 30.354 seconds, without retries or
terminal failures. The second extra-query capture recorded five transient
failures and the sparse set recorded one; pacing and bounded retries recovered
all six. This is a local recovery observation, not a failure-rate guarantee.

| Retained object | SHA-256 |
| --- | --- |
| Report-only report | `9ac7b5f1cb9a92b9596ac354e6f8cc47d5d5a2d60225f9954764699bdcaf6be9` |
| Report-only standard observation | `75ccad7feeb520f3edaae2703a86620828b1962a339b2d65696f57728670abcc` |
| Required-set standard observation | `38ea2179d88683805dd42bddbd2860e1898e799ae718ae49622a003fd43e90b0` |
| Integration promotion evidence | `40dcc6b14408642479e460c64d78d2b7f686992c4e33bed65bb028d19820e4a7` |
| Staging rollback evidence | `b1525c8d28b395d643b7733c02d1d6f4777e019304aed686b83f1bb6c880c36d` |

Reports and observations remain in frozen storage. Signed source reports are
also retained in Nexus under `variant-gates/<source-head>/`. PR comments contain
public baseline/candidate storefronts, expiry, progress and report links.

## Actions and access checks

| Check | Observed result |
| --- | --- |
| Manual preview, Actions run 114 | Submission succeeded on retry; queued operation completed and produced a ready storefront |
| Verify production, run 119 | Current desired state and serving fingerprint verified |
| Recheck already merged deployment PR 16, run 120 | Existing approved deployment verified; no repeated merge |
| Recheck source gate, run 127 | Frozen signed evidence checked; required-set verdict remained blocked |
| Propose integration, run 128 | Fresh evaluation created desired-state PR 17 |
| Propose staging rollback, run 129 | Fresh current-to-retained evaluation created desired-state PR 18 |
| Merge unapproved PR 17, run 130 | Submission succeeded; the coordinator rejected the merge and main stayed unchanged |
| Replay preview submission `manual-114` | Same completed operation returned |
| Change that submission's payload | HTTP 400; no second operation |
| Use workflow identity for environment administration | HTTP 403 |

Production remained at build 108, Git revision
`c44b026c407b0bf91912aa55ff8e0f30700215ec`, fingerprint
`7d99e451865ef138e725c35391b0139c1ac26721b9179d8837cabdee32732031`.
The disposable source PR 28 and desired-state PRs 17–18 were closed without
merging after the checks; their evidence and PR history remain available.

## Setup findings and limits

- The proxy rejected the initial workflow token because its managed service
  account lacked a verified email claim. Setup now reconciles a reserved machine
  address, `delivery-actions@relevance.invalid`, and its verified claim. Audience,
  issuer, signature and restricted client/group checks remain enforced.
- The upgrade installer initially left telemetry describing the previous image.
  It now pins the running digest in each container's environment and ConfigMap.
- Helm's generated Secret and persisted INI file retained the obsolete webhook
  allowlist after its chart values were removed. Reconciliation removes those
  entries, checks the matching supported value and preserves other settings.
  The effective file now contains only `[security].ALLOWED_HOST_LIST`. Gitea
  remains **1.27.0**.
- The Gitea restart caused HTTP 503 before the required-set comparison captured
  results. Its failed operation was retained. A new submission after recovery
  completed the fresh capture; retrying the old key does not replay a failure.

The focused identity, delivery operation, source comparison, query-set and
variant-gate suite passed **54 tests**, with no failures or skipped tests.
The three corrected bootstrap scripts passed lint and syntax checks. Current
developer instructions, the roadmap and next user-check plan were reviewed
against these observations and the technical authorship guidance.

The image manifest covers amd64 and arm64; execution here used amd64. Native
Apple silicon, GHES and Azure were not exercised. Workstation device sign-in
with the user's own account and a fresh human-approved Actions deployment are
the next walkthrough checks. No model qualification, GPU survey, new threshold
exception or human deployment approval was introduced.

See the [next user check](../../plans/remote-delivery-user-check.md) and
[current roadmap](../../plans/roadmap.md).
