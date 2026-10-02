# Use the ESCI catalogue

The lab normally uses **1,215,854 English ESCI products**, **1,000 test queries** and **18,981 published judgements**. API and ranking experiments share a frozen index. A smaller subset is available for live demos.

## Data and lab assumptions

| Field | Source or rule |
| --- | --- |
| Product IDs, titles, descriptions, bullets, brands | Original English US ESCI records; spelling is retained |
| Categories, materials, ratings, review counts | ESCI-S metadata where available; missing values remain empty or null |
| Query suite | Deterministic sample of the ESCI large test split; whitespace is normalised to match API requests |
| Labels | Published E/S/C/I assessments map to grades 3/2/1/0; absent pairs remain unknown |
| Prices | A displayed $19.99 becomes £19.99. For a range, use its lower displayed amount. No exchange rate is applied |
| Missing prices | Deterministic ASIN-based amounts from £1.99 to £499.99; each product marks its price source |
| Market | GB and GBP for lab requests; source locale remains US in provenance |
| Stock and popularity | Every product is available; popularity is zero. These are lab assumptions, independent of labels |
| Traffic | Synthetic timestamps and frequencies over the selected queries; Gatling runs the load tests |

ESCI-S metadata matched 1,018,263 products. It supplied 297,716 prices; 918,138 prices are generated. Customer reviews and images are not imported. These choices support development workflows, not UK market or production traffic modelling.

## Import and publish

Use Python from the repository root. The commands below work in PowerShell, bash and zsh. Set `LAB_STATE_DIR` to your retained lab state directory first; otherwise it defaults to `.lab` in this checkout. Allow space for the approximately 4.8 GB source download and SQLite staging files. The local Floci Pod uses an 8 GiB memory limit for large Blob objects; lower allocations were killed during catalogue publication. Repeat publication checks existing objects before uploading.

Prerequisites: a running lab, retained operator state and the Azure/evaluation dependencies from lab setup. Keep port forwards to `platform/svc/floci` on **14577** and `platform/svc/shared-es-http` on **19200** open while publishing and loading. These are operator endpoints; developer preview URLs remain automatic.

```text
python -m pip install -r data/esci-requirements.txt
python lab/import_catalogue.py --download
python lab/import_catalogue.py --release esci-gb-demo-v1
python lab/publish_default_inputs.py
python lab/load_release.py
```

The importer checks the [source lock](../data/esci-sources.json), writes deterministic compressed products, queries, labels and provenance, and refuses to replace frozen bytes. A repeat with the same inputs verifies and reuses the release. The publisher requires the running Blob Storage endpoint; the loader requires the lab kubeconfig and Elasticsearch endpoint. Follow the [operator access guide](control-runtime.md) for retained state and [index recovery](index-recovery.md) for index access.

`lab/default_inputs.json` pins the independent manifest hashes. Publication must reproduce them. A source, selection or augmentation change requires a new release ID and reviewed hashes; it cannot silently replace an existing default.

## Configure a small demo

[Catalogue profiles](../lab/catalogue-profiles.json) own the default release and optional demo product/query limits. The initial demo has 10,000 products and 50 queries. Select `esci-gb-demo-v1` explicitly in the control UI or with `--release esci-gb-demo-v1` where supported. Deployment commands use `--dataset esci-gb-demo-v1`.

To change the demo size, add a new release ID with the desired `products` and `queries`, import it, publish its manifests and pin their hashes. Every product needed by the selected published labels is included before filling the remaining product slots. A limit too small for that pool fails with the required count.

## Frozen indexes and labels

The full catalogue and demo use the same mapping. Index identity depends on catalogue bytes and the mapping recipe, independently of query and label revisions. Reuse, cloning, snapshot restore and rebuild retain their existing contracts. Historical schema demonstrations keep the explicitly frozen definition.

Published labels cover a subset of possible results. Read coverage with relevance scores; inference may abstain on gaps. A changed recall set requires a fresh judgement snapshot before scoring all variants against the same labels. In the first full-catalogue comparison, published labels covered 29.7% of returned top-10 results; the existing 80% merge gate blocked. See [verification and limits](research/evidence/esci-catalogue.md).

## Attribution

[ESCI](https://github.com/amazon-science/esci-data) and [ESCI-S](https://github.com/shuttie/esci-s) are supplied under Apache 2.0. Source revisions and file SHA-256 checksums are pinned; the unversioned ESCI-S download must match its checksum. [Licences and notices](../data/notices/) are retained in the repository. Raw source files and catalogue objects stay in retained state and Blob Storage, outside Git.
