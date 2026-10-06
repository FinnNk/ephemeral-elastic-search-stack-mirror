# Compare deployed releases with an exploratory notebook

Ready delivery targets and previews should be selectable alongside standalone
ephemeral environments. The same comparison and notebook flow should work for
both; exploratory output must not change a merge or promotion gate.

## Implemented batch

- Discover integration, staging and each production slot from observed release
  definitions, ready deployments and healthy, synced Argo CD applications.
- Include ready, unexpired delivery previews created through **Create preview**
  in Actions. Retain their own expiry policy.
- Label production slots active or inactive and show verified build numbers
  when a matching receipt is available.
- Pin selections by namespace and release fingerprint. Use the slot's service
  directly, hold the delivery coordinator lock and recheck functional capture
  against its initial definitions. Reject stale selections with a refresh action.
- Keep delivery targets outside standalone lease and deletion controls. Preserve
  target metadata so old reports and notebooks remain readable after deployment
  changes or preview removal.

The standalone environment form still uses the earlier search-spike build
workflow. The contributor path for a new delivery preview is Actions →
**Create preview**, followed by **Refresh status** on the control page.

## Verification — 6 October 2026

The installed UI was not replaced. Updated modules ran in an isolated temporary
process inside the control Pod using its existing service account and pinned
notebook runner. These are actual public Search API comparisons through the
cluster services, not synthetic score fixtures.

| Pair | Comparison ID | Capture | Notebook |
| --- | --- | --- | --- |
| Production blue build 108 / green build 158 | `b9f7f46e-3c14-48f7-9c65-683f1d0afe6f` | 9.291 s | 20.526 s |
| Purpose-created delivery previews, builds 156 / 165 | `b2a7f929-69bf-4ace-8425-1301e9e7a714` | 8.061 s | 14.303 s |

Both **Relevance · Quick · first 50** comparisons completed all 50 query cases
on each side with no retries or failed requests. Both notebook Jobs completed;
the authenticated download handler returned HTTP 200, bytes matched the
retained hashes, and saved outputs counted 50 queries with no notebook errors.
The temporary download test used a local verification identity; it did not test
a new browser OIDC login.

For this sample, both sides had nDCG@10 of 0.738912, 84.2% judged coverage,
Jaccard@10 and RBO@10 of 1, and no changed result lists. These values establish
the notebook flow and endpoint routing, not an improvement in relevance. The
selected frozen labels contain previously authorised lab demo predictions;
the current abstaining judge and quality qualifications were not changed.
No production route, promotion or gate threshold was changed. Preview expiry
is 9 October; their workloads reuse the existing frozen index.

| Retained notebook | SHA-256 |
| --- | --- |
| Existing slots | `2b6096052b5cab443955a352aa1f4ba523ecdaae3bf2f0dbbb3f857aacd77a4c` |
| Created previews | `4040c67f564ec47c2aac035464cbad61ff008787fd97d4983780ee645b5b66fa` |

All 33 focused tests passed. They cover ready target discovery, immutable identities, stale
selection, unready omission, separate slot URLs, notebook verdict preservation,
HTTP authorisation and existing comparison contracts. Browser fixture checks
cover the combined selectors, delivery labels, absent lifecycle controls,
paging, selection preservation and mobile layout. A full Gatling run was not
performed. The wider lifecycle run stalled in cleanup coverage and
was stopped; focused comparison tests are the validation for this batch.

## Next batch: activate and walk through both pairs

1. After acceptance, publish and roll out the merged coordinator with no active
   delivery operation. Confirm its ready state and service contracts.
2. Open the control page and **Refresh status**. Select production blue and green,
   **Relevance**, **Quick · first 50**, and `comparison-explorer.ipynb`.
3. Run the comparison. Inspect its report, then **Download executed notebook**.
4. Repeat with the retained previews of builds 156 and 165, or use Actions →
   **Create preview** for other successful builds. No kubectl commands are needed.
5. Resume the production resource investigation and unchanged load gate after
   the walkthrough.


## Activation and first UI run — 6 October 2026

Merged PR #144 is installed using coordinator image
`sha256:3d64cbeed515747df246f8b5a0542b1d3f3cd585af4a44c818689bb151ceac6e`.
There were no queued or running delivery operations, running comparisons or
active coordinator lock before rollout. All four containers became Ready;
Gitea, Elasticsearch and Nexus service checks passed. Both production slots,
integration, staging and the two prepared previews are selectable.

The user's first UI comparison, `346f8b4a-b541-4fc9-b50d-40cd1367c8b0`, completed
50 queries per side with no failed requests. Capture took 6.997 seconds and the
notebook took 6.358 seconds. Its result lists matched, with nDCG@10 of 0.738912
on each side and 84.2% coverage. The executed notebook is retained under hash
`87456bd4dea5b03a4ace6e8c32a19fa2fab3b36001776a3fed3224e6081a1cd4`.

The UI's general response hint remained unchanged, while comparison status was
shown beside the unrelated environment-creation form. This follow-up places
running, completed and failed messages beside **Run comparison**, adds a direct
report link and disables repeat submission while the request is pending.
Chromium checks passed for pending feedback, one submission despite a repeated
submit event, notebook completion text, report link and retry after an error.
No API, comparison or notebook execution behaviour changed.

After accepting and activating the feedback fix, open the completed report and
download its notebook. Then repeat the same settings with previews
`lab-delivery-run-156-6bdbc9b0` and `lab-delivery-run-165-8ba17059`.


### Browser response timeout

The sign-in proxy logged `timeout awaiting response headers` at 20:52:13 UTC.
The comparison completed at 20:52:38 UTC, after 54.493 seconds, and the API's
reply failed because the proxy had already closed the connection. The browser
tried to parse the proxy's HTML error page as JSON. This explains the original
page's error; the saved report and notebook succeeded.

The installed proxy binary confirms a default upstream timeout of 30 seconds.
The reviewed configuration sets it to 60 minutes to accommodate a comparison's
two bounded Gatling jobs and optional notebook. Their existing execution
limits remain in force. This configuration change awaits acceptance and proxy
rollout; it does not alter authentication or start another comparison.

The UI recognises non-JSON responses and gives a recovery instruction. For a
submitted operation it says the request may still be running and directs the
user to refresh status and inspect the latest record before retrying. The
browser test covers the actual HTML 502 response shape, alongside JSON failures.
