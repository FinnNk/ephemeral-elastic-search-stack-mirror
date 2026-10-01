# Developer evaluation loop

## Intent

Demonstrate the local tooling path from a Gitea pull-request revision to a pinned candidate, three comparison verdicts and an inspectable report. Reduce the functional comparison transport overhead without changing the public Search API decision surface.

## Constraints

| Area | Constraint |
| --- | --- |
| Frozen inputs | Keep the existing synthetic releases and judgements. Pin query and judgement bytes; do not generate new labels from a candidate being evaluated. |
| Interpretation | State judgement provenance, top-ten coverage and unjudged IDs. An incomplete comparison cannot pass. A score from a candidate-derived pool is labelled as a proxy. |
| Isolation | Evaluation workers have no Kubernetes API token and can reach only the selected APIs through scoped network policy. Do not weaken other namespace boundaries. |
| PR identity | Evaluate an exact open Gitea PR head SHA and its successful image digest. Ignore unrequested PRs and stale build runs. The Gitea integration remains replaceable for GHES. |
| Lifecycle | Keep retained reports after runtime removal. Clean finite Jobs after each check. Keep PR environments on their normal 72-hour lease, with on-demand removal through the control UI. |

## Acceptance criteria

- A frozen relevance report records judgement source, query and judgement hashes, coverage by side, and unjudged returned IDs without inventing labels.
- The UI lists changed and largest-loss queries, shows ordered results side by side, and offers correlated diagnostic detail when present. Raw report download remains available.
- A bounded in-cluster evaluator handles 1,000 queries through the public APIs with one Job, writes an order-stable report and cleans its resources. Compare wall time with the earlier ~10.5-minute transport path. A small suite offers a fast preflight.
- An opted-in Gitea PR revision resolves to an exact successful build, creates a candidate, runs result preservation, relevance and a short Gatling check, and records report links and verdicts on the PR. Repeated delivery is idempotent for a PR head SHA. A changed SHA is a new run.
- Demonstrate the path locally with synthetic data and record failures and timings honestly.

## More information

- [Comparison implementation](../../lab/control_comparison.py), [control UI](../../lab/control-ui.html), [Gitea source flow](../../lab/deploy_candidate.py)
- [Million-scale evidence](../research/evidence/million-scale.md)
- [Evaluation contract](../prototype-design.md#search-and-comparison)
