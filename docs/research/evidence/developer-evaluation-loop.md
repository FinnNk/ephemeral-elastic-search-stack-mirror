# Local developer evaluation loop

Measured on the Windows lab on 27 September 2026. All products, traffic, queries and judgements are synthetic. The comparison decision surface is the public Search API.

## What passed

| Check | Observed result |
| --- | --- |
| Million-product result comparison | 1,000/1,000 frozen queries completed through two public APIs in **41.078 s** wall time; the finite evaluation Job ran for 33.219 s. All 1,000 ordered top tens changed for the deliberate ranking candidate. Report SHA-256 `c0abccc22d3834ea3c9f059dfaecd209c49e507002a0b8723108b661b12a80fc`. |
| Million-product relevance | 1,000/1,000 queries completed in **38.984 s**. The baseline returned top tens were 10,000/10,000 judged; the candidate's were 19/10,000 judged. The report marks candidate coverage insufficient and lists unjudged IDs. Report SHA-256 `c15fac98b1a6a2a10e7c4ae134969e62667a023174a4e4f3fb57163dcc73216d`. |
| Failure handling | An older API missing the response `country` field failed preflight before any query, producing an incomplete report. One transient network failure made the first PR full comparison incomplete. A retry kept the completed quick result, repeated the incomplete full result and finished all remaining checks. |
| Opt-in Gitea PR | [Source PR #5](http://127.0.0.1:31800/elastic-agent/search-spike/pulls/5) carried `lab-evaluate`. The local watcher pinned its successful build to head `f349746bc60948f0124c1e4c55cb8592989c067c`, created the two frozen environments, completed quick/full result, relevance and Gatling probe, and posted one verdict comment and a successful tooling status. Trigger to first correct candidate search was **14.593 s** with the build already available; checks after readiness took **172.516 s**. |
| Report inspection | The authenticated control UI opened a pinned full comparison from the PR comment. A browser check found 50 changed-query entries and side-by-side ordered results. The same view opened the 1,000-query relevance report with coverage and unjudged-result detail. |
| Resource cleanup | The evaluator removes its finite Job and ConfigMap. The PR run left no evaluator or Gatling Jobs or pods in `lab-evaluation`. Leased API environments remain available under the normal 72-hour policy. |

The earlier per-query host-to-cluster transport path took about **631–638 s** for 1,000 queries. The 41.078 s run is about 15 times faster as a local observation, but the two measurements were not a controlled paired benchmark. The quick PR result check uses the first 50 frozen queries; full result and relevance checks use their complete frozen suites.

## Interpretation and limits

- The million-product judgement release contains positive synthetic assessments collected from a baseline and an earlier candidate. It is a fixed, reproducible proxy pool, not independent human truth. A new ranking can retrieve largely unjudged products. The measured candidate nDCG is therefore **not** evidence of poor real-world relevance.
- A PR's successful tooling status means its checks completed and the short Gatling probe stayed within its budget. It does not approve a changed ranking or claim that synthetic relevance improved. Add `lab-preserve-results` when unchanged ordered results are required.
- The PR timings begin when the local workflow notices an already built revision. They do **not** measure the target's PR update → build → first search interval or establish a p95. The local watcher polls; GHES signed event delivery remains batch 8 work.
- One million-product result run and one relevance run are timing samples. The current Job uses eight bounded workers and retries transient request failures up to three times. Capacity, noise and sustained concurrent evaluation still need repeated measurement.

The [developer evaluation plan](../../plans/developer-evaluation-loop.md), [PR-to-verdict diagram](../../diagrams/interactive/pr-to-verdict.html) and [lab runbook](../../../lab/README.md) give the implementation and reproduction path.
