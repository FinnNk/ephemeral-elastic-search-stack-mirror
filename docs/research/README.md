# Research and modelling notes

These studies record why components and synthetic models were chosen. Product
comparisons describe the editions and documentation reviewed at the time;
experimental results describe their recorded machine, inputs and revision.
They are not the current installation procedure.

## Current procedures

| Task | Guide |
| --- | --- |
| Use or operate the lab | [Lab guide](../../lab/README.md) |
| Build/evaluate/promote source | [Delivery](../delivery.md), [evaluation runbook](../evaluation-runbook.md) |
| Restore an index or change schema | [Index recovery](../index-recovery.md) |
| Provide independent synthetic inputs | [Data contracts](../data-evaluation-contracts.md) |
| Resolve missing labels or replace a model | [Judgements](../judgement-resolution.md), [model installation](../esci-model-installation.md) |
| Sign in to Headlamp or Argo CD | [Named OIDC access](../oidc-access.md) |
| Manage secrets and HTTPS | [Key Vault](../keyvault-secrets.md), [HTTPS](../https-ingress.md) |
| Investigate telemetry | [SigNoz](../observability-backend.md) |
| Check current status | [Roadmap](../plans/roadmap.md) |
| Prepare or transfer to a Mac | [Mac setup](../mac-setup.md), [lab transfer](../lab-transfer.md) |

## Selection studies

- [Platform spike](platform-spike.md): measured Argo/Kubernetes/Gitea probes on 26 September 2026.
- [Gitea lifecycle](gitea-lifecycle.md): original self-contained delivery and GHES boundary checklist.
- [Okteto and Uffizzi](okteto-uffizzi.md): edition and environment-management suitability.
- [Lifecycle, Signadot and Coolify](lifecycle-signadot-coolify.md): alternative control/routing approaches.
- [Index restoration](index-restoration-options.md): clone and snapshot measurements with different conditions.
- [Portability and Azure](portability-azure.md): proposed native/cloud contracts and unverified gates.

## Synthetic modelling

- [ESCI-informed calibration](esci-synthetic-calibration.md): aggregate references, assumptions and limits; no source records copied.
- [Million-product release](million-synthetic-release.md): frozen catalogue/query identity and generator model.
- [Synthetic traffic](synthetic-traffic.md): request/timestamp modelling and versioned workload recipes.

[Evidence records](evidence/README.md) retain individual implementation checks.
[Research harnesses](../../research/platform-spike/README.md) reproduce isolated
experiments; they can create/delete resources and are not ordinary lab setup.
