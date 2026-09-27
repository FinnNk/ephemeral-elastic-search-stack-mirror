# Batch 7k2b: SigNoz account and SLO dashboard

## Intent

Give the local lab distinct agent and human SigNoz identities and a source-controlled dashboard over the existing OTel counters. Keep the dashboard deployable on a newly bootstrapped instance without copying live state. The [runtime investigation batch](signoz-connected-runtime.md) completes coverage, drill-through and overhead checks.

**Status: implemented locally; awaiting review.** The separate `finn@lab.local` Admin invitation is pending activation. The dashboard is provisioned and its synthetic search interval arithmetic is measured. The [evidence](../research/evidence/signoz-dashboard-2026-09-28.md) states what remains unverified.

## Constraints

- Use the approved agent root account only for bootstrap and provisioning. Keep passwords, session tokens and invite links outside Git. The human sets their own password through a manual link; SMTP is not required.
- Keep the Search API's unsampled counters, normal traffic cohort and seven-day policy unchanged. Do not use queries, product bodies or operation IDs as metric labels.
- Do not present a sparse interval or missing telemetry as a healthy seven-day SLO verdict. Frozen comparison reports remain authoritative for promotion.

## Acceptance criteria

1. **Distinct administrator.** Invite the human as a non-root Admin under a synthetic email-shaped identifier. Verify its pending status and role. Store the manual link outside Git and give the human a path to accept it.
2. **Source-controlled v2 dashboard.** Commit a SigNoz `v6` dashboard definition with a deterministic builder, named deployment and idempotent provisioning. Show normal search counts, percentages, allowance and burn, plus operation outcome trends and interpretation guidance. Keep the other traffic cohorts outside the normal SLO population.
3. **Measured formulas.** Produce spaced cumulative metric exports for known fast, slow-success and failed searches. Query SigNoz for stored metric results, checking eligible/good/bad arithmetic, and record exact values. Validate the operation query syntax separately.
4. **Reviewable completion.** Update the backend guide, roadmap and evidence. Check the diagram for topology changes, prepare the next detailed plan, commit to a branch and open a stacked Gitea PR. Merge only after user acceptance.

## Where to find more information

- [Backend operations guide](../observability-backend.md), [backend evidence](../research/evidence/signoz-backend-2026-09-27.md) and [search SLO policy](../../lab/observability/policies/search-slo-v1.json)
- [SigNoz dashboard v2 API](https://signoz.io/docs/dashboards/dashboards-v2-api/), [manual invitations](https://signoz.io/docs/manage/administrator-guide/iam/invite-team-member/) and [metrics query API](https://signoz.io/docs/metrics-management/query-range-api/)
