# Compare seasonal searches

The repository includes three ready-to-use query sets in `evaluation/queries/`:

| Set | Queries | Use |
| --- | ---: | --- |
| `halloween` | 8 | Costumes, pumpkins, lighting and party decorations |
| `christmas` | 8 | Ornaments, stockings, wreaths, lighting and decorations |
| `seasonal-controls` | 10 | Shared Redis lookups, case handling and ordinary controls |

Use `selection.json` as a copy/paste example for `gate/selection.json`.
If your branch already selects variants or additional sets, copy only the three
`additional_query_sets` entries into that file. Preserve the intent appropriate
to your change. All three sets are report-only; the frozen suite remains required.
The comparison reports each set separately and the combined results.

Run the Halloween set against a Halloween environment, then the Christmas set
against a Christmas environment. The controls make the same `seasonal decorations`
request on either dataset; Redis chooses the event-specific rewrite. Inspect the
reported rewrite decision as well as the returned products. An opposite-season
query can demonstrate the selected catalogue's omissions; it is not guaranteed
to return no products because Elasticsearch can match generic decoration terms.

For ranking comparisons, keep both API environments on the **same** catalogue
and use the same query sets and resolved judgement snapshot. Separate runs on
different catalogues demonstrate data differences, not a ranking regression.
These curated queries have no hand-written relevance grades. The judgement
resolver may infer labels or abstain; review coverage and unavailable metric
reasons rather than assuming nDCG is present or that the gate will pass.

For exploratory control-UI and notebook runs, the lab's seasonal-query publisher
provides a combined suite and matching retained-judgement manifest for each event.
Follow [the lab seasonal guide](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/src/branch/main/docs/seasonal-query-demos.md).
