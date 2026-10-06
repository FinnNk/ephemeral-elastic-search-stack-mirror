# Relevance change lifecycle diagram

## Intent and constraints

Show the implemented developer workflow from an API change to simulated
production. Use the existing Archify gallery; developers use Actions and PRs.
Separate the PR-head merge gate from the build of the merged commit.

## Acceptance and result

- Include the frozen baseline/variant APIs, pooled missing labels and shared
  judgement selection. Centre the capture pair around the common vertical axis.
  Compatible runtimes and indexes may be reused.
- Show current-head gating, iteration and eligible recorded exceptions.
- Show unchanged release promotion, reviewed Git state, Argo CD deployment,
  verification and the production normal/peak Gatling gate.
- Link the diagram from the gallery and delivery guide.
- Pass showcase rendering and light/dark browser checks at all four supported
  desktop sizes; inspect the resulting diagram visually. Vertical scrolling
  is intentional: thirteen stages run downwards, with parallel capture and
  explicit pass, bounded-decision and blocked paths.

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
| 2 / 9: PR / merged-source build | Target <5 min | [Cached CI target](reference-ci-cd.md#provisional-first-slice-targets); runner start to published artefacts, excluding queueing. This is a target, not a measured build duration. |
| 3: Baseline and variant capture | ~1 min estimate | [Six paired captures](../research/evidence/evaluation-throughput-adoption.md) had a 45.530 s median on the earlier synthetic million-product catalogue. [Full ESCI capture plus scoring](../research/evidence/esci-catalogue.md) took 52.032 s in one run. Neither isolates each API's duration; the annotation covers both branches together, not a minute per side. |
| 4: Missing judgements | ~5–6 s cached replay | [Inference reuse evidence](../research/evidence/inference-reuse/README.md): local resolution of 6,920 cached predictions took 5.469–5.875 s. Replay timings exclude catalogue loading and network deployment; they are an orientation sample, not an in-cluster SLO. No new inference is included. |
| 5: Score and report | Seconds estimate | [Throughput breakdown](../research/evidence/evaluation-throughput.md#transport-confirmation) recorded 0.20 s scoring and 0.06 s retention on a synthetic-label screen. The current enriched report has no separately measured stage percentile; allow seconds and exclude human reading. |
| 6: Automated gate | Seconds estimate | Small validation and evidence checks; no dedicated stage SLO or representative timing series. Queueing is additional. |
| 7: Gate outcome | Automatic pass; decision / revision time varies | Human decisions and code revision have no bounded duration. A revision restarts the build and comparison; the diagram does not add a return arrow. |
| 8: Source merge | Seconds estimate after approval | Git operation only, excluding approval and any gate rerun. No dedicated stage SLO. |
| 10 / 11: Integration / staging | ~2–5 min evaluation estimate + review; deploy ≤2 min SLO | Planning allowance for two fresh 1,000-query comparisons, short paired Gatling probes and preview preparation. The [ESCI probe observations](../research/evidence/esci-catalogue.json) took ~43–47 s per side including runner overhead. The [deployment SLO](otel-observability.md) starts at approved desired-state merge and ends at Argo health plus API verification; it does not cover evaluation or review. |
| 12: Production load gate | ≥42 min + setup and reports | [Pinned workload](../delivery.md#promote-a-merged-release): 1 min warmup + 5 min normal + 15 min peak per API, executed sequentially. This is a scheduled minimum, not a completion estimate. Fresh correctness/relevance checks precede it in the real evaluation command. |
| 13: Production deployment | Review varies; deploy ≤2 min SLO | Same approved-merge to verified-API boundary as integration/staging. The load gate is counted at stage 12, not repeated here. |

Do not sum these headings as an end-to-end promise: they mix observed samples,
estimates and SLOs, and omit queueing and unbounded human work. Model inference,
index restoration and cold startup timings will be represented separately later.

## Next batch

Review this diagram, then continue the [sneakers walkthrough](sneakers-demo-walkthrough.md)
through the source gate and promotion workflow. Use [delivery](../delivery.md)
and [variant evaluation](../variant-evaluation.md) for executable steps and metric meaning.
