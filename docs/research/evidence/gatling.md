# Gatling performance calibration evidence

All requests in this record used wholly synthetic query/timestamp pairs and the public `/search` API. The baseline and candidate were pinned `retail-baseline` and `retail-candidate` deployments over the same write-blocked 10,000-product index. They used separate read credentials and different API image digests. Runs were sequential on the Windows 11/k3d lab. The [workload model](../synthetic-traffic.md) documents the source, recipe versions and phase assumptions.

| Profile and execution | Measured load | Baseline p95 / p99 | Candidate p95 / p99 | Failures | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Five-minute smoke, Docker loopback, v1 | 3,000 requests/side at 10/s | 23 / 28 ms | 22 / 29 ms | 0/6,000 | Both within 250/500 ms and <1% absolute budgets |
| Normal, finite Kubernetes Jobs, v1 | 1,103 requests/side, 9.192/s mean | 9 / 11 ms | 10 / 13 ms | 0/2,206 | Both within 250/500 ms and <1% budgets |
| Peak calibration, finite Kubernetes Jobs, v2 | 2,400 requests/side at 20/s for 120 s | 9 / 11 ms | 9 / 12 ms | 0/4,800 | Both within 400/800 ms and <1% budgets |
| Stress step at 35/s, finite Kubernetes Jobs, v2 | 1,050 requests/side for 30 s | 8 / 11 ms | 8 / 14 ms | 0/2,100 | No breach through maximum tested step |
| Recovery after stress, finite Kubernetes Jobs, v2 | 600 requests/side at 10/s for 60 s | 9 / 11 ms | 9 / 12 ms | 0/1,200 | Both within 250/500 ms and <1% budgets |

Every listed run recorded all scheduled arrivals and passed the declared arrival-drift check. Warm-up and ramp requests were excluded from measured latency budgets. Native Gatling HTML/log archives, compiled workloads, source, recipes, simulation source and paired reports are retained in Floci by SHA-256. The paired report IDs are:

| Profile | Baseline run | Candidate run | Paired report SHA-256 |
| --- | --- | --- | --- |
| Smoke | `2e8c1fec8b2e` | `457b6d57edca` | `7d640aad0ab621c8ac98ed85936f2878b391cdb7cd7718e611da2b6869992d90` |
| Normal | `a1168e95` | `cf259553` | `ce4c6366b5f6c8088cfde163c7ece286a4be58bfc0e7350fb00e18b37a298916` |
| Peak calibration | `0633c79a` | `ae7686ed` | `749561b0e6e9ced11035867b59f845bc9c7ad613c131240b0a15aad4fe30cde1` |
| Stress/recovery calibration | `2bfaf1ab` | `022a950c` | `95016c6496c679a8e1ccbeed2aeaea82523932b5aa103c4769072587a7982a82` |

The first v2 peak/stress workload ZIPs carried the correct v2 recipe bytes under the filename `recipes-v1.json`. The report's recipe SHA-256 identifies those bytes. Correctly named companion archives are retained under SHA-256 `d4465207e3fa3e4f5187a8b371da1daea11f87dca00fe097b8513023658e4e47` (peak) and `7888307a50cea5d1dd56190e8e51b2b55c19ced61af49897d7cff` (stress); the archiver now uses the recipe's actual filename.

An authenticated control API walkthrough created two temporary, named-owner environments, ran the performance probe, reopened the report and removed both. Its [sanitised record](performance-control.json) gives the exact report hash and final states. Each probe side recorded all 30 arrivals with no failures. The separate static finite-Job probe also completed and removed its temporary Job, ConfigMaps and PVC.

## Limits and next measurements

- One five-minute smoke pair establishes the absolute result above, but not the design's three-pair median relative budget or baseline p95 spread check. The 9→10 ms normal difference is a one-millisecond observation, not a stable regression estimate.
- The 120-second peak and 30-second stress holds are runner calibration. The design's fifteen-minute peak, two-minute stress holds and five-minute recovery gate remains open, especially at 1,000,000 products.
- The single resource snapshots are observations, not peaks: Docker candidate smoke Gatling about 653 MiB of its 2 GiB limit; Kubernetes normal baseline Gatling about 723 MiB, search API 17 MiB and Elasticsearch about 1,507 MiB.
- Earlier exploratory failures exposed a Windows `kubectl cp` path issue and a missing Gatling NetworkPolicy ingress rule. The runner and GitOps chart were corrected; the failed attempts remain under ignored `.lab/evidence/`, while the successful finite Jobs and managed comparison establish the corrected path.
- This local 10,000-product result gives no production capacity estimate. Resource isolation, cache settling between repeats and the million-product gate need further evidence.
