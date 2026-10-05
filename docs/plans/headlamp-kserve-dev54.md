# Headlamp KServe dev.54

## Intent and constraints

Install the supplied KServe plugin dev.54 and retain it in the local release
folder and the reproducible lab setup. Preserve the custom Prometheus plugin,
OIDC configuration, Headlamp image and Kubernetes permissions.

## Acceptance

- Validate the supplied archive checksum, paths and package version.
- Roll out its ConfigMap and verify Headlamp readiness and exact served assets.
- Keep one KServe and one custom Prometheus plugin in discovery.
- Confirm the Prometheus archive checksum remains unchanged.
- Commit the setup and evidence for review; browser interaction remains a user check.

## Next

Refresh Headlamp and exercise dev.54 against the existing KServe testbed.
Continue the relevance walkthrough separately. See [plugin setup](../../lab/headlamp-plugins/README.md).
