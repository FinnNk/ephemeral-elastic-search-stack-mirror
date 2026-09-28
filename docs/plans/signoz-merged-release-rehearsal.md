# Merged-release SigNoz investigation rehearsal

## Intent

Complete the connected observability demonstration with an accepted, telemetry-enabled release on integration, staging and production. Keep the frozen comparison and deployment identities visible from the SLO view through traces, logs and immutable reports.

## Constraints

- Wait for the current source PR stack to be accepted and merged before building a release for protected delivery targets. Promote via the existing Gitea/Argo CD desired-state workflow; preserve the exact release and deployment fingerprints.
- Use synthetic traffic and frozen inputs. Normal-cohort SLO counts must come from actual request arrivals and unsampled SigNoz counters. Gaps and shifted buckets stay unknown until a bounded reconciliation rule is measured and tested.
- Keep the diagnostic overhead comparison on identical images and frozen data, with the existing ≤500 ms p95 arrival-drift gate. Exclude any run that misses it. Do not make a performance claim from this laptop's invalid runs.
- Keep telemetry optional for serving. Operation evidence and Blob reports remain authoritative for promotion.

## Acceptance criteria

1. Build one merged-source release with the OTLP endpoint and release/tier attributes; promote it through all three targets and verify stored search spans, logs and normal-cohort counters per target.
2. Create a slow successful API request and a failed restore and failed promotion verification in disposable environments. In the browser, navigate from the affected SigNoz budget/time/cohort to trace and related log, then to the exact frozen report or deployment reference. Record filters and a manual fallback. Keep this gate open when browser access is unavailable.
3. Show that a sampled-out or expired trace does not turn a missing signal into a good request. Continue independent request and gateway/backend probes through a complete seven-day window, or keep the verdict explicitly unknown.
4. Obtain at least one valid paired telemetry-on/off Gatling measurement on the same frozen million-product index. Report normal request counts, failed requests, p95 values, arrival drift, pair ordering and uncertainty against the provisional ≤5% hypothesis.
5. Update the guide, diagrams and roadmap with observed results; commit the batch and open review PRs without merging `main` before acceptance.

## Where to find more information

- [Connected local evidence](../research/evidence/signoz-investigation-2026-09-28.md), [backend guide](../observability-backend.md), [seven-day policy](../../lab/observability/policies/search-slo-v1.json)
- `lab/observability/export_window.py`, `lab/observability/measure_overhead.py`, `lab/delivery_promote.py`, `lab/observability/dashboard.py`
- [Investigation workflow](../diagrams/interactive/observability-investigation.html)
