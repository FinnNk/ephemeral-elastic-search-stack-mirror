# Local S3 snapshot repository evidence

## Result

The shared self-managed ECK 9.5.4 cluster now uses a regular Elasticsearch S3 repository named `lab-s3`. A separate SeaweedFS 4.47 service stores its objects in the `relevance-snapshot-store` Docker volume. This is independent of the Elasticsearch Pod and data PVC, but remains on the same host. The pinned image digest is `sha256:ce9e796f1fe6f06968f4c04bdaf8f678dad9c8acdfef3d244133d71bfa6bf882`; its manifest includes `linux/amd64` and `linux/arm64`.

| Check | Observed result |
| --- | --- |
| Shared repository | Elasticsearch `_verify` returned one participating node; `_analyze` completed 100 blobs up to 10 MB each / 1 GB total with no reported issues. |
| Isolated cluster replacement | A 10,000-product snapshot restored after deleting its source and again after deleting/recreating the isolated ECK cluster and data PVC. The second restore took 1.359 s. Its 100-blob analysis reported no issues. |
| Million-product source | A disposable `title-keyword-v1` index built from frozen `retail-gb-1m-v1` in 132.125 s, was captured to `lab-s3`, and was deleted before each historical restore. |
| Million-product restores | Three lifecycle restores reached a verified searchable index in **17.219, 17.578 and 17.157 s**. Each retained 1,000,000 products, recipe metadata, write block and ten ordered IDs independently read from the frozen compressed release. |
| Public API | Creating `lab-snapshot-api-check` with the retained recipe selected the `snapshot` path (17.156 s). Its public `search` operation returned 20 product IDs for `running shoes`. The environment and index were deleted afterwards. |
| Store restart | The SeaweedFS container restarted with its named volume. A further verified million-product restore took 17.203 s. |

Times measure index restoration and verification; they exclude environment deployment, API startup and any cold remote-network effects. These are few local observations, not p95 estimates. The ignored run record is `.lab/evidence/million-s3-restore.json`; [the repeatable check](../../../lab/verify_snapshot_recovery.py) independently computes the ordered sample. [The setup script](../../../lab/setup_snapshot_store.py) configures and analyses the shared repository. [The isolated manifest](../../../research/snapshot-restore/s3-probe.yaml) supports a repeat of the cluster-replacement check.

## Boundaries and operation

- Bucket: `lab-index-snapshots`; base path: `shared-v1`; local endpoint: `http://relevance-snapshot-store:8333`. Generated S3 credentials live in ignored `.lab/snapshot-s3.json` and the `lab-s3-snapshot-client` Kubernetes Secret, never in Git. Restrict access to the local machine and controller.
- The SeaweedFS volume survived a store restart and the repository survived separate Elasticsearch cluster/data-PVC replacement. Neither check demonstrates survival of host or Docker-volume loss. The container currently joins the k3d Docker network; a full network rebuild requires reconnecting or recreating it while retaining the volume and credentials.
- The current controller saves one snapshot per immutable recipe SHA-256. Snapshots remain after a 72-hour environment expires. There is no automated snapshot retention or off-host copy yet; both need a policy before long-running use. Only one cluster should write the repository; register a second cluster read-only when restoring from it.
- The Elasticsearch S3 repository passed verification and analysis here. Floci 0.13.0 and Azurite 3.37.0 failed Azure repository verification on batch deletion in local probes. These results say nothing about real Azure Blob. Test the Azure repository, workload identity, cross-cluster restore and timing in a tenant before using it for recovery commitments.
- Missing or incompatible snapshots must fall back to the pinned recipe and product release. A historical snapshot still requires a compatible destination Elasticsearch/index version. The repository accelerates rebuilds; the recipe remains the recovery authority.

Sources: [Elastic S3 repository requirements](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/s3-repository), [repository analysis API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-snapshot-repository-analyze), [SeaweedFS project](https://github.com/seaweedfs/seaweedfs), [ECK snapshot configuration](https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/cloud-on-k8s).
