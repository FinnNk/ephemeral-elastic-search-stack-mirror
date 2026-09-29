# Three-variant synthetic million-product proof

**Run:** 29 September 2026, local k3d lab. All products, queries and labels are synthetic. This is a finite worker and evaluator proof, not a release-quality relevance result.

| Input or result | Measured value |
| --- | ---: |
| Frozen catalogue and query suite | 1,000,000 products; 1,000 UK/GBP queries |
| Runtime variants | `ranker-a` (default), `ranker-b` (baseline), `ranker-c` |
| Capture | 3,000 public Search API requests; 1,000 complete query rows; 68.86 s Job time |
| Shared runtime | One Search API deployment, one Elasticsearch index, three explicit boost configurations |
| Pooled returned pairs | 10,967 distinct query/product pairs through rank 10 |
| Stored labels in pool | 21 |
| Pinned KServe model outcomes | 10,946 abstentions; 0 errors; 0 new labels |
| Judged top-10 coverage | A: 0.21%; B: 0.09%; C: 0.21% |
| nDCG@10 | A: 0.001959; B: 0.000581; C: 0.001959 |
| Changed queries against B | A: 97/1,000; C: 97/1,000 |
| Gate result for A | `blocked` at the policy's 80% minimum coverage; metric delta was +0.001378 |

The Search API returned up to 20 products. The first worker run rejected these valid responses because it expected at most 10; the corrected worker validates all 20 and retains the first 10. Its source SHA-256 was `aa7cab33ed06f1f66f99260a396f3e35247faeeda5cad0d3451981c8939b3178`. The live image was `nexus.localhost:18185/search-api@sha256:93700580c32b5d5de27259fa79bdf13d9cc957403f53938ba5e2714cfa1715d6`.

The first judgement run recorded 10,946 inference failures and marked the report incomplete. The KServe pod had no endpoint: its storage initialiser rejected a non-empty model volume after restart, and MLflow's object-store EndpointSlice pointed at an old local container IP. The endpoint was reconciled with `lab/setup_judgement_secrets.py`; a fresh KServe pod loaded the model. The second run produced 10,946 abstentions and a complete report. The initial failure report remains separate from the successful frozen report.

The complete report SHA-256 is `9699297a6ae11e7e91b9c14875688fa959aea898b1af1acc0ffead81c0110785`; observation SHA-256 is `9bc41de483c51d649e02d805e0266d31f1fb4fa3121599826941b578f433a853`. The gate CLI returned exit code 4 and retained the measured delta and 0.21% selected coverage. That local CLI check used an explicitly synthetic source SHA and signing keys; it was not an approval for a source PR.

The proof deployment was created as a disposable Kubernetes namespace and used the existing million-product index. The finite capture Job and offline evaluator ran from this branch. The retained observation envelope was assembled from the Job's verified rows rather than through `evaluation/capture.py`, because that command requires an Argo-managed frozen environment definition. The current demonstration therefore proves the public API, worker, pooled judgement service, evaluator and gate contracts. A source-bound PR gate run with an Argo-managed variant environment remains the next integration check. The low judged coverage blocks promotion until better labels or a model produce adequate evidence.
