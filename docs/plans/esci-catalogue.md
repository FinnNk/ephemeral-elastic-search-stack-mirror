# ESCI catalogue

Replace the generated retail catalogue with published English ESCI products and labels, enriched with ESCI-S metadata. Use GBP prices with the original numeric amounts. Keep a small, explicitly selected demo catalogue.

Status: implemented for review. Runtime evidence is [recorded here](../research/evidence/esci-catalogue.md). The source PR gate remains blocked by published-label coverage.

## Scope and constraints

- Default: the English US catalogue (1,215,854 products), 1,000 test queries and their published labels. A deterministic product limit is available.
- Preserve product IDs, text and E/S/C/I labels. Do not invent labels for unjudged results.
- Use source prices where available; generate missing prices deterministically. Document stock and popularity assumptions.
- Pin source checksums and importer configuration. Freeze catalogue, queries and judgements independently.
- Keep shared indexes, snapshot recovery and schema-evolution demonstrations. No adapters for superseded generated catalogues.
- Preserve historical evidence under its original conditions. Current guides must describe the new defaults.

## Acceptance criteria

| Area | Required evidence |
| --- | --- |
| Import | Verified source checksums; valid product/query/label references; reproducible bytes |
| Prices | $19.99 becomes £19.99; generated prices are distinguished from published values |
| Defaults | Normal environment creation and evaluation select ESCI; demo size is configurable |
| Runtime | Frozen index loads, returns source products, and supports captured comparisons |
| Recovery | Existing recipe and snapshot paths accept the imported catalogue |
| Documentation | Setup, contracts, diagrams and source templates agree with current behaviour |

## Implementation

1. Build a streaming source importer and provenance contract; test edge cases.
2. Import the default and demo packs; pin independent input manifests.
3. Consolidate runtime defaults and index definitions; publish and deploy the new catalogue.
4. Verify search, labels, comparison and recovery; synchronise guides and diagrams.
5. Record evidence, update the roadmap and open the completed batch for review.

## References

- [Source lock](../../data/esci-sources.json)
- [ESCI](https://github.com/amazon-science/esci-data) and [ESCI-S](https://github.com/shuttie/esci-s)
- [Technical authorship](../technical-authorship.md)
- [Independent inputs](../data-evaluation-contracts.md)

## Next batch

[Published-label coverage and gates](esci-coverage-gates.md) is the next detailed batch. Resume the developer walkthrough after agreeing how the existing gate should treat this catalogue; keep result preservation and relevance evidence separate.
