# Exploratory notebook verification

**30 September 2026 · local k3d lab**

The `comparison-explorer.ipynb` demo ran under Papermill as a finite Kubernetes Job. The active control Pod submitted the Job using its existing lab namespace permissions. The installer had prepared the fixed `lab-notebooks` namespace and Blob-only network policy; the control service account received no NetworkPolicy permission.

| Pinned evidence | Value |
| --- | --- |
| Synthetic relevance comparison report | `eb6879b6491ca845ab9ea4891135ef9fa8c85a1e3faa944ccb68bbee50648dea` |
| Notebook source SHA-256 | `56064e207e5c5795ee3d38e2821cac9d3604d5d1e9a92cb890d2c3015d87a6f0` |
| Papermill runner image | `nexus.localhost:18185/lab-notebook@sha256:7d702910b27b054886779701cae8a3378e2fb731b1bd88337372271745fc2ba4` |
| Executed notebook SHA-256 | `f168c2a3de842a6be783f2f495eb5cdb510baebaf68030f46eb96126fee5cb36` |
| Retained notebook | `runs/notebooks/f168c2a3de842a6be783f2f495eb5cdb510baebaf68030f46eb96126fee5cb36/executed.ipynb` |
| In-cluster task duration | 5.27 seconds |

The retained notebook was downloaded again and its SHA-256 checked. Its executed cells reported 50 queries, 20 changed top-ten result lists and mean Jaccard@10 of 0.6928. The source report's relevance verdict remained `measured`. Both amd64 and arm64 runner images were published under the multi-architecture digest; execution was checked on this machine's amd64 lab node.

The same active control Pod also ran the notebook over a retained 1,000-query result-regression report (`c0abccc22d3834ea3c9f059dfaecd209c49e507002a0b8723108b661b12a80fc`, 818,529 bytes). The task completed in 6.209 seconds and retained executed notebook SHA-256 `78721758476e574433a8ebefbb2d9ea081636f6274209f6b010f9368b11c3560`. Its cells counted 1,000 queries and 1,000 changed top-ten lists. This verifies notebook execution at the current query-suite scale, not search or evaluation performance at that scale.

The offline evaluator's `--notebook` post-step ran after retaining a 1,000-query pair report (`ea125627d79430904c945b389fe895c14293e2225ea755de10fd356b528b82f1`). With the final example source, a repeat Job retained executed notebook `05d82fa1dda0fd2e375da85c013c0eade015ac17550823183d3c6c3edbf658c7` and receipt `8ce8240342099e1526aab087976500cba2a6e423774f42fb6d2a8882fa6cad41`. It printed baseline and candidate metrics, coverage and metric deltas. The pair had zero metric delta and very low judged coverage; it is a wiring check, not evidence of relevance quality.

The N-way post-step used the frozen synthetic `variant-proof/evaluation.json` with 1,000 queries and three variants. It retained report SHA-256 `16ed6e5dd8570ddfde7b30d0fff40e484522bc5f49afc9d2de0239a6bb0ab68d`, executed notebook `fc000fd481d18bc3d2394fe743a1139638e04aeec0118cafd64a6d3f6067a296` and receipt `3810688e8fc8c7af08e4b4f3e4608b2c776540930c3e554803b95c79a6a6191c`. Its cells identified `ranker-a` as default and `ranker-b` as metric baseline and printed all three sets of metrics, deltas, coverage and changed-query fractions. Judged coverage was around 0.1–0.2%; no release-quality conclusion follows from this fixture.

The final control image (`nexus.localhost:18185/lab-control@sha256:baa5ead3bbae39647ee3a9decd950bb4f14422b7293748e6cc6531b9549782aa`) rolled out and passed its read-only smoke check inside the Pod. That Pod ran the final example source against the frozen variant report and retained executed notebook `e5fa0ae6f022b20c284fd6e20684a391a53d570e66d4e0d36cc04aed7257cfb8` with receipt `47a363489514f2c758d17d52c291367a3c84b00980dc20b9a67f79d65023ffd7`. Kubernetes authorisation checks returned `no` for creating NetworkPolicies and `yes` for creating Jobs as the control service account in `lab-notebooks`; no temporary Job remained. The lifecycle and API unit suites passed (24 tests), including a failed-notebook case that preserved the standard comparison verdict and an authenticated, hash-checked notebook download. C4 model validation and SVG/PNG export passed; the affected evaluation and deployment views were inspected.

An end-to-end **new comparison plus notebook** could not be run through the active controller. Its desired-state Git checkout already had unpublished deletion commits and diverged from Gitea, so pushes for two temporary environment definitions were rejected. The two unpublished test-definition commits, namespaces and scoped Elasticsearch credentials were removed; their lifecycle records were marked `deleted`. The earlier unpublished commits were left untouched. The existing frozen report was used for the successful in-cluster notebook execution. Repairing that desired-state divergence is separate from notebook execution.
