# Keep fresh installation aligned with activated delivery changes

## Findings and change

Fresh images copy the current control, evaluation and judgement source. The
source seed copies current Search API instrumentation and the delivery chart;
both delivery and exploratory charts configure OTLP, release/environment resource
attributes and port 4318 egress. Standard and smaller observability profiles load
the same corrected log mapping. New environments therefore need no legacy
baseline telemetry repair.

Dashboard definitions were available only through separate manual apply commands,
and the live-check UI embedded the original Windows dashboard ID. Add one setup
command to apply both definitions and register the returned public IDs in local
and runtime state. An authenticated API exposes these links; operation pages use
them, or display an explicit setup message with a SigNoz-home fallback.
Credentials are not stored. Registration requires the operator's existing
short-lived administrator session after creating the new organisation.

## Verification and limits

All 59 focused tests passed, covering fresh source/chart telemetry, both log-agent profiles,
runtime/host registration, credential exclusion, failed registration, missing or
invalid IDs, and authenticated API access. The run included existing fresh application, observability and control API
checks. JavaScript syntax validation also passed. Documentation explains
organisation setup, dashboard registration and completed-stage resume behaviour.

No running lab configuration is changed by this batch. A complete clean Mac
installation is not repeated on the Windows host; source and fixture checks do
not establish that end-to-end result. Preserve the user's active evaluation.

## Next action

Review and merge the batch. Activate the accepted control runtime when idle,
then register this lab's dashboards with the new setup command. A fresh Mac
installation uses the same documented command with its own administrator session.
