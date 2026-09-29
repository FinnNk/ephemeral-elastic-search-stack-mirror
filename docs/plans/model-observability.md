# Model observability batch

**Status:** implemented on the review branch. [Local evidence](../research/evidence/model-observability-2026-09-29.md) records the connected model trace, dashboard values and disposable Search API trace proof.

## Intent

Show the operational behaviour of the judgement model in SigNoz and preserve one W3C trace across the frozen evaluator, judgement API and KServe predictor. The dashboard must distinguish model health, judgement coverage and input-mix shift from relevance quality.

## Constraints

- Keep OTLP vendor-neutral so the same signals can flow to New Relic later.
- Do not export query text, product fields, pair IDs or artefact hashes as metric dimensions. Model version, outcomes and fixed feature names are bounded.
- Treat absent metrics as unknown. The all-abstaining model has no accuracy or output-label drift estimate.
- A telemetry outage must not change inference or evaluation results.
- Preserve frozen reports. A new evaluator version can add an input-shift field to new reports but cannot rewrite retained older reports.

## Acceptance

1. A dashboard is source-controlled, provisioned idempotently and accepts live queries for prediction outcomes, request failures, batch latency, labelled coverage, model label mix and query-length input shift.
2. A connected request shows parent/child spans from the evaluator to the judgement service and KServe predictor. The Search API and control API remain on their existing OTel path.
3. Model-version and source-profile identity is visible without unbounded metric dimensions or raw input payloads.
4. A fresh frozen comparison reports query-length Jensen–Shannon divergence against the observed frozen query mix; no model attempts give an unknown value.
5. The pinned image, 10k and 1M services, diagram and operating guide are updated. Tests and live SigNoz evidence are retained.

The current source chart and Search API image enable OTLP. Retained deployments built from older source gain tracing only when redeployed. The proof uses a disposable Pod with current source rather than changing a frozen environment in place.

## Where to look

- [Judgement resolution](../judgement-resolution.md)
- [Local SigNoz backend](../observability-backend.md)
- `judgements/telemetry.py`, `judgements/drift.py`, `lab/observability/model_dashboard.py`
