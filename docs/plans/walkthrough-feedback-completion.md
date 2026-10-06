# Complete the walkthrough feedback

## Outcome

Use focused Actions forms and the control UI for delivery, with visible progress,
repeat-safe preparation, reviewed deployment and useful failed-gate evidence.

The abstaining v1 judge was restored on 6 October. Both judgement APIs rolled out
and reported the pinned v1 identity as ready. Stored labels, inference caches and
published demo evidence remain intact. This does not qualify model accuracy or
make missing labels available.

## Review batches

1. Accept [lab PR #138](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/pulls/138) first.
2. Review [lab PR #139](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/pulls/139),
   then [delivery-source PR #33](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/33).
   Retarget #139 from the blue–green branch to main after #138 is merged.
3. Merge accepted batches. Install the coordinator only when no delivery operation
   is running. Apply delivery-state protection with `delivery_promote.protect()`.
   Run the source Actions setup after the accepted workflows are on source main.
   Apply the accepted search and model dashboard definitions.
4. Build a new source release and use its new preview for telemetry verification.
   Keep old immutable releases unchanged.

## Acceptance

| Check | Required result |
| --- | --- |
| Duplicate preparation across tabs/refresh | One operation and preparation PR for identical observed inputs and desired-state revision |
| Staging changes while queued | Rejected before proposal creation |
| Human approval and coordinator merge | Human cannot merge directly; approved exact head deploys through coordinator |
| Queue and live logs | Visible blocker, scoped bounded messages, pause/resume |
| Gatling check | Driver counters and scoped dashboard link update; retained native report determines the gate |
| Failed performance gate | Evidence remains linked, failure names threshold or incomplete execution |
| New source telemetry | Search metrics and traces arrive with release/environment labels |
| Recalculate frozen comparison | Same scores and no judgement-service calls |

A dashboard with no samples cannot establish health. Older source releases are
not instrumented for search export; an instrumented service with no requests has
no activity. Verify the selected time window, environment and collector before
interpreting an empty panel.

The full production gate remains blocked by its retained performance evidence.
No latency budget, coverage policy or load duration is changed in this batch.
Continue the [resource investigation](production-release-walkthrough.md#production-load-recovery)
before retrying the full gate.

## OpenCost assessment

OpenCost can reuse the existing Prometheus service. Check duplicate kube-state
metric emission before installing it, as advised by the
[OpenCost Prometheus guide](https://opencost.io/docs/installation/prometheus/).
The [official Headlamp plugins repository](https://github.com/headlamp-k8s/plugins)
contains an OpenCost plugin. A separate installation batch should pin both
components and verify their compatibility with the installed Headlamp version.

For this laptop, CPU/memory usage and requests/limits are useful measurements;
monetary estimates require explicitly illustrative prices. OpenCost does not
replace Prometheus CPU throttling, memory and restart metrics in the current
performance investigation. No additional monitoring stack is required.

## Verification, 6 October

- 64 focused coordinator, HTTP, scoring, ownership and gate tests passed.
- Release controls and readable reports passed browser checks, including mobile
  layout, scoped logs and the Gatling dashboard link.
- The source application passed its 18 existing tests. Helm rendered its telemetry
  settings and collector egress rule. Seven focused/advanced workflows matched
  their templates, retained the trusted client checks and passed shell parsing.
- Gatling compiled in the pinned Maven image. A local counter probe recorded two
  completions, one failure and their latency; it sent no search traffic.
- A temporary SigNoz dashboard accepted the variable definition, rendered the
  scoped interval and sent environment-filtered queries without query errors.
  It was deleted afterwards; installed dashboards remain unchanged. This does
  not demonstrate search telemetry from the new source chart.

Activation is recorded in the [runtime evidence](walkthrough-feedback-activation.md).
Next: resume the production resource investigation and the reviewed release rehearsal.
