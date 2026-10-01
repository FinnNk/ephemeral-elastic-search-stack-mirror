# Search filter verification — 1 October 2026

The current API and capture workers were checked against a disposable index in
the real local Elasticsearch service. The fixture contained ten synthetic
products, including unavailable and non-GB records. The index was deleted after
the check; existing frozen catalogues and schema-evolution examples were untouched.

| Check | Result and scope |
| --- | --- |
| Real Elasticsearch and HTTP Search API | Five filter cases passed through paired and three-variant capture: 25 API requests. Membership, filtered totals and echoed filters matched expectations. |
| Contract and demo tests | 12 tests passed, including invalid input, price bounds and empty outcomes. |
| Capture, proxy and traffic tests | 26 tests passed, including identical dispatch, mismatched echoes, finite-Job contract packaging, diagnostic replay, proxy lease handling and frozen feeder context. |
| Browser | Filtered results, edited price bounds, reload and unsupported-filter rejection passed in headless Edge. |
| Image packaging | Search API and evaluator Docker images built; the evaluator imports the shared contract. |
| Gatling | The Java simulation compiled. A two-request filtered demo probe passed with zero failed requests; it checks runner wiring and it is not a capacity measurement. |

The [raw Elasticsearch check](search-request-filters.json) was produced by
[prove_search_filters.py](../../../lab/prove_search_filters.py). It used the
current HTTP handler and a host-side TLS transport to Elasticsearch. Capture
workers ran on the host; this does not claim a new Kubernetes release or finite
capture Job was deployed.

These are functional checks, not relevance improvement evidence, merge-gate
approval or load capacity results. The source PR still needs the normal
exact-commit evaluation and review before deployment. Existing source/demo work
in delivery-source PR #13 is a prerequisite.
