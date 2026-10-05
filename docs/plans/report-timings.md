# Timings in readable comparison reports

## Intent

Help developers see how long evaluation takes and review existing performance
measurements without opening JSON.

## Constraints

- Preserve frozen reports. Retain capture execution metadata in newly generated reports.
- Operation duration includes queueing and preparation; it is not API latency.
- Capture duration includes Job scheduling and completion checks. Pacing wait is
  summed across workers, so it can exceed elapsed time.
- Functional search capture is not a performance test. Gatling owns load tests
  and the promotion performance check; PR relevance capture adds no load test.
- Leave relevance calculations, thresholds and deployment behaviour unchanged.

## Acceptance criteria

| Report | Visible measurements |
| --- | --- |
| Delivery comparison | Elapsed time since submission, including waiting |
| New standard and extra suites | Capture Job duration, worker count and recorded request/retry counts |
| New controlled comparison | Retained capture execution timing |
| Gatling comparison | Baseline/candidate workload duration, p95/p99, failures, offered rate and budgets |
| Promotion and rollback | Readable evidence report linking result preservation, relevance and Gatling |
| Deployment verification | Release identity, index, checked product count and verification/merge duration |
| Existing frozen reports | Display available measurements without inventing absent capture timing |

See [delivery](../delivery.md), `lab/delivery_results.js`, `evaluation/offline.py`,
`evaluation/query_sets.py` and `lab/control_comparison.py`.
