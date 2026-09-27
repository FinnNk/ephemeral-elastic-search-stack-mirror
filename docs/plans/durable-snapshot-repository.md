# Durable snapshot repository

## Intent

Make the implemented regular snapshot workflow usable on the serving cluster with storage that survives Elasticsearch cluster and data-volume replacement. Prove both creation and historical restore through the environment lifecycle.

## Constraints

| Area | Constraint |
| --- | --- |
| Storage | Use an independently persisted repository that passes Elasticsearch verification and repository analysis. The local Docker volume survives Elasticsearch data-PVC replacement but is not an off-host backup. |
| Authority | Recipes and synthetic product releases remain canonical. Keep the recipe rebuild fallback. |
| Compatibility | Test the same Elasticsearch version and repository implementation as the serving cluster. Do not infer Azure compatibility from the filesystem probe. |
| Isolation | Snapshot administration belongs to the lab controller. Search API credentials remain index-scoped and read-only. |
| Retention | Keep snapshots referenced by retained recipes beyond the 72-hour runtime lease. Define an explicit archival or deletion policy before accumulating many versions. |

## Acceptance criteria

- Repository verification and analysis pass on every participating node; the storage survives Pod and Elasticsearch cluster/data-PVC recreation.
- A dedicated index is captured through `LAB_SNAPSHOT_REPOSITORY`, then deleted and restored by creating an environment with the historical recipe. The public Search API returns the frozen ordered sample.
- Repeat at one million products at least three times and record capture, restore, index verification and API readiness separately.
- Missing, incompatible and corrupt snapshot cases rebuild from the pinned recipe, preserve fallback errors and never bind an unverified index.
- Document capacity, repository version, credentials, restore permissions, cleanup and Azure migration implications.

## Outcome

Implemented on `slice/durable-snapshot-repository`. The shared ECK cluster uses a regular S3 repository backed by a pinned SeaweedFS 4.47 container and a separate named Docker volume. Repository verification and 100-blob analysis passed. Three one-million-product restores through the lifecycle took 17.157–17.578 seconds and passed count, recipe, write-block and ordered-ID checks. A fresh environment restored through the public Search API, and a further restore passed after the store restarted. A separate probe also restored after deleting and recreating its Elasticsearch cluster and data PVC. The canonical recipe rebuild remains the fallback. See the [evidence and limits](../research/evidence/durable-snapshot-repository.md).

## More information

- [Recovery selection and repository options](../research/index-restoration-options.md)
- [Recovery implementation](../../lab/index_recovery.py)
- [Elasticsearch repository guidance](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/self-managed)
- [ECK repository guidance](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/cloud-on-k8s)
