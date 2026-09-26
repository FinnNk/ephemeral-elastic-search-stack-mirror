# Lifecycle identity and measurement batch

## Intent

Finish the local control-plane acceptance gates after the API/UI comparison slice: associate operations with a verified named user, measure removal over enough real samples, and prove expiry cleanup when the UI is unavailable.

## Constraints

| Area | Constraint |
| --- | --- |
| Identity | Use local Gitea as the prototype identity provider, with a migration path to GitHub Enterprise. Keep each user distinct from the agent identity. Never put passwords, access tokens or session secrets in Git, saved reports or browser response bodies. |
| Access | A user can operate their own environments; an administrator can inspect and clean up all environments. Reject cross-owner mutation. The control service remains bound to loopback in this lab. |
| Expiry | Preserve the 72-hour genuine-use rule. Run reconciliation independently of the UI and recover after a stopped process or machine restart. Do not count polling or health checks as use. |
| Measurement | Use at least 20 real warm removal runs on the documented machine. Include failures, publish raw timings and calculate p95 from the full sample. Preserve the shared index and canonical data. |
| Scope | This is a local operational validation, not proof that 40 simultaneous workloads or AKS meet the same timing. |

## Work

1. Verify Gitea credentials through its user API, create a short-lived local session and enforce owner/admin checks on create, inspect, search, compare, activity and deletion.
2. Add a login/logout UI flow. Use HttpOnly, SameSite cookies and a separate request-intent check for mutations; avoid retaining the password after verification.
3. Make the independent reconciler start reliably with the local control service and persist enough state to recover after restart. Demonstrate an expired namespace being removed while the UI process is stopped.
4. Run and retain 20 warm on-demand removal samples, including any failures. Report p50/p95, phases and machine conditions; compare with the five-minute target.
5. Test owner isolation, administrator cleanup, restart recovery and report access. Document a Gitea-to-GitHub Enterprise identity migration boundary.

## Acceptance criteria

- Two distinct local Gitea users appear as distinct owners; one cannot mutate the other's environment, and an administrator can clean up either. No stored report or browser response body contains a credential.
- A successful search, explicit activity or comparison renews a lease; status reads, polling and health checks do not.
- With the UI stopped, the independent reconciler begins cleanup within ten minutes of expiry and completes within 15 minutes under stated lab conditions. Restarting the UI preserves environment and comparison records.
- At least 20 real warm deletions have raw timings and failures retained. The reported p95 is ≤ five minutes, or a missed target has a measured cause and a revised plan.
- Shared frozen indices, datasets and completed reports survive deletion; namespaces and dedicated credentials do not.

## More information

- [Prototype lifecycle and targets](../prototype-design.md#environment-lifecycle-and-api)
- [Local Gitea identity setup](../../research/platform-spike/README.md#personal-access)
- [Lifecycle store](../../lab/lifecycle.py), [control API](../../lab/control_api.py) and [independent reconciler](../../lab/reconcile_leases.py)
- [Comparison batch evidence](../research/evidence/lifecycle-comparison/summary.json)
