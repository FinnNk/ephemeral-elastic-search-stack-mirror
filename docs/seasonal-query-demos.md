# Try seasonal query sets

Use the Halloween and Christmas datasets to demonstrate how the same API behaves
with different restored products and Redis rewrite data. There are three query
sets: eight Halloween searches, eight Christmas searches and ten shared rewrite
and control searches. The files are in delivery-source's `evaluation/queries/`.
The [paired data guide](paired-data-restores.md) describes creating environments
by name or simulated date.

## Explore through the control UI and a notebook

Fresh setup publishes these additional inputs automatically. To prepare them in
an existing lab after accepting this batch, run from the lab repository root:

```sh
uv run --locked python lab/prepare_data_versions.py --publish
uv run --locked python lab/prepare_seasonal_queries.py --publish
```

Expect two seasonal-query preparation messages and manifest hashes. They are
also retained in `.lab/seasonal-queries/references.json`. This publishes additional
immutable inputs; it does not change the standard frozen suites or their pins.

1. Create two ready environments on the Halloween dataset to compare API changes.
2. In **Compare frozen environments**, choose the baseline and candidate.
3. Copy Halloween's `query_manifest_sha256` into **Query-suite manifest SHA-256**.
   The combined suite contains the original 54 queries and all 26 extra queries.
4. For **Relevance**, also copy the matching `judgement_manifest_sha256` into
   **Judgement-set manifest SHA-256**. Its original 968 labels are unchanged;
   the new queries have no invented grades. The resolver may infer labels or
   abstain. Read judgement coverage and the reasons for any unavailable metrics.
5. Select an exploratory notebook if desired and run the comparison. Open its
   report and **View notebook** link when complete.
6. Repeat with two Christmas environments and the Christmas manifest hashes.

Use the same API release on both sides for a data demonstration, or a candidate
API change on one side for a ranking demonstration. Each comparison requires a
matching frozen catalogue on both sides. Compare the two event reports as data
examples; their score differences are not evidence of a ranking regression.
The control comparison reports the combined suite; separate per-set and combined
metrics are available through the source PR workflow below.

## Include separate query sets in a source PR

In delivery-source, open `examples/seasonal/selection.json`. Copy its three
`additional_query_sets` entries into `gate/selection.json`, retaining existing
selected variants and their intended expectations. The supplied example uses
`ranking-change` for `ranker-a`; it is not a universal intent for every change.
Commit and push the selection change. The normal PR comparison reports each set
and combined metrics. All three extra sets are report-only by default; the
standard frozen suite remains required.

The queries are already tracked, so repeated demos can select one event set or
all three without reverting API code. To demonstrate Redis directly, search for
`seasonal decorations`, `party decorations`, `spooky decorations` and `festive
decorations`. The Redis decision has a `redis:` prefix when lookup succeeds.
Only the selected season's rules apply; absent rules use the local fallback.
Generic decoration terms may still return products for an opposite-season query.

The source PR workflow uses its configured catalogue. Selecting a query set does
not switch that catalogue to Halloween or Christmas. Use the control UI's named
event environments for seasonal data demonstrations.
