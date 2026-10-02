# Lab storefront

Give the search page a simple retail appearance while keeping its lab purpose clear.

## Scope and acceptance

| Change | Acceptance |
| --- | --- |
| Header and copy | “Lab storefront”, a short synthetic-data note and direct search labels; no baseline claim |
| Catalogue size | Count all GB/GBP products in the current index; show an unavailable state on failure |
| Product cards | Category, product name, brand and GBP price, without technical identifiers |
| Filters | Pound inputs become integer pence; saved addresses restore those inputs |
| Diagnostics | Timing and availability details remain under “Search details” |
| Standalone demo | Use the same page, with its eight-product count and an explicit offline label |

Keep ranking, query understanding and the search response contract unchanged.
Use the existing Elasticsearch pool and tracing for the count. Do not add carts,
checkout, product images or new dependencies.

## Verification

Run the application contract tests, inspect desktop and mobile layouts, and check
search, price filters and address reload. Publish fresh comparison evidence for
the exact source PR build before declaring its merge gate ready. Synthetic labels
can demonstrate result preservation; they do not establish human relevance.

Implementation: [frontend](../../lab/search-app/index.html),
[API](../../lab/search-app/app.py), [demo](../../lab/search-app/demo.py).
See the [request contract](../search-request.md) and [delivery guide](../delivery.md).

## Status

Implemented for review. Application tests and desktop/mobile browser checks passed.
The [verification record](../research/evidence/lab-storefront.md) identifies the
exact source build and frozen comparison.

Next batch: [developer walkthrough](developer-walkthrough.md).
