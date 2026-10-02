# Adopt measured evaluation improvements

## Intent

Shorten offline comparisons by pooling Search API → Elasticsearch connections,
the smallest qualifying change from the
[experiment plan](evaluation-throughput.md). Keep every search fresh and preserve
ordered observations, request/configuration checks and failure outcomes.

## Constraints

- Apply the predeclared 15% capture / 10% retained-report thresholds. An additional
  technique must clear them against the simpler qualifying implementation.
- Keep the default eight query workers, three bounded transient attempts and
  current Job deadlines unless their alternatives qualify independently.
- Retain verified Elasticsearch TLS, read-only identities and connected tracing.
- Keep the disconnected demo usable with Python alone; its mock backend must not
  construct an Elasticsearch client.
- Package dependencies in images. Do not install packages when a capture Job
  starts, add old-data adapters or copy research switches into normal services.
- Keep Gatling profiles and release gates unchanged. Timing results cannot exempt
  an API change from exact-commit relevance evidence.

## Work and acceptance

| Work | Acceptance criterion |
| --- | --- |
| Select the simplest qualifying transport | Six confirmation blocks satisfy the declared speed/reliability rules; rejected techniques remain in research only |
| Pool Search API → Elasticsearch connections | One verified, bounded client per API process; per-request trace headers; close connections when the server closes |
| Decide evaluator-side pooling separately | Adopt only if its incremental confirmation clears both thresholds; otherwise retain the existing capture runtime |
| Package and publish source | Source templates, deployment copy lists, Docker tests and portable CI agree; expose no experiment-mode flag |
| Test transport behaviour | Real local HTTP fixtures prove reuse, response handling and failure visibility; disconnected demo never calls the backend |
| Verify the normal Job path | Fresh complete 1,000-query captures for two and three variants preserve ordered IDs/totals, selectors and filters against the frozen experimental reference |
| Record delivery evidence | Retain source/image/worker/input hashes, normal Job timing and telemetry proof; state unrun gates explicitly |
| Submit review batches | Update roadmap and current guides, commit project and source branches, open stacked PRs; do not merge |

Evaluator-side pooling did not clear the incremental capture threshold. Keep
paired and N-way workers and their existing image unchanged. Async scheduling,
adaptive control, higher request limits and judgement concurrency remain research
options, with no normal-path switches.

## Verification boundaries

Compare the normal finite Job path on a disposable API deployment with the same
million-product index, variant settings and API CPU/memory quota used in research.
The new API deployment is a candidate, not a replacement of an accepted release.
Measure Job completion, retained observations and scoring separately. Verify new
source PR build/gate checks without inventing a human exception or substituting
mock relevance for lab evidence.

After this batch, return to [canonical HTTPS control sessions](reference-https-control-session.md).
The roadmap owns unrelated cloud, judgement and observability validation gates.

## Sources

- [Experiment harness](../../lab/experiments/evaluation-throughput/README.md).
- `lab/search-app/app.py`, its tests and image definition.
- `lab/evaluation_worker.py`, `lab/variant_capture_worker.py`, `lab/evaluation_job.py`.
- `lab/setup_delivery.py`, `lab/deploy_baseline.py`, `lab/deploy_diagnostics.py`.
- [Evaluation runbook](../evaluation-runbook.md), [delivery](../delivery.md),
  [technical authorship](../technical-authorship.md).
