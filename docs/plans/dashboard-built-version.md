# Show versions before the first promotion

## Cause and change

Build 194 has retained version `1.2.0+build.194.1`, but the release dashboard only
obtained versions from deployment/proposal records. Newly built releases therefore
showed no version before their first promotion.

Read successful builds' exact receipts and checksum-verified release descriptors
without downloading source bundles. Reuse the existing receipt/source/image and
semantic-version checks. Cache successful metadata by run, attempt, source and
event; failures are not cached. Include the version and release ID in cards and
the build selector. Missing or invalid metadata remains explicit, and no version
is inferred from the latest source branch. Deployment validation still verifies
the full source bundle as before.

## Verification and next action

All 24 release integrity and dashboard projection tests passed. A read-only
check inside the running API independently confirmed build 194's retained version
as `1.2.0+build.194.1` and source `890b616da309`. After acceptance, activate the runtime when idle and confirm the
selected build in the served dashboard API. No rebuild or reevaluation of the
Search API is required.
