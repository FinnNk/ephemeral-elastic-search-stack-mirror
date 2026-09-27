# Snapshot restoration research

## Intent

Find a faster, reliable way to recover a historical frozen index **without rebuilding it**, while retaining the immutable recipe and Blob-to-bulk rebuild as the fallback. Measure full time to a correct search, not only the Elasticsearch restore API duration.

## Constraints

| Area | Constraint |
| --- | --- |
| Baseline | Existing index reuse and recipe rebuild remain supported. Snapshots are optional accelerators. |
| Data and schema | Use synthetic frozen releases and recipe SHA-256 identities. Restore old and new mappings side by side under separate names. |
| Compatibility | Verify repository operations, snapshot/index/cluster version compatibility, settings and security boundaries. Do not assume Floci's Azure emulation supports Elasticsearch's repository calls. |
| Storage | Compare a local shared filesystem repository, an independent compatible object store and real Azure Blob where access exists. Do not copy a live Elasticsearch data directory as a backup. |
| Licence | Do not add searchable snapshots or other paid features. Keep the current ECK cluster/licence shape. |
| Measurement | Separate snapshot creation, transfer, restore, shard recovery, index verification and API readiness. Record bytes, memory and disk. |

## Work

1. Inspect the available repository implementations and version requirements. Record compatibility, operational dependencies and portability to Azure and Apple silicon.
2. Run a repository verification and snapshot/restore probe on the 10,000-product release. If compatible, repeat on the million-product index. Use a different restored index name and check recipe identity, count, write block and ordered sample results.
3. Compare at least three paths on the same warm lab: retained-index reuse, snapshot restore and recipe rebuild. Repeat enough times to report variability and make cache state explicit.
4. Test a missing/incompatible snapshot and prove automatic fallback to the recipe rebuild without changing the chosen historical definition.
5. Record a recommended cache and retention policy: which historical index versions remain live, which receive snapshots, and when restored indices are removed.

## Acceptance criteria

- A comparison table names each tested repository, verification result, snapshot and restore duration, end-to-end readiness, storage footprint and failure mode.
- A selected route restores the historical mapping without a bulk reindex and reproduces the pinned sample results, or the report states the measured blocker and retains rebuild as the only supported path.
- The design states when to reuse, restore or rebuild, and how an incompatible engine version changes the destination cluster.
- No feature requiring an additional Elastic licence is introduced.

## More information

- [Historical recipe batch](historical-index-recipes.md)
- [Million-product rebuild measurements](../research/evidence/million-scale.md)
- [Failed Floci Azure repository probe](../research/evidence/platform-spike/snapshot-compatibility.json)
- [Elasticsearch repository types](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/self-managed)
- [Elasticsearch restore and rename](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/restore-snapshot)
