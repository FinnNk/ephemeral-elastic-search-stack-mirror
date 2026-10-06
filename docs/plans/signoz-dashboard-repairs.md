# SigNoz dashboard repairs

## Result

The review batch removes fixed-interval query warnings, adds search activity by
traffic class and a model-version selector, and connects coverage telemetry to
the current resolution path. It preserves both installed dashboard IDs and the
normal-only SLO policy. Installed definitions and the coordinator remain at the
accepted release until this batch is merged and activated.

## Findings

- The collector stores search and model metrics. Empty normal-traffic charts
  during browser use are expected: browser requests are unclassified, and
  comparison probes are outside the normal cohort.
- A fixed 60-second interval produces warnings over a 24-hour window. Setting
  the interval to automatic lets SigNoz choose 300 seconds without warnings.
- Ratios and mean latency are undefined when interval counter increases are
  zero. The dashboard preserves that state rather than displaying a healthy zero.
- Model outcomes and latency work. Combining historical model versions obscures
  the current abstaining judge, so the model dashboard now offers a selector.
- Coverage and shift were emitted by the older evaluator, not the current
  additional-query and final-release comparison path. The completed resolution
  pool now emits coverage and retains its query-length shift observation.

The new shift metric describes gaps sent for resolution, including cached
outcomes. It is separate from the older model-input metric because those are
different populations. Neither measures relevance accuracy or training drift.
Coverage uses labels actually present in the frozen pool and separates `gate`,
`exploratory` and `demo` selections. An empty pool emits no coverage value.

## Verification — 6 October 2026

- Twenty-two focused tests passed, including real persistent-cache reuse, coverage
  selection, empty-pool handling and harmless export failure.
- Temporary dashboards rendered all twelve search panels and nine model panels.
  Their query responses had no aggregation-interval warnings. The temporary
  dashboards were deleted afterwards.
- Ten sequential diagnostic searches against build 163's instrumented preview
  returned HTTP 200. Retained metric increases were ten eligible, ten successful
  and ten responsive requests. The temporary dashboard showed 100% for both
  ratios at the active interval and zero budget burn. This is a small functional
  sample, not SLO or Gatling acceptance.
- Selecting model version 1 showed abstentions of 100% during its observed
  activity and populated batch latency. Empty label-mix intervals are expected
  for that judge.
- An isolated `dashboard-diagnostic` exporter with model version
  `dashboard-check` sent a synthetic fixture: two labelled pairs out of eight
  and a shift value of 0.25. This checks transport and rendering, not model
  quality or a real comparison's coverage. Both values rendered in the temporary
  dashboard after ingestion; the other diagnostic model panels had no activity.
- The AMD64 coordinator image built locally, and a network-isolated container
  successfully imported the resolution module, including its new packaged drift
  dependency. No coordinator rollout or ARM64 build was performed.

## Next batch: activate and verify a real comparison

1. After acceptance, rebuild and install the coordinator by its immutable image
   digest. Keep release routes, judgement caches and published labels unchanged.
2. Apply both committed dashboard definitions to their existing IDs.
3. Trigger one new additional-query comparison through Actions. Inspect its
   frozen pool, model version and selection alongside the stored coverage gauge.
   Replaying retained scores is unsuitable: it deliberately makes no resolution
   calls.
4. Verify the normal-traffic dashboard during the next authorised Gatling run.
   Continue the existing production resource investigation with unchanged gate
   thresholds. Historical missing telemetry cannot be reconstructed.
