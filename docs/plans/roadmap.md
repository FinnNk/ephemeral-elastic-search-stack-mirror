# Lab delivery roadmap

Use this page for ongoing work and remaining acceptance checks. Use the
[delivery guide](../delivery.md) and [fresh-install guide](../fresh-install.md)
for operating procedures. The [archived roadmap](roadmap-history-2026-10-16.md)
retains previous implementation entries and measurements.

## Current work

| Work | Next step |
| --- | --- |
| Code and documentation simplification | Review the [findings and cleanup batch](../reviews/codebase-simplicity-2026-10-16.md), then follow its bounded refactoring plan. |
| [Build previews from a branch or SHA](branch-preview-builds.md) | Delivery-source #44 and lab #220 are merged. Activate when idle, then rehearse a real branch and exact-SHA preview. |
| Promotion walkthrough feedback | Review the separate advisory-outcome and judgement-data work. Keep accepted labels and their provenance together; verify fresh-install seeds before activation. |
| Realistic ranking-change example | Complete the retained judgement review and re-score the frozen title-match experiment. Preserve the original published-label result and protocol. |

The build-207 Production walkthrough completed with the user's confirmation.
This review did not recheck the live deployment. Use the release dashboard and
its verification receipts to identify what is serving now; build numbers in old
plans do not describe current state.

## Implemented capabilities

| Area | Current procedure |
| --- | --- |
| Source and releases | [Versioned builds, merge gates and reviewed promotion](../delivery.md); Integration, Staging and blue/green Production use frozen release definitions. |
| Release check plans | [Review accumulated changes and query sets](../release-check-plans.md). Standard sets remain mandatory; additional required sets gate independently. |
| Experiments | [Compare ready environments and view notebooks](../../lab/README.md). Queries are selected separately from catalogue/index restoration. |
| Data | [Paired catalogue and Redis restores](../paired-data-restores.md), retained index recipes and timestamped metadata. |
| Observability | [SigNoz metrics, traces and correlated logs](../observability-backend.md), retained operation progress and native Gatling reports. |
| Installation | [Resumable fresh CPU installation](../fresh-install.md), optional demo SigNoz and scoped cleanup. |
| Access and backup | [Named sign-in](../oidc-access.md), [Git mirrors](../github-mirror.md), [service recovery](../gitea-upgrade.md) and [whole-lab transfer](../lab-transfer.md). |

A capability being implemented does not establish model accuracy, performance
on another host, or successful restoration. Compare the relevant retained
evidence with the acceptance work below.

## Remaining validation

| Area | Work still needed |
| --- | --- |
| Fresh installation | Repeat an empty owned Mac installation without intermediate manual repairs, including browser trust, source build, comparison and promotion. |
| Recovery | Rehearse backup/restore of the complete lab and control state in a disposable target. Git mirrors alone do not back up service databases or volumes. |
| Performance | Recheck full workload budgets on the target hardware and assess resource contention. Short diagnostics do not replace promotion evidence. |
| Judgement quality | Complete independent actual-gap quality evidence and qualification before making model-accuracy claims. Accepted demonstration labels retain their own provenance. |
| Observability | Verify sustained ingestion, counter alignment and instrumentation overhead on the target setup. Historical runs cannot acquire missing telemetry retrospectively. |
| Cloud portability | Verify AKS, GitHub Enterprise provider/protection, Azure identity/storage and external producer/evaluator boundaries. |
| Transport | Complete the [HTTPS OCI transport work](https-oci-transport.md); selected bootstrap and registry HTTP paths remain explicit local boundaries. |

The [evidence index](../research/evidence/README.md) records measurements and
conditions. Individual plans retain their original acceptance criteria; they
must not be read as new instructions to merge, deploy or rerun completed work.

## Working on the next batch

Keep each change on a branch, commit it and open a PR. Obtain human acceptance
before merging. Update this page and the relevant detailed plan when the batch
changes what remains to be done. Operational guidance describes current
behaviour; implementation chronology belongs in evidence or archived plans.
