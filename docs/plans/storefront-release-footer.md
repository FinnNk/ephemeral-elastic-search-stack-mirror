# Identify the release serving the storefront

## Behaviour

Add a footer with the semantic version, short source commit and promotion time.
The Search API exposes public identity through `/release`; charts supply version
and source plus a read-only optional release-status volume. Successful verification
publishes a small ConfigMap keyed by deployment fingerprint. Reverification keeps
the existing time; a changed target deployment, including rollback, records a new
time. Historical receipts without a time remain unknown. Kubernetes propagates
volume updates without restarting the API.

Production slots mount their own fingerprint's metadata. The API accepts a time
only when its running image and source match that metadata. Missing metadata does
not break search or fabricate a promotion date. No credentials are exposed.

## Rollout

Review the coordinator/chart/source-template batch first, then the delivery-source
PR. The storefront needs a new API build and normal promotion; do not replace
build 184's frozen image or retag its existing evidence. Fresh installations seed
the current source and chart automatically. Keep the ongoing walkthrough intact.

## Verification

Twenty-nine focused promotion/production tests and nine template Search API
tests passed. All 21 tests in the matching delivery-source suite passed using
its pinned application requirements alongside the locked operator environment.
Helm rendering confirmed the fingerprint-specific optional volume and
version/source environment values. Browser rendering and a live promoted build
have not been verified in this batch.
