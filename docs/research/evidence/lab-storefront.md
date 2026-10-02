# Lab storefront verification — 2 October 2026

The storefront shows the current catalogue size and a compact retail product grid.
Source PR #18 uses commit `2b4a95da1db3d4ca3f4d5a4aed0f300f63e718c8`.
The [machine-readable record](lab-storefront.json) pins both images, the frozen
catalogue, capture worker and signed report.

| Check | Observed result |
| --- | --- |
| Application contracts | 16 tests passed locally; final multi-platform CI build #77 passed |
| Source merge checks | Build #77 and relevance #78 attempt 2 passed for the exact PR head |
| Live catalogue | `GET /catalogue` returned 1,000,000 GB/GBP products from `retail-gb-1m-v1` |
| Desktop and mobile | Edge at 1440×1050 and 390×844; cards, count and three-line titles inspected; no horizontal overflow |
| Price controls | £65 maximum returned only prices at or below £65; saved address restored the pound input |
| Count unavailable | Intercepted HTTP 502 displayed the unavailable message; this was a browser fixture |
| Standalone demo | Eight-product count, search, pound conversion and saved-address reload passed without Elasticsearch |
| Frozen comparison | 1,000 fresh queries against each release; identical ordered top-ten IDs for every query; gate verdict `pass` |
| Documentation | Updated source README and API contract reviewed; plan/reference links and rendered pages checked |

The first multi-platform build failed because ARM64 emulation was absent after
Docker restarted. Re-registering the existing lab emulator restored the build.
The relevance check initially blocked while exact-source evidence was absent;
it was rerun after the signed report was published.

Synthetic labels were informed by earlier recall pools. This demonstrates result
preservation and evidence transport, not independent human relevance or performance
capacity. The count includes unavailable products; search returns available products.
No search-result caching, schema translation or compatibility fallback was added.

The final [preview](https://lab-storefront-candidate-6f78a040.preview.relevance.test:34443/)
is retained for review. It uses a disposable Argo application and the shared frozen
index. Superseded previews and proof baselines were removed. Remove the final
application and namespace after review; it is a manually retained review fixture,
not a control-managed environment lease. Integration remains on merged source main.
