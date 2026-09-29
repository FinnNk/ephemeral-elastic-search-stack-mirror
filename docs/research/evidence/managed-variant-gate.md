# Managed offline variant gate rehearsal

**Run:** 29 September 2026, local k3d/Gitea/Nexus lab. All products, queries and judgements are synthetic. The live model abstains on missing labels.

## Frozen capture and live result

The environment-state ApplicationSet deployed `lab-variant-managed` through Argo CD. Its frozen definition pinned the synthetic `retail-gb-1m-v1` index, a Nexus image, three ranking configurations and one default (`ranker-a`). The evaluation baseline was `ranker-b`. The environment was `Synced` and `Healthy`; `evaluation/capture.py` verified the definition and API deployment before running the finite 1,000-query Job.

| Item | Evidence |
| --- | --- |
| Source PR | [delivery-source #8](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/8), stacked on [#7](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/7) |
| Live source commit / build receipt | `9853fa33d379967d35b5834049dc563ee0e2e4e5` / run 33 attempt 1 |
| Evaluated image | `nexus.localhost:18185/search-api@sha256:4abc31145f2e9f3f53b557d1f1386060e39c3cdcb343ba1997de28830505083c` |
| Frozen environment fingerprint | `1ba02481494b0284d9163f9ea8aed4cd7661c610fa6b8d5d6ed699aba13c9d2c` |
| Observation / report SHA-256 | `93621f6eaba7423381bef79c36bd0054fc9032075fe83dc4bd72595d00470fec` / `d5531acc8dcb4f0260dcc1a1a3770b9cd84a3bfaf418dfb1753fff01b1dcf60d` |
| Pooled pairs | 10,967 required; 21 stored labels; 10,946 model abstentions; no inference errors |
| Judged top-10 coverage | `ranker-a`: 0.21%; `ranker-b`: 0.09%; `ranker-c`: 0.21% |
| Live metric | nDCG@10: `ranker-a` 0.001959; baseline `ranker-b` 0.000581. These scores lack adequate coverage for a quality decision. |

CI run 33 attempt 1 failed because no evidence existed under that exact source SHA. After the finite evaluation, a trusted attestation bound the report, source SHA and immutable run 33 attempt 1 build receipt. Attempt 2 on the **unchanged commit** read the bundle and returned `blocked` (exit 4) at the policy's 80% coverage minimum. The result retained the positive observed delta (+0.001378) and 9.7% changed-query fraction. The missing bundle and low-coverage outcomes are distinct.

An earlier experiment showed that two CI attempts for one source SHA can produce different OCI digests. The gate therefore checks the captured selected image against the attested immutable build receipt, rather than the image built by the latest attempt. A wrong image produces `invalid`. The attestation also protects the report and receipt bytes; the gate checks the protected policy and gate-code pins.

## Structural fixture

For commit `05cf4a6c9ffc4433ac5eb7d6669e8dce8310904d`, run 34 attempt 1 built image `nexus.localhost:18185/search-api@sha256:4c7e867d66fc93cdcd433d9fdad2eff238a3fc16bec3bc658aa6f55a268cefb7`. A second managed 1,000-query capture of that image had observation SHA-256 `462efa3511485faa945fa8dd438c489fb88ce776dce7b7b53de49080bf1e4d05`.

The fixture labels every returned query/product pair as exactly relevant. This produces 100% judged coverage and nDCG@10 of 1.0 for each variant by construction. It tests evidence transport and decision logic; it says nothing about model accuracy or search quality. The fixture report SHA-256 was `05c676018d03be9d7eee4abd26ffce580079467a3d360f8dfbf3f8726e1e7230`. CI run 34 attempt 1 failed on the absent bundle; after publication, attempt 2 on the unchanged SHA returned `pass` with the run 34 attempt 1 image receipt.

A second fixture marks selected-only results for one changed query as irrelevant while retaining baseline-only results as relevant. Both sides remain 100% judged; `ranker-a` has nDCG@10 0.999 against baseline 1.0. The CLI returned `decision_required` (exit 3). A fixture-only signed receipt then returned `approved_exception` (exit 0), retaining the −0.001 delta, reason, reviewer field and approval hash. These fixture keys and reviewer are **not** trusted lab credentials or a real human decision. The separate unit test exercises the Gitea administrator check with a mocked identity and rejects forged or retargeted approval receipts. A real exception requires an administrator's deliberate decision.

## Limits and replay

- The live result remains blocked. The first model abstains on gaps; a reviewed label source or useful model is required before any relevance-quality promotion.
- The proof used one shared Elasticsearch index and one Search API deployment for three ranker configurations. Image or schema differences require separate frozen environments.
- Source CI uses a trusted same-repository runner. GHES, Apple silicon and Azure have not been validated by this run.
- Historical Nexus reports, build receipts and source commits remain addressable. Frozen environments can be removed and recreated from the synthetic generators, exact image and desired-state definition; no old observation-schema reader was added.

See the [variant contract](../../variant-evaluation.md), [gate plan](../../plans/offline-variants-and-gates.md) and [source workflow](../../../lab/delivery/workflows/release.yaml).
