# Historical index recipe check

The live local check used the 10,000-product synthetic release and Elasticsearch 9.5.4. It stored two content-addressed recipes in Floci: the original title-as-`keyword` mapping and a changed title-as-`text` mapping. Both specified the same frozen product hash, indexer source and digest-pinned image.

| Check | Observation |
| --- | ---: |
| Original dedicated build | 8.703 s; 10,000 products |
| Historical rebuild after deletion | 8.344 s; 10,000 products |
| Historical mapping lookup | Disabled during rebuild; stored recipe used |
| Ordered sample after rebuilding | Same first ten product IDs under an explicit ID sort |
| `running shoes` title matches, old → new schema | 0 → 540 |
| Check indices after run | Both removed; shared baseline retained with 10,000 products |
| Existing 10,000- and 1,000,000-product shared indices | Verified against their published recipes without rebuilding |

The old recipe SHA-256 was `511b1d4aa37af0313af09eb4d3a15ab6edb93a9feb87a18b17429cae7758b6e2`; the changed recipe SHA-256 was `0d71b7f2d3b0c7f4a819c75a53b8160699df758f36d2a1ae1e6f9338638242ef`. The script saved the native local result under ignored `.lab/evidence/historical-index-rebuild.json`. The check rebuilt a 10,000-product index twice; it does not establish million-product timing, a p95, snapshot restore speed, or equivalence of every result. The production comparison surface remains the two search APIs.
