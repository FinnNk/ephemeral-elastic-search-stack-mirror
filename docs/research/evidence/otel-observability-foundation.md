# OTel foundation: local evidence

**Historical foundation check — 27 September 2026.** SigNoz was installed in later batches. The absence/capacity statements below describe this run; use the [current backend guide](../../observability-backend.md) for access and interpretation.

Measured on 27 September 2026, Windows x64 with the two-node k3d relevance lab. This is a signal-contract demonstration, not a SigNoz dashboard or a production SLO result.

| Check | Observation |
| --- | --- |
| Search API build | `docker build` passed six Search API tests, including a real local HTTP search with telemetry disabled, using OpenTelemetry Python 1.44.0; local image `sha256:9a74a83259280b3396a0f65a6516d2c29e6ef894d22479de4fcdee0cea4e806a`. |
| OTLP receiver | The isolated image emitted `/v1/traces` (615 bytes) and `/v1/metrics` (1,093 bytes) to a loopback receiver. The `search.completed` log carried the same trace/span context and classified a 260 ms HTTP 200 as success good and responsive bad. The repeat run shut down cleanly. |
| Collector outage | With OTLP pointed to a closed loopback port, a local public API search still returned HTTP 200 and the expected product ID in 0.005 s. Exporters subsequently reported retries/failure; telemetry loss did not block that response. This is one synthetic request, not a load-overhead result. |
| SLO fixture | Three tests passed: 30 slow successes among 1,000 consume 60% of a 95% latency budget while the success budget remains untouched; 11 failures breach the 99% success target; empty and unverified windows do not show a met state. |
| Host memory | 100,267,516 KiB visible, 13,572,172 KiB free at the snapshot (about 95.6/12.9 GiB). The host was also running unrelated Docker workloads. |
| k3d memory | Server: 4.301/6 GiB; agent: 2.297/4 GiB. About 3.4 GiB remained inside the two node limits. These are point-in-time container readings, not capacity under load. |
| Storage | D: reported about 326 GB free. The cluster uses local-path PVCs, including Elasticsearch, Gitea and control state. Docker's own backing-store capacity was not established by this check. |

SigNoz was not installed into this lab cluster. Its [published minimum](https://signoz.io/docs/install/kubernetes/local/) is 8 GB memory, four cores and 30 GB storage. The existing node limits do not leave that much memory after current lab use. The next batch needs a deliberate allocation or release of unrelated host capacity before backend installation. This slice does not demonstrate metric/log/trace navigation, Collector resilience, New Relic export or telemetry overhead under Gatling load.
