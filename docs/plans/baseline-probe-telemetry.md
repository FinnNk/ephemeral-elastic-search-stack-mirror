# Clarify traffic panels and enable legacy baseline telemetry

## Scope

Add **Successful probe requests** using the probe cohort of the existing success
counter. Label every normal-search count, percentage and budget panel explicitly
as normal traffic. Preserve the cohort filters and SLO policy.

The exact baseline image for build 158 contains the telemetry implementation and
the required OpenTelemetry SDK/exporter. Its historical chart lacks the endpoint,
release/environment attributes and collector egress. Enable those as operator
runtime wiring through the existing runtime configuration Secret and a separately
owned NetworkPolicy. Keep the image, frozen release fields, indices and stored
comparison evidence unchanged. This changes future instrumentation overhead and
requires restarting the affected API; do not do it during an evaluation.

The helper validates the selected fingerprint, rejects conflicting chart settings,
preserves credentials, checks the SDK, bounds the target namespaces and records
only public telemetry configuration in an activation receipt. Repeating it while
the settings are active does not restart the API. New release charts already
configure telemetry; this helper covers retained legacy environments.

## Validation and limits

Fourteen focused tests passed, covering success-panel filters, normal-panel labels, committed JSON,
credential preservation, idempotence, active-operation guards, conflicting chart
settings and fingerprint mismatch. No baseline configuration has been activated
in this batch. Runtime ingestion must be checked after acceptance using separated
probe requests and metric exports; readiness alone is insufficient.

## Next action

Merge #199, #200, then this batch. Activate the accepted runtime when idle and
apply the updated SigNoz dashboard. Enable telemetry for the retained build-158
baseline preview and current Integration baseline, checking their live fingerprints.
Verify both API environments export successful probe requests. Keep historical
missing telemetry explicit and retain the existing completed comparison/proposal.
