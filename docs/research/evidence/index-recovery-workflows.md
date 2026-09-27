# Index recovery workflow check

27 September 2026, local Windows x64 lab, Elasticsearch 9.5.4. All products were generated from the frozen synthetic `retail-gb-10k-v1` release.

| Path | Check | Result |
| --- | --- | --- |
| Historical recipe | Existing schema-evolution check rebuilt the old mapping after the current mapping changed and preserved ordered IDs. | Passed in batch 7a. |
| Live clone | Built a disposable recipe-marked dedicated index, cloned it into another dedicated name, then checked recipe marker, mapping, settings, count, write block and ordered IDs. | **1.219 s** to verified clone. Both disposable indices removed. |
| Regular snapshot | On the isolated `lab-fs-probe` ECK cluster, saved the disposable 10,000-product index with recipe metadata, deleted its source, restored into a separate name, then checked the frozen ordered IDs and index contract. | **1.203 s** to verified restored index. Probe cluster and repository PVC removed. |

The original shared 10,000-product and million-product indices lack recipe markers, so the exact-clone selection correctly refuses to use them as sources. They remain available for the existing shared-index reuse workflow. The shared ECK cluster was green after probe cleanup and was again the only Elasticsearch cluster; its data PVC remained bound.

The filesystem snapshot was a mechanism check, not a durable repository qualification or a public Search API readiness measurement. The shared serving cluster still has no configured snapshot repository. Million-product clone and restore timings from the preceding research are in [index restoration options](../index-restoration-options.md). A durable repository, in-cluster lifecycle run and Azure compatibility test remain open.
