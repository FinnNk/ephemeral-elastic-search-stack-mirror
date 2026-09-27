# Finite Job telemetry: local verification

Measured on 28 September 2026 in the Windows x64 k3d lab. All inputs were synthetic. The updated producer and evaluator images were published as multi-architecture Nexus manifests, then run by digest:

| Job | Image digest | Retained result | Stored SigNoz event |
| --- | --- | --- | --- |
| Independent producer | `sha256:5f7979d973a3c5d36b854f82c1b2cdf98d69d0102bd5bfde3954a689f720c90e` | Catalogue manifest `f2953d213f03f34b231753a7299d4194e14ba9cc769b19eda4b33412c68773be`; query manifest `5d5067aee6521092ba15a7012b7dde68cf8e2e3f66bf77e2f1b7910f227fad81`; judgement manifest `05f761a6916f1c1fa757cc5d824d41e54433e2d2ee679764e9c9b604edccf005` | `data.publish`, `complete`, Job `lab-data-example-c9f8017b`, matching catalogue hash |
| Offline evaluator | `sha256:22debdbe03828e6ada74945140017124c78d55c041a5f6c4ddbc813d1e25fb61` | 1,000 queries; report `2c6815c4a12832c1516c59623f8d7709fff8919956e6c4731ae5e2e4a2322d04` | `evaluation.score`, `complete`, Job `offline-evaluate-6c771f30`, matching report hash |

`signoz_logs.logs_v2` held both events with `event=lab.operation.completed` after the Jobs had been deleted. The image-pull Secret and each Job's Blob Secret were temporary; the Job Pod had no Kubernetes API token and its NetworkPolicy still allowed only DNS and Floci egress. A second run confirmed that `job_name` matches the exact Kubernetes Job resource name, rather than its generated Pod name. The result document remained the last stdout line, so the existing runner contract continued to work.

The first producer attempt scheduled on the newly added observability worker and failed to pull from `nexus.localhost:18185`: that worker lacks the application nodes' registry mapping. It reached its 180-second deadline and was cleaned up. Both runners now exclude nodes labelled `lab.relevance/role`; the successful rerun used an application node. This is a local scheduling constraint, not an Azure topology recommendation.

The safe event helper is shared by both images and admits only release and immutable SHA-256 fields. It rejects free-form query text, Blob paths and malformed hashes. Five data tests, three evaluator tests, three SLO tests and the focused event-contract test passed using the lab's pinned Python dependencies. Source compilation and `git diff --check` passed.

The [investigation diagram](../../diagrams/interactive/observability-investigation.html) already shows the scoped stdout log agent and OTLP gateway. The producer and evaluator add sources to that existing route; no new component or edge was introduced. Stored logs establish ingestion and retained-hash correlation. They do not establish a seven-day SLO verdict, browser drill-through, collection completeness or New Relic parity.
