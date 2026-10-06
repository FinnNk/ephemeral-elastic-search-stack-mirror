# Relevance change lifecycle diagram

## Intent and constraints

Show the implemented developer workflow from an API change to simulated
production. Use the existing Archify gallery; developers use Actions, the production release UI and PRs.
Separate the PR-head merge gate from the build of the merged commit.

## Acceptance and result

- Include the frozen baseline/variant APIs, pooled missing labels and shared
  judgement selection. Centre the capture pair around the common vertical axis.
  Compatible runtimes and indexes may be reused.
- Show current-head gating, iteration and eligible recorded exceptions.
- Show unchanged release promotion, reviewed Git state, Argo CD deployment,
  verification and an explicit gate before each promotion. Integration and
  staging use short Gatling probes; production requires normal/peak load.
- Link the diagram from the gallery and delivery guide.
- Pass showcase rendering and light/dark browser checks at all four supported
  desktop sizes; inspect the resulting diagram visually. Vertical scrolling
  is intentional: seventeen stages run downwards, with parallel capture and
  explicit pass, bounded-decision and blocked paths with clear horizontal gaps
  between the decision outcomes.

The generated receipts bind the JSON source and HTML output. Browser checks
passed with intentional vertical scrolling; labels and the full timeline were
inspected at 1440×900. Stage order is not proportional to elapsed time. These are
diagram checks, not a fresh release or deployment rehearsal.

## Timing sources and boundaries

Timings cover warm runs only: retained images, a compatible index, reused
judgements, 1,000 queries and one baseline plus one variant. These are demo estimates, not measured
percentiles for the full SDLC. Queueing and human waiting are separate.
Cold images, index creation/restoration and new model inference are outside this
timing key; additional variants need separate measurement.
Step 1 has no duration estimate.

| Stage | Diagram annotation | Basis and limits |
| --- | --- | --- |
| 2 / 8: PR / merged-source build | Target <5 min | [Cached CI target](reference-ci-cd.md#provisional-first-slice-targets); runner start to published artefacts, excluding queueing. |
| 3: Baseline and variant capture | ~1 min estimate | [Six paired captures](../research/evidence/evaluation-throughput-adoption.md) had a 45.530 s median; [one full ESCI capture and score](../research/evidence/esci-catalogue.md) took 52.032 s. Both APIs together. |
| 4: Score and report, with resolver branch | Seconds estimate | [Throughput breakdown](../research/evidence/evaluation-throughput.md#transport-confirmation) recorded 0.20 s scoring and 0.06 s retention. [Cached resolution](../research/evidence/inference-reuse/README.md) took ~5–6 s, excluding catalogue loading. No new inference is included. |
| 5 / 6 / 7: Gate, decision, merge | Seconds; human time varies | No bounded duration for review or revision. A new commit restarts comparison. |
| 9 / 11: Integration / staging gates | ~2–5 min estimate | Fresh paired functional checks, short Gatling probes and preview preparation; no measured stage percentile. |
| 10 / 12 / 13: Integration, staging, candidate preparation | Deploy ≤2 min SLO | Approved desired-state merge to Argo health and API verification; excludes review and checks. |
| 14: Production load gate | ≥42 min load + other checks | [Pinned workload](../delivery.md#promote-a-merged-release): 1 min warmup + 5 min normal + 15 min peak for each API, sequentially. |
| 15: Final production comparison | Warm ~1–2 min estimate | Planning allowance based on the paired capture and cached resolution samples above. Active API versus candidate slot, including catalogue reading and retention. New inference is additional. |
| 16: Release review | Human time varies | Review the load gate, relevance, result changes and coverage before approving the route switch. |
| 17: Route switch | Deploy ≤2 min SLO | Approved activation merge to verified active API; previous slot remains available. |

Do not sum these headings as an end-to-end promise: they mix observed samples,
estimates and SLOs, and omit queueing and unbounded human work. Model inference,
index restoration and cold startup timings will be represented separately later.

## Next batch

Review this diagram, then continue the [sneakers walkthrough](sneakers-demo-walkthrough.md)
through the source gate and promotion workflow. Use [delivery](../delivery.md)
and [variant evaluation](../variant-evaluation.md) for executable steps and metric meaning.
