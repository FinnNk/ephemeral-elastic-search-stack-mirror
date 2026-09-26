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

This is a baseline search slice. Comparison environments, evaluation reports, Gatling phases, 72-hour leases, automatic teardown, Apple silicon verification and the 1,000,000-product/1,000-query gate remain later batches. The current 10,000-product result counts demonstrate functional behaviour, not relevance quality or production performance.
