# Observability links for short evaluation runs

## Findings

The run link selected 2026-10-15 15:28:42–15:29:23 UTC, approximately 42 seconds.
The installed dashboard's principal search SLO panels filter normal traffic;
this run exported probe traffic. In the exact window, SigNoz returned one
minute-bucket activity point. A padded window returned six activity points per
traffic class. The browser sent the expected millisecond timestamps; URL units
and the variable format were verified rather than guessed.

Read-only SigNoz queries for candidate `lab-delivery-run-184-ad3fb34f` in the
padded interval returned a probe counter increase of 30, zero probe failures and
96.667% successful responses within 250 ms. Normal-traffic requests returned no
series. These are server metrics for the padded interval, not Gatling's measured
normal-phase ledger or client latency percentiles.

Baseline preview `lab-delivery-run-158-139cbacf` has no OTLP endpoint configured.
Candidate build 184 does. The baseline's immutable API release is not modified;
its absent historical telemetry cannot be recovered by widening a time range.

## Change

- Add visible probe/evaluation request, failure and responsiveness panels to the
  existing dashboard. Keep normal-traffic SLO formulas separate.
- Generate minute-aligned links with two minutes of padding on each side and an
  explicit selected environment. Invalid timestamps fall back to a recent range.
- Explain export padding, probe traffic and the scope of dashboard counts.
- Preserve Gatling evidence, gate budgets, pinned releases and telemetry sources.

## Validation

14 dashboard/SLO tests passed in the locked uv environment on Windows. The
headless Chrome operation/report fixture passed with padded times and the exact
environment selector. An isolated live browser session confirmed the existing
SigNoz frontend accepted both timestamp and variable formats. The proposed panel
queries returned retained candidate data through the live query API. The new
installed dashboard has not been changed before acceptance.

Diagnostic query responses are retained in ignored lab state under
`feedback-test-temp/signoz-probe-panels-live.json`, with exact/padded window and
browser query records alongside them. No new traffic or inference was generated.

## Merge and activate

Merge #193 first, then this batch. Publish and activate the control runtime while
idle, and apply the committed search dashboard with an administrator session.
Verify the same historical candidate window displays probe activity, with the
normal SLO panels remaining empty for that probe-only traffic. Then retry build
184's Integration checks and review the immutable performance and query reports.
