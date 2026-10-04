# Production promotion load gate

Require a meaningful normal and sustained-peak load check before promoting from
staging to simulated production.

## Intent and constraints

- Use Gatling and existing frozen query/timestamp traffic generation.
- Keep the same immutable release, index and workload on both sides.
- Test isolated previews sequentially; do not load the deployed target.
- Keep integration and staging probes available.
- Require five measured minutes at 10 requests/second and fifteen at 20, after
  one minute of warmup per release. These are speculative local lab rates.
- Preserve existing frozen recipes and historical evidence. Add a dedicated
  production recipe; do not reinterpret old probe reports as load evidence.
- Preserve explicit ranking intent, approvals and target ordering. Add no RBO gate.

## Acceptance

| Check | Expected result |
| --- | --- |
| Production evaluation with no profile | Selects `production-load` |
| Explicit production probe or smoke | Rejected before evaluation work |
| Production proposal with old probe evidence | Rejected |
| PR validation before merge | Rechecks the production load policy |
| Changed recipe, shortened peak, missing arrivals or exceeded budgets | Rejected |
| Earlier target with valid probe evidence | Still accepted |
| CSV larger than one ConfigMap | Bounded chunks restore the exact original bytes |

## Verification and next batch

All 37 focused delivery, Gatling and traffic tests passed. They cover target
defaults, proposal/PR enforcement, phase duration/rates, arrival validity,
budgets and byte-preserving workload transport. Compilation against the actual
1,000-query ESCI suite produced 600 warmup, 3,000 normal and 18,000 peak requests.
Five bounded ConfigMaps carry its CSV bytes.

A finite Kubernetes Gatling probe using the changed runner completed with valid
arrivals and retained its native report at
`runs/5424ec48b27ba5fa0c8bbd3df7282f4436bb520ada7319a9d67a87c7602d33ba/gatling-report.zip`.
This checks runner transport and execution, not the full production load profile.
A complete load run must be measured after this batch is accepted and installed;
unit fixtures do not establish capacity or latency.

Next: follow [activation and measurement](production-load-activation.md), then
resume the walkthrough with a fresh `production-load` evaluation for the merged
Search API release.
Keep the remaining walkthrough feedback in one follow-up batch, including manual
Actions workflows, automatic PR comparisons and report similarity metrics.

## References

- [Delivery procedure and budgets](../delivery.md#evaluate-and-propose-deployment)
- [Pinned production workload](../../lab/traffic/production-load-v1.json)
- [Target policy](../../lab/delivery_load_policy.py)
- [Gatling runner](../../lab/run_gatling_job.py)
- [Walkthrough](developer-walkthrough.md)
