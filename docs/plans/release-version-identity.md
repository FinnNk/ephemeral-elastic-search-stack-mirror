# Show the exact source commit beside each release version

Use `version · short source SHA` on promotion report comparisons, verification
reports, release cards/dropdowns, observed environments, production details and
planned comparison controls. Promotion PR descriptions use the same convention.
Retain full identifiers in existing evidence views. Historical build 158 has no
VERSION file or version metadata; show that absence with its actual commit.

## Fresh-install contract

The delivery-source seed already supplies VERSION and CI requires it. Add a
baseline check before bootstrap and require `verify --require-version` for all
three delivery targets before writing fresh-ready.json. This requires valid
SemVer and a complete Git source SHA. Ordinary verification of retained legacy
releases remains available; no frozen release is relabelled.

## Verification and next step

The 61 selected fresh-install, delivery-gate, release-control and description
fixtures pass in the locked Windows uv environment. They cover seeded VERSION,
rejection of missing/invalid versions or commits and version-required final
verification. Chrome report, dashboard, planned-control and production-page
fixtures passed, including narrow layouts and exact version/SHA labels. Browser
harnesses use installed Chrome and close their fixture server on launch failure.
Production fixture expectations were aligned with the already active
source-controlled intent contract.

Review and activate this batch, then refresh build 184's report and dashboard.
Update PR #25's presentation without changing its deployment/evidence values.
A complete fresh install on a clean Mac remains an external acceptance check.
