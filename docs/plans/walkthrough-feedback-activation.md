# Walkthrough feedback activation

The accepted changes from lab PRs #138/#139 and delivery-source PR #33 were
activated on 6 October 2026. The coordinator was idle before installation.

## Installed and checked

| Component | Observed result |
| --- | --- |
| Coordinator | Four containers ready; PVC state and OIDC retained; smoke checks reached Gitea, Elasticsearch 9.5.4 and Nexus |
| Runtime image | `nexus.localhost:18185/lab-control@sha256:a17365b8d2e8949c715a3f14fd9138e0c2250b093afd40eda65b4be28604d319` |
| Delivery-state main | Merge allowlist contains only `elastic-agent`; one approval, `delivery/validation` and administrator override prohibition retained |
| Source workflows | Six focused forms and Advanced delivery registered as active; source gate configuration reconciled |
| Dashboards | Accepted search and model definitions applied to their existing SigNoz dashboard IDs |
| Actions authentication | Existing scoped credentials and variables reconciled |

The [verification-only Actions run #166](https://gitea.localhost:34443/elastic-agent/delivery-source/actions/runs/166)
submitted a staging verification through the authenticated delivery client.
Its [operation](https://control.localhost:34443/api/delivery/operations/34cdb06ac0544a562b84441471dbd5af)
completed with `state: verified` and retained three scoped log entries. It did
not promote a release or switch production.

## Fresh-preview telemetry

Build 163's preview uses the new source chart. Its environment includes the OTLP
endpoint and release/environment identity; the chart grants collector egress.
Ten sequential functional searches returned HTTP 200 and non-empty results.
SigNoz's latest counters showed 10 eligible, 10 successful and 9 completed within
250 ms. These ten requests verify export, not an SLO or load-test result.

The normal-cohort increase query showed four requests because the initial export
already contained earlier requests. Its increase alone is not the total sent.
The cumulative counters accounted for all ten. A supplied trace ID reached the
Search API; SigNoz's flamegraph and waterfall APIs returned 200 and the trace
view showed `search-api`.

The [source comparison](https://control.localhost:34443/api/delivery/operations/51998b9be2c4181f9625fd0ace77251d/report)
for PR #33 passed. Its standard-suite nDCG@10 difference was zero and judged
coverage was 81.22%. It continues to disclose authorised demo labels. The
abstaining v1 judge remains active; existing retained judgements were preserved.

## Next

Continue the [production resource investigation](production-release-walkthrough.md#production-load-recovery)
and rerun the unchanged full load gate when the resource change has evidence.
Production has not been switched by this activation. A fresh human approval and
coordinator deployment rehearsal can confirm the installed merge restriction;
this batch inspected its configuration without attempting a direct human merge.
