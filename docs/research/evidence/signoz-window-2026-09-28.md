# Seven-day SLO window: fixture verification

Measured on 28 September 2026 with deterministic synthetic hourly buckets covering exactly seven days. This is arithmetic and coverage-contract evidence, not a live seven-day SigNoz verdict.

| Fixture | Expected result | Observed |
| --- | --- | --- |
| 168 complete hours, 1,008 fast requests, one extra retry attempt, one slow HTTP 200, one HTTP error and one expired deadline | 1,009 eligible; success bad 2; responsive bad 3; both objectives met | Passed |
| One failed collector probe or a missing hour | Coverage unverified; no `met` verdict | Passed |
| Independent ledger expects seven attempts but SigNoz counter shows six | Mismatch; no `met` verdict | Passed |
| All counters zero | `no-data` | Passed |
| One successful request with otherwise complete coverage | Low sample; `unverified` | Passed |
| Duplicate hour or negative count | Reject input | Passed |

The earlier event analyser was also corrected: `coverage_complete=True` cannot produce `met` with fewer than 100 requests. Eight observability tests passed. The companion reports observed totals as lower bounds during gaps; missing events are never counted as successes.

The current lab has no seven-day independent request ledger or collector probe covering every interval. Therefore `source_verified` cannot yet be asserted for live traffic, and the dashboard still displays per-interval trends rather than a verified seven-day verdict. The [next batch](../../plans/signoz-investigation-overhead.md) must connect the live evidence sources and then check trace/log drill-through and telemetry overhead.

This batch adds a companion calculation from the already drawn metrics path; it does not add a deployed component or change an edge in the C4 or Archify views. The diagram remains aligned with the installed signal route.
