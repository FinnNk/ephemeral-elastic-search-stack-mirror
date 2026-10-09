# Show next-target promotion status and early expiry

## Behaviour

Environment cards show the next promotion target and its matching evidence:
grey for absent or unavailable evidence, red for incomplete checks or review,
orange for an approved older release, and green for an approved newer release.
Same-commit and unknown source order remain neutral. Git ancestry distinguishes
source order without assuming that tags or rebuilt images are newer code.

Readiness requires the exact observed candidate definition, target fingerprint,
desired-state base revision, current reviewed PR head and successful validation.
The projection reads a bounded operation history and up to twenty relevant PR
reviews; missing data stays explicit. It does not authorise promotion. The
coordinator still rechecks every deployment. Production preparation is not a
substitute for final production checks.

**Expire now** uses existing deletion for ephemeral environments. Delivery
previews submit an idempotent coordinator operation bound to their fingerprint
and lease. It checks ownership and running comparisons, marks the lease due,
and leaves removal to normal cleanup. Human administrators can request it;
Actions identities and reader accounts cannot. Integration, Staging and both
Production slots are rejected by name validation and have no UI control.

## Verification and next step

Run focused projection, expiry, operation and preview tests, including real
local Git ancestry. Exercise environment colours, protected targets, reader
permissions and inline expiry progress in the browser fixture.

Verification: 31 focused Python tests passed on Windows, including real local
Git ancestry and stale-lease rejection. The Chromium fixture passed promotion
colours, preview-only expiry, reader restrictions, inline progress, paging and
mobile overflow checks. The synthetic card screenshot was visually inspected.
The installed Gitea status response fields were checked read-only. No Mac or
Windows cluster was changed or environment expired. Native runtime acceptance
still needs the updated Mac deployment.

After acceptance, merge and update the Mac control runtime through the normal
installer/update path. Verify the existing PR remains green, inspect a matching
reviewed promotion and end a disposable preview. No live environment is expired
as part of local verification. A clean Mac installation remains outstanding.
