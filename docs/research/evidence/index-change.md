# Frozen index-change walkthrough

The [live result](index-change-live.json) records one complete local walkthrough with the versioned [`title-keyword-v1` mapping](../../../lab/mappings/title-keyword-v1.json). The candidate uses a distinct index on the shared self-managed Elasticsearch cluster. A finite Kubernetes Job loaded it from the same `retail-gb-10k-v1` Blob release as the baseline, then applied a write block. The source API image was the same on both sides, so the mapping change caused the observed result changes.

A second [authenticated control API walkthrough](index-http.json) created both environment kinds, ran a complete 51-query result comparison and removed both. The candidate reached a correct search in 17.703 seconds, changed the same 20 queries and was deleted in 54.031 seconds. This exercises the same routes used by the UI; browser interaction was not separately timed.

| Check | Observed |
| --- | ---: |
| Candidate request to first correct search | 15.094 s |
| Candidate products and write block | 10,000; enabled |
| Mapping hash matched the pinned request | Yes |
| Result preservation | Complete; 20 of 51 ordered top tens changed |
| Synthetic nDCG@10, baseline → candidate | 0.911474 → 0.899054 |
| Candidate read access to baseline / write access to its index | Both denied |
| Candidate environment deletion | 49.828 s; dedicated index removed |
| Shared baseline after cleanup | 10,000 products; write blocked |

The relevance scores use incomplete, positive-only synthetic judgements. Candidate Judged@10 rose from 0.888 to 1.0, so the nDCG difference is not a human relevance conclusion. Complete per-query API results and score details are retained in the two content-addressed Floci reports named in the live result. One startup run does not establish a p95 or capacity at one million products. Job duration, Kubernetes resource use and failed-build recovery still need separate measurement.
