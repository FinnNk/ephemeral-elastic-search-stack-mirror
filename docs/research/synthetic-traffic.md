# Synthetic search traffic workload

The [frozen trace](../../lab/traffic/source-trace-v1.csv) has 4,399 synthetic `(timestamp, query)` pairs across ten minutes. Its [manifest](../../lab/traffic/source-manifest-v1.json) pins the source SHA-256, 50-query release hash, seed, time range and modelling assumptions. It contains no production traffic.

| Assumption | Synthetic choice |
| --- | --- |
| Query mix | 70% drawn from ten head queries; 30% from forty tail queries in the frozen release. |
| Intensity | A smooth wave around seven arrivals/s plus a ten-second burst every three minutes. |
| Placement | Requests evenly spaced within each source second. |
| Market | GB and GBP, matching the 10,000-product release. |

The [active v2 recipes](../../lab/traffic/recipes-v2.json) select source windows and resample their query mix into explicit one-second arrival buckets. [V1](../../lab/traffic/recipes-v1.json) is retained because the first normal-load and smoke evidence used it. V1's peak window averaged only 10.45 requests/s, so v2 sets a sustained 20 requests/s plateau. The [compiler](../../lab/traffic.py) writes a schedule and one Gatling feeder per phase under ignored `.lab/workloads/<workload-sha>/`. Every file has a hash in the compiled manifest. A timestamp in the feeder identifies the planned event; Gatling's open injection steps schedule the arrivals. The Java simulation records actual arrival time, phase, query ID and planned offset so the report adapter can reject missing events or large scheduling drift.

| Profile | Warm-up and measured phases | Offered load |
| --- | --- | --- |
| Probe | 5 s warm-up, 10 s normal | 2 requests/s |
| Smoke | 30 s ramp, 60 s warm-up, 300 s normal | 10 requests/s measured |
| Normal | 30 s warm-up, 120 s normal | Source trace rate |
| Peak | 30 s warm-up, 120 s sustained peak | 20 requests/s measured; source query mix |
| Stress/recovery | 30 s warm-up, three 30 s stress steps, 60 s recovery | 15, 25, 35, then 10 requests/s |

The source windows and scaling choices are lab hypotheses, not measured production rates. Fixed-rate resampling changes the source's exact within-second gaps; it keeps the selected query order and places the compiled requests regularly within each target second. Warm-up and ramp traffic establish the declared runtime state but are excluded from measured latency verdicts. Normal, peak and recovery have separate provisional budgets; stress steps identify the first budget breach or state that no breach occurred at the maximum offered rate. The 120-second peak and 30-second stress steps are calibration runs. The [design's longer duration gate](../prototype-design.md#traffic-profiles-and-phases) remains outstanding, including fifteen measured peak minutes, two-minute stress holds and five-minute recovery.

The pinned [Gatling simulation](../../lab/gatling/src/test/java/lab/relevance/SyntheticSearchSimulation.java) checks public `/search` responses. The [report adapter](../../lab/gatling_report.py) checks all planned versus actual events, phase counts and arrival drift before a result can be valid. Gatling's displayed request rate uses the whole simulation duration, so the adapter also reports each phase's offered rate from the frozen schedule. The compiled schedule, source trace, recipe, native Gatling HTML/log archive and paired summary are retained in Floci by SHA-256.

Gatling documents [open injection steps](https://docs.gatling.io/concepts/injection/), [file-based feeders](https://docs.gatling.io/concepts/session/feeders/) and [request-scoped assertions](https://docs.gatling.io/concepts/assertions/). The source uses its Java SDK 3.15.1 and Maven plugin 4.21.12, matching the pinned upstream [Java demo POM](https://github.com/gatling/gatling-maven-plugin-demo-java/blob/main/pom.xml) at the time of this lab batch.
