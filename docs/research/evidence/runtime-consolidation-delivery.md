# Control runtime and schema delivery: local evidence

**27 September 2026 · Windows 11 / local k3d.** All catalogues, queries, judgements and traffic are synthetic. The timings below are individual samples. The local integration, staging and production targets share one cluster and are not separate failure domains.

## Owned runtime and deployed control

The active control image copies `lab/` and `data/`, with no `research/platform-spike` tree. Blob, Elasticsearch, Gitea, Kubernetes and search-probe helpers are owned by `lab/`. The standalone index worker in `lab/index_job.py` has byte-for-byte the same SHA-256 as the retained research worker, so existing frozen worker source hashes remain valid. The delivery runner template also matches the previously generated runner YAML exactly. Historical source remains embedded in format-1 recipes.

The final multi-platform control image is `nexus.localhost:18185/lab-control@sha256:5b7a4f05f45739890b64f378e3ef707861e8c7aab5b918acb1cb65af8fc319aa`. Its `lab-control` Deployment rolled out with four ready containers. The in-Pod smoke check matched the pinned cluster UID, authenticated as `elastic-agent`, reached Elasticsearch 9.5.4 and Nexus, and read 152 retained environment and 43 comparison records at final rollout. The deployed CLI also exposed `evaluate-target --help`. The local browser forward recovered after Pod replacement. The target status check showed matching desired and observed fingerprints with `verified` state for integration, staging and production.

| Deployed control API check | Retained identity | Result |
| --- | --- | --- |
| Two API-only 10k environments | `lab-reference-v2-a` and `lab-reference-v2-b`; format-2 recipe `379d0387750155b84c4d6291690aee8b5885aa4c4dfcc003a54fefad00c2e569` | Both became ready and served public searches from the same recipe-derived shared index. |
| Dedicated 10k schema environment | `lab-reference-v2-schema`; format-2 recipe `a3bdc04bab6372991e31ed9424a74aadbfb719ac0680abd9a1aabbd26ad76619` | Ready and served public searches from a separate index over the same catalogue. |
| Explicit historical replay | `lab-reference-v1-replay`; format-1 recipe `511b1d4aa37af0313af09eb4d3a15ab6edb93a9feb87a18b17429cae7758b6e2` | Ready and served the pinned old dedicated schema. Its new environment record has no independent catalogue-manifest claim. |

The first replay request incorrectly selected `shared` for this dedicated recipe and was rejected with HTTP 400. Retrying with the recipe's pinned `title-keyword-v1` kind succeeded; the controller did not silently adapt it.

## Revised evaluation inputs

The producer published a three-query synthetic suite and a compatible 90-row judgement set, changing one synthetic assessor grade without consulting API results. Their manifest hashes are query `379efa82f6808555a38baa58937b37820c339c00396c9da3c3607ec151e149ae` and judgement `1b46d80814866cd2c4e65fac1726700291f4032c757f0b589411562a9702286d`. The product content hash remained `164ca27a8a12ba5231f8896ca9ac2bd44492d9d341aa0d7c3ddd0c4f61aa434e`.

An older content-addressed catalogue Blob lacked the producer's metadata despite having matching bytes. Publication initially rejected it. The publisher now streams and hashes an existing metadata-free object before reuse; same-size tampering is rejected by a focused test. No retained object was overwritten.

The deployed control API compared the two shared-index environments using these selected manifests. Result preservation completed with verdict `unchanged` and report SHA-256 `aa651295f70ffc2b3d565ba567cae967f571ed81c7606c0c904d3d7a0a9cfe13`. Synthetic relevance completed with verdict `measured` and report SHA-256 `13cb80fc300dbad13a780f1d64b9affaef7c1427183a6a0130ec88b0daed0a24`. These are three-query checks of contract wiring, not relevance-quality or capacity evidence.

## Million-product schema candidate

The local stable targets already used the 1M catalogue. The first reviewed schema release (source run 19) supported a 10k title-keyword mapping only, so it could not pass exact compatibility for those targets. [Delivery-source PR #5](http://127.0.0.1:31800/elastic-agent/delivery-source/pulls/5) added the existing versioned 1M mapping without changing API or indexer bytes. Its PR-head run 20 and merged-source push run 21 passed. The merged source SHA-1 is `494b1ffbcc1734c5ef111a2dbffc5430495d82b3`; the Nexus release descriptor is `cf1ae1eb2a81f55d15fed832a85ca60cc287c0be11bdf44e7a8e1387d7803954`.

Format-2 dedicated recipe `83877e5435059716539493991aad365104f9251d80c545b1f02f5ce6e2021c6e` built `lab-release-83877e543505971653949399-idx` from the pinned 1M catalogue: 1,000,000 documents, 165.609 s, no recovery errors. Run 21 resolved against that recipe with candidate deployment fingerprint `12cefb03f27895ab5ea2b033f2157b600366cd99782050a4fb257a2834865871`.

## Delivery rehearsal

The current integration and staging definition before this exercise was fingerprint `df2e057cc9d889b9c08b96721cc2fc370579841d9f118b87777186212b4fe595`; production served `00cd57233b8a30a6e452a82e7237e97892553c1408af21fc9aa1deb7e2845dea`. Both are retained format-1 1M definitions. The full public-API comparison uses the target's actual desired definition as its baseline.

| Integration baseline → schema candidate check | Retained report SHA-256 | Result |
| --- | --- | --- |
| Result preservation | `e2c73638ea286541877466ffb68c85f5d1b3c4c922d9a5ea934bb6d2b255ffc8` | Full 1,000/1,000 queries; intentionally `changed`. |
| Synthetic relevance | `0b75a742da664c2722aaa87bec2265f6238d2f5221d77d9af536ee824ce33b06` | Full 1,000/1,000 queries; `measured`, not an automatic quality decision. |
| Paired Gatling probe | `6542bcdfb03a0cf3a861da8049dda2a470d4f668db31107b68c45b0d9d66654d` | Valid, same workload and within budget; normal-phase p95 56 ms baseline and 30 ms candidate at 2 offered requests/s, 0% errors. This short probe is not capacity evidence. |

The complete delivery evidence reference is `runs/a844c6125449f6929a7e60cc1f62742aa402322d9d4731a0150abba00da1e0fa/delivery-evidence.json` (SHA-256 `a844c6125449f6929a7e60cc1f62742aa402322d9d4731a0150abba00da1e0fa`), validated for intentional ranking change. It applied to both integration and staging because their exact baseline fingerprints matched. Production had a different old definition, so a new full check produced evidence `f0839142e5891eb7d477faef5ce5d78612b3738240dd3523596d087246551b80` with result, relevance and performance report hashes `5f7cb5bccff315fd5bf63e6d5bc027e3b1f34f07d78f84e363348e80f1a45dec`, `7ce788295c55973b9b8d8b423c8385df0fa6d4a081f55aed123e0007acbf4cab` and `dbae4c4fc1ba535405cc8b5b9142a50fe367bbb3edea5675e18aa825410baf11`.

The separate `lab-admin` fixture account approved each exact PR head. The control Pod revalidated, squash merged and verified the following deployments through Argo CD and the public API. No candidate image or index was rebuilt during promotion.

| Target | Promotion PR | Old → new fingerprint | Verification report SHA-256 | Merge to verified |
| --- | --- | --- | --- | ---: |
| Integration | [#7](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/7) | `df2e057c…` → `12cefb03…` | `91ed49b57ca6612ee75dff1f16d01627c2d5d0177012953205f9e0071a8c9ff0` | 3.112 s |
| Staging | [#8](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/8) | `df2e057c…` → `12cefb03…` | `aa92e7b7f0303c3539a803402fa9d5321a622ad313e34cacbc58845674d4fdc9` | 5.069 s |
| Production simulation | [#9](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/9) | `00cd5723…` → `12cefb03…` | `e23b26cdc0ded3c56adef44b0fa64051bc434b6d8ae8999eba2279d488b81f06` | 2.895 s |

The reverse comparison from `12cefb03…` to the old `df2e057c…` integration/staging definition produced evidence `e30be9cc718bb82691c2c78521192df95fe64cebe534cafc4b9363f8f7c14d02`. It passed the same full result, relevance and paired Gatling gates with explicit `ranking-change` intent. The rollback CLI previously allowed only its default preserve-results intent; this exercise added an explicit `--intent` argument and a test so an intentional reversal cannot be mislabelled.

| Target | Rollback PR | Restored fingerprint | Verification report SHA-256 | Merge to verified |
| --- | --- | --- | --- | ---: |
| Integration | [#10](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/10) | `df2e057cc9d889b9c08b96721cc2fc370579841d9f118b87777186212b4fe595` | `a19cdafd8c02426b471a0d234d53861b7056353f9a836a57bf5d1f2b29789480` | 2.987 s |
| Staging | [#11](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/11) | `df2e057cc9d889b9c08b96721cc2fc370579841d9f118b87777186212b4fe595` | `9c46bd43beb898ad48da0fcd39a3dc699fa95131a4e289d8f8a2bacd0f30cc8b` | 5.587 s |

The first production reverse check retained evidence `f784d1a75850acebcf9772441c27d9cc001322f9435b824fb751f83609141288` but failed performance validity: the older candidate's arrival-drift p95 was 628 ms. All planned requests were sent; the report was not used for a rollback proposal. An isolated rerun passed with evidence `8f3366a0e62b3357d631e2664d1b32cc32357e80ee1607bef8b0b27a7ae913cc` and result, relevance and performance report hashes `bc9415d321551b0cf20da88b069468e12f7ccce7fd2cb415821c0004d4b91c64`, `0ae453317954e3de1a4a81b1b1397388620021a0cbc10e111dfc5e6bcc54b7db` and `274e4869a19f6cde3468faac8fc1b9361613159d128399b356afc8c6f8ba687c`. Arrival-drift p95 was 117 ms for the new baseline and 6 ms for the old candidate. The normal-phase p95 was 30 ms versus 46 ms at 2 offered requests/s, with 0% errors; both remained under the absolute 250 ms budget. The 53.3% relative increase is a measured difference, not a capacity finding.

| Target | Rollback PR | Restored fingerprint | Verification report SHA-256 | Merge to verified |
| --- | --- | --- | --- | ---: |
| Production simulation | [#12](http://127.0.0.1:31800/elastic-agent/delivery-state/pulls/12) | `00cd57233b8a30a6e452a82e7237e97892553c1408af21fc9aa1deb7e2845dea` | `c04d5e67020e2df83dbbc6d9061bf7bb5c4c7dd2d95f2823a5a4c43ab9bfbb28` | 5.682 s |

All three local targets finished on their original verified definitions. Their source releases, images, index recipes, indexes and settings match the retained deployment records. The target exercise demonstrates the topology and contracts locally; its short Gatling probes do not establish million-product peak capacity, independent failure domains or cloud portability.

The exercise called the delivery evaluator with the exact desired-state deployment objects because the earlier `evaluate` CLI reconstructed a new definition from each run ID. That would have misidentified the old protected baseline. The final branch exposes this supported path as `evaluate-target`: it reads the current target and either a new merged-source run or an exact retained prior fingerprint. Focused tests cover both selections. The live reports above were generated by the same evaluator before this CLI wrapper was added; the wrapper itself was not used for those reports.

The final branch passed 89 lab tests, 5 data tests, Python compilation and `git diff --check`. The Structurizr and Archify sources were rendered and inspected earlier in this batch; the C4 workspace description now distinguishes the local reference topology from proposed Azure placement. No diagram asserts that SigNoz is deployed.
