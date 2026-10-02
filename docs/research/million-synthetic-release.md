# Million-product synthetic UK release

Historical synthetic-release research. Current workflows use the [ESCI catalogue](../esci-catalogue.md); the measurements and frozen inputs below retain their original conditions.

`retail-gb-1m-v1` contains 1,000,000 original synthetic products, 1,000 distinct synthetic requests and 20,000 rule-based graded assessments. The [generator](../../lab/release_million.py) streams a deterministic gzip product object; the [profile](../../lab/profiles/esci-informed-uk-v1.json) and [calibration note](esci-synthetic-calibration.md) record the ESCI aggregate references used to choose its shape. The generator copies no ESCI products, queries, labels, identifiers, images or reviews.

| Frozen property | Value |
| --- | ---: |
| Market | GB / GBP / `en-GB` |
| Product object | `products.jsonl.gz`, 104,911,501 bytes |
| Product object SHA-256 | `a6c78afb7df078016828a8a9a93b88b2d1db6a16ef64080a37dc33c23c2cc1d6` |
| Query object SHA-256 | `4ab64cfbb3a3a581593ec380f1eae2a5c33ecbce791578ed7f814be06eb05946` |
| Assessments | 20 per query, with E/S/C/I grades 3/2/1/0; 20 held-out no-match phrases |
| Generator seed | `20260927` |

The 20 intended no-match phrases in the original suite retrieved incidental products on the shared-index APIs under broad lexical matching; the dedicated title-keyword mapping returned zero for them. A separate [frozen additional request](../../lab/million-no-match-v1.jsonl) verifies an actual zero-result response from all three million-product APIs without changing this release.

The top ten published ESCI-S template shares account for 62.76% of the category allocation. Five named modelled departments allocate the remaining 37.24%: electronics, grocery, garden, pets and stationery. Types, brands, product text, GBP prices, availability, popularity, ratings, review counts and every assessment are generated anew. Text paragraphs intentionally repeat generated phrases to reach the target length bands; lexical diversity is lower than in a real catalogue. Titles and descriptions are indexed, as are bullets. Attribute objects are stored but not indexed by the current mapping.

A deterministic 20,000-product sample of the generator measured:

| Field | Presence | p50 | p90 |
| --- | ---: | ---: | ---: |
| Title characters | 100% | 98 | 164 |
| Description characters when present | 83.18% | 1,609 | 3,717 |
| Bullet count when present | 84.66% | 9 | 14 |
| Attribute count when present | 57.29% | 6 | 7 |
| Category path count when present | 94.69% | 5 | 5 |

These sample measurements are checked with [`profile_million.py`](../../lab/profile_million.py). They calibrate shape, not search quality. Availability was 93.08% in the sample; median price was £40.50. The original 20-per-query assessment set is sparse across a million products. A separate [frozen pooled set](../../lab/pool_million.py) has 39,759 assessments: the original labels plus the baseline and both candidate top tens. It retains original grades and applies deterministic rules to newly observed IDs. Its manifest pins the original judgement hash, two source report hashes and pool hash. It assesses those known lists symmetrically but may leave future candidate results unjudged.

The [bounded loader](../../lab/load_million_release.py) publishes the exact compressed object and creates a write-blocked index. Its indexing worker downloads and verifies the compressed bytes, then sends batches of 1,000 products. The first shared-index build took 135.563 seconds including a 23.875-second publish check; the Job indexed 1,000,000 documents in 103.565 seconds, and the index store was 664,180,744 bytes. These are single local measurements on Windows 11/k3d with a 1 GiB Elasticsearch heap, not a p95 estimate or Azure capacity prediction.
