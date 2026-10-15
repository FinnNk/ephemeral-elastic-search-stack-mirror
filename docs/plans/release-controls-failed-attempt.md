# Retry promotion after an attempt without a proposal

The release controls must remain usable when an operation fails before creating
a desired-state PR. Such an operation has `pr: null`; the approved-proposals
filter previously treated that value as an object and terminated the request.
The browser then displayed its generic service/sign-in error.

Treat a null PR as absent. Retain the failed activity, permit an otherwise
eligible new check and continue requiring an approved PR before deployment.

## Verification and next step

The regression fixture covers a failed attempt without a PR, retry eligibility,
disabled deployment and an approved proposal alongside the failed attempt.
Run the release-control and dashboard fixtures, then review and activate this
batch. Verify build 184's controls against the retained failed operation.

Separately, prevent stale Nexus routing after Docker restarts. A disposable
Docker test showed that an explicit container address can still be claimed by
another container while the original is stopped; address reservation alone
does not meet the requirement. Implement automatic endpoint reconciliation.
