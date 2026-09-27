# Batch 7k2c: finite Job telemetry

Status: implemented locally; awaiting review. See the [measured evidence](../research/evidence/signoz-finite-jobs-2026-09-28.md). The remaining connected investigation moves to [batch 7k2d](signoz-window-coverage.md).

## Intent

Complete the local observability demonstration from a search or operation SLO breach to its trace, related log and immutable report. Start with the pinned backend, stored signals and [source-controlled dashboard](signoz-connected-investigation.md). Test the runtime path rather than assuming API acceptance means a useful investigation.

## Constraints

- Keep OTel SDKs, OTLP meanings and the Search API contract vendor-neutral so New Relic remains a configuration and dashboard migration. Keep Blob reports and human review authoritative.
- Preserve Blob-only egress for independent producer/evaluator Jobs. Their completion correlation must use safe structured stdout through the existing scoped log agent, with no duplicate log route or secret-bearing fields.
- Keep normal, warm-up, peak, stress and probe populations separate. No telemetry gap may produce a green verdict. Use a seven-day search window and the 100-request minimum only when collection coverage is known.
- Work on a review branch and open a stacked PR. Do not merge main before user acceptance.

## Acceptance criteria

1. Build and publish digest-pinned amd64/arm64 producer and evaluator images containing the shared safe event contract.
2. Run both finite Jobs under their existing Blob-only egress policies; retain the original final-line result protocol.
3. Verify the producer manifest hash and evaluator report hash in SigNoz after the Jobs are removed.
4. Update the runbook, roadmap and evidence. Commit the batch to a review branch; leave `main` untouched.

## Where to find more information

- [Dashboard evidence](../research/evidence/signoz-dashboard-2026-09-28.md), [backend guide](../observability-backend.md) and [parent observability plan](otel-observability.md)
- Independent Jobs in `data/` and `evaluation/`; delivery verification in `lab/delivery_promote.py`; Gatling runner in `lab/run_gatling_job.py`
- [SigNoz trace/log correlation](https://signoz.io/docs/traces-management/guides/correlate-traces-and-logs/) and [New Relic OTLP guidance](https://docs.newrelic.com/docs/opentelemetry/best-practices/opentelemetry-otlp/)
