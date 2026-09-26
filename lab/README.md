# Runnable search baseline

This slice runs a browser page and black-box search API against a frozen UK retail release. It builds the API in local Gitea, deploys the pinned image through Argo CD and reads a dedicated index on the shared Elasticsearch cluster.

| Item | Current baseline |
| --- | --- |
| Products | 10,000 wholly synthetic, deterministic UK/GBP products |
| Queries | 50 synthetic queries; every query returns results through the API |
| Judgements | 1,433 rules-based positive labels for later evaluation work |
| Release | `retail-gb-10k-v1`; three hashed JSONL objects and a manifest in Floci |
| Index | One shard, zero replicas, explicit mapping, write-blocked after indexing |
| Environment | `retail-baseline` namespace, pinned image digest, scoped index read access |

## Run on the current lab

Use PowerShell from the repository root. The [platform research bootstrap](../research/platform-spike/README.md) must have created the named k3d cluster, Gitea runner, Argo CD, Floci, shared Elasticsearch and the two loopback forwards for Floci (`14577`) and Elasticsearch (`19200`). Python needs the Azure Blob SDK installed under `.lab/python-libs`. The scripts use the dedicated `.lab/kubeconfig.yaml` and generated credentials under ignored `.lab` files.

```powershell
python lab/release.py
python -m unittest discover -s lab -p 'test_*.py' -v
python -m unittest discover -s lab/search-app -p 'test_*.py' -v
python lab/load_release.py
python lab/deploy_baseline.py
kubectl --kubeconfig .lab/kubeconfig.yaml -n retail-baseline port-forward svc/search 18080:8080 --address 127.0.0.1
```

Keep the port-forward terminal running. Open [the search page](http://127.0.0.1:18080/) and try `running shoes` or `wireless headphones`. In another terminal:

```powershell
python lab/verify_baseline.py
```

`release.py` refuses to replace a differing local release. `load_release.py` uses conditional Blob creates, checks all four objects byte for byte, and verifies the index mapping, product count and write block on repeat runs. On a fresh index it gives a finite Kubernetes Job a 15-minute read SAS for one Blob object and an index-scoped write credential. It revokes the writer and write-blocks the index after indexing. `deploy_baseline.py` publishes the exact app source to the `search-spike` Gitea repository, waits for its test/build run, then commits an environment definition with the source image digest, product hash and index. Argo CD owns the deployment.

The product generator uses unequal category shares, rotating product types and brands, seeded colour/material/availability, bounded category-specific prices and synthetic popularity. The 50 queries span type, colour, brand and material intents. Judgements come from rules applied to available products; they are useful as a repeatable seed, but they are not human relevance labels or exhaustive negatives. No production product or traffic data is used.

Gatling phases, 72-hour leases, automatic teardown, Apple silicon verification and the 1,000,000-product/1,000-query gate remain later batches. The current 10,000-product result counts demonstrate functional behaviour, not production performance.

The later million-product release will use a [versioned ESCI-informed aggregate profile](profiles/esci-informed-uk-v1.json). Its [modelling note](../docs/research/esci-synthetic-calibration.md) separates reference observations from synthetic UK assumptions. It does not change this frozen 10,000-product release.

## Compare a pinned API candidate

The next slice demonstrates an API query-understanding change without reindexing. It applies the tracked [candidate patch](candidate/trainers.patch) to a branch in local Gitea's `search-spike` repository, opens a source PR and waits for its exact-SHA image build. Argo CD then deploys `retail-candidate` with a distinct read-only credential and the **same frozen index and product hash** as `retail-baseline`.

```powershell
python lab/deploy_candidate.py
python lab/compare_search.py
```

The comparison combines the original 50 frozen requests with the [extra `trainers` request](comparison-extra.jsonl), stores the 51-request suite in Floci by hash, and sends every request through both public search APIs. It verifies the two environment fingerprints, deployed image digests, shared index and Argo CD health first. The immutable report contains ordered top-ten IDs, totals, equality, Jaccard@10 and finite extrapolated RBO@10 (`p=0.9`) for every query. It does **not** infer relevance from unjudged results or count latency as a result-preservation metric.

In the measured run, the 50 original requests returned identical ordered top-ten IDs. `trainers` changed from zero baseline results to 494 candidate results; Jaccard@10 and RBO@10 were both zero. Repeating the full run produced the same report SHA-256. The [sanitised evidence](../docs/research/evidence/runnable-comparison/summary.json) points to the full Floci report.

To inspect both browser pages, forward the candidate service to a second loopback port while keeping the baseline forward on `18080`:

```powershell
kubectl --kubeconfig .lab/kubeconfig.yaml -n retail-candidate port-forward svc/search 18081:8080 --address 127.0.0.1
```

Open the [baseline page](http://127.0.0.1:18080/) and [candidate page](http://127.0.0.1:18081/) and search for `trainers`. The local [source candidate PR](http://127.0.0.1:31800/elastic-agent/search-spike/pulls/2) remains open as review evidence; it is not required to merge into the source repository's main branch.

## Score a ranking change against frozen judgements

Install the pinned open-source evaluation library into the ignored lab dependency directory, then deploy a second API variant and run the evaluation:

```powershell
python -m pip install --target .lab/python-libs -r lab/requirements-eval.txt
python lab/deploy_rank_candidate.py
python lab/evaluate_relevance.py
```

The [price-ranking patch](rank-candidate/price-rank.patch) changes only the API's Elasticsearch sort. Gitea builds its source PR at an exact SHA; Argo CD deploys `retail-price-rank` with a distinct read credential over the same write-blocked index and product release as the baseline. The evaluator verifies those pinned definitions and sends the original 50 frozen queries through both public APIs. It uses `ir-measures` for nDCG@10, Judged@10 and reciprocal rank of a grade-2-or-higher result at depth ten. The report includes every ordered result list, query-level scores, judgement counts and unjudged returned IDs. It is stored in Floci under its SHA-256.

| Synthetic judgement-pool metric | Baseline | Price-order candidate |
| --- | ---: | ---: |
| nDCG@10 | 0.911474 | 0.170948 |
| Judged@10 | 0.888 | 0.178 |
| RR(rel=2)@10 | 1.0 | 0.258690 |

These are **proxy scores for this incomplete, positive-only synthetic judgement pool**. Unjudged results have unknown relevance, even though nDCG scores them as zero. The low candidate Judged@10 shows that pool coverage contributes substantially to the apparent difference. The [sanitised evidence](../docs/research/evidence/runnable-relevance/summary.json) identifies the full immutable report. The local [ranking source PR](http://127.0.0.1:31800/elastic-agent/search-spike/pulls/3) remains open. This evaluation covers the search API's complete returned ranking; Elasticsearch diagnostics, human labels, index-change comparisons and performance testing remain separate work.
