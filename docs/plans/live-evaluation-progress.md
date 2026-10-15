# Live evaluation progress

## Scope

Show live evaluation phases and bounded query/batch counters on the operation
page and in its logs. Preserve capture ordering, frozen scores, label reuse,
retry policy, gate limits and finite Job cleanup/deadlines.

## Implementation

- Finite capture workers emit a small counter snapshot at most once per second,
  plus initial/final counts. Query completion is counted across all selected APIs;
  failed captures count as completed with an error. Results retain input order.
- The coordinator polls Job state and a bounded log tail every five seconds,
  forwards only validated counters and retains the latest valid sample when
  logs are temporarily unavailable. CLI calls without a live sink keep their
  existing wait behaviour. Worker helper hashes are retained with execution data.
- Preview preparation, result capture, frozen scoring, significance calculation
  and judgement resolution emit phase events. Batch replies provide real pair
  counts; pending synchronous calls do not claim finer-grained progress.
- The browser retains the latest panel across refreshes, displays the sample's
  timestamp and keeps completed/failed operation status authoritative.
- Gatling keeps its last known counters when later log samples are absent,
  showing finalisation instead of incorrectly returning to startup.
- Variant failure summaries and reports include the concrete retained reason.

## Failure observed before this change

Operation `5b47e81d97b1d4f90eb1da8df9fc7440` failed with valid, matching,
ready performance workloads. Baseline normal p95 was 253 ms against a 250 ms
limit; candidate p95 was 138 ms. Both sides had 20 measured requests and zero
failed requests. The budget failure stopped the run before additional queries.

Root evidence:
`eb1a2f3df6acc761fcce776f577f3c8f1b724666669d8cbf3046e51d4bd503e4`.
The failed evidence is preserved. This batch does not relax the limit, repeat
Gatling or start another promotion operation.

## Acceptance and activation

Review and merge this batch, then publish and activate the runtime when the
coordinator is idle. Retry **Check and propose Integration** for build 184 and
follow the new phase/counter updates. A retry is a new measured run, not an
acceptance of the previous failure. Review every retained result before approval.

## Validation

103 affected Python tests passed in the locked uv environment on Windows.
The headless Chrome report fixture passed with sampled progress, refresh
persistence, batch-wait messaging, mobile layout and precise failure text.
These are isolated fixtures, not live workload evidence. Fixtures exercise
concurrent counters, result order, bounded/private log forwarding, missing log
samples, failure/deadline handling, refresh persistence and unknown progress
while a judgement batch is pending. No live workload is run before acceptance.
