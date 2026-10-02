# Source PR merge readiness — 2 October 2026

Delivery-source PRs #13, #14 and #15 have passing build and offline relevance
checks for their current heads. The previous failures on #13 and #14 came from
missing frozen report evidence. The gate policy and source code are unchanged.

Source PRs #13–#15 have since been merged to source main. This page retains the
checks and advice recorded before those merges; the
[merge status](source-merge-readiness/merge-status.json) records their completion.
No source merge action remains for this stack.

## Checks and evidence

| PR | Change | Build | Relevance | Comparison |
| --- | --- | --- | --- | --- |
| #13 | Disconnected demo and contributor instructions | Run 54, attempt 1: passed | Run 55, attempt 2: passed | Exact PR image against source main image from run 49 |
| #14 | Caller filters | Run 56, attempt 1: passed | Run 57, attempt 2: passed | Exact PR image against #13 image from run 54 |
| #15 | Elasticsearch connection reuse | Run 58, attempt 1: passed | Run 59, attempt 2: passed | Previously verified against #14; [adoption evidence](evaluation-throughput-adoption.md) |

The new captures each issued 2,000 fresh searches over all 1,000 frozen queries
and the shared million-product index. Both comparisons had zero changed queries;
synthetic nDCG@10 remained 0.979894 with judged coverage 1.0. Signed reports and
attestations were published to Nexus for the exact build receipts, then the
protected checks were rerun. No exemption, override or fabricated result was used.

The suite contains no caller filters. It checks preservation of existing requests;
the [filter verification](search-request-filters.md) separately exercises filtered
membership, bounds, rejected requests and browser controls. Synthetic rule-pool
labels do not establish independent relevance quality or customer benefit.

These historical source images predate the current required filter echo. Their
comparisons explicitly pinned the capture worker from before filter support
(`ef73f88^`), without changing the current runtime or adding a fallback. The
retained worker hash and report metadata identify the capture implementation.
Current source changes continue to use the current capture contract.

| Retained record | Contents |
| --- | --- |
| [Checks](source-merge-readiness/checks.json) | PR heads, bases, mergeability and successful run attempts |
| [#13 summary](source-merge-readiness/build-54-summary.json) / [archives](source-merge-readiness/build-54-archives.json) | Image, configuration and input pins; verdict; observation and report Blob hashes |
| [#14 summary](source-merge-readiness/build-56-summary.json) / [archives](source-merge-readiness/build-56-archives.json) | Same records for the filter PR |
| [Capture worker](source-merge-readiness/capture-worker.json) | Historical revision, SHA-256 and restricted scope |
| [Cleanup](source-merge-readiness/cleanup.json) | Removed disposable namespaces |

Raw files were uploaded to hash-addressed Floci Blob objects and read back for
equality. Disposable Argo applications and namespaces were removed; the frozen
index and retained evidence remain. Single capture timings are diagnostic records,
not additional throughput or capacity claims.

## Original merge recommendation

1. Review and squash-merge [source #13](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/13).
2. Rebase #14 onto the resulting main, preserving only its filter change. Build
   the new head and refresh exact-commit evidence before squash-merging it.
3. Repeat for #15, preserving only its connection-pool change.

At the time of the recommendation, all three checks passed. A rebase changes the
source hash; reports for the previous head
cannot approve the rewritten head. Do not transfer successful statuses manually.
No source merge was performed during this batch.

PR #12 is an intentional negative gate-tampering fixture against an isolated
exercise branch. Its failing relevance check is expected; it is not an
implementation PR and should not be merged into main.
