# Relevance change lifecycle diagram

## Intent and constraints

Show the implemented developer workflow from an API change to simulated
production. Use the existing Archify gallery; developers use Actions and PRs.
Separate the PR-head merge gate from the build of the merged commit.

## Acceptance and result

- Include the frozen baseline/variant APIs, pooled missing labels and shared
  judgement selection. Compatible runtimes and indexes may be reused.
- Show current-head gating, iteration and eligible recorded exceptions.
- Show unchanged release promotion, reviewed Git state, Argo CD deployment,
  verification and the production normal/peak Gatling gate.
- Link the diagram from the gallery and delivery guide.
- Pass showcase rendering and light/dark browser checks at all four supported
  desktop sizes; inspect the resulting diagram visually. Vertical scrolling
  is intentional: eleven chronological stages have only downward connectors.

The generated receipts bind the JSON source and HTML output. Browser checks
passed with intentional vertical scrolling; labels and the full timeline were
inspected at 1440×900. Stage order is not proportional to elapsed time. These are
diagram checks, not a fresh release or deployment rehearsal.

## Next batch

Review this diagram, then continue the [sneakers walkthrough](sneakers-demo-walkthrough.md)
through the source gate and promotion workflow. Use [delivery](../delivery.md)
and [variant evaluation](../variant-evaluation.md) for executable steps and metric meaning.
