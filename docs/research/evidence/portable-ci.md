# Portable CI evidence

Executed in local Gitea 1.27.0 with runner 3.5.0 on 27 September 2026. The workflow lives in `.github/workflows` and uses standard Actions syntax and `github` aliases.

| Probe | Result |
| --- | --- |
| Source PR #1, run 13 | Passed in 13 seconds; exact PR SHA and multi-platform image |
| Merged source, run 15 | Passed in 2 seconds with cached layers; distinct merge SHA and release ID |
| Deliberate failing test, PR #2/run 14 | Failed; completed release receipt absent (HTTP 404); PR closed unmerged |
| Final contract PR #3/run 16 and merged run 17 | Passed; complete schema/indexer validation in retained source |
| Nexus image manifests | amd64 and arm64 entries present; attestation entries are separate |
| Release integrity tests | Four passed: deterministic bundle/change detection, mutable-image rejection, altered contract and traversal rejection |

[Sanitised run receipts](portable-ci/summary.json) retain exact revisions, release IDs and URLs. These durations are individual Gitea job samples, not p95 estimates. Native arm64 and GHES execution remain external gates. Initial bootstrap run 12 failed because Git treats `.localhost` as loopback; the shared workflow now supports a configured internal checkout base URL.

The first merged release and the final contract release are retained for the promotion/rollback demonstration. The project implementation PR is separate from these source fixture PRs. The next batch has a [detailed promotion plan](../../plans/promotion-deployment.md).
