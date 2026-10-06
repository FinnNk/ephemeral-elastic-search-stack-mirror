# Read-only release dashboard

## Purpose

Follow a merged Search API change through its source gate, reviewed promotions,
verified deployments and production activation. Start with a searchable release
overview, then open a connected tree for one release. The design takes its
general card overview and connected status view from Argo CD.

## This batch

- Add `/release-dashboard` and its authenticated GET projection at
  `/api/delivery/dashboard`. Link it from search environments and production release.
- List merged-source builds and retained deployment records as searchable,
  filterable, paged cards. A selected build has a stable `?run=<number>` URL.
- Connect Source merged → Integration → Staging → Production candidate →
  Active production. Attach the recorded source gate, build result, promotion
  checks, exact-head review and deployment verification to the relevant node.
- Show current environments, GitOps sync and health, active production,
  frozen inputs, change intent and retry history. Link to existing reports,
  progress records, source configuration and Gitea reviews.
- Read existing records and provider GETs only. Do not submit, merge, validate
  a promotion, create a database, rerun checks or acquire the delivery writer lock.

## Identity and unavailable data

The selected journey uses one deployment fingerprint and its complete frozen
fields. Its anchor is the furthest observed stage for that build, falling back
to a retained definition. Successful records for a different definition cannot
fill stages in that journey.

Source gate status comes from the original PR head and a visible frozen verdict
recorded before source merge. It is not inferred from a successful build or a
later comparison. Reviews use the proposal's current head. A merged proposal,
ready inactive slot and verified active release are distinct states.

The view includes the latest 50 source workflow runs, 300 visible operations and
retained deployment verification history. Older source PRs can fall outside its
50-PR window. Missing records and provider failures show unknown or unavailable
states. Production requests without recorded release identity appear separately
and are never attributed to the currently prepared candidate. Existing owner,
administrator and reader visibility applies; Actions identities cannot read the
dashboard. Refreshes do not extend leases.

## Verification — 6 October 2026

All 30 focused projection and control HTTP tests passed. They cover exact
fingerprints and frozen fields, candidate/active separation, failed retries,
current-head approvals, source gates before merge, unavailable evidence,
ownership, sign-in and the restriction on Actions identities.

Chromium checks passed for card filters and paging, tree connections, escaped
content, keyboard tabs, sign-in feedback and the 390-pixel layout. All seven
requests in each browser rehearsal were GETs. The connected tree scrolls within
its panel on mobile; the page itself does not overflow.

The read-only lab snapshot at `2026-10-06T21:51:31Z` confirmed source PR #31's
passing gate, build 158's verified Integration and Staging deployments, prepared
green candidate and unchanged active blue build 108. It included the retained
Gatling, relevance and result-change verdicts and had no provider warnings.
Its locally retained JSON SHA-256 is
`4fca938fced0f8ea9aae63a7254b0f16efa052646cf3c669d1c848175e37ab7f`.

Desktop and mobile previews were visually inspected at 1600 × 1100 and
390 × 844 viewports. These previews render the retained real snapshot using a
local disposable server; the dashboard is not yet installed. No release,
comparison, inference or load test was triggered. The affected delivery guide,
lab README and current roadmap were reviewed for consistent navigation and
status meanings.

## Next batch: activate and walk through

1. Accept and merge this batch.
2. Publish the merged coordinator image. Check for active operations before
   rolling the coordinator; wait for readiness and run its service smoke check.
3. Sign in and open **Release dashboard**. Select build 158 and confirm its
   source gate, Integration and Staging verification, prepared green candidate
   and unchanged active blue production.
4. Continue the existing authorised promotion walkthrough and confirm that the
   tree follows the actual reviews, checks and activation. The dashboard itself
   does not trigger any of those steps.

Future guided actions need a separate batch. No workflow designer or deployment
button is included in this first version.
