# Paired demo data and manual lease editor

## Scope

Implement fixed expiry controls for ephemeral environments, a shared Redis rewrite
dependency with local fallback, and three small named/date-selected catalogue versions.
Keep stable targets protected and preserve existing frozen data and human rewrite rules.

## Design

- Manual expiry uses a persisted fixed mode and optimistic current-expiry checks.
  Explicit Extend lease restores rolling activity renewal.
- Delivery preview edits pass through the existing durable, idempotent coordinator.
- Paired manifests bind catalogue/query/judgement identities and Redis content.
  Runtime restore verifies the seeded hash; the API rejects foreign catalogue rows.
- Redis is shared, read-only to search clients, seeded on restart and has no PVC.
- The three dated fixtures retain unchanged ESCI products and labels. Membership
  and dates are explicitly simulated. No model inference is needed.
- New delivery source uses version 1.1.0. Legacy releases remain usable without
  claiming a Redis binding. API images and charts are reviewed with the lab changes.

## Acceptance and next batch

Review the lab, environment-state chart and delivery-source PRs. After acceptance,
publish the three fixtures, install Redis and update the control runtime. Build the
new source API through CI. Create two environments using the same named release,
then another using a date. Check displayed identities, Redis rewrite diagnostics,
local fallback and fixed expiry. Verify comparisons retain matching catalogue and
judgement identities. Record the Windows activation and repeat the fresh install
on the Mac before claiming native installation verification.

## Verification evidence

- 53 lifecycle, delivery, expiry and pairing tests passed.
- 26 fresh-install regression tests passed.
- 18 template API, 20 delivery-source API and 5 standalone API tests passed.
- Chromium fixture checks passed with no page errors or mobile overflow, including
  fixed expiry submission, reader restrictions and protected stable targets.
- Both legacy and Redis-bound definitions rendered successfully in all four chart copies.
- A disposable 96 MiB Redis container accepted the exact installer seed, served
  read-only lookups, denied writes and allowed offline fallback; it was removed.
- Full dated fixture regeneration matched committed pins. Linux Python 3.12.15
  and 3.13.16 reproduced the exact January manifest and compressed data bytes. Shared lab deployment
  and native Mac acceptance remain after review.

## Review batch

- [Lab #171](https://gitea.localhost:34443/elastic-agent/ephemeral-elastic-search-stack/pulls/171): UI, paired data, runtime and fresh installation.
- [Environment-state #1](https://gitea.localhost:34443/elastic-agent/environment-state/pulls/1): render Redis bindings for standalone previews.
- [Delivery-source #35](https://gitea.localhost:34443/elastic-agent/delivery-source/pulls/35): API 1.1.0, chart and copy/paste examples.
- [Search-spike #7](https://gitea.localhost:34443/elastic-agent/search-spike/pulls/7): Redis support in the standalone UI build path.

Accept the lab and environment chart changes first. Publish paired data and
activate Redis/control, then accept and build the APIs. A fresh source comparison
under the new runtime is required before promoting a Redis-bound API release.

## Seasonal extension

Add Halloween and Christmas datasets to the same review batch. Each contains
1,000 identical ordinary controls and 250 distinct themed products, selected
unchanged from full ESCI. Keep selection bounded in memory and scan the full
catalogue once for both events; reruns verify retained bytes. Add simulated
October/December dates, paired event rewrites and four unlabelled demo queries.
Preserve the previously pinned full, demo and monthly releases byte for byte.

Acceptance: restore both events, check the same seasonal query produces visibly
different products and Redis decisions, and check ordinary controls retain their
identity. Do not describe cross-catalogue metric differences as a ranking regression.

Seasonal verification: four selection/pairing tests and the real non-root Redis
seed test passed. Actual catalogues contain 1,250 products each, exactly 1,000
shared IDs, 54 queries and 968 unchanged labels each. The four curated seasonal
queries have no fabricated labels. Compressed product files total 1,440,852 bytes.
All five earlier input pins and Redis pairings remain unchanged. Repeated producer
execution verifies and reuses the frozen seasonal outputs.
