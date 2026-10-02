# Shorter offline evaluations

## Intent

Find the simplest combination of transport, scheduling and concurrency changes
that materially shortens a complete offline evaluation on the local lab. Every
run performs fresh searches; repeated captures remain visible so non-deterministic
results cannot be hidden by observation reuse.

## Boundaries

- Use the frozen synthetic million-product catalogue and all 1,000 queries.
- Keep mappings, ranking configurations, result depth and filter semantics fixed.
  Test two and three variants, including a default selection.
- Do not reuse search observations between runs, modes or repetitions. Reuse of
  connections and the engine's normal caches is allowed and recorded.
- Keep load profiles, throughput capacity claims and NFR verdicts in Gatling.
  These experiments measure evaluation completion and functional reliability.
- Use disposable API deployments and capture Jobs. Preserve installed services,
  secrets, frozen indices and historical schema demonstrations.
- Keep API/Job CPU and memory limits constant during a comparison. Record image,
  source, suite and configuration hashes, host, competing work and resource samples.
- No production compatibility adapters, permanent experiment-mode switches or
  automatic human approvals. Only adopted techniques enter the normal path.

## Adoption rules, declared before measurement

| Requirement | Rule |
| --- | --- |
| Meaningful speed | At least 15% lower median capture duration and 10% lower median capture-to-retained-report duration against the simpler alternative; at least four of six paired confirmation blocks improve |
| Correctness | All queries/variants complete; request echoes, configuration pins, totals and result depth remain valid; no unexplained increase in result instability |
| Reliability | No additional timeouts/rejections, retry amplification, OOMs or failed Jobs in confirmation; deliberate failures still produce an incomplete result |
| Complexity | Async scheduling or adaptive control must improve on the best simpler fixed/threaded configuration, not merely on the original baseline |
| Resource fairness | Bounded requests and connections; two overlapping captures must fit the declared aggregate budget; faster runs cannot obtain unrecorded extra CPU/memory |
| No clear winner | Keep the simpler implementation and publish the negative or inconclusive result |

Six confirmation pairs describe these local samples, not a p95 or proof of cloud
portability. Report individual runs, medians, paired ratios and observed worst
cases. Do not substitute request latency for end-to-end duration.

## Measurements

Measure image availability/startup, Job creation-to-worker-start, client setup,
fresh capture, judgement preparation/resolution, scoring, serialisation and
retention separately. Report both capture-to-retained-report and the optional
judgement-enabled path. API deployment readiness is a separate setup measurement.

Retain each run's raw observations, request completion timings, attempts, errors,
concurrency history and semantic result hash. Compare every repeated capture
against previous runs of the same variant; report changed ordered lists and totals
even if relevance aggregates remain unchanged. Exclude timestamps and elapsed
durations from the semantic hash, but never discard them from the raw record.

Use current OTLP signals and Kubernetes resource samples as supporting evidence.
Do not use missing telemetry as proof that contention was absent. The experiment
ledger is the completion/count source of truth.

## Experiment sequence

| Stage | Options | Decision |
| --- | --- | --- |
| Baseline | Current blocking client, eight query workers, sequential variants per query | Repeat and establish stage costs; verify complete fresh requests |
| Transport screening | Cached TLS context; pooled API → Elasticsearch; pooled evaluator → API with HTTP/1.1; combinations | Two complete captures per option; promote only plausible winners |
| Fixed concurrency | 8, 16 and 32 outstanding requests; 64 only if 32 is healthy and still improving | Find the useful ceiling without a load/stress campaign |
| Scheduling | Query-owned threads; pooled synchronous requests; async query scheduling; async individual-request scheduling | Compare at identical request limits; isolate pooling from scheduling |
| Adaptive control | Start 8, minimum 2, ceiling 32; bounded additive growth and multiplicative reduction on rejection/timeout or sustained latency inflation | Compare against the best fixed setting; retain only if it clears the complexity threshold |
| Judgement path | Current sequential batches of 64; bounded batch concurrency 2/4 where live model/service contract permits | Measure source lookup, cold/warm resolution and scoring separately; no model-quality claims |
| Confirmation | Original baseline, selected transport/fixed setting and any challenger; six counterbalanced pairs | Adopt the simplest qualifying combination |
| Resilience/fairness | Transient errors, slow target, cancellation/deadline, two overlapping evaluations | Bound retries/in-flight work and retain incomplete outcomes |

Before timing, give each API mode the same unmeasured warm-up. Counterbalance the
order of options and rotate query scheduling with a recorded seed. Always retain
the full frozen query identity and original output order. Separate first-use
connection costs from steady runs; do not clear the shared engine's caches or
restart other users' services to manufacture an improvement.

An adaptive prototype uses client-observed service latency after admission,
completion throughput and transient failures. Record scheduler waiting separately.
Use enough completed requests before adjusting, hysteresis and per-target samples
so one slow variant does not starve others. A per-job ceiling is insufficient for
multiple jobs: test a fixed aggregate allocation before adopting a shared adaptive
allocator. Resource signals can explain results; the first prototype does not
depend on a vendor-specific monitoring API to dispatch requests.

If the live judgement model is an abstaining fixture or mostly cache hits, state
that limitation. Do not adopt an inference optimisation based on a simulated
model delay or imply that it will accelerate a future real model. Missing
qualification means keeping the current judgement implementation.

## Batches and deliverables

1. **Experiment plan and harness:** isolated implementations, immutable ledger,
   baseline/screening/confirmation runs, functional fault checks and a measured
   decision. Commit the plan before recording experiment results; publish a PR.
2. **Adoption:** put only qualifying techniques in the normal code path, including
   packaging, tracing, tests, source templates and operator documentation. Verify
   through the normal finite-Job path and create project/source PRs as required.
   If nothing qualifies, record that decision without adding machinery.

At completion update the roadmap, retain the experiment evidence and create the
next detailed plan. Existing source relevance gates require exact-commit evidence;
experiment timing is not a gate exemption. No PR is merged without acceptance.

## Sources

- `lab/evaluation_worker.py`, `lab/variant_capture_worker.py`, `lab/evaluation_job.py`.
- `lab/search-app/app.py`, `judgements/core.py`, `judgements/prepare.py`, `evaluation/offline.py`.
- [Historical capture timings](../research/evidence/developer-evaluation-loop.md),
  [filter contract](../search-request.md), [observability](../observability-backend.md).
- [HTTPX clients](https://www.python-httpx.org/advanced/clients/) and
  [async support](https://www.python-httpx.org/async/).
- [Python HTTP server](https://docs.python.org/3/library/http.server.html),
  [adaptive concurrency reference](https://github.com/Netflix/concurrency-limits).
