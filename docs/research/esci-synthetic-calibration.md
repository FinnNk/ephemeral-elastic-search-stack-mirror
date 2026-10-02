# ESCI-informed synthetic data profile

Historical synthetic-release research. Current workflows use the [ESCI catalogue](../esci-catalogue.md); the measurements and frozen inputs below retain their original conditions.

The [million-product release](million-synthetic-release.md) is wholly synthetic. [ESCI-S](https://github.com/shuttie/esci-s) and the [original ESCI dataset](https://github.com/amazon-science/esci-data) supplied **aggregate modelling references** for its generator profile. The `retail-gb-10k-v1` release remains frozen and unchanged. No ESCI product, query, identifier, image, review or judgement is copied into a lab release.

The machine-readable [profile](../../lab/profiles/esci-informed-uk-v1.json) records the source URLs, sample hash, observations and generator decisions. [The calibration script](../../lab/calibrate_esci.py) reduces the ESCI-S sample to aggregates; it does not emit source records.

## Reference observations

ESCI-S reports 1,661,908 scraped products and publishes the shares of its ten largest page templates. They cover 62.76% of the full set; the other 37.24% needs an explicit synthetic category model. These are Amazon catalogue proportions, not measured UK retail proportions. [Source: ESCI-S README](https://github.com/shuttie/esci-s#statistics).

The script read the published 10.1 MB compressed sample (SHA-256 `c88659e2ed4a9c3ed16487ef27a37ae8dc95226723d6b0ed5dcbd422d587eb55`). Of 4,487 records, 2,919 were US-locale products or books. The table below describes that **sample subset**, not the full dataset or a UK catalogue.

| Field | Present | Size when present |
| --- | ---: | --- |
| Title | 100.0% | 96 characters at p50; 187 at p90 |
| Description | 83.4% | 1,554 characters at p50; 3,763 at p90 |
| Bullets | 84.8% | 6 entries at p50; 14 at p90 |
| Attributes | 57.7% | 5 entries at p50; 7 at p90 |
| Category path | 94.7% | 4 levels at p50; 6 at p90 |
| Price | 29.2% | Original price text, not a dependable GBP minor-unit value |

The original ESCI large version reports 130,652 queries, 2,621,288 assessed query-product pairs and roughly 20 judgements per query, with Exact, Substitute, Complement and Irrelevant labels. These are pooled assessments, so an unjudged result must remain *unjudged*. [Source: original ESCI README](https://github.com/amazon-science/esci-data#dataset).

## Generator decisions for the million-product release

| Concern | Synthetic modelling decision |
| --- | --- |
| Market | Generate UK products and queries with `GB`, `en-GB` and `GBP`; use integer pence. ESCI does not supply a UK locale. |
| Category mix | Use the published ESCI-S top-ten template shares (62.76%) and allocate the remaining 37.24% across electronics, grocery, garden, pets and stationery. These are modelled departments, not measured UK shares. |
| Text and structure | Generate original titles, descriptions, bullets and attributes near the observed length, presence and hierarchy-depth bands. Keep the separate 10,000-product release for rapid local development. |
| Price and stock | Generate category-dependent GBP prices and availability. ESCI-S sample price presence is too sparse for a filterable UK price field; availability is not supplied as a dependable source field. |
| Behavioural features | Generate rating and review counts numerically with declared distributions. Do not copy reviews or image URLs. Synthetic popularity remains separate from genuine behavioural evidence. |
| Queries and labels | Generate 1,000 distinct synthetic requests and 20 graded products per query using documented E/S/C/I rules. Include 20 held-out no-match queries and distinguish unjudged products from Irrelevant. These labels are not human assessments. |
| Frozen release | Record profile ID and hash, generator revision, seed, market, source-reference hashes, assumptions, product/query/judgement hashes and byte counts in the new manifest. The same canonical objects build baseline and mapping-change indices. |

The million-product run uses this text profile. Its compressed product object is 104,911,501 bytes, and its first index store is 664,180,744 bytes. The [release note](million-synthetic-release.md) records sample field distributions and indexing time. The short-title 10,000-product timing is not a scale estimate. API-only environments share the compatible frozen index; mapping changes build a separate index from the same release.

## Reproduce the aggregates

Download the linked [ESCI-S sample](https://github.com/shuttie/esci-s/blob/master/sample.json.gz) into ignored `.lab/references/esci-s-sample.json.gz`, then run from the repository root:

```powershell
python lab/calibrate_esci.py --sample .lab/references/esci-s-sample.json.gz
```

The script checks the compressed file hash before processing. Its output is the aggregate-only profile; the source sample is not committed or indexed. A future source revision requires a new profile ID, source hash and review of the modelling decisions.
