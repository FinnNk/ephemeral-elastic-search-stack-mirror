# Filter search requests

The Search API, browser, capture workers and Gatling runner use the same query,
market and filter context. Each response echoes the applied `filters` object.

## Supported filters

Send an optional JSON object in the `filters` query parameter. Omit it or send
`{}` for an unfiltered search within the GB/GBP/available catalogue scope.

| Field | Value | Matches |
| --- | --- | --- |
| `category` | Array of 1–20 exact strings | Any selected category |
| `colour` | Array of 1–20 exact strings | Any selected colour |
| `material` | Array of 1–20 exact strings | Any selected material |
| `price_minor` | Object with `gte`, `lte` or both | Inclusive price bounds in pence |

Values within one field use OR; different fields use AND. Text matches are case
sensitive; each value is at most 128 characters. Filter JSON is at most 4096
characters. Prices must be integers from 0 to 2,147,483,647, and the lower bound
must not exceed the upper bound. Unknown fields, empty arrays, duplicate values
or keys, malformed JSON and repeated filter parameters return HTTP 400. Brand
filtering and pagination are outside this contract.

## Try a filtered search

With a Search API port-forward on 18088, run this in PowerShell:

```powershell
$filters = '{"category":["footwear"],"price_minor":{"lte":6500}}'
$encoded = [uri]::EscapeDataString($filters)
Invoke-RestMethod "http://127.0.0.1:18088/search?q=running%20shoes&country=GB&currency=GBP&filters=$encoded"
```

The API returns only matching products and a filtered total. No matches is a
successful response with empty `ids` and `results`, and `total: 0`. In the browser,
open **Filter results**, enter exact values and price bounds in pounds, then search.
The page converts pounds to integer pence for the API. The
page address retains the selected filters.

## Freeze a filtered evaluation

Include filters in each query-suite row before publishing its manifest:

```json
{"query_id":"shoes-under-65","query":"running shoes","country":"GB","currency":"GBP","filters":{"category":["footwear"],"price_minor":{"lte":6500}}}
```

Follow the [evaluation runbook](evaluation-runbook.md) to publish the suite and
capture it. Every variant receives the same object. A missing or different echo
makes capture incomplete; fix or redeploy the API and recapture rather than
scoring that run. Selected-query diagnostic replay also retains these filters.

Gatling compilation binds each trace query ID to the frozen query's text, market
and filters. Recompile workloads with the current compiler before running the
current simulation; changed feeder bytes produce a new workload hash. Retained
historical workload reports remain evidence of their original runs.

The shared contract lives in [search_filters.py](../lab/search-app/search_filters.py).
It is included in Search API images, evaluator images and finite capture Jobs.
There is no compatibility reader for older API responses or feeder formats.
See the [verification record](research/evidence/search-request-filters.md).

## Catalogue size

`GET /catalogue` returns the product count for GB/GBP in the environment's index,
including unavailable products. It does not apply the current search or filters.
The storefront shows this count; search results include only available products.
A failed count returns HTTP 502, and the page shows that the size is unavailable.
The standalone demo returns its eight sample products through the same endpoint.

```json
{"products":1000000,"country":"GB","currency":"GBP","mode":"lab"}
```
