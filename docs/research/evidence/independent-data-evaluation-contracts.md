# Independent data and evaluation contract evidence

Batch 7j keeps the synthetic input bytes fixed while separating their contracts and scoring. This is a local topology and reproducibility demonstration; the synthetic labels are not evidence of customer relevance.

| Check | Observed result |
| --- | --- |
| Existing input validation | The 10,000-product and 1,000,000-product releases passed streamed identity, market and reference checks without changing their files. The million-product catalogue SHA-256 is `a6c78afb7df078016828a8a9a93b88b2d1db6a16ef64080a37dc33c23c2cc1d6`. |
| Independent producer | A third 12-product/3-query synthetic pack was published twice through the finite `lab-data` Job. Catalogue, query and judgement hashes were identical on the second run. The Job and its temporary Blob credential were removed. |
| Catalogue-only recipe | The 10,000-product format-2 recipe `f62196f3b621f1924db0e27d3f149351f30531b82deb04ae087f37379be88043` built a dedicated index, returned HTTP 200 through its Search API, and was explicitly deleted. The million-product recipe was retained but not rebuilt. |
| Direct observation capture | A 50-query comparison retained observation hash `243bb005f18e0a85104cebbf3f30da54463d704ea8cfbfbe425f297de591c9d2` separately from comparison report `784c0c0e259dc3bacfc6f76983e046f9b99e5d161d7ec3edcf4a232f8c081f62`. |
| Revised query execution | A separately retained three-query suite (`2e79b3390d74c56da275d8d05190e0cca2f2025b2766176485833f316262da49`) changed one original request. The existing frozen APIs completed a new finite capture, retaining observation hash `b5ba148a328794c8d9c0f0b7bf7f810d8c72f656b1ecfecc1a8a2509b186e992`. No environment or index was recreated. |
| Offline rescore | A complete historical 1,000-query observation set was adapted without changing its source report. The same observation hash `aa21ac7d3747ff7b135e83ca2396c40cc25db323911e1871877986d5475cd179` produced separate retained reports `446bb857378189932d805497da0418b97192e1a06b566a651d3391f129022409` and `e776b6a880196fcac318cfa14e0127879145f41cca76917113e32c6de97c423f` under different synthetic judgements and metric specifications. The first report was reproduced with the evaluator container's network disabled. No Search API request, environment deployment or index build was involved in that rescore. |
| Finite evaluator Job | A `lab-offline-evaluation` Job fetched six exact Blob inputs, scored all 1,000 observations and retained report `446bb857378189932d805497da0418b97192e1a06b566a651d3391f129022409`, byte-identical to the standalone result. The Job used digest-pinned image `sha256:3ef3af10f30d4393e00ef44154661bf240d3dd24160bc84bd660c7dcc8ffda06`, no Kubernetes API token, and DNS/Floci-only egress. The Job and its temporary Blob Secret were removed. |
| Policy separation | The 50-query offline report passed the separately hashed policy `74a366dcf40d6ae4b8a840ca1574ab7433fa73b305a9dd4d82e9a9d000e44919`; the result required human review and did not approve a promotion. Delivery validation can now select an optional immutable offline addendum and bind its catalogue/query/observation hashes to the full relevance capture. Tests reject a substituted policy and mismatched capture. An actual reviewed promotion using that addendum remains open. |
| Retention inventory | The read-only inventory checked 12 million-release input, recipe, report and image references and found zero missing at the time of the local check. A separate deliberately absent observation reference returned one missing item among five checked references. The inventory does not verify backups or guarantee future retention. |

Separate amd64/arm64 Nexus images were published for the producer (`sha256:31446f2734cca85d9091921e0bbbbc8fb4c95e25512a9459ef88b366578ad0e0`) and evaluator (`sha256:3ef3af10f30d4393e00ef44154661bf240d3dd24160bc84bd660c7dcc8ffda06`). The evaluator image needs republishing if its copied source changes after this receipt.

The control image with optional delivery policy validation was published as `sha256:09369bf07164c148650fd72cdf3688592fc4041bfd8b09677d8e83f3d8a48693`. An idle-only rollout completed, and the control smoke check confirmed the named cluster, 148 retained environments, 41 comparison records, Gitea identity and Nexus reachability. This does not constitute a clean-checkout activation rehearsal.

## Open checks

- The control comparison endpoint still chooses legacy query suites and pooled judgements by release name. `evaluation/capture.py` accepts an explicit independent query manifest for a new live execution, and the offline evaluator accepts an explicit judgement manifest. The web UI has not yet exposed these selectors.
- The separate policy is available as an optional delivery evidence addendum, but no actual promotion PR has yet selected it. Legacy delivery validation remains in force when omitted.
- A schema-changing promotion and rollback through the Kubernetes coordinator needs reviewed desired-state promotion. The existing Gitea delivery-state PR 6 is awaiting that review; no merge was performed as part of this batch.
- The standalone evaluator ran with Docker networking disabled; the Kubernetes Job used DNS/Floci-only egress. Disposable fresh-checkout activation and native Apple silicon/Azure checks remain unverified.

See [contract and commands](../../data-evaluation-contracts.md), [batch plan](../../plans/independent-data-evaluation-contracts.md), and the earlier [delivery evidence](promotion-deployment.md).
