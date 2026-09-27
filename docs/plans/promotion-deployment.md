# Batch 7h: promotion and deployment

## Intent

Implemented on `slice/promotion-deployment`; [operating guide](../delivery.md) and [measured evidence](../research/evidence/promotion-deployment.md). Project review is pending.

Promote one tested Nexus release through integration, staging and simulated production using reviewed desired-state PRs. Argo CD deploys; verification records whether the declared release is serving correctly.

## Constraints

| Area | Rule |
| --- | --- |
| Targets | Three stable namespaces in the same cluster. They share compatible frozen Elasticsearch indices; this is not failure-domain or performance isolation. |
| Artifacts | Promotion copies an immutable release ID and its image/bundle digests. No build runs during promotion. |
| Approval | A protected desired-state branch requires a passing validation status and a review. Demonstration approvals are explicitly identified as automation acting as a simulated reviewer; the user's project PRs remain unmerged. |
| Evidence | Pin release, source SHA, dataset, recipe, settings, baseline and target revision. Changed inputs invalidate evidence. |
| Relevance | Result-preserving changes require exact unchanged results. Intentional ranking changes require review of relevance results and judgement coverage; no automatic approval from proxy scores. |
| Schema | Verify the index recipe against release compatibility before publishing desired state. Materialise historical indices with the existing reuse/clone/snapshot/rebuild functions. Rollback selects the previous release, configuration and recipe together. |
| Control | One local command/process coordinates proposals and verification. Argo CD owns workloads. Provider calls stay separate from release and gate logic. |

## Work and acceptance criteria

1. **Resolve release and deployment.** Verify Nexus descriptor/bundle hashes and a successful merged-source build. Produce a deployment fingerprint containing all search-affecting inputs. Reject mutable images, missing artifacts and incompatible schema/engine combinations.
2. **Evaluate a frozen candidate.** Reuse existing in-cluster functional and Gatling runners. Run full result preservation, frozen relevance with coverage, and a short paired performance check against a frozen baseline. Store report hashes and exact inputs. The short Gatling profile is a promotion demonstration, not capacity validation.
3. **Propose promotion.** Open a desired-state PR with an inspectable deployment diff, baseline/target and report references. Validate the exact PR head. Failed, incomplete or stale evidence prevents a passing promotion status; a moved target requires a fresh proposal/evaluation as applicable.
4. **Approve and deploy.** Demonstrate a distinct reviewer approval, merge, Argo convergence and public API smoke verification. Record proposed/approved/deploying/verified separately. Next-stage promotion requires the source target's current verified deployment.
5. **Promote unchanged.** Reach all three targets with identical artifact digests. Keep per-target credentials and settings outside the release.
6. **Rollback.** Propose a rollback to a retained previous deployment, review/merge it, and verify restored API/config/index selection. A failed deployment must not become eligible for onward promotion.
7. **Capture negative cases.** Failed checks, stale baseline or target, incompatible schema and a changed PR head fail closed. Record live cases where meaningful and focused tests for race/integrity boundaries.
8. **Synchronise documentation.** Update roadmap, operating guide, source-provider migration notes, C4 delivery/deployment views and an Archify promotion workflow. Rebuild and visually inspect changed diagrams. Open stacked Gitea/GitHub implementation PRs.

## Information

- [Reference CI/CD contract and targets](reference-ci-cd.md)
- [Portable release CI](portable-ci.md), `lab/delivery_release.py` and `lab/delivery_provider.py`
- `lab/lifecycle.py`, `lab/evaluation_job.py`, `lab/compare_search.py`, `lab/performance_pair.py`: existing comparison boundaries.
- `lab/index_recipe.py`, `lab/index_recovery.py`, `lab/shared_index.py`: frozen schemas and restore methods.
- `research/platform-spike/chart`, `applicationset.yaml`: Argo deployment and namespace isolation.
- [Gitea Actions differences](https://docs.gitea.com/usage/actions/comparison/) and [Argo CD CI automation](https://argo-cd.readthedocs.io/en/stable/user-guide/ci_automation/).

The next local batch is [Kubernetes control services](kubernetes-control-services.md), followed by [independent data/evaluation contracts](independent-data-evaluation-contracts.md). [Native, GHES and Azure validation](native-cloud-validation.md) remains the subsequent external gate.
