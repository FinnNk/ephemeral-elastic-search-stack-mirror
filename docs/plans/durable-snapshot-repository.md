# Durable snapshot repository

## Intent

Make the implemented regular snapshot workflow usable on the serving cluster with storage that survives a cluster rebuild. Prove both creation and historical restore through the environment lifecycle.

## Constraints

| Area | Constraint |
| --- | --- |
| Storage | Use a repository that passes Elasticsearch verification and repository analysis. The one-node research PVC does not qualify as off-host recovery. |
| Authority | Recipes and synthetic product releases remain canonical. Keep the recipe rebuild fallback. |
| Compatibility | Test the same Elasticsearch version and repository implementation as the serving cluster. Do not infer Azure compatibility from the filesystem probe. |
| Isolation | Snapshot administration belongs to the lab controller. Search API credentials remain index-scoped and read-only. |
| Retention | Keep snapshots referenced by retained recipes beyond the 72-hour runtime lease. Define an explicit archival or deletion policy before accumulating many versions. |

## Acceptance criteria

- Repository verification and analysis pass on every participating node; the storage survives Pod and cluster recreation.
- A dedicated index is captured through `LAB_SNAPSHOT_REPOSITORY`, then deleted and restored by creating an environment with the historical recipe. The public Search API returns the frozen ordered sample.
- Repeat at one million products at least three times and record capture, restore, index verification and API readiness separately.
- Missing, incompatible and corrupt snapshot cases rebuild from the pinned recipe, preserve fallback errors and never bind an unverified index.
- Document capacity, repository version, credentials, restore permissions, cleanup and Azure migration implications.

## More information

- [Recovery selection and repository options](../research/index-restoration-options.md)
- [Recovery implementation](../../lab/index_recovery.py)
- [Elasticsearch repository guidance](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/self-managed)
- [ECK repository guidance](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/cloud-on-k8s)
