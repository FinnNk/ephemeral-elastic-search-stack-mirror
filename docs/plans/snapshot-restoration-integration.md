# Optional snapshot restoration integration

## Intent

Add regular snapshots as an accelerator for historical frozen index creation when a durable, compatible repository is available. Preserve existing live-index reuse and recipe rebuild as fallback paths.

## Constraints

| Area | Constraint |
| --- | --- |
| Authority | The index recipe and synthetic product release remain canonical. A snapshot must be linked to a recipe SHA-256 and engine version. |
| Repository | Select a repository only after verification and restore tests in the intended placement. The one-node local filesystem PVC is a research result, not a cloud backup design. |
| Isolation | Restore under a distinct index name. Do not replace an active shared index or widen environment Elasticsearch privileges. |
| Licence | Use regular snapshot and restore APIs; do not add searchable snapshots or paid orchestration features. |
| Correctness | Verify mapping, settings, count, write block, recipe marker and frozen ordered sample before marking an environment ready. |
| Fallback | Missing, incompatible or failed snapshots must take the immutable recipe rebuild path and report the path and error. |

## Acceptance criteria

- A compatible snapshot can recreate a deleted dedicated historical index without a bulk reindex; the API sees the original schema and returns the frozen ordered sample.
- A missing or incompatible snapshot falls back to a recipe rebuild for the same definition. A hash or mapping mismatch never falls back to a different recipe.
- Reuse, restore and rebuild timings are captured separately from API readiness. At least three million-product restores and a cold Pod/cluster recovery are recorded for the selected repository.
- Snapshot retention and cleanup preserve snapshots referenced by retained environment definitions; 72-hour runtime expiry does not erase them.
- The chosen Azure or local object repository has passed repository analysis, version compatibility and operational recovery checks. If no durable repository passes, this batch remains unimplemented and the current rebuild path remains supported.

## More information

- [Restore research and measured limits](../research/index-restoration-options.md)
- [Index recipe implementation](../../lab/index_recipe.py)
- [Current lifecycle](../../lab/lifecycle.py)
- [Elastic restore API](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/restore-snapshot)
