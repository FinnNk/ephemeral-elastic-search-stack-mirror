# Readable delivery results

## Intent

Make links from source PRs, Actions and delivery evidence usable during demos.
Show current progress and retained results without requiring a JSON reader.

## Constraints

- Retain existing URLs and JSON payloads for scripts and downloads.
- Serve HTML only when a browser requests it; the page fetches JSON explicitly.
- Keep owner checks, sign-in and report digest verification on data requests.
- Present measurements without changing scores, gates or deployment behaviour.
- Keep coverage separate from relevance and identify report-only query sets.
- Do not interrupt an active comparison or create another model inference job.

## Acceptance criteria

| Surface | Behaviour |
| --- | --- |
| Operation links | Refresh current stage; distinguish completion, failure and the gate/deployment outcome |
| Source reports | Show standard, extra and combined results, coverage and demo label qualification |
| Result overlap | Show each variant against the baseline; keep RBO and Jaccard separate from per-variant relevance scores |
| Control reports | Open readable summaries; explicit JSON downloads still return JSON |
| Promotion evidence | Link each frozen result-regression, relevance and performance check |
| Gatling reports | Show each measured phase, latency, failures and recorded budgets |
| Access and integrity | JSON retains owner checks; both root and nested report hashes are checked |

## Verification and limits

HTTP and browser tests cover presentation and existing access controls. Browser
fixtures demonstrate the view; they do not establish search relevance or load
capacity. Shared-runtime activation is outstanding until acceptance.

See [delivery](../delivery.md), [remote commands](../remote-delivery.md),
`lab/control_api.py`, `lab/delivery_results.js` and the
[next activation plan](readable-delivery-results-activation.md).
