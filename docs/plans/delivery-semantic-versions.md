# Delivery semantic versions

## Scope

Adopt a reviewed VERSION file in delivery-source, beginning at 1.0.0. Carry the
version through verified descriptors, desired state and the user interface.
Use SemVer for ordering and Git ancestry for historic releases. Reserve each
stable version against its complete Git tree; let the coordinator create tags
after successful publication. Keep exact artefact/evidence checks unchanged.

## Validation and acceptance

42 parser, publication, bundle, tag identity, seed, promotion and dashboard
tests passed on Windows. Release dashboard and production release browser
fixtures passed, including version display and mobile layout. These checks do not establish native
Mac builds or actual tag publication. After review, update the runtime before
merging source changes. Verify the first merged build, v1.0.0 tag, automatic
mirror and promotion status. No live release, tag or deployment is created by
the implementation batch.

## Next

Review both PRs. After activation, run the next walkthrough with a reviewed
minor bump for a ranking change; use an empty commit to refresh the comparison
without changing its declared version.
