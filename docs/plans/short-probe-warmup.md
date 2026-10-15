# Give the short performance probe more warm-up time

## Current batch

The previous Integration attempt measured baseline p95 at 253 ms against a
250 ms limit, with only 5 seconds of warm-up and 20 measured requests. That
does not establish insufficient warm-up as the cause. The candidate was faster
in that run; shared Elasticsearch caches and run order remain possible factors.

Use 20 seconds of warm-up and 30 seconds of measurement at 2 requests/s per API.
This gives 40 warm-up and 60 measured requests, with 100 seconds of planned
traffic for a sequential pair. Driver startup and report collection add elapsed
time. Keep all latency/error budgets and the production load profile unchanged.

Add v3 recipes and retain earlier recipe files, compiled workloads and evidence.
New workload hashes identify the changed recipe. Successful warm-up responses
still do not prove latency stability.

## Possible extension: bounded adaptive warm-up

Consider a minimum and maximum warm-up duration, allowing measurement to begin
after the minimum when successive windows show stable latency and sufficient
successful requests. Record actual duration, sample counts and the reason for
transitioning. Reaching the maximum without stability should block promotion
with an explicit warm-up outcome. Stable but slow responses must still face the
ordinary performance budgets.

Illustrative values discussed were 30–120 seconds and three 10-second windows,
using median/p90 rather than noisy short-window p95. These are unvalidated design
options. The frozen arrival schedule, validity checks, live progress and retained
report would all need to represent a variable phase boundary. This extension is
recorded only; it is not part of the current implementation.

## Next action

Eight traffic/compiler and performance-gate contract tests passed using the
locked uv environment. The revised compiled probe is deterministic, has distinct
warm-up/measured schedule windows, and has a different hash from the retained
v2 recipe. No new API traffic was generated. Runtime latency improvement remains
unmeasured.

Review and merge this batch, then activate the control runtime when idle. Run a
fresh Integration check through the release UI. Preserve the earlier failed
report. If the longer probe still misses its budget, inspect request timings
and consider a separate run with the API order reversed before drawing a cause.
