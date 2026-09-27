# Historical index recipes

## Intent

Make a deleted historical index reproducible after mapping or indexer code changes, while retaining shared-index reuse and the canonical Blob-to-bulk build path.

## Constraints

| Area | Constraint |
| --- | --- |
| Source of truth | Synthetic frozen release objects remain immutable in Blob storage. A recipe must identify its exact product object and release manifest. |
| Schema | Pin complete mappings and settings. An old recipe must not read the current mapping file during recreation. |
| Runtime | Pin the Elasticsearch version and indexer source and image digest. Reject an incompatible engine version. |
| Safety | A shared release-named index with a different schema must not be overwritten. Dedicated schema variants use separate names and are removed with their environments. |
| Existing records | Older environment records have no recipe. Do not infer an exact historical schema from a mapping hash alone. |
| Delivery | Commit on a branch, open stacked Gitea and GitHub backup PRs, and await review before merging. |

## Acceptance criteria

- New shared and dedicated environment records retain a content-addressed index recipe in Blob storage and its SHA-256 in lifecycle metadata.
- Creating an environment with a previously pinned SHA-256 uses the stored mapping, settings and indexer even if local mapping source has changed.
- Two dedicated versions can coexist on the shared Elasticsearch cluster; a conflicting shared index fails without deletion.
- A disposable live test rebuilds a historical index, reproduces its ordered sample, demonstrates changed schema behaviour and removes only its check indices.
- Recipe or release hash mismatch, tampered worker source and incompatible Elasticsearch version fail before index creation.

## More information

- [Frozen data and environment contract](../prototype-design.md#frozen-dataset-contract)
- [Existing index-change evidence](../research/evidence/index-change.md)
- [Index builder](../../lab/index_candidate.py)
- [Lifecycle](../../lab/lifecycle.py)
