# Navigate from a release to its result and storefront

## Change

Use **View result** for completed, failed and interrupted operations wherever the
release dashboard renders operation links. Active attempts retain **Progress**.
The **Deployed environments** table adds **Open storefront** for ready APIs,
using the existing observed URL. This respects the stable active production route
and the inactive slot's separate URL. Unready environments say **Available when
ready**. Versions and readiness remain visible alongside the link.

## Verification and next action

JavaScript syntax validation passed. Eleven HTML link fixture cases passed for
active/terminal operations, ready/unready environments and production route/slot
URLs. Browser rendering has not been checked. After review and merge,
activate when idle and refresh the dashboard. No Search API build, evaluation or
deployment change is required.
