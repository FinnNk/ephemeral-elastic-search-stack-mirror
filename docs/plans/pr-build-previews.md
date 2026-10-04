# Preview a source PR build

Deploy the contributor's successful PR build through the normal delivery CLI so
they can inspect a change before evaluation and source merge.

## Scope and constraints

- Accept verified `pull_request` and `push` builds for leased previews.
- Keep image digests, bundle checksums, source revision, index compatibility,
  frozen inputs and read-only search access checks.
- Continue to require a merged-source `push` build for promotion.
- Freeze named variants in preview configuration; include standard candidate
  and baseline examples.
- Keep the contributor's branch unchanged. Do not generate its comparison or
  merge either repository while correcting the preview path.

## Acceptance and observed results

| Check | Result |
| --- | --- |
| Ordinary CLI deploys a successful PR build | Host CLI created `lab-delivery-run-106-b312de9c` from source build 106 |
| Frozen provenance remains checked | Actual build receipt and bundle verified; focused tests reject a substituted image and an unsupported workflow event |
| Promotion rejects PR builds | Validator, renderer and index materialiser reject a PR build with their default promotion settings |
| Merged builds remain supported | Focused positive test passes |
| Named default is frozen | CLI loads the JSON configuration into the deployment fingerprint |
| HTTPS storefront and catalogue | CA-validated requests returned HTTP 200; catalogue reports 1,215,854 GB/GBP products |
| Verification | 23 focused preview, release-integrity and promotion-gate tests passed, including six new preview tests |

The deployed candidate uses source
`b58d403e34bfc20a68423f94b07795b8b17f7f0d` and fingerprint
`b312de9ca65b4ac58bdd74ca51c9141b537b3ba92ba3dc0dfc8512a60835c7b4`.
It reuses the full ESCI index. Its URL is
[the candidate storefront](https://lab-delivery-run-106-b312de9c.preview.relevance.test:34443/).
The host CLI used this review branch; the installed control image has not yet
been updated. No comparison evidence was published for source PR #26.

## Next batch: resume the walkthrough

After acceptance, publish and install the reviewed control image using the
[control update procedure](../control-runtime.md#update-an-existing-runtime).
Then proceed one step at a time:

1. Open the candidate and inspect the `trainers` rewrite.
2. Open a baseline using a successful build of current source main and the same
   frozen catalogue, inputs and standard boosts.
3. Capture and inspect the comparison, explaining coverage and metric limits.
4. Publish evidence for the exact PR commit, rerun the gate and review its result.

The frozen suite has no exact `trainers` query. A focused search demonstrates the
rewrite separately; the general suite cannot establish this query's relevance.
Retain that distinction rather than silently changing frozen queries or the
temporary demo-label policy.

## References

- [Source PR #26](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/26)
- [Preview procedure](../delivery.md#preview-or-compare-manually)
- [Evaluation runbook](../evaluation-runbook.md)
- [Walkthrough and collected feedback](developer-walkthrough.md)
- Implementation: `lab/delivery_cli.py`, `lab/delivery_runtime.py`
- Focused checks: `lab/test_delivery_previews.py`
