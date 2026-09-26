# Synthetic traffic and Gatling batch

## Intent

Add the third comparison mode: run the same frozen synthetic arrival schedule against two pinned search APIs, then report latency, throughput, failures and workload validity. Cover a constant-rate smoke run and separate normal, sustained-peak and stress/recovery profiles derived from synthetic query/timestamp pairs.

## Constraints

| Area | Constraint |
| --- | --- |
| Inputs | All queries and timestamps are synthetic. Version the source trace, recipe, compiled schedule and their hashes; do not import production traffic. |
| Surface | Send original requests through the public search APIs. Elasticsearch `_profile` and `_rank_eval` may inform diagnosis but never the black-box performance verdict. |
| Fairness | Run baseline and candidate sequentially on the same constrained runner and cluster, with identical arrival schedule, warm-up, connection policy and resource limits. Record order and settle conditions; use repeated B/C pairs to expose noise. |
| Scheduling | A feeder timestamp is data, not a trigger. Compile one-second arrival buckets into Gatling open injection steps and deterministic within-bucket query order. Record planned versus actual arrivals. |
| Phases | Exclude warm-up from acceptance latency percentiles. Give normal, peak and stress/recovery separate budgets and validity rules; do not call a smoke run sustained peak. |
| Runtime | Use the open-source Gatling Java SDK in finite Kubernetes Jobs with a pinned image/JDK/simulation revision. Retain native logs and HTML reports alongside a small versioned comparison summary. |

## Work

1. Generate deterministic, realistic synthetic query/timestamp traces with diurnal intensity, head/tail query mix and bounded bursts. Document modelling assumptions and compile a versioned workload recipe.
2. Build a Gatling simulation with frozen feeder data and an open arrival schedule. Start with a 30-second ramp, 60-second warm-up and 300 seconds at 10 requests/second for the 10,000-product smoke profile.
3. Run controlled baseline/candidate pairs through public endpoints, collecting Gatling reports, planned/actual arrivals and Kubernetes/Elasticsearch resource evidence. Keep warm-up and measured requests separately named.
4. Add a performance choice to the control API/UI, retain immutable run and comparison artifacts, and show validity and threshold failures distinctly from a passing verdict.
5. Exercise normal, sustained-peak and stress/recovery recipes, including a recovery check after overload. Calibrate provisional thresholds from measured host capacity without rewriting the agreed initial smoke target silently.

## Acceptance criteria

- The same frozen trace, recipe and compiled workload bytes are bound to both API runs; hashes, environment fingerprints and runner version appear in the report.
- The 10 requests/s smoke profile has five measured minutes per side. Its provisional targets are p95 ≤ 250 ms, p99 ≤ 500 ms and failures < 1%; a miss is reported with evidence.
- Warm-up is excluded from measured percentiles. Planned and actual arrivals are compared, and an invalid generator or incomplete phase cannot pass.
- Normal, sustained-peak and stress/recovery each have explicit duration, offered load, budgets and outcomes. Stress identifies the first budget breach and whether recovery meets its separate check.
- Native Gatling output, summary, resource conditions and all synthetic input hashes remain accessible after the ephemeral APIs are removed.

## More information

- [Prototype performance and traffic design](../prototype-design.md#performance-check-the-search-api-with-gatling)
- [Traffic workload view](../diagrams/interactive/traffic-workload.html) and [performance workflow](../diagrams/interactive/performance-check.html)
- [Current controlled API comparison](../../lab/control_comparison.py)
- [Gatling feeders](https://docs.gatling.io/concepts/session/feeders/) and [open injection](https://docs.gatling.io/concepts/injection/)
