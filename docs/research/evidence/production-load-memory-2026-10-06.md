# Production load and memory investigation

The full production gate completed, but its baseline failed. A short diagnostic
with more memory avoided request failures and restarts; both sides still missed
the peak latency budget. The production route remains on build 108.

## Full gate

Operation `ebc001cea66a2fb0fb5949f3bf9b15fd` compared builds 108 and 158 against
the same frozen index and traffic. Each side ran for 21 planned minutes, including
15 minutes at 20 requests/s. Both arrival ledgers were valid.

| Peak phase | Baseline 108 | Candidate 158 | Budget |
| --- | ---: | ---: | ---: |
| Failed requests | 5.33% | 0% | <1% |
| p95 | 34,601 ms | 119 ms | 400 ms |
| p99 | 55,603 ms | 324 ms | 800 ms |

The baseline container was OOM-killed at 15:36:49 UTC with a 96 MiB limit.
Its runner recorded 670 premature closes, 258 request timeouts, 31 refused
connections and one connection timeout. Historical Prometheus samples reached
86.9 MiB working set before the kill. Around that failure, about 95% of CPU
quota periods were throttled. A brief source comparison found identical
telemetry and dependency files; the API change was the sneakers rewrite and
docstrings. This review does not establish the underlying allocation cause.

## Short diagnostic

The user authorised a memory increase. Separate commits in delivery-state
preview branches changed only the API memory limit to 192 MiB. CPU stayed at
250m. Argo deployed and verified both previews. Active production and its
prepared candidate configuration were unchanged.

Gatling replayed the same diagnostic workload on each side: 30 seconds warm-up,
30 seconds normal load and 120 seconds peak load, using source seconds 1320–1439
for the peak. Each run made 3,000 requests. The diagnostic has a separate profile,
recipe and workload identity and cannot satisfy the production gate.

| Diagnostic peak | Baseline 108 | Candidate 158 |
| --- | ---: | ---: |
| Requests | 2,400 | 2,400 |
| Failed requests | 0 | 0 |
| p95 | 5,432 ms | 2,081 ms |
| p99 | 10,053 ms | 4,092 ms |

Both arrival ledgers were valid and both new Pods had zero restarts. Sampled
baseline working set peaked at about 38.2 MiB in the inspected interval.
Both previews landed on the server node after rollout; the original baseline
had run on the observability node. Fresh processes, node placement and shorter
traffic exposure prevent attributing the difference solely to memory.

## Conclusion and next step

Do not repeat the 42-minute gate expecting memory alone to resolve the problem.
The short screen still exceeds peak latency limits on both sides. CPU throttling,
query mix and shared-node contention merit the next controlled check, with equal
resources and placement for both APIs. Do not change gate thresholds on the basis
of this screen. A permanent resource default needs a reviewed change and the full
gate must pass before the final relevance comparison and route switch.

Prometheus already holds CPU and memory history. OpenCost can add allocation
and efficiency views, but its installation is a separate proposed batch.

The [retained evidence](production-load-memory-2026-10-06.json) includes full-run
references, diagnostic reports and exact preview resource commits. Native Gatling
reports remain content-addressed in the lab's run store.
