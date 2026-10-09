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
