# Align log fields with dashboard drill-through

## Cause and change

The user's candidate drill-through covers 15 October 2026, 17:25–17:26 UTC.
Storage contains 43 probe logs for that environment and minute, all with trace
IDs. None has `lab.traffic_class` or the environment resource field used by the
metric filters. The resource processor reads resource attributes, but the JSON
parser places these values in log attributes.

Replace that processor with a log-context transform that copies service,
version and environment into resource attributes and adds `lab.traffic_class`.
Preserve the original fields for existing searches, trace correlation, redaction,
scope and structured-event filtering. Historical logs retain their old schema.

## Validation

The pinned Collector Contrib 0.161.0 image accepted the manifest configuration.
A CRI stdout fixture passed through its container parser, JSON parser, redaction
and transform into a debug exporter. Assertions confirmed canonical resource
fields, probe class, trace/span IDs and removal of the query attribute.
All seven existing demo observability tests passed. This is an isolated
collector check; live SigNoz ingestion and browser drill-through need verification
after acceptance and activation.

## Next action

After review and merge, apply the log-agent manifest and restart its DaemonSet.
Generate a small probe on each API and verify both log filters in SigNoz.
Do not rewrite historical logs or rerun the comparison merely to populate logs.
